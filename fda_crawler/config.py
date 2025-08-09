"""Configuration management using Pydantic"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://sanatanupmanyu:ksDq2jazKmxxzv.VxXbkwR6Uxz@localhost:5432/quriousri_db",
        env="DATABASE_URL"
    )
    schema_name: str = Field(default="source", env="SCHEMA_NAME")
    
    # File storage (optional - PDFs stored in database by default)
    pdf_root: Path = Field(default=Path("./exported_pdfs"), env="PDF_ROOT")
    
    # Crawling behavior
    max_concurrency: int = Field(default=4, env="MAX_CONCURRENCY")
    rate_limit: float = Field(default=1.0, env="RATE_LIMIT")  # requests per second
    user_agent: str = Field(default="FDA-Crawler/1.0", env="USER_AGENT")
    
    # HTTP timeouts
    connect_timeout: int = Field(default=30, env="CONNECT_TIMEOUT")
    read_timeout: int = Field(default=60, env="READ_TIMEOUT")
    
    # Retry settings
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    retry_delay: float = Field(default=1.0, env="RETRY_DELAY")
    
    # Testing
    test_limit: Optional[int] = Field(default=None, env="TEST_LIMIT")  # Limit docs for testing
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def model_post_init(self, __context):
        """Ensure export directory exists if needed"""
        # Only create directory if it will be used for exports
        pass


# Global settings instance
settings = Settings()
