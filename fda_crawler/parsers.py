"""HTML parsing and data extraction utilities"""
import re
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SeleniumTableParser:
    """Parser for extracting data from Selenium WebDriver table elements"""
    
    def parse_table_row(self, row, cells, links) -> Optional[Dict[str, Any]]:
        """Parse a table row using Selenium WebDriver elements"""
        try:
            if not links:
                return None
            
            main_link = links[0]
            title = main_link.text.strip()
            document_url = main_link.get_attribute('href')
            
            if not title or not document_url:
                return None
            
            # Extract other information from cells
            cell_texts = [cell.text.strip() for cell in cells]
            
            # Basic document structure
            document_data = {
                'title': title,
                'document_url': document_url,
                'pdf_url': '',  # Will be extracted later
                'pdf_size': '',
                'issue_date': '',
                'fda_organization': '',
                'topic': '',
                'guidance_status': '',
                'open_for_comment': False,
            }
            
            # Try to extract additional information from cell texts
            for cell_text in cell_texts:
                if 'KB' in cell_text or 'MB' in cell_text:
                    document_data['pdf_size'] = cell_text
                elif '/' in cell_text and len(cell_text.split('/')) == 3:  # Date format
                    document_data['issue_date'] = cell_text
                elif 'Final' in cell_text or 'Draft' in cell_text:
                    document_data['guidance_status'] = cell_text
            
            return document_data
            
        except Exception as e:
            logger.warning(f"⚠️ Error parsing table row: {e}")
            return None


