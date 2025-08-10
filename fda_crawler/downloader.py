"""PDF downloading and file management utilities"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class PDFDownloader:
    """Handles PDF downloading with rate limiting and error handling"""
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
    
    async def download_pdf(self, pdf_url: str) -> Optional[Dict[str, Any]]:
        """Download PDF file and return binary data with metadata"""
        try:
            await asyncio.sleep(1.0 / settings.rate_limit)  # Rate limiting
            
            # Convert relative URLs to absolute URLs
            if pdf_url.startswith('/'):
                pdf_url = f"https://www.fda.gov{pdf_url}"
                logger.info(f"📄 Converted relative URL to absolute: {pdf_url}")
            
            response = await self.client.get(pdf_url)
            response.raise_for_status()
            
            # Get binary content
            pdf_content = response.content
            
            # Calculate checksum
            checksum = hashlib.sha256(pdf_content).hexdigest()
            
            return {
                'pdf_content': pdf_content,
                'checksum': checksum,
                'size_bytes': len(pdf_content)
            }
            
        except Exception as e:
            logger.error(f"Error downloading PDF {pdf_url}: {e}")
            return None


class FileNameGenerator:
    """Generates consistent file names for downloaded PDFs"""
    
    @staticmethod
    def generate_pdf_filename_from_data(doc_data: Dict[str, Any], pdf_url: str) -> str:
        """Generate deterministic PDF filename from document data"""
        title = doc_data.get('title', 'untitled')
        issue_date = doc_data.get('issue_date', 'unknown')
        
        # Create slug from title
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', title.lower())[:50]
        
        # Extract media ID from PDF URL if available
        media_id = ''
        if '/media/' in pdf_url:
            try:
                media_id = pdf_url.split('/media/')[1].split('/')[0]
            except:
                pass
        
        # Clean up issue date
        clean_date = re.sub(r'[^0-9/-]', '', issue_date) if issue_date else 'unknown'
        
        return f"{clean_date}_{slug}_{media_id}.pdf"
    
    @staticmethod
    def generate_filename_from_url(url: str, title: str = None) -> str:
        """Generate filename from URL and optional title"""
        # Extract media ID from URL
        media_id = ''
        if '/media/' in url:
            try:
                media_id = url.split('/media/')[1].split('/')[0]
            except:
                pass
        
        if title:
            # Create slug from title
            slug = re.sub(r'[^a-zA-Z0-9]+', '_', title.lower())[:30]
            return f"{slug}_{media_id}.pdf"
        else:
            return f"fda_document_{media_id}.pdf"


class DocumentProcessor:
    """Processes individual documents including metadata extraction and PDF download"""
    
    def __init__(self, client: httpx.AsyncClient, session_id: str):
        self.client = client
        self.session_id = session_id
        self.downloader = PDFDownloader(client)
        self.filename_generator = FileNameGenerator()
    
    async def parse_document_page(self, url: str) -> Dict[str, Any]:
        """Parse a document detail page and extract additional metadata"""
        from .parsers import DocumentDetailParser
        
        try:
            await asyncio.sleep(1.0 / settings.rate_limit)  # Rate limiting
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'lxml')
            
            parser = DocumentDetailParser()
            metadata = parser.parse_document_page(soup, url)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error parsing document page {url}: {e}")
            return {'document_url': url, 'parsing_error': str(e)}
    
    async def process_document_with_db(self, doc_data: Dict[str, Any], async_session_class) -> bool:
        """Process a single document with database operations"""
        from .models import Document, DocumentAttachment
        from sqlalchemy import select
        
        async with async_session_class() as session:
            try:
                url = doc_data['document_url']
                
                # Check if document already processed
                result = await session.execute(
                    select(Document).where(Document.document_url == url)
                )
                existing_doc = result.scalar_one_or_none()
                
                if existing_doc and existing_doc.processing_status == "completed":
                    logger.info(f"Document already processed: {url}")
                    return True
                
                logger.info(f"Processing document: {doc_data.get('title', url)}")
                
                # Get additional metadata from detail page
                detail_metadata = await self.parse_document_page(url)
                
                if 'parsing_error' in detail_metadata:
                    logger.warning(f"Could not parse detail page {url}: {detail_metadata['parsing_error']}")
                    detail_metadata = {}  # Continue with listing data only
                
                # Combine listing data with detail page data
                combined_metadata = {
                    'title': detail_metadata.get('title') or doc_data.get('title'),
                    'summary': detail_metadata.get('summary'),
                    'issue_date': doc_data.get('issue_date'),
                    'fda_organization': doc_data.get('fda_organization'),
                    'topic': doc_data.get('topic'),
                    'guidance_status': doc_data.get('guidance_status'),
                    'open_for_comment': doc_data.get('open_for_comment'),
                    'docket_number': detail_metadata.get('docket_number'),
                    'guidance_type': None,  # Not in current data structure
                    'comment_closing_date': None,  # Would need to be extracted
                }
                
                # Create or update document record
                if existing_doc:
                    doc = existing_doc
                    # Update metadata
                    for key, value in combined_metadata.items():
                        if hasattr(doc, key) and value is not None:
                            setattr(doc, key, value)
                else:
                    doc = Document(
                        crawl_session_id=self.session_id,
                        document_url=url,
                        **combined_metadata
                    )
                    session.add(doc)
                
                doc.processing_status = "processing"
                await session.commit()
                await session.refresh(doc)
                
                # Download PDF if available
                pdf_success = await self._handle_pdf_download(
                    doc, doc_data, detail_metadata, session
                )
                
                # Update document status
                doc.processing_status = "completed" if pdf_success else "failed"
                doc.processed_at = datetime.utcnow()
                
                await session.commit()
                return pdf_success
                
            except Exception as e:
                logger.error(f"Error processing document {doc_data.get('title', 'unknown')}: {e}")
                # Update document with error
                if 'doc' in locals():
                    doc.processing_status = "failed"
                    doc.processing_error = str(e)
                    await session.commit()
                return False
    
    async def _handle_pdf_download(self, doc, doc_data: Dict[str, Any], 
                                 detail_metadata: Dict[str, Any], session) -> bool:
        """Handle PDF download and storage"""
        from .models import DocumentAttachment
        from sqlalchemy import select
        
        pdf_success = True
        pdf_url = doc_data.get('pdf_url') or detail_metadata.get('pdf_download_url')
        
        if pdf_url:
            # Generate filename for reference
            filename = self.filename_generator.generate_pdf_filename_from_data(doc_data, pdf_url)
            
            # Check if attachment already exists
            result = await session.execute(
                select(DocumentAttachment).where(
                    DocumentAttachment.document_id == doc.id,
                    DocumentAttachment.source_url == pdf_url
                )
            )
            existing_attachment = result.scalar_one_or_none()
            
            if existing_attachment and existing_attachment.download_status == "completed":
                logger.info(f"PDF already downloaded and stored in database: {filename}")
            else:
                # Download PDF binary data
                download_result = await self.downloader.download_pdf(pdf_url)
                
                if download_result:
                    if existing_attachment:
                        attachment = existing_attachment
                    else:
                        attachment = DocumentAttachment(
                            document_id=doc.id,
                            filename=filename,
                            source_url=pdf_url,
                            file_type='pdf'
                        )
                        session.add(attachment)
                    
                    # Store PDF binary data in database
                    attachment.pdf_content = download_result['pdf_content']
                    attachment.checksum = download_result['checksum']
                    attachment.size_bytes = download_result['size_bytes']
                    attachment.download_status = "completed"
                    attachment.downloaded_at = datetime.utcnow()
                    
                    # Update document with PDF info (keep for backward compatibility)
                    doc.pdf_checksum = download_result['checksum']
                    doc.pdf_size_bytes = download_result['size_bytes']
                    
                    logger.info(f"Downloaded and stored PDF in database: {filename} ({download_result['size_bytes']} bytes)")
                else:
                    pdf_success = False
                    logger.warning(f"Failed to download PDF from {pdf_url}")
        else:
            logger.warning(f"No PDF URL found for document: {doc_data.get('title', doc.document_url)}")
        
        return pdf_success
