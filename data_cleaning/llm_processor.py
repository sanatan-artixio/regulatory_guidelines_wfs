"""LLM processing for feature extraction using OpenAI GPT-4.1"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
import httpx
from openai import AsyncOpenAI
from pydantic import ValidationError

from .config import settings
from .models import ExtractionRequest, ExtractionResponse, MedicalDeviceFeatures

logger = logging.getLogger(__name__)


class LLMProcessor:
    """Process documents using OpenAI GPT-4.1 for feature extraction"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature
        self.max_retries = settings.max_retries
        self.retry_delay = settings.retry_delay
        
    async def extract_features(self, request: ExtractionRequest) -> ExtractionResponse:
        """
        Extract structured features from document using LLM
        
        Args:
            request: ExtractionRequest containing document data
            
        Returns:
            ExtractionResponse with extracted features
        """
        try:
            # Create the prompt for medical device feature extraction
            system_prompt = self._create_system_prompt()
            user_prompt = self._create_user_prompt(request)
            
            # Make API call with retries
            response = await self._call_openai_with_retry(system_prompt, user_prompt)
            
            # Parse and validate response
            extraction_response = self._parse_llm_response(response, request)
            
            logger.info(
                f"Successfully extracted features for document: {request.document_title[:50]}... "
                f"(confidence: {extraction_response.features.confidence_score:.2f})"
            )
            
            return extraction_response
            
        except Exception as e:
            logger.error(f"Error extracting features for {request.document_title}: {e}")
            
            # Return empty response with error info
            return ExtractionResponse(
                features=MedicalDeviceFeatures(confidence_score=0.0),
                processing_notes=f"Extraction failed: {str(e)}",
                success=False
            )
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for medical device feature extraction"""
        return """You are an expert FDA regulatory analyst specializing in medical device regulations. 
Your task is to extract structured information from FDA guidance documents related to medical devices.

You will be provided with:
1. Document metadata (title, URL, FDA organization, etc.)
2. Full text content extracted from the PDF document

Your goal is to extract specific regulatory features and return them as structured JSON that matches the provided schema.

Key areas to focus on:
- Device classification (Class I, II, III)
- Product codes and device types
- Regulatory pathways (510(k), PMA, De Novo, etc.)
- Referenced standards (ISO, ASTM, IEC, etc.)
- Testing and submission requirements
- Compliance requirements (QSR, labeling, etc.)
- Risk classifications and safety information

Guidelines:
1. Only extract information that is explicitly mentioned in the document
2. Use exact terminology from the document when possible
3. For lists, extract all relevant items mentioned
4. Assign a confidence score (0-1) based on how clear and explicit the information is
5. If information is unclear or not present, leave fields empty rather than guessing
6. Focus on actionable regulatory requirements and guidance

Return your response as valid JSON matching the MedicalDeviceFeatures schema."""

    def _create_user_prompt(self, request: ExtractionRequest) -> str:
        """Create the user prompt with document data"""
        return f"""Please extract medical device regulatory features from the following FDA document:

**Document Metadata:**
- Title: {request.document_title}
- URL: {request.document_url}
- FDA Organization: {request.document_metadata.get('fda_organization', 'N/A')}
- Issue Date: {request.document_metadata.get('issue_date', 'N/A')}
- Topic: {request.document_metadata.get('topic', 'N/A')}
- Guidance Status: {request.document_metadata.get('guidance_status', 'N/A')}

**Document Content:**
{request.extracted_text}