class PlaywrightTableParser:
    """Parser for extracting data from Playwright/BeautifulSoup table elements"""
    
    def parse_table_data(self, soup: BeautifulSoup, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Parse table data from BeautifulSoup"""
        documents = []
        
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
        
        return documents
    
    def _parse_browser_table_row(self, row) -> Optional[Dict[str, Any]]:
        """Parse a DataTable row extracted via browser automation"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 6:  # Ensure we have enough columns
                return None
            
            # Extract data from table columns
            title_cell = cells[0]
            
            # Find the document link
            title_link = title_cell.find('a')
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            document_url = title_link.get('href')
            
            # Make URL absolute if needed
            if document_url and not document_url.startswith('http'):
                document_url = urljoin('https://www.fda.gov', document_url)
            
            # Extract other columns
            issue_date = cells[1].get_text(strip=True) if len(cells) > 1 else None
            fda_organization = cells[2].get_text(strip=True) if len(cells) > 2 else None
            topic = cells[3].get_text(strip=True) if len(cells) > 3 else None
            guidance_status = cells[4].get_text(strip=True) if len(cells) > 4 else None
            
            # Look for PDF download link
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


class DocumentDetailParser:
    """Parser for extracting detailed information from FDA document detail pages"""
    
    def __init__(self):
        self.base_url = "https://www.fda.gov"
    
    def parse_document_page(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Parse a document detail page and extract additional metadata"""
        try:
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
        title_element = soup.find('h1')
        if title_element:
            return title_element.get_text(strip=True)
        return None
    
    def _extract_detail_summary(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract detailed summary/description from detail page"""
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            # Skip short paragraphs and navigation text
            if len(text) > 100 and 'guidance' in text.lower():
                return text
        return None
    
    def _extract_docket_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract docket number from detail page"""
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
        
        # Method 1: Look for the specific structure with h2 heading and ul.lcds-metadata-list
        headings = soup.find_all('h2', class_='lcds-description-list__item-heading')
        for heading in headings:
            if 'regulated product' in heading.get_text().lower():
                # Find the associated ul.lcds-metadata-list
                parent_div = heading.find_parent('div')
                if parent_div:
                    metadata_list = parent_div.find('ul', class_='lcds-metadata-list')
                    if metadata_list:
                        items = metadata_list.find_all('li', role='menuitem')
                        for item in items:
                            product_text = item.get_text(strip=True)
                            if product_text:
                                products.append(product_text)
                        break
        
        # Method 2: Fallback - look for any h2/h3 with "regulated product" and associated menu
        if not products:
            headings = soup.find_all(['h2', 'h3'])
            for heading in headings:
                if 'regulated product' in heading.get_text().lower():
                    # Find the associated menu or ul
                    menu = heading.find_next_sibling('menu') or heading.find_next('menu')
                    if not menu:
                        menu = heading.find_next_sibling('ul') or heading.find_next('ul')
                    if menu:
                        items = menu.find_all(['menuitem', 'li'])
                        for item in items:
                            product_text = item.get_text(strip=True)
                            if product_text:
                                products.append(product_text)
                    break
        
        logger.info(f"📊 Extracted {len(products)} regulated products: {products}")
        return products
    
    def _extract_detail_topics(self, soup: BeautifulSoup) -> List[str]:
        """Extract topics from sidebar"""
        topics = []
        
        # Method 1: Look for the specific structure with h2 heading and ul.lcds-metadata-list
        headings = soup.find_all('h2', class_='lcds-description-list__item-heading')
        for heading in headings:
            heading_text = heading.get_text().lower()
            if 'topic' in heading_text and 'regulated' not in heading_text:
                # Find the associated ul.lcds-metadata-list
                parent_div = heading.find_parent('div')
                if parent_div:
                    metadata_list = parent_div.find('ul', class_='lcds-metadata-list')
                    if metadata_list:
                        items = metadata_list.find_all('li', role='menuitem')
                        for item in items:
                            topic_text = item.get_text(strip=True)
                            if topic_text:
                                topics.append(topic_text)
                        break
        
        # Method 2: Fallback - look for any h2/h3 with "topic" and associated menu
        if not topics:
            headings = soup.find_all(['h2', 'h3'])
            for heading in headings:
                heading_text = heading.get_text().lower()
                if 'topic' in heading_text and 'regulated' not in heading_text:
                    # Find the associated menu or ul
                    menu = heading.find_next_sibling('menu') or heading.find_next('menu')
                    if not menu:
                        menu = heading.find_next_sibling('ul') or heading.find_next('ul')
                    if menu:
                        items = menu.find_all(['menuitem', 'li'])
                        for item in items:
                            topic_text = item.get_text(strip=True)
                            if topic_text:
                                topics.append(topic_text)
                    break
        
        logger.info(f"📊 Extracted {len(topics)} topics: {topics}")
        return topics
    
    def _extract_content_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract content current date"""
        # Method 1: Look for the specific "Content current as of" structure
        headings = soup.find_all('h2', class_='lcds-description-list__item-heading')
        for heading in headings:
            if 'content current as of' in heading.get_text().lower():
                # Find the associated time element
                parent_div = heading.find_parent('div')
                if parent_div:
                    time_elem = parent_div.find('time')
                    if time_elem:
                        # Try to get the datetime attribute first, then text content
                        datetime_attr = time_elem.get('datetime')
                        if datetime_attr:
                            # Convert from ISO format to MM/DD/YYYY if needed
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                                return dt.strftime('%m/%d/%Y')
                            except:
                                pass
                        return time_elem.get_text(strip=True)
        
        # Method 2: Fallback - look for any time elements
        time_elements = soup.find_all('time')
        for time_elem in time_elements:
            return time_elem.get_text(strip=True)
        
        return None


class LegacyTableParser:
    """Legacy parser for direct HTTP extraction (fallback when browser automation fails)"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def parse_table_row(self, row, base_url: str) -> Optional[Dict[str, Any]]:
        """Parse a single DataTable row to extract document information"""
        try:
            cells = row.find_all('td')
            if len(cells) < 6:  # Expected columns
                return None
            
            # Extract data from each cell based on FDA structure
            summary_cell = cells[0]  # Summary column (contains + and title link)
            document_cell = cells[1]  # Document (PDF) column  
            issue_date_cell = cells[2]  # Issue Date column
            fda_org_cell = cells[3]  # FDA Organization column
            topic_cell = cells[4]  # Topic column
            status_cell = cells[5]  # Guidance Status column
            comment_cell = cells[6] if len(cells) > 6 else None  # Open for Comment column
            
            # Extract title and detail page URL from summary cell
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
                    # Extract file size from link text
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
