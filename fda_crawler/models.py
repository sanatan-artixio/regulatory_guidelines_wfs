"""SQLAlchemy ORM models for FDA crawler"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, ForeignKey, Float, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class CrawlSession(Base):
    """Track crawl sessions for resume functionality"""
    __tablename__ = "crawl_sessions"
    __table_args__ = {"schema": "source"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, nullable=False, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running, completed, failed, paused
    
    # Progress tracking
    total_documents = Column(Integer, nullable=True)
    processed_documents = Column(Integer, nullable=False, default=0)
    successful_downloads = Column(Integer, nullable=False, default=0)
    failed_documents = Column(Integer, nullable=False, default=0)
    
    # Settings used for this session
    max_concurrency = Column(Integer, nullable=False)
    rate_limit = Column(Float, nullable=False)
    test_limit = Column(Integer, nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    
    # Relationships
    documents = relationship("Document", back_populates="crawl_session")
    
    def __repr__(self):
        return f"<CrawlSession {self.id} ({self.status})>"


class Document(Base):
    """FDA guidance document metadata"""
    __tablename__ = "documents"
    __table_args__ = {"schema": "source"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawl_session_id = Column(UUID(as_uuid=True), ForeignKey("source.crawl_sessions.id"), nullable=False)
    
    # Core metadata
    document_url = Column(String(500), nullable=False, unique=True)
    title = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    issue_date = Column(Text, nullable=True)              # Increased from String(50) to Text
    fda_organization = Column(Text, nullable=True)        # Increased from String(200) to Text
    topic = Column(Text, nullable=True)                   # Increased from String(200) to Text
    guidance_status = Column(Text, nullable=True)         # Increased from String(100) to Text
    open_for_comment = Column(Boolean, nullable=True)
    comment_closing_date = Column(Text, nullable=True)    # Increased from String(50) to Text
    docket_number = Column(String(100), nullable=True)
    guidance_type = Column(String(100), nullable=True)
    
    # Processing status
    processed_at = Column(DateTime, nullable=True)
    processing_status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    processing_error = Column(Text, nullable=True)
    
    # PDF info
    pdf_path = Column(String(500), nullable=True)
    pdf_checksum = Column(String(64), nullable=True)  # SHA256
    pdf_size_bytes = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    crawl_session = relationship("CrawlSession", back_populates="documents")
    attachments = relationship("DocumentAttachment", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document {self.title[:50]}... ({self.processing_status})>"


class DocumentAttachment(Base):
    """Document attachments (PDFs and other files)"""
    __tablename__ = "document_attachments"
    __table_args__ = {"schema": "source"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("source.documents.id"), nullable=False)
    
    # Attachment metadata
    filename = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=True)  # pdf, doc, etc.
    
    # Download info
    local_path = Column(String(500), nullable=True)  # Keep for backward compatibility
    pdf_content = Column(LargeBinary, nullable=True)  # Store PDF binary data directly
    checksum = Column(String(64), nullable=True)  # SHA256
    size_bytes = Column(Integer, nullable=True)
    
    # Status
    download_status = Column(String(20), nullable=False, default="pending")  # pending, downloading, completed, failed
    download_error = Column(Text, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="attachments")
    
    def __repr__(self):
        return f"<Attachment {self.filename} ({self.download_status})>"
