"""Browser automation for FDA guidance documents extraction"""
import asyncio
import logging
import os
import random
import time
import shutil
from typing import List, Dict, Any, Optional

import undetected_chromedriver as uc
from playwright.async_api import async_playwright
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup

from .config import settings

logger = logging.getLogger(__name__)


class UndetectedChromeAutomation:
    """Handles undetected Chrome browser automation for bot detection bypass"""
    
    def __init__(self):
        self.driver = None
    
    def _configure_chrome_options(self) -> uc.ChromeOptions:
        """Configure Chrome options for stealth and cloud optimization"""
        options = uc.ChromeOptions()
        
        # Essential options for cloud environments
        cloud_options = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-field-trial-config',
            '--memory-pressure-off',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-default-apps',
            '--disable-background-networking',
            '--disable-sync',
            '--disable-translate',
            '--hide-scrollbars',
            '--metrics-recording-only',
            '--mute-audio',
            '--no-crash-upload',
            '--disable-logging',
            '--disable-permissions-api',
            '--disable-notifications',
            '--disable-speech-api',
            '--disable-file-system',
            '--disable-presentation-api',
            '--disable-remote-fonts',
            '--disable-shared-workers',
        ]
        
        for option in cloud_options:
            options.add_argument(option)
        
        # Set headless mode
        if settings.browser_headless:
            options.add_argument('--headless=new')
        
        # Set realistic window size with randomization
        width = random.randint(1366, 1920)
        height = random.randint(768, 1080)
        options.add_argument(f'--window-size={width},{height}')
        
        # Advanced stealth options
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-features=VizDisplayCompositor,VizHitTestSurfaceLayer')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Memory and performance tweaks
        options.add_argument('--max_old_space_size=2048')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-first-run')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-features=TranslateUI')
        
        return options
    
    def _find_chrome_executable(self) -> Optional[str]:
        """Find Chrome/Chromium executable"""
        chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable', 
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser'
        ]
        
        for path in chrome_paths:
            if shutil.which(path.split('/')[-1]) or os.path.exists(path):
                logger.info(f"Found Chrome/Chromium at: {path}")
                return path
        
        return None
    
    def _apply_stealth_techniques(self):
        """Apply advanced fingerprint masking and stealth techniques"""
        logger.info("🎭 Applying advanced fingerprint masking...")
        
        stealth_script = """
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override automation flags
            window.chrome = {
                runtime: {},
            };
            
            // Override permissions API
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' }),
                }),
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: ""},
                        description: "",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ],
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Override platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
            });
            
            // Override vendor
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.',
            });
            
            // Override connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                }),
            });
            
            // Mock screen properties
            Object.defineProperty(screen, 'colorDepth', {
                get: () => 24,
            });
            
            // Mock timezone
            Date.prototype.getTimezoneOffset = () => 300; // EST
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """
        
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': stealth_script
        })
        
        # Set realistic viewport
        viewport_width = random.randint(1366, 1920)
        viewport_height = random.randint(768, 1080)
        self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': viewport_width,
            'height': viewport_height,
            'deviceScaleFactor': 1,
            'mobile': False,
        })
    
    def _simulate_human_behavior(self):
        """Simulate human-like behavior to avoid detection"""
        logger.info("🤖 Simulating human behavior...")
        
        self.driver.execute_script("""
            // Simulate mouse movement
            document.dispatchEvent(new MouseEvent('mousemove', {
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': Math.random() * window.innerWidth,
                'clientY': Math.random() * window.innerHeight
            }));
            
            // Simulate scrolling
            window.scrollTo(0, Math.random() * 500);
            
            // Simulate focus events
            window.dispatchEvent(new Event('focus'));
            document.dispatchEvent(new Event('visibilitychange'));
        """)
        
        time.sleep(random.uniform(2, 4))
    
    def _check_bot_detection(self) -> bool:
        """Check if bot detection was triggered"""
        current_url = self.driver.current_url
        if "apology_objects/abuse-detection-apology.html" in current_url:
            logger.error("❌ Bot detection triggered - redirected to apology page")
            logger.error(f"Current URL: {current_url}")
            return True
        return False
    
    def _attempt_evasion(self) -> bool:
        """Attempt advanced evasion techniques"""
        logger.info("🔄 Attempting advanced evasion technique...")
        
        # Clear all browser data
        self.driver.execute_script("window.localStorage.clear();")
        self.driver.execute_script("window.sessionStorage.clear();")
        self.driver.delete_all_cookies()
        
        time.sleep(random.uniform(5, 10))
        
        # Try alternative entry points
        alternative_urls = [
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            "https://www.fda.gov/regulatory-information/",
            "https://www.fda.gov/"
        ]
        
        for alt_url in alternative_urls:
            try:
                logger.info(f"🔄 Trying alternative URL: {alt_url}")
                self.driver.get(alt_url)
                time.sleep(random.uniform(3, 6))
                
                if not self._check_bot_detection():
                    logger.info(f"✅ Successfully accessed: {self.driver.current_url}")
                    
                    # Navigate to guidance page if needed
                    if "search-fda-guidance-documents" not in self.driver.current_url:
                        logger.info("🔄 Navigating to guidance documents page...")
                        self.driver.get("https://www.fda.gov/regulatory-information/search-fda-guidance-documents")
                        time.sleep(random.uniform(3, 6))
                        
                        if self._check_bot_detection():
                            continue
                    
                    return True
            except Exception as e:
                logger.warning(f"⚠️ Alternative URL failed: {e}")
                continue
        
        return False
    
    def _change_pagination_to_all(self) -> bool:
        """Change pagination to show all entries"""
        try:
            logger.info("🔧 Attempting to increase page size...")
            
            page_size_selectors = [
                'select[name*="length"]',
                'select[name*="pageSize"]', 
                '.dataTables_length select',
                'select.form-control',
                'select[name="example_length"]',
                '.dataTables_wrapper select'
            ]
            
            for selector in page_size_selectors:
                try:
                    select_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    logger.info(f"📋 Found pagination selector: {selector}")
                    
                    # Get all available options
                    options = select_element.find_elements(By.TAG_NAME, "option")
                    option_texts = [opt.text.strip() for opt in options]
                    option_values = [opt.get_attribute("value") for opt in options]
                    logger.info(f"📊 Available page size options: {option_texts} (values: {option_values})")
                    
                    # Priority 1: Look for "All" option
                    for option in options:
                        option_text = option.text.strip().lower()
                        option_value = option.get_attribute("value")
                        
                        if option_text == "all" or option_value == "-1":
                            logger.info(f"🎯 Selecting 'All' option: {option.text}")
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", option)
                            time.sleep(0.5)
                            option.click()
                            time.sleep(random.uniform(3, 5))
                            return True
                    
                    # Priority 2: Select largest number
                    numeric_options = []
                    for option in options:
                        try:
                            value = int(option.get_attribute("value"))
                            numeric_options.append((value, option))
                        except (ValueError, TypeError):
                            continue
                    
                    if numeric_options:
                        largest_value, largest_option = max(numeric_options, key=lambda x: x[0])
                        logger.info(f"📈 Selecting largest option: {largest_option.text} (value: {largest_value})")
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", largest_option)
                        time.sleep(0.5)
                        largest_option.click()
                        time.sleep(random.uniform(3, 5))
                        return True
                        
                except Exception as selector_error:
                    logger.debug(f"Selector {selector} failed: {selector_error}")
                    continue
            
            logger.warning("⚠️ Could not find or change pagination selector")
            return False
                    
        except Exception as e:
            logger.warning(f"⚠️ Could not change page size: {e}")
            return False
    
    def launch_and_extract_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Launch Chrome and extract FDA guidance documents data"""
        documents = []
        
        try:
            logger.info("🚀 Launching undetected Chrome browser...")
            
            options = self._configure_chrome_options()
            chrome_executable = self._find_chrome_executable()
            
            self.driver = uc.Chrome(
                options=options,
                version_main=None,
                driver_executable_path=None,
                browser_executable_path=chrome_executable,
                user_data_dir=None,
                headless=settings.browser_headless,
                use_subprocess=False,
                debug=False
            )
            
            logger.info("✅ Undetected Chrome browser launched successfully")
            
            # Apply stealth techniques
            self._apply_stealth_techniques()
            self.driver.implicitly_wait(10)
            
            # Navigate to FDA page
            logger.info("📄 Navigating to FDA guidance documents page...")
            self.driver.get("https://www.fda.gov/regulatory-information/search-fda-guidance-documents")
            time.sleep(random.uniform(3, 7))
            
            # Wait for page load
            WebDriverWait(self.driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            logger.info("✅ Page loaded successfully")
            
            # Simulate human behavior
            self._simulate_human_behavior()
            
            # Check for bot detection and attempt evasion if needed
            if self._check_bot_detection():
                if not self._attempt_evasion():
                    raise Exception("Bot detection triggered - all evasion attempts failed")
            
            logger.info(f"✅ Current URL: {self.driver.current_url}")
            
            # Wait for content to load
            time.sleep(random.uniform(5, 10))
            
            # Find the data table
            table_found, found_selector = self._find_data_table()
            if not table_found:
                raise Exception("No DataTable found")
            
            # Change pagination to show all entries
            self._change_pagination_to_all()
            
            # Extract documents from table
            documents = self._extract_documents_from_table(found_selector, limit)
            
            logger.info(f"✅ Successfully extracted {len(documents)} documents")
            
        except Exception as e:
            logger.error(f"❌ Undetected Chrome error: {e}")
            
            # Take screenshot for debugging
            if self.driver:
                try:
                    screenshot_path = f"/tmp/fda_error_{int(time.time())}.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.error(f"📸 Error screenshot saved to: {screenshot_path}")
                except:
                    pass
            
            raise
        
        finally:
            self.cleanup()
        
        return documents
    
    def _find_data_table(self) -> tuple[bool, Optional[str]]:
        """Find the data table on the page"""
        table_selectors = [
            'table',
            'table.dataTable',
            'table[id*="DataTable"]',
            'table.display',
            '.dataTables_wrapper table',
            'table tbody tr',
            '[role="alert"] table',
            '.table-responsive table'
        ]
        
        for i, selector in enumerate(table_selectors, 1):
            try:
                logger.info(f"🔍 Trying selector {i}/{len(table_selectors)}: {selector}")
                
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                table_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if table_element and table_element.text.strip():
                    logger.info(f"✅ Found table with selector: {selector}")
                    return True, selector
                
            except TimeoutException:
                logger.info(f"⏳ Selector {selector} not found, trying next...")
                continue
            except Exception as e:
                logger.warning(f"⚠️ Error with selector {selector}: {e}")
                continue
        
        # Debug information
        self._log_debug_info()
        return False, None
    
    def _log_debug_info(self):
        """Log debug information about the page"""
        try:
            screenshot_path = f"/tmp/fda_debug_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_path)
            logger.error(f"📸 Debug screenshot saved to: {screenshot_path}")
            
            page_title = self.driver.title
            page_source_length = len(self.driver.page_source)
            
            logger.error(f"📄 Page title: {page_title}")
            logger.error(f"📝 Page source length: {page_source_length}")
            logger.error(f"🔗 Current URL: {self.driver.current_url}")
            
            all_elements = self.driver.find_elements(By.CSS_SELECTOR, "*")
            table_elements = self.driver.find_elements(By.CSS_SELECTOR, "table")
            
            logger.error(f"🔍 Found {len(all_elements)} total elements on page")
            logger.error(f"📊 Found {len(table_elements)} table elements")
            
        except Exception as e:
            logger.error(f"Could not capture debug info: {e}")
    
    def _extract_documents_from_table(self, selector: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Extract document data from the table"""
        from .parsers import SeleniumTableParser
        
        documents = []
        
        # Find all table rows
        rows = self.driver.find_elements(By.CSS_SELECTOR, f"{selector} tbody tr")
        
        if not rows:
            # Try alternative selectors
            alternative_selectors = ["table tr", ".dataTable tr", "[role='row']"]
            for alt_selector in alternative_selectors:
                rows = self.driver.find_elements(By.CSS_SELECTOR, alt_selector)
                if rows:
                    logger.info(f"✅ Found {len(rows)} rows with alternative selector: {alt_selector}")
                    break
        
        logger.info(f"📊 Found {len(rows)} table rows")
        
        parser = SeleniumTableParser()
        
        for i, row in enumerate(rows):
            try:
                row_text = row.text.strip()
                if not row_text or len(row_text) < 20:
                    continue
                
                links = row.find_elements(By.TAG_NAME, "a")
                if not links:
                    continue
                
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 3:
                    continue
                
                document_data = parser.parse_table_row(row, cells, links)
                
                if document_data:
                    documents.append(document_data)
                    logger.info(f"✅ Extracted document {i+1}: {document_data.get('title', 'Unknown')[:50]}...")
                    
                    if limit and len(documents) >= limit:
                        logger.info(f"✅ Reached limit of {limit} documents")
                        break
            
            except Exception as e:
                logger.warning(f"⚠️ Error extracting row {i+1}: {e}")
                continue
        
        return documents
    
    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ Chrome browser closed")
            except:
                pass


