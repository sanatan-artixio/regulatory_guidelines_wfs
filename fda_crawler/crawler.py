"""Main crawler logic - HTTP, parsing, and database operations"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, text

from .config import settings
from .models import Base, CrawlSession, Document, DocumentAttachment

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FDACrawler:
    """Main FDA guidance documents crawler with resume capability"""
    
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
        self.engine = create_async_engine(settings.database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
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
            
    async def get_listing_data_with_browser(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Use browser automation to extract document data from JavaScript-rendered DataTable"""
        documents = []
        
        async with async_playwright() as p:
            # Enhanced browser args for cloud environments
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--single-process',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-field-trial-config',
                '--memory-pressure-off',
                '--max_old_space_size=4096',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps',
                '--disable-background-networking',
                # Additional cloud-optimized settings
                '--disable-ipc-flooding-protection',
                '--disable-software-rasterizer',
                '--disable-background-media-processing',
                '--disable-component-update',
                '--disable-domain-reliability',
                '--disable-sync',
                '--metrics-recording-only',
                '--no-crash-upload',
                '--disable-logging',
                '--disable-permissions-api',
                '--disable-notifications',
                '--disable-speech-api',
                '--disable-file-system',
                '--disable-presentation-api',
                '--disable-remote-fonts',
                '--disable-shared-workers',
                '--disable-storage-reset',
                '--disable-tabbed-options',
                '--disable-threaded-animation',
                '--disable-threaded-scrolling',
                '--disable-in-process-stack-traces',
                '--disable-histogram-customizer',
                '--disable-gl-extensions',
                '--disable-composited-antialiasing',
                '--disable-canvas-aa',
                '--disable-3d-apis',
                '--disable-accelerated-2d-canvas',
                '--disable-accelerated-jpeg-decoding',
                '--disable-accelerated-mjpeg-decode',
                '--disable-app-list-dismiss-on-blur',
                '--disable-accelerated-video-decode',
                '--num-raster-threads=1'
            ]
            
            try:
                logger.info("🚀 Launching browser with enhanced cloud settings...")
                browser = await p.chromium.launch(
                    headless=settings.browser_headless,
                    args=browser_args,
                    slow_mo=100  # Add slight delay between actions for stability
                )
                
                logger.info("✅ Browser launched successfully")
                page = await browser.new_page()
                
                # Set a reasonable viewport and realistic user agent
                await page.set_viewport_size({"width": 1280, "height": 720})
                
                # Set realistic headers to avoid bot detection
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-User': '?1',
                    'Sec-Fetch-Dest': 'document'
                })
                
                # Add stealth techniques
                await page.add_init_script("""
                    // Remove webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    // Mock plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    // Mock languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en'],
                    });
                """)
                
                logger.info("📄 Navigating to FDA guidance documents page...")
                await page.goto(
                    "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
                    timeout=120000,  # Increased to 120 seconds for cloud environments
                    wait_until="networkidle"  # Wait for network to be completely idle
                )
                logger.info("✅ Page loaded successfully")
                
                # Wait for JavaScript to execute and DOM to be ready
                logger.info("⏳ Waiting for JavaScript execution...")
                await page.wait_for_timeout(5000)  # Give JavaScript time to run
                
                # Try to wait for specific content indicators
                try:
                    # Wait for the guidance document count text to appear
                    await page.wait_for_function("""
                        () => document.body.innerText.includes('entries') || 
                             document.body.innerText.includes('Showing') ||
                             document.querySelectorAll('table').length > 0
                    """, timeout=60000)
                    logger.info("✅ Page content indicators found")
                except Exception as e:
                    logger.warning(f"⚠️ Content indicators not found: {e}")
                
                # Additional wait for DataTables to initialize
                try:
                    await page.wait_for_function("""
                        () => window.jQuery && window.jQuery.fn.DataTable && 
                             (window.jQuery('table').DataTable || document.querySelectorAll('table').length > 0)
                    """, timeout=45000)
                    logger.info("✅ DataTables initialization detected")
                except Exception as e:
                    logger.warning(f"⚠️ DataTables not detected: {e}")
                
                # Take a screenshot for debugging
                try:
                    screenshot = await page.screenshot()
                    logger.info(f"📸 Page screenshot captured ({len(screenshot)} bytes)")
                except Exception as e:
                    logger.warning(f"Could not capture screenshot: {e}")
                
                # Log page content for debugging
                try:
                    content = await page.content()
                    logger.info(f"📝 Page content length: {len(content)} characters")
                    # Check if DataTable-related content exists
                    if 'dataTable' in content.lower():
                        logger.info("✅ DataTable-related content found in page")
                    else:
                        logger.warning("⚠️ No DataTable-related content found in page")
                        
                    if 'showing' in content.lower() and 'entries' in content.lower():
                        logger.info("✅ Table pagination text found")
                    else:
                        logger.warning("⚠️ No pagination text found")
                        
                except Exception as e:
                    logger.warning(f"Could not analyze page content: {e}")
                
                # Wait for the DataTable to load - try multiple selectors with better logging
                logger.info("🔍 Searching for DataTable elements...")
                table_selectors = [
                    'table',  # Start with basic table
                    'table.dataTable',
                    'table[id*="DataTable"]', 
                    'table.display',
                    '.dataTables_wrapper table',
                    'table tbody tr',
                    '[role="alert"] table',  # The table is in an alert role
                    '.table-responsive table'
                ]
                
                table_found = False
                found_selector = None
                for i, selector in enumerate(table_selectors, 1):
                    try:
                        logger.info(f"🔍 Trying selector {i}/{len(table_selectors)}: {selector}")
                        await page.wait_for_selector(selector, timeout=20000)  # Increased timeout
                        logger.info(f"✅ Found table with selector: {selector}")
                        table_found = True
                        found_selector = selector
                        break
                    except Exception as e:
                        logger.debug(f"❌ Selector {selector} failed: {str(e)[:100]}")
                        continue
                
                if not table_found:
                    # Try to get all available selectors for debugging
                    try:
                        all_elements = await page.query_selector_all('*')
                        logger.error(f"🔍 Found {len(all_elements)} total elements on page")
                        
                        # Check for common table-related elements
                        table_elements = await page.query_selector_all('table')
                        logger.error(f"📊 Found {len(table_elements)} table elements")
                        
                        div_elements = await page.query_selector_all('div[class*="table"]')
                        logger.error(f"📊 Found {len(div_elements)} div elements with 'table' in class")
                        
                        # Log page title and URL for debugging
                        page_title = await page.title()
                        page_url = page.url
                        logger.error(f"📄 Page title: {page_title}")
                        logger.error(f"🔗 Page URL: {page_url}")
                        
                        # Check if we got redirected or blocked
                        if 'blocked' in page_title.lower() or 'access denied' in page_title.lower():
                            logger.error("🚫 Page appears to be blocked or access denied")
                        elif len(all_elements) < 20:  # Very few elements suggests minimal page
                            logger.error("⚠️ Page has very few elements - likely bot detection or network issue")
                            
                            # Try refreshing the page once
                            logger.info("🔄 Attempting page refresh...")
                            await page.reload(timeout=60000, wait_until="networkidle")
                            await page.wait_for_timeout(3000)
                            
                            # Check again after refresh
                            refreshed_elements = await page.query_selector_all('*')
                            logger.info(f"🔄 After refresh: {len(refreshed_elements)} elements")
                            
                            if len(refreshed_elements) > len(all_elements):
                                logger.info("✅ Page refresh improved element count, retrying table search...")
                                # Quick retry on the basic table selector
                                try:
                                    await page.wait_for_selector('table', timeout=10000)
                                    logger.info("✅ Found table after refresh!")
                                    table_found = True
                                    found_selector = 'table'
                                except:
                                    logger.warning("❌ Still no table found after refresh")
                        
                    except Exception as e:
                        logger.error(f"Could not analyze page elements: {e}")
                    
                    if not table_found:
                        raise Exception("No DataTable found with any selector - see debug info above")
                
                # Wait a bit more for data to populate
                await page.wait_for_timeout(3000)
                
                # Try to change page size to show more results
                try:
                    # Look for page size selector (common DataTable pattern)
                    page_size_selectors = [
                        'select[name*="length"]',
                        'select[name*="pageSize"]', 
                        '.dataTables_length select',
                        '[aria-label*="entries"] select'
                    ]
                    
                    for selector in page_size_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=2000)
                            # Try to select "All" or a large number like 100
                            await page.select_option(selector, value='-1')  # -1 often means "All"
                            logger.info("Set DataTable to show all entries")
                            await page.wait_for_timeout(3000)
                            break
                        except:
                            try:
                                await page.select_option(selector, value='100')
                                logger.info("Set DataTable to show 100 entries per page")
                                await page.wait_for_timeout(3000)
                                break
                            except:
                                continue
                    
                except Exception as e:
                    logger.warning(f"Could not change DataTable page size: {e}")
                    logger.info("Proceeding with default page size")
                
                # Get the page content after JavaScript execution
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Find the DataTable
                table = soup.find('table', class_='dataTable')
                if not table:
                    logger.error("Could not find DataTable after browser loading")
                    return documents
                
                # Find all data rows in the table body
                tbody = table.find('tbody')
                if not tbody:
                    logger.error("Could not find table body")
                    return documents
                
                rows = tbody.find_all('tr')
                logger.info(f"Found {len(rows)} rows in DataTable")
                
                for i, row in enumerate(rows):
                    if limit and i >= limit:
                        break
                        
                    try:
                        doc_data = self._parse_browser_table_row(row)
                        if doc_data:
                            documents.append(doc_data)
                    except Exception as e:
                        logger.error(f"Error parsing row {i}: {e}")
                        continue
                
                logger.info(f"Successfully extracted {len(documents)} documents using browser")
                
            except Exception as e:
                logger.error(f"Browser automation error: {e}")
                # Fallback to hardcoded documents for testing
                return await self.get_listing_data_fallback(limit)
            
            finally:
                await browser.close()
        
        return documents
    
    def _parse_browser_table_row(self, row) -> Optional[Dict[str, Any]]:
        """Parse a DataTable row extracted via browser automation"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 6:  # Ensure we have enough columns
                return None
            
            # Extract data from table columns (adjust indices based on actual table structure)
            title_cell = cells[0]  # Usually first column
            
            # Find the document link
            title_link = title_cell.find('a')
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            document_url = title_link.get('href')
            
            # Make URL absolute if needed
            if document_url and not document_url.startswith('http'):
                document_url = urljoin('https://www.fda.gov', document_url)
            
            # Extract other columns (adjust based on actual table structure)
            # This will need to be refined based on the actual table columns
            issue_date = cells[1].get_text(strip=True) if len(cells) > 1 else None
            fda_organization = cells[2].get_text(strip=True) if len(cells) > 2 else None
            topic = cells[3].get_text(strip=True) if len(cells) > 3 else None
            guidance_status = cells[4].get_text(strip=True) if len(cells) > 4 else None
            
            # Look for PDF download link (might be in a separate column or as an icon)
            pdf_url = None
            for cell in cells:
                pdf_link = cell.find('a', href=lambda x: x and 'download' in x.lower())
                if pdf_link:
                    pdf_url = pdf_link.get('href')
                    if pdf_url and not pdf_url.startswith('http'):
                        pdf_url = urljoin('https://www.fda.gov', pdf_url)
                    break
            
            return {
                'title': title,
                'document_url': document_url,
                'pdf_url': pdf_url,
                'issue_date': issue_date,
                'fda_organization': fda_organization,
                'topic': topic,
                'guidance_status': guidance_status,
                'open_for_comment': False  # Default, will be updated from detail page
            }
            
        except Exception as e:
            logger.error(f"Error parsing table row: {e}")
            return None

    async def get_listing_data_fallback(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fallback method with hardcoded documents for testing"""
        logger.warning("Using fallback hardcoded documents")
        
        documents = self.FALLBACK_DOCUMENTS[:limit] if limit else self.FALLBACK_DOCUMENTS
        return documents

    async def get_listing_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch document data directly from FDA listing page DataTable"""
        base_url = "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        documents = []
        
        try:
            logger.info("Fetching FDA guidance listing page...")
            response = await self.client.get(base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Debug: Let's see what we actually get
            logger.info("Analyzing page structure...")
            
            # Look for any table elements
            tables = soup.find_all('table')
            logger.info(f"Found {len(tables)} table elements")
            
            # Look for any tr elements with role="row"
            rows_with_role = soup.find_all('tr', {'role': 'row'})
            logger.info(f"Found {len(rows_with_role)} rows with role='row'")
            
            # Look for any tbody elements
            tbody_elements = soup.find_all('tbody')
            logger.info(f"Found {len(tbody_elements)} tbody elements")
            
            # Look for any elements with DataTable-related classes
            datatable_elements = soup.find_all(attrs={'class': lambda x: x and any('datatable' in cls.lower() for cls in x) if x else False})
            logger.info(f"Found {len(datatable_elements)} elements with DataTable classes")
            
            # The FDA site might use JavaScript to load the table dynamically
            # For now, let's try to extract from any available table structure
            data_rows = []
            
            # Try different approaches to find the data
            if rows_with_role:
                # Filter out header rows
                data_rows = [row for row in rows_with_role if row.find('td')]
                logger.info(f"Using {len(data_rows)} data rows from role='row' elements")
            elif tbody_elements:
                for tbody in tbody_elements:
                    rows = tbody.find_all('tr')
                    data_rows.extend([row for row in rows if row.find('td')])
                logger.info(f"Using {len(data_rows)} data rows from tbody elements")
            elif tables:
                for table in tables:
                    rows = table.find_all('tr')
                    data_rows.extend([row for row in rows if row.find('td')])
                logger.info(f"Using {len(data_rows)} data rows from table elements")
            
            if not data_rows:
                logger.warning("Could not find any data rows in the page")
                # Since the table is loaded via JavaScript, let's use known real documents for testing
                logger.info("Using known real FDA guidance documents for testing")
                
                # Return the requested number of documents from our fallback list
                documents = self.FALLBACK_DOCUMENTS[:limit] if limit else self.FALLBACK_DOCUMENTS
                return documents
            
            logger.info(f"Found {len(data_rows)} data rows in listing")
            
            for row in data_rows[:limit] if limit else data_rows:
                try:
                    doc_data = self._parse_table_row(row, base_url)
                    if doc_data:
                        documents.append(doc_data)
                        
                        if limit and len(documents) >= limit:
                            break
                            
                except Exception as e:
                    logger.error(f"Error parsing table row: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching listing data: {e}")
            
        logger.info(f"Extracted {len(documents)} documents from listing")
        return documents
        
    def _parse_table_row(self, row, base_url: str) -> Optional[Dict[str, Any]]:
        """Parse a single DataTable row to extract document information"""
        try:
            cells = row.find_all('td')
            if len(cells) < 6:  # Expected: Summary, Document, Issue Date, FDA Org, Topic, Status, Comment
                return None
                
            # Extract data from each cell based on the real FDA structure
            summary_cell = cells[0]  # Summary column (contains + and title link)
            document_cell = cells[1]  # Document (PDF) column  
            issue_date_cell = cells[2]  # Issue Date column
            fda_org_cell = cells[3]  # FDA Organization column
            topic_cell = cells[4]  # Topic column
            status_cell = cells[5]  # Guidance Status column
            comment_cell = cells[6] if len(cells) > 6 else None  # Open for Comment column
            
            # Extract title and detail page URL from summary cell
            # The summary cell contains both the "+" text and the title link
            title_link = summary_cell.find('a')
            if not title_link:
                return None
                
            title = title_link.get_text(strip=True)
            # Remove the "+" prefix if present
            if title.startswith('+'):
                title = title[1:].strip()
                
            detail_url = urljoin(base_url, title_link.get('href', ''))
            
            # Extract PDF download URL from document cell
            pdf_link = document_cell.find('a')
            pdf_url = None
            pdf_size = None
            if pdf_link:
                pdf_href = pdf_link.get('href', '')
                if pdf_href:
                    pdf_url = urljoin(base_url, pdf_href)
                    # Extract file size from link text - look for pattern like "PDF (418.69 KB)"
                    pdf_text = pdf_link.get_text(strip=True)
                    size_match = re.search(r'PDF \\(([0-9.]+\\s*[KMGT]?B)\\)', pdf_text)
                    if size_match:
                        pdf_size = size_match.group(1)
            
            # Extract other metadata
            issue_date = issue_date_cell.get_text(strip=True) if issue_date_cell else None
            fda_organization = fda_org_cell.get_text(strip=True) if fda_org_cell else None
            topic = topic_cell.get_text(strip=True) if topic_cell else None
            guidance_status = status_cell.get_text(strip=True) if status_cell else None
            open_for_comment = comment_cell.get_text(strip=True) if comment_cell else None
            
            # Clean up the data
            if open_for_comment:
                open_for_comment = open_for_comment.strip().lower() == 'yes'
            else:
                open_for_comment = False
            
            return {
                'title': title,
                'document_url': detail_url,
                'pdf_url': pdf_url,
                'pdf_size': pdf_size,
                'issue_date': issue_date,
                'fda_organization': fda_organization,
                'topic': topic,
                'guidance_status': guidance_status,
                'open_for_comment': open_for_comment
            }
            
        except Exception as e:
            logger.error(f"Error parsing table row: {e}")
            return None
        
    async def parse_document_page(self, url: str) -> Dict[str, Any]:
        """Parse a document detail page and extract additional metadata"""
        try:
            await asyncio.sleep(1.0 / settings.rate_limit)  # Rate limiting
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Extract metadata from detail page
            metadata = {
                'document_url': url,
                'title': self._extract_detail_title(soup),
                'summary': self._extract_detail_summary(soup),
                'docket_number': self._extract_docket_number(soup),
                'docket_url': self._extract_docket_url(soup),
                'issued_by': self._extract_issued_by(soup),
                'federal_register_url': self._extract_federal_register_url(soup),
                'pdf_download_url': self._extract_pdf_download_url(soup),
                'regulated_products': self._extract_regulated_products(soup),
                'topics': self._extract_detail_topics(soup),
                'content_date': self._extract_content_date(soup),
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error parsing document page {url}: {e}")
            return {'document_url': url, 'parsing_error': str(e)}
            
    def _extract_detail_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract full title from detail page"""
        # Look for the main heading
        title_element = soup.find('h1')
        if title_element:
            return title_element.get_text(strip=True)
        return None
        
    def _extract_detail_summary(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract detailed summary/description from detail page"""
        # Look for the main content paragraph
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            # Skip short paragraphs and navigation text
            if len(text) > 100 and 'guidance' in text.lower():
                return text
        return None
        
    def _extract_docket_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract docket number from detail page"""
        # Look for docket number in definition list
        dt_elements = soup.find_all('dt')
        for dt in dt_elements:
            if 'docket' in dt.get_text().lower():
                dd = dt.find_next_sibling('dd')
                if dd:
                    link = dd.find('a')
                    if link:
                        return link.get_text(strip=True)
                    else:
                        return dd.get_text(strip=True)
        return None
        
    def _extract_docket_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract docket URL from detail page"""
        # Look for docket link in definition list
        dt_elements = soup.find_all('dt')
        for dt in dt_elements:
            if 'docket' in dt.get_text().lower():
                dd = dt.find_next_sibling('dd')
                if dd:
                    link = dd.find('a')
                    if link:
                        return link.get('href')
        return None
        
    def _extract_issued_by(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract 'Issued by' information"""
        dt_elements = soup.find_all('dt')
        for dt in dt_elements:
            if 'issued by' in dt.get_text().lower():
                dd = dt.find_next_sibling('dd')
                if dd:
                    return dd.get_text(strip=True)
        return None
        
    def _extract_federal_register_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract Federal Register notice URL"""
        links = soup.find_all('a')
        for link in links:
            if 'federal register' in link.get_text().lower():
                return link.get('href')
        return None
        
    def _extract_pdf_download_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract PDF download URL from detail page"""
        links = soup.find_all('a')
        for link in links:
            text = link.get_text().lower()
            href = link.get('href', '')
            if 'download' in text and 'guidance' in text and '/media/' in href:
                return href
        return None
        
    def _extract_regulated_products(self, soup: BeautifulSoup) -> List[str]:
        """Extract regulated products from sidebar"""
        products = []
        # Look for regulated products section
        headings = soup.find_all(['h2', 'h3'])
        for heading in headings:
            if 'regulated product' in heading.get_text().lower():
                # Find the associated menu
                menu = heading.find_next_sibling('menu') or heading.find_next('menu')
                if menu:
                    items = menu.find_all('menuitem')
                    for item in items:
                        products.append(item.get_text(strip=True))
                break
        return products
        
    def _extract_detail_topics(self, soup: BeautifulSoup) -> List[str]:
        """Extract topics from sidebar"""
        topics = []
        # Look for topics section
        headings = soup.find_all(['h2', 'h3'])
        for heading in headings:
            if 'topic' in heading.get_text().lower() and 'regulated' not in heading.get_text().lower():
                # Find the associated menu
                menu = heading.find_next_sibling('menu') or heading.find_next('menu')
                if menu:
                    items = menu.find_all('menuitem')
                    for item in items:
                        topics.append(item.get_text(strip=True))
                break
        return topics
        
    def _extract_content_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract content current date"""
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            return time_elem.get_text(strip=True)
        return None

        
    async def download_pdf(self, pdf_url: str) -> Optional[Dict[str, Any]]:
        """Download PDF file and return binary data with metadata"""
        try:
            await asyncio.sleep(1.0 / settings.rate_limit)  # Rate limiting
            
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
            

        
    async def process_document(self, doc_data: Dict[str, Any]) -> bool:
        """Process a single document: combine listing data with detail page data, download PDF, save to DB"""
        async with self.async_session() as session:
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
                pdf_success = True
                pdf_url = doc_data.get('pdf_url') or detail_metadata.get('pdf_download_url')
                
                if pdf_url:
                    # Generate filename for reference
                    filename = self._generate_pdf_filename_from_data(doc_data, pdf_url)
                    
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
                        download_result = await self.download_pdf(pdf_url)
                        
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
                    logger.warning(f"No PDF URL found for document: {doc_data.get('title', url)}")
                        
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
                
    def _generate_pdf_filename_from_data(self, doc_data: Dict[str, Any], pdf_url: str) -> str:
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
                
    async def crawl(self, test_limit: Optional[int] = None, resume_session_id: Optional[str] = None) -> str:
        """Main crawl method with resume capability"""
        try:
            # Create or resume session
            if resume_session_id:
                if not await self.resume_crawl_session(resume_session_id):
                    raise Exception(f"Could not resume session {resume_session_id}")
            else:
                await self.create_crawl_session(test_limit)
                
            # Get document data
            if not resume_session_id:
                # Fresh crawl - get data from listing using browser automation
                documents_data = await self.get_listing_data_with_browser(test_limit)
                
                # Update session with total count
                async with self.async_session() as session:
                    await session.execute(
                        update(CrawlSession)
                        .where(CrawlSession.id == self.session_id)
                        .values(total_documents=len(documents_data))
                    )
                    await session.commit()
            else:
                # Resume - get unprocessed documents from database
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
                    
            logger.info(f"Processing {len(documents_data)} documents")
            
            # Process documents with concurrency control
            semaphore = asyncio.Semaphore(settings.max_concurrency)
            
            async def process_with_semaphore(doc_data: Dict[str, Any]):
                async with semaphore:
                    return await self.process_document(doc_data)
                    
            # Process all documents
            tasks = [process_with_semaphore(doc_data) for doc_data in documents_data]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes
            successful = sum(1 for r in results if r is True)
            
            # Update session status
            async with self.async_session() as session:
                await session.execute(
                    update(CrawlSession)
                    .where(CrawlSession.id == self.session_id)
                    .values(
                        status="completed",
                        completed_at=datetime.utcnow(),
                        processed_documents=len(documents_data),
                        successful_downloads=successful
                    )
                )
                await session.commit()
                
            logger.info(f"Crawl completed. Processed: {len(documents_data)}, Successful: {successful}")
            return self.session_id
            
        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            # Update session with error
            if self.session_id:
                async with self.async_session() as session:
                    await session.execute(
                        update(CrawlSession)
                        .where(CrawlSession.id == self.session_id)
                        .values(
                            status="failed",
                            last_error=str(e),
                            error_count=CrawlSession.error_count + 1
                        )
                    )
                    await session.commit()
            raise
            
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
