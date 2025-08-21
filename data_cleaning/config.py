"""Configuration settings for the data processing pipeline"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Database configuration (inherits from FDA crawler)
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/fda_db",
        description="Database connection URL"
    )
    source_schema: str = Field(default="source", description="Source data schema name")
    processed_schema: str = Field(default="source", description="Processed data schema name (same as source)")
    
    # OpenAI API configuration
    openai_api_key: str = Field(description="OpenAI API key for GPT-4.1")
    openai_model: str = Field(default="gpt-4-1106-preview", description="OpenAI model to use")
    openai_max_tokens: int = Field(default=4000, description="Maximum tokens per request")
    openai_temperature: float = Field(default=0.1, description="Model temperature for consistency")
    
    # Processing configuration
    max_concurrency: int = Field(default=4, description="Maximum concurrent processing tasks")
    batch_size: int = Field(default=10, description="Number of documents per batch")
    rate_limit_requests_per_minute: int = Field(default=50, description="OpenAI API rate limit")
    
    # PDF processing
    max_pdf_pages: int = Field(default=100, description="Maximum pages to process per PDF")
    max_text_length: int = Field(default=50000, description="Maximum text length to send to LLM")
    
    # Processing filters
    product_types: list[str] = Field(
        default=["medical devices", "Medical Devices", "MEDICAL DEVICES"],
        description="Product types to process"
    )
    
    # Retry configuration
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Base retry delay in seconds")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
