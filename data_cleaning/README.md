# FDA Data Processing Pipeline

A comprehensive data processing pipeline that extracts structured information from FDA regulatory guidance documents using LLM-powered analysis. This system processes PDFs downloaded by the FDA crawler and extracts regulatory features using GPT-4.1.

## Overview

This pipeline takes raw FDA documents (with PDFs) from the crawler database and processes them through:

1. **PDF Text Extraction** - Uses PDFplumber to extract text content from stored PDFs
2. **Data Organization** - Structures document metadata and content for LLM processing
3. **LLM Feature Extraction** - Uses GPT-4.1 to extract regulatory features with Pydantic schema validation
4. **Structured Storage** - Saves extracted features as JSON in PostgreSQL

## Features

✅ **PDF Processing**
- Extract text from PDF files stored in database
- Handle various PDF formats and encodings
- Configurable page limits and text length limits
- Structured content extraction (tables, metadata)

✅ **LLM Integration**
- OpenAI GPT-4.1 API integration
- Pydantic schema validation for structured outputs
- Retry logic with exponential backoff
- Confidence scoring for extractions

✅ **Medical Device Focus**
- Specialized extraction for medical device regulations
- Device classification, regulatory pathways, standards
- Compliance requirements and submission information
- Risk classifications and safety considerations

✅ **Scalable Processing**
- Async processing with configurable concurrency
- Batch processing with rate limiting
- Resume capability for interrupted sessions
- Comprehensive logging and error handling

## Quick Start

### 1. Install Dependencies

```bash
cd data_cleaning
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your settings
```

Required configuration:
- `DATABASE_URL` - PostgreSQL connection (same as FDA crawler)
- `OPENAI_API_KEY` - Your OpenAI API key for GPT-4.1

### 3. Initialize Database

```bash
# Run migration script
psql -h localhost -U your_user -d your_db -f migrate.sql

# Or use the CLI
python -m data_cleaning.cli init
```

### 4. Test Components

```bash
# Test all pipeline components
python -m data_cleaning.cli test

# Check configuration
python -m data_cleaning.cli config
```

### 5. Process Documents

```bash
# Test run with 5 documents
python -m data_cleaning.cli process --limit 5

# Full processing run
python -m data_cleaning.cli process --product-type "medical devices"

# Check processing status
python -m data_cleaning.cli status <session-id>
```

## CLI Commands

### Core Commands

```bash
# Initialize database schema
python -m data_cleaning.cli init

# Process documents
python -m data_cleaning.cli process [OPTIONS]

# Check session status  
python -m data_cleaning.cli status <session-id>

# Test components
python -m data_cleaning.cli test

# Show configuration
python -m data_cleaning.cli config
```

### Processing Options

```bash
# Limit number of documents (for testing)
python -m data_cleaning.cli process --limit 10

# Specify product type
python -m data_cleaning.cli process --product-type "medical devices"

# Resume interrupted session
python -m data_cleaning.cli process --resume <session-id>
```

## Architecture

### Data Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   Source DB     │───▶│  PDF Extraction  │───▶│  LLM Processing │───▶│  Processed DB    │
│ (FDA Crawler)   │    │  (PDFplumber)    │    │   (GPT-4.1)     │    │ (Structured)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────────┘
```

### Database Schema

**Source Data (from FDA crawler):**
- `source.documents` - Document metadata
- `source.document_attachments` - PDF files as binary data

**Processed Data:**
- `processed.processing_sessions` - Track processing runs
- `processed.document_features` - Extracted structured features
- `processed.processing_logs` - Processing logs and errors

### Extracted Features (Medical Devices)

The pipeline extracts comprehensive regulatory information:

```json
{
  "device_classification": "Class II",
  "product_code": "LRH", 
  "device_type": "Blood Glucose Monitor",
  "regulatory_pathway": "510(k)",
  "standards_referenced": ["ISO 15197:2013", "IEC 62304"],
  "testing_requirements": ["Clinical accuracy studies"],
  "submission_requirements": ["510(k) premarket notification"],
  "quality_system_requirements": ["QSR 820.30"],
  "labeling_requirements": ["21 CFR 801"],
  "confidence_score": 0.85
}
```

## Configuration

### Environment Variables

Key settings in `.env`:

```bash
# Database (inherits from FDA crawler)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/fda_db

# OpenAI API
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4-1106-preview
RATE_LIMIT_REQUESTS_PER_MINUTE=50

