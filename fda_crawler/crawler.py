"""FDA Guidance Documents Crawler - All-in-one implementation"""
import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from .config import settings
from .models import Base, CrawlSession, Document, DocumentAttachment

logger = logging.getLogger(__name__)


class FDACrawler:
    """Simple, consolidated FDA crawler implementation"""
    
    # Known FDA documents for fallback
    FALLBACK_DOCUMENTS = [
        {
            'title': 'Medical Device User Fee Small Business Qualification and Determination: Guidance for Industry, Food and Drug Administration Staff and Foreign Governments',
            'document_url': 'https://www.fda.gov/regulatory-information/search-fda-guidance-documents/medical-device-user-fee-small-business-qualification-and-determination',
            'pdf_url': 'https://www.fda.gov/media/176439/download',
            'pdf_size': '418.69 KB',
            'issue_date': '07/31/2025',
            'fda_organization': 'Center for Devices and Radiological Health Center for Biologics Evaluation and Research',
            'topic': 'User Fees, Administrative / Procedural',
            'guidance_status': 'Final',
            'open_for_comment': False,
        },
        {
            'title': 'CVM GFI #294 - Animal Food Ingredient Consultation (AFIC)',
            'document_url': 'https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cvm-gfi-294-animal-food-ingredient-consultation-afic',
            'pdf_url': 'https://www.fda.gov/media/180442/download',
            'pdf_size': '397.81 KB',
            'issue_date': '07/31/2025',
            'fda_organization': 'Center for Veterinary Medicine',
            'topic': 'Premarket, Animal Food Additives, Labeling, Safety - Issues, Errors, and Problems',
            'guidance_status': 'Final',
            'open_for_comment': False,
        },
        {
            'title': 'E21 Inclusion of Pregnant and Breastfeeding Women in Clinical Trials: Draft Guidance for Industry',
            'document_url': 'https://www.fda.gov/regulatory-information/search-fda-guidance-documents/e21-inclusion-pregnant-and-breastfeeding-women-clinical-trials',
            'pdf_url': 'https://www.fda.gov/media/187755/download',
            'pdf_size': '429.62 KB',
            'issue_date': '07/21/2025',
            'fda_organization': 'Center for Biologics Evaluation and Research Center for Drug Evaluation and Research Office of the Commissioner,Office of Women\'s Health',
            'topic': 'ICH-Efficacy',
            'guidance_status': 'Draft',
            'open_for_comment': True,
        },
    ]
    
    def __init__(self):
        self.engine = create_async_engine(settings.database_url)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False
        )
        self.client: Optional[httpx.AsyncClient] = None
        self.session_id: Optional[str] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.connect_timeout,
                read=settings.read_timeout,
                write=settings.connect_timeout,
                pool=settings.read_timeout
            ),
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def init_database(self):
        """Initialize database schema (idempotent)"""
        async with self.engine.begin() as conn:
            # Create schema if not exists
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.schema_name}"))
            # Create tables only if they don't exist (idempotent)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema checked/initialized")
    
    async def crawl(self, test_limit: Optional[int] = None, resume_session_id: Optional[str] = None) -> str:
        """Main crawl method"""
        await self.init_database()
        
        # Create or resume session
        async with self.async_session() as db_session:
            if resume_session_id:
                session = await db_session.get(CrawlSession, resume_session_id)
                if not session:
                    raise ValueError(f"Session {resume_session_id} not found")
                logger.info(f"Resuming session {session.id}")
            else:
                session = CrawlSession(
                    max_concurrency=settings.max_concurrency,
                    rate_limit=settings.rate_limit,
                    test_limit=test_limit or settings.test_limit
                )
                db_session.add(session)
                await db_session.commit()
                logger.info(f"Created new session {session.id}")
            
            self.session_id = str(session.id)
        
        # Get document URLs from FDA JSON API (faster than scraping)
        document_urls = await self._get_document_urls_from_api()
        
        if test_limit:
            document_urls = document_urls[:test_limit]
            logger.info(f"Limited to {test_limit} documents for testing")
        
        # Process documents
        await self._process_documents(document_urls, self.session_id)
        
        # Mark session complete
        async with self.async_session() as db_session:
            session = await db_session.get(CrawlSession, self.session_id)
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            await db_session.commit()
        
        logger.info(f"Crawl completed. Session ID: {self.session_id}")
        return self.session_id
    
    async def _get_document_urls_from_api(self) -> List[str]:
        """Get document URLs from FDA JSON API"""
        try:
            response = await self.client.get("https://www.fda.gov/files/api/datatables/static/search-for-guidance.json")
            response.raise_for_status()
            data = response.json()
            
            urls = []
            for item in data:
                title_html = item.get('title', '')
                soup = BeautifulSoup(title_html, 'html.parser')
                link = soup.find('a')
                if link:
                    url_path = link.get('href', '')
                    full_url = urljoin('https://www.fda.gov', url_path) if url_path else ''
                    if full_url:
                        urls.append(full_url)
            
            logger.info(f"Found {len(urls)} documents from FDA API")
            return urls
            
        except Exception as e:
            logger.warning(f"Failed to get URLs from API: {e}. Using fallback documents.")
            return [doc['document_url'] for doc in self.FALLBACK_DOCUMENTS]
    
    async def _process_documents(self, document_urls: List[str], session_id: str):
        """Process documents with concurrency control"""
        semaphore = asyncio.Semaphore(settings.max_concurrency)
        
        async def process_single(url: str):
            async with semaphore:
                await self._process_document(url, session_id)
                await asyncio.sleep(1.0 / settings.rate_limit)  # Rate limiting
        
        tasks = [process_single(url) for url in document_urls]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_document(self, document_url: str, session_id: str):
        """Process a single document: fetch, parse, download PDF, save to DB"""
        try:
            # Check if document already exists
            async with self.async_session() as db_session:
                result = await db_session.execute(
                    select(Document).where(Document.document_url == document_url)
                )
                existing_doc = result.scalar_one_or_none()
                if existing_doc:
                    logger.info(f"Document already exists: {document_url}")
                    return
            
            # Fetch document page
            response = await self.client.get(document_url)
            response.raise_for_status()
            
            # Parse document metadata
            doc_data = self._parse_document_page(response.text, document_url)
            
            # Download PDF if available
            pdf_data = None
            if doc_data.get('pdf_url'):
                pdf_data = await self._download_pdf(doc_data['pdf_url'])
            
            # Save to database
            await self._save_document(doc_data, pdf_data, session_id)
            
            logger.info(f"Processed: {doc_data.get('title', 'Unknown')[:50]}...")
            
        except Exception as e:
            logger.error(f"Error processing {document_url}: {e}")
            await self._update_session_error_count(session_id)
    
    def _parse_document_page(self, html: str, document_url: str) -> Dict[str, Any]:
        """Parse FDA document page to extract metadata"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Basic document data
        doc_data = {
            'document_url': document_url,
            'title': '',
            'summary': '',
            'issue_date': '',
            'fda_organization': '',
            'topic': '',
            'guidance_status': '',
            'open_for_comment': False,
            'comment_closing_date': '',
            'docket_number': '',
            'guidance_type': '',
            'regulated_products': '',
            'topics': '',
            'content_current_date': '',
            'pdf_url': ''
        }
        
        # Extract title
        title_elem = soup.find('h1')
        if title_elem:
            doc_data['title'] = title_elem.get_text(strip=True)
        
        # Extract PDF link
        pdf_link = soup.find('a', href=re.compile(r'/media/\d+/download'))
        if pdf_link:
            pdf_url = pdf_link.get('href')
            if pdf_url.startswith('/'):
                pdf_url = f"https://www.fda.gov{pdf_url}"
            doc_data['pdf_url'] = pdf_url
        
        # Extract sidebar metadata
        sidebar = soup.find('div', class_='region-sidebar-second') or soup.find('aside')
        if sidebar:
            # Look for structured data in sidebar
            for dt_dd_pair in sidebar.find_all(['dt', 'dd']):
                if dt_dd_pair.name == 'dt':
                    label = dt_dd_pair.get_text(strip=True).lower()
                    dd = dt_dd_pair.find_next_sibling('dd')
                    if dd:
                        value = dd.get_text(strip=True)
                        
                        if 'issue date' in label or 'issued' in label:
                            doc_data['issue_date'] = value
                        elif 'organization' in label or 'center' in label:
                            doc_data['fda_organization'] = value
                        elif 'topic' in label:
                            doc_data['topic'] = value
                        elif 'status' in label or 'guidance status' in label:
                            doc_data['guidance_status'] = value
                        elif 'docket' in label:
                            doc_data['docket_number'] = value
                        elif 'type' in label:
                            doc_data['guidance_type'] = value
                        elif 'regulated product' in label:
                            # Convert to JSON array
                            products = [p.strip() for p in value.split(',') if p.strip()]
                            doc_data['regulated_products'] = json.dumps(products)
                        elif 'current as of' in label:
                            doc_data['content_current_date'] = value
        
        # Extract summary from main content
        main_content = soup.find('div', class_='field-type-text-with-summary') or soup.find('div', class_='field-item')
        if main_content:
            paragraphs = main_content.find_all('p')
            if paragraphs:
                doc_data['summary'] = paragraphs[0].get_text(strip=True)[:1000]  # Limit length
        
        return doc_data
    
    async def _download_pdf(self, pdf_url: str) -> Optional[Dict[str, Any]]:
        """Download PDF file and return binary data with metadata"""
        try:
            response = await self.client.get(pdf_url)
            response.raise_for_status()
            
            pdf_content = response.content
            checksum = hashlib.sha256(pdf_content).hexdigest()
            
            return {
                'pdf_content': pdf_content,
                'checksum': checksum,
                'size_bytes': len(pdf_content)
            }
            
        except Exception as e:
            logger.error(f"Error downloading PDF {pdf_url}: {e}")
            return None
    
    async def _save_document(self, doc_data: Dict[str, Any], pdf_data: Optional[Dict[str, Any]], session_id: str):
        """Save document and PDF to database"""
        async with self.async_session() as db_session:
            try:
                # Create document record
                document = Document(
                    crawl_session_id=session_id,
                    document_url=doc_data['document_url'],
                    title=doc_data['title'],
                    summary=doc_data['summary'],
                    issue_date=doc_data['issue_date'],
                    fda_organization=doc_data['fda_organization'],
                    topic=doc_data['topic'],
                    guidance_status=doc_data['guidance_status'],
                    open_for_comment=doc_data['open_for_comment'],
                    comment_closing_date=doc_data['comment_closing_date'],
                    docket_number=doc_data['docket_number'],
                    guidance_type=doc_data['guidance_type'],
                    regulated_products=doc_data['regulated_products'],
                    topics=doc_data['topics'],
                    content_current_date=doc_data['content_current_date'],
                    processing_status='completed',
                    processed_at=datetime.utcnow()
                )
                
                if pdf_data:
                    document.pdf_checksum = pdf_data['checksum']
                    document.pdf_size_bytes = pdf_data['size_bytes']
                
                db_session.add(document)
                await db_session.flush()  # Get document ID
                
                # Create attachment record if PDF was downloaded
                if pdf_data and doc_data.get('pdf_url'):
                    attachment = DocumentAttachment(
                        document_id=document.id,
                        filename=f"{document.id}.pdf",
                        source_url=doc_data['pdf_url'],
                        file_type='pdf',
                        pdf_content=pdf_data['pdf_content'],
                        checksum=pdf_data['checksum'],
                        size_bytes=pdf_data['size_bytes'],
                        download_status='completed',
                        downloaded_at=datetime.utcnow()
                    )
                    db_session.add(attachment)
                
                await db_session.commit()
                
                # Update session progress
                await self._update_session_progress(session_id)
                
            except IntegrityError:
                # Document already exists
                await db_session.rollback()
                logger.info(f"Document already exists (integrity constraint): {doc_data['document_url']}")
            except Exception as e:
                await db_session.rollback()
                logger.error(f"Error saving document {doc_data['document_url']}: {e}")
                raise
    
    async def _update_session_progress(self, session_id: str):
        """Update session progress counters"""
        async with self.async_session() as db_session:
            session = await db_session.get(CrawlSession, session_id)
            session.processed_documents += 1
            session.successful_downloads += 1
            await db_session.commit()
    
    async def _update_session_error_count(self, session_id: str):
        """Update session error count"""
        async with self.async_session() as db_session:
            session = await db_session.get(CrawlSession, session_id)
            session.error_count += 1
            session.failed_documents += 1
            await db_session.commit()
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get crawl session status"""
        async with self.async_session() as db_session:
            session = await db_session.get(CrawlSession, session_id)
            if not session:
                return None
            
            return {
                'id': str(session.id),
                'status': session.status,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                'total_documents': session.total_documents,
                'processed_documents': session.processed_documents,
                'successful_downloads': session.successful_downloads,
                'failed_documents': session.failed_documents,
                'error_count': session.error_count,
                'last_error': session.last_error
            }
