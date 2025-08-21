"""PDF text extraction using PDFplumber"""
import io
import logging
from typing import Optional, Dict, Any
import pdfplumber
from .config import settings

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text content from PDF files using PDFplumber"""
    
    def __init__(self):
        self.max_pages = settings.max_pdf_pages
        self.max_text_length = settings.max_text_length
    
    def extract_text(self, pdf_content: bytes, filename: str = "document.pdf") -> Dict[str, Any]:
        """
        Extract text from PDF binary content
        
        Args:
            pdf_content: Binary PDF data
            filename: Optional filename for logging
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        try:
            # Create file-like object from bytes
            pdf_buffer = io.BytesIO(pdf_content)
            
            extracted_data = {
                "text": "",
                "page_count": 0,
                "extraction_successful": False,
                "extraction_error": None,
                "metadata": {}
            }
            
            with pdfplumber.open(pdf_buffer) as pdf:
                total_pages = len(pdf.pages)
                pages_to_process = min(total_pages, self.max_pages)
                
                extracted_data["page_count"] = total_pages
                extracted_data["metadata"]["total_pages"] = total_pages
                extracted_data["metadata"]["pages_processed"] = pages_to_process
                
                if pages_to_process < total_pages:
                    logger.warning(
                        f"PDF {filename} has {total_pages} pages, "
                        f"processing only first {pages_to_process} pages"
                    )
                
                # Extract text from each page
                text_parts = []
                for page_num, page in enumerate(pdf.pages[:pages_to_process], 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            # Add page separator for context
                            text_parts.append(f"\\n--- Page {page_num} ---\\n{page_text}")
                        else:
                            logger.warning(f"No text found on page {page_num} of {filename}")
                    except Exception as e:
                        logger.error(f"Error extracting text from page {page_num} of {filename}: {e}")
                        continue
                
                # Combine all text
                full_text = "\\n".join(text_parts)
                
                # Truncate if too long
                if len(full_text) > self.max_text_length:
                    logger.warning(
                        f"Text from {filename} is {len(full_text)} chars, "
                        f"truncating to {self.max_text_length}"
                    )
                    full_text = full_text[:self.max_text_length] + "\\n[TEXT TRUNCATED]"
                
                extracted_data["text"] = full_text
                extracted_data["extraction_successful"] = True
                extracted_data["metadata"]["text_length"] = len(full_text)
                
                # Extract PDF metadata if available
                if pdf.metadata:
                    extracted_data["metadata"]["pdf_metadata"] = {
                        k: str(v) for k, v in pdf.metadata.items() if v is not None
                    }
                
                logger.info(
                    f"Successfully extracted {len(full_text)} chars from {pages_to_process} pages of {filename}"
                )
                
                return extracted_data
                
        except Exception as e:
            error_msg = f"Failed to extract text from PDF {filename}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "text": "",
                "page_count": 0,
                "extraction_successful": False,
                "extraction_error": error_msg,
                "metadata": {"error_type": type(e).__name__}
            }
    
    def extract_text_with_structure(self, pdf_content: bytes, filename: str = "document.pdf") -> Dict[str, Any]:
        """
        Extract text with additional structure information
        
        Args:
            pdf_content: Binary PDF data
            filename: Optional filename for logging
            
        Returns:
            Dictionary containing text, structure info, and metadata
        """
        try:
            pdf_buffer = io.BytesIO(pdf_content)
            
            extracted_data = {
                "text": "",
                "structured_content": [],
                "page_count": 0,
                "extraction_successful": False,
                "extraction_error": None,
                "metadata": {}
            }
            
            with pdfplumber.open(pdf_buffer) as pdf:
                total_pages = len(pdf.pages)
                pages_to_process = min(total_pages, self.max_pages)
                
                extracted_data["page_count"] = total_pages
                extracted_data["metadata"]["total_pages"] = total_pages
                extracted_data["metadata"]["pages_processed"] = pages_to_process
                
                text_parts = []
                structured_content = []
                
                for page_num, page in enumerate(pdf.pages[:pages_to_process], 1):
                    try:
                        # Extract basic text
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"\\n--- Page {page_num} ---\\n{page_text}")
                        
                        # Extract structured elements (tables, etc.)
                        page_content = {
                            "page_number": page_num,
                            "text": page_text or "",
                            "tables": [],
                            "bbox": page.bbox if hasattr(page, 'bbox') else None
                        }
                        
                        # Extract tables if present
                        try:
                            tables = page.extract_tables()
                            if tables:
                                for i, table in enumerate(tables):
                                    page_content["tables"].append({
                                        "table_index": i,
                                        "data": table,
                                        "row_count": len(table) if table else 0
                                    })
                                logger.info(f"Found {len(tables)} tables on page {page_num}")
                        except Exception as table_error:
                            logger.warning(f"Error extracting tables from page {page_num}: {table_error}")
                        
                        structured_content.append(page_content)
                        
                    except Exception as e:
                        logger.error(f"Error processing page {page_num} of {filename}: {e}")
                        continue
                
                # Combine text
                full_text = "\\n".join(text_parts)
                
                # Truncate if needed
                if len(full_text) > self.max_text_length:
                    full_text = full_text[:self.max_text_length] + "\\n[TEXT TRUNCATED]"
                
                extracted_data["text"] = full_text
                extracted_data["structured_content"] = structured_content
                extracted_data["extraction_successful"] = True
                extracted_data["metadata"]["text_length"] = len(full_text)
                extracted_data["metadata"]["tables_found"] = sum(
                    len(page.get("tables", [])) for page in structured_content
                )
                
                return extracted_data
                
        except Exception as e:
            error_msg = f"Failed to extract structured content from PDF {filename}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "text": "",
                "structured_content": [],
                "page_count": 0,
                "extraction_successful": False,
                "extraction_error": error_msg,
                "metadata": {"error_type": type(e).__name__}
            }
    
    def validate_pdf_content(self, pdf_content: bytes) -> bool:
        """
        Validate that the content is a valid PDF
        
        Args:
            pdf_content: Binary PDF data
            
        Returns:
            True if valid PDF, False otherwise
        """
        try:
            pdf_buffer = io.BytesIO(pdf_content)
            with pdfplumber.open(pdf_buffer) as pdf:
                # Try to access basic properties
                _ = len(pdf.pages)
                return True
        except Exception as e:
            logger.error(f"PDF validation failed: {e}")
            return False
