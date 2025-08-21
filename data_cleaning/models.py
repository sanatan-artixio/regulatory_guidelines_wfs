"""Database models for processed data"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, ForeignKey, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field

Base = declarative_base()


class ProcessingSession(Base):
    """Track data processing sessions"""
    __tablename__ = "processing_sessions"
    __table_args__ = {"schema": "source"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, nullable=False, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running, completed, failed, paused
    
    # Processing configuration
    product_type = Column(String(50), nullable=False)
    total_documents = Column(Integer, nullable=True)
    processed_documents = Column(Integer, nullable=False, default=0)
    failed_documents = Column(Integer, nullable=False, default=0)
    configuration = Column(JSON, nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    
    # Relationships
    document_features = relationship("DocumentFeatures", back_populates="processing_session")
    processing_logs = relationship("ProcessingLog", back_populates="processing_session")
    
    def __repr__(self):
        return f"<ProcessingSession {self.id} ({self.status})>"


class DocumentFeatures(Base):
    """Extracted features from processed documents"""
    __tablename__ = "document_features"
    __table_args__ = {"schema": "source"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(UUID(as_uuid=True), nullable=False)  # References source.documents.id
    processing_session_id = Column(UUID(as_uuid=True), ForeignKey("source.processing_sessions.id"), nullable=False)
    
    # Processing metadata
    product_type = Column(String(50), nullable=False)
    extracted_text = Column(Text, nullable=True)
    features = Column(JSON, nullable=False)  # Structured extracted features
    confidence_score = Column(Float, nullable=True)
    processing_metadata = Column(JSON, nullable=True)
    
    # Status tracking
    processing_status = Column(String(20), nullable=False, default="completed")
    processing_error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    processing_session = relationship("ProcessingSession", back_populates="document_features")
    
    def __repr__(self):
        return f"<DocumentFeatures {self.source_document_id} ({self.product_type})>"


class ProcessingLog(Base):
    """Processing logs and errors"""
    __tablename__ = "processing_logs"
    __table_args__ = {"schema": "source"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    processing_session_id = Column(UUID(as_uuid=True), ForeignKey("source.processing_sessions.id"), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=True)  # Optional reference to source document
    
    # Log details
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    error_details = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    processing_session = relationship("ProcessingSession", back_populates="processing_logs")
    
    def __repr__(self):
        return f"<ProcessingLog {self.level}: {self.message[:50]}...>"


# Pydantic models for feature extraction

class MedicalDeviceFeatures(BaseModel):
    """Extracted features for medical device documents"""
    
    # Device identification
    device_classification: Optional[str] = Field(
        None, 
        description="Device class (Class I, Class II, Class III)"
    )
    product_code: Optional[str] = Field(
        None, 
        description="FDA product code (3-letter code)"
    )
    device_type: Optional[str] = Field(
        None, 
        description="Type of medical device (e.g., 'Glucose Monitor', 'Pacemaker')"
    )
    device_category: Optional[str] = Field(
        None,
        description="Broad device category (e.g., 'Cardiovascular', 'Diagnostic')"
    )
    intended_use: Optional[str] = Field(
        None, 
        description="Intended use statement from the document"
    )
    
    # Regulatory pathway
    regulatory_pathway: Optional[str] = Field(
        None, 
        description="Regulatory pathway (510(k), PMA, De Novo, Exempt, etc.)"
    )
    premarket_requirements: List[str] = Field(
        default_factory=list, 
        description="Required premarket submissions or studies"
    )
    
    # Standards and testing
    standards_referenced: List[str] = Field(
        default_factory=list, 
        description="Referenced standards (ISO, ASTM, IEC, etc.)"
    )
    testing_requirements: List[str] = Field(
        default_factory=list, 
        description="Required testing procedures or protocols"
    )
    performance_criteria: List[str] = Field(
        default_factory=list,
        description="Performance standards or criteria mentioned"
    )
    
    # Compliance requirements
    quality_system_requirements: List[str] = Field(
        default_factory=list,
        description="Quality system or QSR requirements"
    )
    labeling_requirements: List[str] = Field(
        default_factory=list,
        description="Labeling and marking requirements"
    )
    post_market_requirements: List[str] = Field(
        default_factory=list,
        description="Post-market surveillance or reporting requirements"
    )
    
    # Submission information
    submission_requirements: List[str] = Field(
        default_factory=list, 
        description="Required documentation for submission"
    )
    timeline_information: Optional[str] = Field(
        None, 
        description="Processing timelines or review periods mentioned"
    )
    fee_information: Optional[str] = Field(
        None,
        description="User fees or payment requirements"
    )
    
    # Risk and safety
    risk_classification: Optional[str] = Field(
        None,
        description="Risk classification or safety considerations"
    )
    contraindications: List[str] = Field(
        default_factory=list,
        description="Contraindications or warnings mentioned"
    )
    
    # Metadata
    confidence_score: float = Field(
        0.0, 
        ge=0.0, 
        le=1.0, 
        description="Overall confidence score for extraction (0-1)"
    )
    extraction_notes: Optional[str] = Field(
        None,
        description="Notes about the extraction process or data quality"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_classification": "Class II",
                "product_code": "LRH",
                "device_type": "Blood Glucose Monitor",
                "device_category": "Clinical Chemistry",
                "intended_use": "For quantitative measurement of glucose in whole blood",
                "regulatory_pathway": "510(k)",
                "standards_referenced": ["ISO 15197:2013", "IEC 62304"],
                "testing_requirements": ["Clinical accuracy studies", "Shelf life testing"],
                "submission_requirements": ["510(k) premarket notification", "Clinical data"],
                "confidence_score": 0.85
            }
        }


class ExtractionRequest(BaseModel):
    """Request model for LLM feature extraction"""
    
    document_title: str = Field(description="Document title")
    document_url: str = Field(description="Document URL")
    document_metadata: Dict[str, Any] = Field(description="Document metadata from crawler")
    extracted_text: str = Field(description="Extracted PDF text content")
    product_type: str = Field(description="Product type to focus extraction on")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_title": "Medical Device User Fee Guidance",
                "document_url": "https://www.fda.gov/...",
                "document_metadata": {"fda_organization": "CDRH", "issue_date": "2024"},
                "extracted_text": "This guidance document provides...",
                "product_type": "medical devices"
            }
        }


class ExtractionResponse(BaseModel):
    """Response model for LLM feature extraction"""
    
    features: MedicalDeviceFeatures = Field(description="Extracted features")
    processing_notes: Optional[str] = Field(None, description="Processing notes or warnings")
    success: bool = Field(True, description="Whether extraction was successful")
    
    class Config:
        json_schema_extra = {
            "example": {
                "features": {
                    "device_classification": "Class II",
                    "regulatory_pathway": "510(k)",
                    "confidence_score": 0.85
                },
                "processing_notes": "High confidence extraction",
                "success": True
            }
        }
