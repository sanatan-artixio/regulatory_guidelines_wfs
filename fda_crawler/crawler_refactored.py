"""Refactored main crawler logic - orchestrates all components"""
import asyncio
import logging
from typing import List, Optional, Dict, Any

import httpx

from .config import settings
from .browser_automation import UndetectedChromeAutomation, PlaywrightAutomation
from .database import DatabaseManager, CrawlSessionManager, DocumentRepository
from .downloader import DocumentProcessor
from .parsers import LegacyTableParser

logger = logging.getLogger(__name__)


class FDACrawlerRefactored:
    """Refactored FDA guidance documents crawler with modular design"""
    
    # Known FDA documents for fallback (single source of truth)
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
        {
            'title': 'Formal Meetings Between the FDA and Sponsors or Applicants of BsUFA Products Guidance for Industry',
            'document_url': 'https://www.fda.gov/regulatory-information/search-fda-guidance-documents/formal-meetings-between-fda-and-sponsors-or-applicants-bsufa-products-guidance-industry',
            'pdf_url': 'https://www.fda.gov/media/113913/download',
            'pdf_size': '358.01 KB',
            'issue_date': '07/18/2025',
            'fda_organization': 'Center for Drug Evaluation and Research',
            'topic': 'Administrative / Procedural, Biosimilars',
            'guidance_status': 'Final',
            'open_for_comment': False,
        },
        {
            'title': 'Development of Cancer Drugs for Use in Novel Combination - Determining the Contribution of the Individual Drugs\' Effects: Draft Guidance for Industry',
            'document_url': 'https://www.fda.gov/regulatory-information/search-fda-guidance-documents/development-cancer-drugs-use-novel-combination-determining-contribution-individual-drugs-effects',
            'pdf_url': 'https://www.fda.gov/media/187589/download',
            'pdf_size': '326.46 KB',
            'issue_date': '07/17/2025',
            'fda_organization': 'Oncology Center of Excellence',
            'topic': 'Clinical - Medical',
            'guidance_status': 'Draft',
            'open_for_comment': True,
        },
    ]
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.session_manager = None
        self.document_repo = None
        self.client: Optional[httpx.AsyncClient] = None
        self.document_processor = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.db_manager.init_database()
        
        self.session_manager = CrawlSessionManager(self.db_manager.get_session_factory())
        self.document_repo = DocumentRepository(self.db_manager.get_session_factory())
        
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
        await self.db_manager.close()
    
    async def init_database(self):
        """Initialize database schema (delegated to database manager)"""
        await self.db_manager.init_database()
    
    async def get_listing_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get document listing data using the best available method"""
        documents = []
        
        # Method 1: Try undetected Chrome (primary method)
        try:
            logger.info("🚀 Attempting to extract data using undetected Chrome...")
            automation = UndetectedChromeAutomation()
            documents = automation.launch_and_extract_data(limit)
            
            if documents:
                logger.info(f"✅ Successfully extracted {len(documents)} documents using undetected Chrome")
                return documents
            
        except Exception as e:
            logger.error(f"❌ Undetected Chrome failed: {e}")
        
        # Method 2: Try Playwright (fallback)
        try:
            logger.info("🚀 Attempting to extract data using Playwright...")
            automation = PlaywrightAutomation()
            documents = await automation.launch_and_extract_data(limit)
            
            if documents:
                logger.info(f"✅ Successfully extracted {len(documents)} documents using Playwright")
                return documents
                
        except Exception as e:
            logger.error(f"❌ Playwright automation failed: {e}")
        
        # Method 3: Try direct HTTP extraction (legacy fallback)
        try:
            logger.info("🚀 Attempting direct HTTP extraction...")
            documents = await self._get_listing_data_http(limit)
            
            if documents:
                logger.info(f"✅ Successfully extracted {len(documents)} documents using HTTP")
                return documents
                
        except Exception as e:
            logger.error(f"❌ HTTP extraction failed: {e}")
        
        # Method 4: Use fallback documents
        logger.warning("⚠️ All extraction methods failed, using fallback documents")
        documents = self.FALLBACK_DOCUMENTS[:limit] if limit else self.FALLBACK_DOCUMENTS
        
        return documents
    
    async def _get_listing_data_http(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Legacy HTTP-based extraction (fallback)"""
        base_url = "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        documents = []
        
        try:
            logger.info("Fetching FDA guidance listing page...")
            response = await self.client.get(base_url)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for table data
            tables = soup.find_all('table')
            rows_with_role = soup.find_all('tr', {'role': 'row'})
            tbody_elements = soup.find_all('tbody')
            
            logger.info(f"Found {len(tables)} table elements, {len(rows_with_role)} role rows, {len(tbody_elements)} tbody elements")
            
            data_rows = []
            
            if rows_with_role:
                data_rows = [row for row in rows_with_role if row.find('td')]
            elif tbody_elements:
                for tbody in tbody_elements:
                    rows = tbody.find_all('tr')
                    data_rows.extend([row for row in rows if row.find('td')])
            elif tables:
                for table in tables:
                    rows = table.find_all('tr')
                    data_rows.extend([row for row in rows if row.find('td')])
            
            if not data_rows:
                logger.warning("Could not find any data rows in the page")
                return []
            
            logger.info(f"Found {len(data_rows)} data rows in listing")
            
            parser = LegacyTableParser(base_url)
            
            for row in data_rows[:limit] if limit else data_rows:
                try:
                    doc_data = parser.parse_table_row(row, base_url)
                    if doc_data:
                        documents.append(doc_data)
                        
                        if limit and len(documents) >= limit:
                            break
                            
                except Exception as e:
                    logger.error(f"Error parsing table row: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching listing data: {e}")
            raise
        
        return documents
    
    async def crawl(self, test_limit: Optional[int] = None, resume_session_id: Optional[str] = None) -> str:
        """Main crawl method with resume capability"""
        try:
            # Create or resume session
            if resume_session_id:
                if not await self.session_manager.resume_crawl_session(resume_session_id):
                    raise Exception(f"Could not resume session {resume_session_id}")
            else:
                await self.session_manager.create_crawl_session(test_limit)
            
            # Initialize document processor
            self.document_processor = DocumentProcessor(self.client, self.session_manager.session_id)
            
            # Get document data
            if not resume_session_id:
                # Fresh crawl - get data from listing
                documents_data = await self.get_listing_data(test_limit)
                
                # Update session with total count
                await self.session_manager.update_session_total_documents(len(documents_data))
            else:
                # Resume - get unprocessed documents from database
                documents_data = await self.session_manager.get_unprocessed_documents()
            
            logger.info(f"Processing {len(documents_data)} documents")
            
            # Process documents with concurrency control
            semaphore = asyncio.Semaphore(settings.max_concurrency)
            
            async def process_with_semaphore(doc_data: Dict[str, Any]):
                async with semaphore:
                    return await self.document_processor.process_document_with_db(
                        doc_data, self.db_manager.get_session_factory()
                    )
            
            # Process all documents
            tasks = [process_with_semaphore(doc_data) for doc_data in documents_data]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes
            successful = sum(1 for r in results if r is True)
            
            # Update session status
            await self.session_manager.complete_session(len(documents_data), successful)
            
            logger.info(f"Crawl completed. Processed: {len(documents_data)}, Successful: {successful}")
            return self.session_manager.session_id
            
        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            # Update session with error
            if self.session_manager and self.session_manager.session_id:
                await self.session_manager.fail_session(str(e))
            raise
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get crawl session status and statistics"""
        return await self.session_manager.get_session_status(session_id)


# Convenience functions for backward compatibility
async def create_crawler() -> FDACrawlerRefactored:
    """Create and initialize a new crawler instance"""
    crawler = FDACrawlerRefactored()
    await crawler.__aenter__()
    return crawler


async def crawl_fda_documents(test_limit: Optional[int] = None, 
                            resume_session_id: Optional[str] = None) -> str:
    """Convenience function to crawl FDA documents"""
    async with FDACrawlerRefactored() as crawler:
        return await crawler.crawl(test_limit, resume_session_id)


async def get_session_status(session_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get session status"""
    async with FDACrawlerRefactored() as crawler:
        return await crawler.get_session_status(session_id)
