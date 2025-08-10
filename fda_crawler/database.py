"""Database operations and session management"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, text

from .config import settings
from .models import Base, CrawlSession, Document

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self):
        self.engine = create_async_engine(settings.database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_database(self):
        """Initialize database schema (idempotent)"""
        async with self.engine.begin() as conn:
            # Create schema if not exists
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.schema_name}"))
            # Create tables only if they don't exist (idempotent)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema checked/initialized")
    
    def get_session_factory(self):
        """Get the async session factory"""
        return self.async_session
    
    async def close(self):
        """Close database connections"""
        await self.engine.dispose()


class CrawlSessionManager:
    """Manages crawl session operations"""
    
    def __init__(self, async_session_factory):
        self.async_session = async_session_factory
        self.session_id: Optional[str] = None
    
    async def create_crawl_session(self, test_limit: Optional[int] = None) -> str:
        """Create a new crawl session and return session ID"""
        async with self.async_session() as session:
            crawl_session = CrawlSession(
                max_concurrency=settings.max_concurrency,
                rate_limit=settings.rate_limit,
                test_limit=test_limit or settings.test_limit
            )
            session.add(crawl_session)
            await session.commit()
            await session.refresh(crawl_session)
            
            self.session_id = str(crawl_session.id)
            logger.info(f"Created crawl session: {self.session_id}")
            return self.session_id
    
    async def resume_crawl_session(self, session_id: str) -> bool:
        """Resume an existing crawl session"""
        async with self.async_session() as session:
            result = await session.execute(
                select(CrawlSession).where(CrawlSession.id == session_id)
            )
            crawl_session = result.scalar_one_or_none()
            
            if not crawl_session:
                logger.error(f"Crawl session {session_id} not found")
                return False
            
            if crawl_session.status == "completed":
                logger.info(f"Session {session_id} already completed")
                return False
            
            # Update session status to running
            await session.execute(
                update(CrawlSession)
                .where(CrawlSession.id == session_id)
                .values(status="running")
            )
            await session.commit()
            
            self.session_id = session_id
            logger.info(f"Resumed crawl session: {session_id}")
            return True
    
    async def update_session_total_documents(self, total_documents: int):
        """Update the total documents count for the current session"""
        if not self.session_id:
            raise ValueError("No active session")
        
        async with self.async_session() as session:
            await session.execute(
                update(CrawlSession)
                .where(CrawlSession.id == self.session_id)
                .values(total_documents=total_documents)
            )
            await session.commit()
    
    async def complete_session(self, processed_documents: int, successful_downloads: int):
        """Mark the current session as completed"""
        if not self.session_id:
            raise ValueError("No active session")
        
        async with self.async_session() as session:
            await session.execute(
                update(CrawlSession)
                .where(CrawlSession.id == self.session_id)
                .values(
                    status="completed",
                    completed_at=datetime.utcnow(),
                    processed_documents=processed_documents,
                    successful_downloads=successful_downloads
                )
            )
            await session.commit()
    
    async def fail_session(self, error_message: str):
        """Mark the current session as failed"""
        if not self.session_id:
            raise ValueError("No active session")
        
        async with self.async_session() as session:
            await session.execute(
                update(CrawlSession)
                .where(CrawlSession.id == self.session_id)
                .values(
                    status="failed",
                    last_error=error_message,
                    error_count=CrawlSession.error_count + 1
                )
            )
            await session.commit()
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get crawl session status and statistics"""
        async with self.async_session() as session:
            result = await session.execute(
                select(CrawlSession).where(CrawlSession.id == session_id)
            )
            crawl_session = result.scalar_one_or_none()
            
            if not crawl_session:
                return None
            
            return {
                'session_id': str(crawl_session.id),
                'status': crawl_session.status,
                'started_at': crawl_session.started_at,
                'completed_at': crawl_session.completed_at,
                'total_documents': crawl_session.total_documents,
                'processed_documents': crawl_session.processed_documents,
                'successful_downloads': crawl_session.successful_downloads,
                'failed_documents': crawl_session.failed_documents,
                'error_count': crawl_session.error_count,
                'last_error': crawl_session.last_error
            }
    
    async def get_unprocessed_documents(self) -> List[Dict[str, Any]]:
        """Get unprocessed documents from the current session for resume functionality"""
        if not self.session_id:
            raise ValueError("No active session")
        
        async with self.async_session() as session:
            result = await session.execute(
                select(Document)
                .where(
                    Document.crawl_session_id == self.session_id,
                    Document.processing_status.in_(["pending", "failed"])
                )
            )
            db_docs = result.fetchall()
            
            # Convert DB documents back to data format for processing
            documents_data = []
            for doc in db_docs:
                documents_data.append({
                    'title': doc.title,
                    'document_url': doc.document_url,
                    'pdf_url': None,  # Will be fetched from detail page
                    'issue_date': doc.issue_date,
                    'fda_organization': doc.fda_organization,
                    'topic': doc.topic,
                    'guidance_status': doc.guidance_status,
                    'open_for_comment': doc.open_for_comment,
                })
            
            return documents_data


class DocumentRepository:
    """Repository pattern for document database operations"""
    
    def __init__(self, async_session_factory):
        self.async_session = async_session_factory
    
    async def document_exists_and_completed(self, url: str) -> bool:
        """Check if document exists and is already completed"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Document).where(
                    Document.document_url == url,
                    Document.processing_status == "completed"
                )
            )
            return result.scalar_one_or_none() is not None
    
    async def get_document_by_url(self, url: str) -> Optional[Document]:
        """Get document by URL"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Document).where(Document.document_url == url)
            )
            return result.scalar_one_or_none()
    
    async def create_or_update_document(self, doc_data: Dict[str, Any], session_id: str) -> Document:
        """Create or update a document record"""
        async with self.async_session() as session:
            existing_doc = await self.get_document_by_url(doc_data['document_url'])
            
            if existing_doc:
                doc = existing_doc
                # Update metadata
                for key, value in doc_data.items():
                    if hasattr(doc, key) and value is not None:
                        setattr(doc, key, value)
            else:
                doc = Document(
                    crawl_session_id=session_id,
                    **doc_data
                )
                session.add(doc)
            
            await session.commit()
            await session.refresh(doc)
            return doc
    
    async def update_document_status(self, document_id: UUID, status: str, error: str = None):
        """Update document processing status"""
        async with self.async_session() as session:
            update_values = {
                'processing_status': status,
                'processed_at': datetime.utcnow()
            }
            
            if error:
                update_values['processing_error'] = error
            
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(**update_values)
            )
            await session.commit()
    
    async def get_session_document_count(self, session_id: str) -> Dict[str, int]:
        """Get document counts for a session"""
        async with self.async_session() as session:
            # Total documents
            total_result = await session.execute(
                select(Document).where(Document.crawl_session_id == session_id)
            )
            total_count = len(total_result.fetchall())
            
            # Completed documents
            completed_result = await session.execute(
                select(Document).where(
                    Document.crawl_session_id == session_id,
                    Document.processing_status == "completed"
                )
            )
            completed_count = len(completed_result.fetchall())
            
            # Failed documents
            failed_result = await session.execute(
                select(Document).where(
                    Document.crawl_session_id == session_id,
                    Document.processing_status == "failed"
                )
            )
            failed_count = len(failed_result.fetchall())
            
            return {
                'total': total_count,
                'completed': completed_count,
                'failed': failed_count,
                'pending': total_count - completed_count - failed_count
            }