# Processing
MAX_CONCURRENCY=4
BATCH_SIZE=10
MAX_PDF_PAGES=100
MAX_TEXT_LENGTH=50000
```

### Performance Tuning

- **Concurrency**: Adjust `MAX_CONCURRENCY` based on your system and API limits
- **Rate Limiting**: Set `RATE_LIMIT_REQUESTS_PER_MINUTE` per your OpenAI plan
- **Batch Size**: Increase `BATCH_SIZE` for better throughput
- **PDF Limits**: Set `MAX_PDF_PAGES` and `MAX_TEXT_LENGTH` to control processing time

## Monitoring

### Session Status

```bash
# Check current processing status
python -m data_cleaning.cli status <session-id>
```

### Database Queries

```sql
-- Processing statistics
SELECT * FROM processed.processing_stats;

-- Session summary
SELECT * FROM processed.session_summary WHERE status = 'running';

-- Document features summary  
SELECT * FROM processed.document_features_summary 
WHERE confidence_score > 0.8;

-- Recent processing logs
SELECT * FROM processed.processing_logs 
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
```

## Error Handling

The pipeline includes comprehensive error handling:

- **PDF Extraction Errors**: Corrupted or protected PDFs are logged and skipped
- **LLM API Errors**: Automatic retry with exponential backoff
- **Schema Validation**: Partial extraction when possible, full error logging
- **Database Errors**: Transaction rollback and detailed error logging
- **Resume Capability**: Interrupted sessions can be resumed

## Extending the Pipeline

### Adding New Product Types

1. Create new Pydantic models in `models.py`
2. Update LLM prompts in `llm_processor.py`  
3. Add product type filters in `processor.py`
4. Update configuration in `config.py`

### Custom Feature Extraction

1. Define new Pydantic schemas for your features
2. Create specialized LLM prompts for extraction
3. Add validation and confidence scoring logic
4. Update database schema if needed

## Development

### Project Structure

```
data_cleaning/
├── __init__.py          # Package initialization
├── config.py            # Configuration settings
├── models.py            # Database and Pydantic models
├── pdf_extractor.py     # PDF text extraction
├── llm_processor.py     # LLM feature extraction
├── processor.py         # Main processing pipeline
├── cli.py               # Command line interface
├── migrate.sql          # Database migration
├── requirements.txt     # Dependencies
└── README.md           # This file
```

### Testing

```bash
# Test all components
python -m data_cleaning.cli test

# Test with limited documents
python -m data_cleaning.cli process --limit 5

# Check logs for issues
SELECT * FROM processed.processing_logs WHERE level = 'ERROR';
```

## Integration with FDA Crawler

This pipeline is designed to work seamlessly with the existing FDA crawler:

1. **Shared Database**: Uses the same PostgreSQL instance
2. **Source Data**: Reads from `source.documents` and `source.document_attachments`
3. **No Conflicts**: Only reads from source, writes to separate `processed` schema
4. **Complementary**: Enhances crawled data with structured analysis

## Costs and Considerations

### OpenAI API Costs

- GPT-4.1 pricing: ~$0.01-0.03 per 1K tokens
- Average document: ~3000-8000 tokens
- Estimated cost: $0.05-0.25 per document
- For 1000 documents: ~$50-250

### Performance

- Processing speed: 50-100 documents/hour (depending on concurrency and rate limits)
- Memory usage: ~1-2GB for batch processing
- Storage: ~1-5MB per processed document (including extracted text)

## Troubleshooting

### Common Issues

1. **API Rate Limits**: Reduce `RATE_LIMIT_REQUESTS_PER_MINUTE`
2. **Memory Issues**: Reduce `MAX_CONCURRENCY` and `BATCH_SIZE`
3. **PDF Extraction Failures**: Check `MAX_PDF_PAGES` and `MAX_TEXT_LENGTH`
4. **Database Connection**: Verify `DATABASE_URL` and permissions

### Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check component tests
python -m data_cleaning.cli test --components

# Review processing logs
SELECT * FROM processed.processing_logs 
WHERE level IN ('ERROR', 'WARNING') 
ORDER BY created_at DESC LIMIT 20;
```

## Future Enhancements

- Support for additional product types (pharmaceuticals, biologics)
- Real-time processing triggers
- Advanced document similarity analysis
- Regulatory change detection
- Interactive query interface
- Export capabilities for compliance tools