Please extract the relevant medical device regulatory information and return it as JSON matching the MedicalDeviceFeatures schema. Focus on information that would be useful for regulatory compliance and device development."""

    async def _call_openai_with_retry(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenAI API with retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"}
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                logger.warning(f"OpenAI API call attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise e
    
    def _parse_llm_response(self, response_text: str, request: ExtractionRequest) -> ExtractionResponse:
        """Parse and validate LLM response"""
        try:
            # Parse JSON response
            response_data = json.loads(response_text)
            
            # Handle different possible response formats
            if "features" in response_data:
                features_data = response_data["features"]
                processing_notes = response_data.get("processing_notes")
            else:
                # Assume the entire response is the features object
                features_data = response_data
                processing_notes = None
            
            # Flatten nested structures that might come from LLM
            flattened_data = {}
            for key, value in features_data.items():
                if isinstance(value, dict):
                    # If it's a dict, try to extract the main value
                    if 'classification' in value:
                        flattened_data[key] = value['classification']
                    elif 'value' in value:
                        flattened_data[key] = value['value']
                    elif 'text' in value:
                        flattened_data[key] = value['text']
                    else:
                        # Take the first string value found
                        string_values = [v for v in value.values() if isinstance(v, str)]
                        if string_values:
                            flattened_data[key] = string_values[0]
                        else:
                            flattened_data[key] = str(value)
                else:
                    flattened_data[key] = value
            
            # Validate against Pydantic schema
            features = MedicalDeviceFeatures(**flattened_data)
            
            # Ensure confidence score is set
            if features.confidence_score == 0.0:
                # Calculate basic confidence based on extracted data
                features.confidence_score = self._calculate_confidence_score(features)
            
            return ExtractionResponse(
                features=features,
                processing_notes=processing_notes,
                success=True
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")
            
            return ExtractionResponse(
                features=MedicalDeviceFeatures(
                    confidence_score=0.0,
                    extraction_notes=f"JSON parsing failed: {str(e)}"
                ),
                processing_notes="Failed to parse LLM response as JSON",
                success=False
            )
            
        except ValidationError as e:
            logger.error(f"Response validation failed: {e}")
            logger.debug(f"Raw response: {response_text}")
            
            # Try to create partial features with what we can extract
            try:
                response_data = json.loads(response_text)
                if "features" in response_data:
                    features_data = response_data["features"]
                else:
                    features_data = response_data
                
                # Create features with only valid fields
                valid_fields = {}
                for field_name, field_info in MedicalDeviceFeatures.__fields__.items():
                    if field_name in features_data:
                        try:
                            valid_fields[field_name] = features_data[field_name]
                        except Exception:
                            continue
                
                features = MedicalDeviceFeatures(**valid_fields)
                features.confidence_score = 0.3  # Lower confidence due to validation issues
                features.extraction_notes = f"Partial extraction due to validation errors: {str(e)}"
                
                return ExtractionResponse(
                    features=features,
                    processing_notes=f"Partial extraction completed with validation errors",
                    success=True
                )
                
            except Exception:
                return ExtractionResponse(
                    features=MedicalDeviceFeatures(
                        confidence_score=0.0,
                        extraction_notes=f"Validation failed: {str(e)}"
                    ),
                    processing_notes="Response validation failed",
                    success=False
                )
        
        except Exception as e:
            logger.error(f"Unexpected error parsing LLM response: {e}")
            
            return ExtractionResponse(
                features=MedicalDeviceFeatures(
                    confidence_score=0.0,
                    extraction_notes=f"Parsing error: {str(e)}"
                ),
                processing_notes="Unexpected parsing error",
                success=False
            )
    
    def _calculate_confidence_score(self, features: MedicalDeviceFeatures) -> float:
        """Calculate confidence score based on extracted features"""
        score = 0.0
        total_fields = 0
        
        # Key fields with higher weight
        key_fields = {
            'device_classification': 0.2,
            'device_type': 0.15,
            'regulatory_pathway': 0.15,
            'intended_use': 0.1,
        }
        
        # List fields with moderate weight
        list_fields = {
            'standards_referenced': 0.1,
            'testing_requirements': 0.1,
            'submission_requirements': 0.1,
        }
        
        # Other fields with lower weight
        other_fields = {
            'product_code': 0.05,
            'device_category': 0.05,
        }
        
        # Calculate score for key fields
        for field, weight in key_fields.items():
            value = getattr(features, field, None)
            if value and value.strip():
                score += weight
            total_fields += 1
        
        # Calculate score for list fields
        for field, weight in list_fields.items():
            value = getattr(features, field, [])
            if value and len(value) > 0:
                score += weight
            total_fields += 1
        
        # Calculate score for other fields
        for field, weight in other_fields.items():
            value = getattr(features, field, None)
            if value and value.strip():
                score += weight
            total_fields += 1
        
        # Ensure score is between 0 and 1
        return min(1.0, max(0.0, score))
    
    async def test_api_connection(self) -> bool:
        """Test OpenAI API connection"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello, please respond with 'API test successful'"}],
                max_tokens=50,
                temperature=0
            )
            
            result = response.choices[0].message.content
            logger.info(f"API test response: {result}")
            return "API test successful" in result.lower()
            
        except Exception as e:
            logger.error(f"API test failed: {e}")
            return False