class PlaywrightAutomation:
    """Handles Playwright browser automation (fallback option)"""
    
    def __init__(self):
        self.browser = None
        self.page = None
    
    async def _get_browser_args(self) -> List[str]:
        """Get browser arguments optimized for cloud environments"""
        return [
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
    
    async def launch_and_extract_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Launch Playwright and extract data (fallback method)"""
        documents = []
        
        async with async_playwright() as p:
            try:
                logger.info("🚀 Launching browser with enhanced cloud settings...")
                browser_args = await self._get_browser_args()
                
                self.browser = await p.chromium.launch(
                    headless=settings.browser_headless,
                    args=browser_args,
                    slow_mo=100
                )
                
                logger.info("✅ Browser launched successfully")
                self.page = await self.browser.new_page()
                
                # Configure page
                await self._configure_page()
                
                # Navigate and extract data
                documents = await self._navigate_and_extract(limit)
                
            except Exception as e:
                logger.error(f"Browser automation error: {e}")
                raise
            
            finally:
                if self.browser:
                    await self.browser.close()
        
        return documents
    
    async def _configure_page(self):
        """Configure page with realistic settings"""
        await self.page.set_viewport_size({"width": 1280, "height": 720})
        
        await self.page.set_extra_http_headers({
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
        
        # Add stealth script
        await self.page.add_init_script("""
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
    
    async def _navigate_and_extract(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Navigate to FDA page and extract documents"""
        from .parsers import PlaywrightTableParser
        
        logger.info("📄 Navigating to FDA guidance documents page...")
        await self.page.goto(
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
            timeout=120000,
            wait_until="networkidle"
        )
        logger.info("✅ Page loaded successfully")
        
        # Wait for JavaScript execution
        await self.page.wait_for_timeout(5000)
        
        # Wait for content indicators
        try:
            await self.page.wait_for_function("""
                () => document.body.innerText.includes('entries') || 
                     document.body.innerText.includes('Showing') ||
                     document.querySelectorAll('table').length > 0
            """, timeout=60000)
            logger.info("✅ Page content indicators found")
        except Exception as e:
            logger.warning(f"⚠️ Content indicators not found: {e}")
        
        # Find table and change pagination
        found_selector = await self._find_table_and_change_pagination()
        if not found_selector:
            raise Exception("No DataTable found")
        
        # Extract data
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        parser = PlaywrightTableParser()
        documents = parser.parse_table_data(soup, limit)
        
        logger.info(f"Successfully extracted {len(documents)} documents using browser")
        return documents
    
    async def _find_table_and_change_pagination(self) -> Optional[str]:
        """Find table and attempt to change pagination to show all entries"""
        table_selectors = [
            'table',
            'table.dataTable',
            'table[id*="DataTable"]', 
            'table.display',
            '.dataTables_wrapper table',
            'table tbody tr',
            '[role="alert"] table',
            '.table-responsive table'
        ]
        
        found_selector = None
        for i, selector in enumerate(table_selectors, 1):
            try:
                logger.info(f"🔍 Trying selector {i}/{len(table_selectors)}: {selector}")
                await self.page.wait_for_selector(selector, timeout=20000)
                logger.info(f"✅ Found table with selector: {selector}")
                found_selector = selector
                break
            except Exception as e:
                logger.debug(f"❌ Selector {selector} failed: {str(e)[:100]}")
                continue
        
        if found_selector:
            await self._change_pagination_to_all()
        
        return found_selector
    
    async def _change_pagination_to_all(self):
        """Change pagination to show all entries"""
        try:
            logger.info("🔧 Attempting to increase page size (Playwright)...")
            
            page_size_selectors = [
                'select[name*="length"]',
                'select[name*="pageSize"]', 
                '.dataTables_length select',
                '[aria-label*="entries"] select',
                'select[name="example_length"]',
                '.dataTables_wrapper select'
            ]
            
            for selector in page_size_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000)
                    logger.info(f"📋 Found pagination selector: {selector}")
                    
                    # Get available options
                    options = await self.page.query_selector_all(f"{selector} option")
                    option_values = []
                    option_texts = []
                    
                    for option in options:
                        value = await option.get_attribute("value")
                        text = await option.text_content()
                        option_values.append(value)
                        option_texts.append(text.strip() if text else "")
                    
                    logger.info(f"📊 Available options: {option_texts} (values: {option_values})")
                    
                    # Try to select "All"
                    try:
                        await self.page.select_option(selector, value='-1')
                        logger.info("🎯 Selected 'All' entries option")
                        await self.page.wait_for_timeout(4000)
                        return
                    except:
                        try:
                            await self.page.select_option(selector, label='All')
                            logger.info("🎯 Selected 'All' entries option by label")
                            await self.page.wait_for_timeout(4000)
                            return
                        except:
                            pass
                    
                    # Select largest numeric value
                    numeric_values = []
                    for value in option_values:
                        try:
                            if value and value != "-1":
                                numeric_values.append(int(value))
                        except (ValueError, TypeError):
                            continue
                    
                    if numeric_values:
                        largest_value = str(max(numeric_values))
                        try:
                            await self.page.select_option(selector, value=largest_value)
                            logger.info(f"📈 Selected largest option: {largest_value}")
                            await self.page.wait_for_timeout(4000)
                            return
                        except:
                            continue
                            
                except Exception as selector_error:
                    logger.debug(f"Selector {selector} failed: {selector_error}")
                    continue
            
            logger.warning("⚠️ Could not change pagination - proceeding with default page size")
            
        except Exception as e:
            logger.warning(f"Could not change DataTable page size: {e}")
