"""Main data processing pipeline"""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text, and_
from sqlalchemy.exc import IntegrityError

from .config import settings
from .models import Base, ProcessingSession, DocumentFeatures, ProcessingLog, ExtractionRequest
from .pdf_extractor import PDFExtractor
from .llm_processor import LLMProcessor

logger = logging.getLogger(__name__)


class DataProcessor:
    """Main data processing pipeline for FDA documents"""
    
    def __init__(self):
        # Database setup
        self.engine = create_async_engine(settings.database_url)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False
        )
        
        # Processing components
        self.pdf_extractor = PDFExtractor()
        self.llm_processor = LLMProcessor()
        
        # Current session
        self.session_id: Optional[str] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.engine:
            await self.engine.dispose()
    
    async def init_database(self):
        """Initialize database schema for processed data"""
        async with self.engine.begin() as conn:
            # Create source schema if not exists (should already exist from crawler)
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.source_schema}"))
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Source data schema initialized with processing tables")
    
    async def process_documents(
        self, 
        product_type: str = "medical devices",
        limit: Optional[int] = None,
        resume_session_id: Optional[str] = None
    ) -> str:
        """
        Main processing pipeline
        
        Args:
            product_type: Type of products to process
            limit: Maximum number of documents to process (for testing)
            resume_session_id: Resume existing session
            
        Returns:
            Processing session ID
        """
        await self.init_database()
        
        # Create or resume processing session
        session_id = await self._create_or_resume_session(
            product_type, limit, resume_session_id
        )
        self.session_id = session_id
        
        try:
            # Get documents to process
            documents = await self._get_documents_to_process(product_type, limit)
            
            if not documents:
                await self._log_message("INFO", "No documents found to process")
                await self._complete_session(session_id)
                return session_id
            
            await self._log_message("INFO", f"Found {len(documents)} documents to process")
            
            # Update session with total count
            await self._update_session_total(session_id, len(documents))
            
            # Process documents with concurrency control
            await self._process_documents_batch(documents, session_id)
            
            # Complete session
            await self._complete_session(session_id)
            
            logger.info(f"Processing completed. Session ID: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            await self._fail_session(session_id, str(e))
            raise
    
    async def _get_documents_to_process(
        self, 
        product_type: str, 
        limit: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Get documents from source database that need processing"""
        async with self.async_session() as session:
            # Query source documents with PDF content
            # Focus on medical device related documents
            query = text("""
                SELECT 
                    d.id,
                    d.document_url,
                    d.title,
                    d.summary,
                    d.issue_date,
                    d.fda_organization,
                    d.topic,
                    d.guidance_status,
                    d.regulated_products,
                    d.topics,
                    da.pdf_content,
                    da.filename,
                    da.size_bytes
                FROM source.documents d
                JOIN source.document_attachments da ON d.id = da.document_id
                WHERE da.pdf_content IS NOT NULL 
                  AND da.download_status = 'completed'
                  AND d.processing_status = 'completed'
                  AND (
                    LOWER(d.title) LIKE '%medical device%' OR
                    LOWER(d.topic) LIKE '%medical device%' OR
                    LOWER(d.regulated_products) LIKE '%medical device%' OR
                    LOWER(d.fda_organization) LIKE '%device%' OR
                    LOWER(d.fda_organization) LIKE '%cdrh%'
                  )
                  AND d.id NOT IN (
                    SELECT source_document_id 
                    FROM source.document_features 
                    WHERE processing_status = 'completed'
                  )
                ORDER BY d.created_at DESC
            """)
            
            if limit:
                query = text(str(query) + f" LIMIT {limit}")
            
            result = await session.execute(query)
            rows = result.fetchall()
            
            documents = []
            for row in rows:
                documents.append({
                    'id': str(row.id),
                    'document_url': row.document_url,
                    'title': row.title or 'Untitled Document',
                    'summary': row.summary,
                    'issue_date': row.issue_date,
                    'fda_organization': row.fda_organization,
                    'topic': row.topic,
                    'guidance_status': row.guidance_status,
                    'regulated_products': row.regulated_products,
                    'topics': row.topics,
                    'pdf_content': row.pdf_content,
                    'filename': row.filename,
                    'size_bytes': row.size_bytes
                })
            
            return documents
    
    async def _process_documents_batch(self, documents: List[Dict[str, Any]], session_id: str):
        """Process documents in batches with concurrency control"""
        semaphore = asyncio.Semaphore(settings.max_concurrency)
        
        async def process_single(doc: Dict[str, Any]):
            async with semaphore:
                await self._process_single_document(doc, session_id)
                # Rate limiting for LLM API
                await asyncio.sleep(60.0 / settings.rate_limit_requests_per_minute)
        
        # Process in batches
        for i in range(0, len(documents), settings.batch_size):
            batch = documents[i:i + settings.batch_size]
            
            logger.info(f"Processing batch {i//settings.batch_size + 1}: {len(batch)} documents")
            
            tasks = [process_single(doc) for doc in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info(f"Completed batch {i//settings.batch_size + 1}")
    
    async def _process_single_document(self, document: Dict[str, Any], session_id: str):
        """Process a single document through the pipeline"""
        doc_id = document['id']
        title = document['title']
        
        try:
            await self._log_message("INFO", f"Processing document: {title[:50]}...", doc_id)
            
            # Step 1: Extract text from PDF
            pdf_content = document['pdf_content']
            filename = document.get('filename', f"{doc_id}.pdf")
            
            extraction_result = self.pdf_extractor.extract_text(pdf_content, filename)
            
            if not extraction_result['extraction_successful']:
                error_msg = f"PDF extraction failed: {extraction_result['extraction_error']}"
                await self._log_message("ERROR", error_msg, doc_id)
                await self._increment_failed_count(session_id)
                return
            
            extracted_text = extraction_result['text']
            
            if not extracted_text or len(extracted_text.strip()) < 100:
                error_msg = f"Insufficient text extracted: {len(extracted_text)} characters"
                await self._log_message("WARNING", error_msg, doc_id)
                await self._increment_failed_count(session_id)
                return
            
            # Step 2: Prepare extraction request
            extraction_request = ExtractionRequest(
                document_title=title,
                document_url=document['document_url'],
                document_metadata={
                    'fda_organization': document.get('fda_organization'),
                    'issue_date': document.get('issue_date'),
                    'topic': document.get('topic'),
                    'guidance_status': document.get('guidance_status'),
                    'regulated_products': document.get('regulated_products'),
                    'topics': document.get('topics')
                },
                extracted_text=extracted_text,
                product_type="medical devices"
            )
            
            # Step 3: Extract features using LLM
            extraction_response = await self.llm_processor.extract_features(extraction_request)
            
            if not extraction_response.success:
                error_msg = f"LLM extraction failed: {extraction_response.processing_notes}"
                await self._log_message("ERROR", error_msg, doc_id)
                await self._increment_failed_count(session_id)
                return
            
            # Step 4: Save processed data to database
            await self._save_processed_document(
                document_id=doc_id,
                session_id=session_id,
                extracted_text=extracted_text,
                features=extraction_response.features,
                processing_metadata={
                    'pdf_extraction': extraction_result['metadata'],
                    'llm_processing': extraction_response.processing_notes,
                    'text_length': len(extracted_text)
                }
            )
            
            await self._increment_processed_count(session_id)
            await self._log_message(
                "INFO", 
                f"Successfully processed document (confidence: {extraction_response.features.confidence_score:.2f})",
                doc_id
            )
            
        except Exception as e:
            error_msg = f"Error processing document: {str(e)}"
            logger.error(f"Document {doc_id}: {error_msg}")
            await self._log_message("ERROR", error_msg, doc_id)
            await self._increment_failed_count(session_id)
    
    async def _save_processed_document(
        self,
        document_id: str,
        session_id: str,
        extracted_text: str,
        features,
        processing_metadata: Dict[str, Any]
    ):
        """Save processed document features to database"""
        async with self.async_session() as session:
            try:
                document_features = DocumentFeatures(
                    source_document_id=document_id,
                    processing_session_id=session_id,
                    product_type="medical devices",
                    extracted_text=extracted_text,
                    features=features.dict(),
                    confidence_score=features.confidence_score,
                    processing_metadata=processing_metadata,
                    processing_status="completed"
                )
                
                session.add(document_features)
                await session.commit()
                
            except IntegrityError as e:
                await session.rollback()
                logger.warning(f"Document {document_id} already processed: {e}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Error saving processed document {document_id}: {e}")
                raise
    
    async def _create_or_resume_session(
        self, 
        product_type: str, 
        limit: Optional[int], 
        resume_session_id: Optional[str]
    ) -> str:
        """Create new processing session or resume existing one"""
        async with self.async_session() as session:
            if resume_session_id:
                # Resume existing session
                existing_session = await session.get(ProcessingSession, resume_session_id)
                if not existing_session:
                    raise ValueError(f"Session {resume_session_id} not found")
                
                existing_session.status = "running"
                await session.commit()
                logger.info(f"Resumed processing session {resume_session_id}")
                return str(existing_session.id)
            else:
                # Create new session
                new_session = ProcessingSession(
                    product_type=product_type,
                    configuration={
                        'limit': limit,
                        'max_concurrency': settings.max_concurrency,
                        'batch_size': settings.batch_size,
                        'rate_limit': settings.rate_limit_requests_per_minute,
                        'openai_model': settings.openai_model
                    }
                )
                
                session.add(new_session)
                await session.commit()
                logger.info(f"Created new processing session {new_session.id}")
                return str(new_session.id)
    
    async def _update_session_total(self, session_id: str, total: int):
        """Update session with total document count"""
        async with self.async_session() as session:
            proc_session = await session.get(ProcessingSession, session_id)
            proc_session.total_documents = total
            await session.commit()
    
    async def _increment_processed_count(self, session_id: str):
        """Increment processed document count"""
        async with self.async_session() as session:
            proc_session = await session.get(ProcessingSession, session_id)
            proc_session.processed_documents += 1
            await session.commit()
    
    async def _increment_failed_count(self, session_id: str):
        """Increment failed document count"""
        async with self.async_session() as session:
            proc_session = await session.get(ProcessingSession, session_id)
            proc_session.failed_documents += 1
            await session.commit()
    
    async def _complete_session(self, session_id: str):
        """Mark session as completed"""
        async with self.async_session() as session:
            proc_session = await session.get(ProcessingSession, session_id)
            proc_session.status = "completed"
            proc_session.completed_at = datetime.utcnow()
            await session.commit()
    
    async def _fail_session(self, session_id: str, error_message: str):
        """Mark session as failed"""
        async with self.async_session() as session:
            proc_session = await session.get(ProcessingSession, session_id)
            proc_session.status = "failed"
            proc_session.last_error = error_message
            proc_session.completed_at = datetime.utcnow()
            await session.commit()
    
    async def _log_message(
        self, 
        level: str, 
        message: str, 
        document_id: Optional[str] = None
    ):
        """Log message to processing logs table"""
        if not self.session_id:
            return
            
        async with self.async_session() as session:
            log_entry = ProcessingLog(
                processing_session_id=self.session_id,
                document_id=document_id,
                level=level,
                message=message
            )
            
            session.add(log_entry)
            await session.commit()
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get processing session status"""
        async with self.async_session() as session:
            proc_session = await session.get(ProcessingSession, session_id)
            if not proc_session:
                return None
            
            return {
                'id': str(proc_session.id),
                'status': proc_session.status,
                'product_type': proc_session.product_type,
                'started_at': proc_session.started_at.isoformat() if proc_session.started_at else None,
                'completed_at': proc_session.completed_at.isoformat() if proc_session.completed_at else None,
                'total_documents': proc_session.total_documents,
                'processed_documents': proc_session.processed_documents,
                'failed_documents': proc_session.failed_documents,
                'error_count': proc_session.error_count,
                'last_error': proc_session.last_error,
                'configuration': proc_session.configuration
            }
    
    async def test_components(self) -> Dict[str, bool]:
        """Test all pipeline components"""
        results = {}
        
        # Test database connection
        try:
            async with self.async_session() as session:
                await session.execute(text("SELECT 1"))
            results['database'] = True
        except Exception as e:
            logger.error(f"Database test failed: {e}")
            results['database'] = False
        
        # Test LLM API
        try:
            api_test = await self.llm_processor.test_api_connection()
            results['llm_api'] = api_test
        except Exception as e:
            logger.error(f"LLM API test failed: {e}")
            results['llm_api'] = False
        
        # Test PDF extraction with dummy data
        try:
            # Create minimal PDF content for testing
            test_pdf = b"%PDF-1.4\\n1 0 obj\\n<< /Type /Catalog /Pages 2 0 R >>\\nendobj\\n"
            extraction_result = self.pdf_extractor.extract_text(test_pdf, "test.pdf")
            results['pdf_extraction'] = extraction_result['extraction_successful']
        except Exception as e:
            logger.error(f"PDF extraction test failed: {e}")
            results['pdf_extraction'] = False
        
        return results
