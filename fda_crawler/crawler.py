"""Main crawler logic - backward compatibility wrapper for refactored crawler"""
import asyncio
import logging
from typing import List, Optional, Dict, Any

from .crawler_refactored import FDACrawlerRefactored

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FDACrawler:
    """Backward compatibility wrapper for the refactored crawler"""
    
    def __init__(self):
        """Initialize the crawler wrapper"""
        self._refactored_crawler = None
        logger.warning("Using legacy FDACrawler wrapper. Consider migrating to FDACrawlerRefactored for better modularity.")
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._refactored_crawler = FDACrawlerRefactored()
        await self._refactored_crawler.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._refactored_crawler:
            await self._refactored_crawler.__aexit__(exc_type, exc_val, exc_tb)
    
    async def init_database(self):
        """Initialize database schema (delegated to refactored crawler)"""
        if not self._refactored_crawler:
            raise RuntimeError("Crawler not initialized. Use async context manager.")
        return await self._refactored_crawler.init_database()
    
    async def crawl(self, test_limit: Optional[int] = None, resume_session_id: Optional[str] = None) -> str:
        """Main crawl method (delegated to refactored crawler)"""
        if not self._refactored_crawler:
            raise RuntimeError("Crawler not initialized. Use async context manager.")
        return await self._refactored_crawler.crawl(test_limit, resume_session_id)
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get crawl session status (delegated to refactored crawler)"""
        if not self._refactored_crawler:
            raise RuntimeError("Crawler not initialized. Use async context manager.")
        return await self._refactored_crawler.get_session_status(session_id)
    
    # Expose fallback documents as class attribute for backward compatibility
    @property
    def FALLBACK_DOCUMENTS(self):
        """Get fallback documents"""
        return FDACrawlerRefactored.FALLBACK_DOCUMENTS


# Maintain backward compatibility for any code that might import these directly
async def create_crawler():
    """Create and initialize a crawler instance"""
    crawler = FDACrawler()
    await crawler.__aenter__()
    return crawler
