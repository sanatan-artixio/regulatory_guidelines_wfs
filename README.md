# FDA Regulatory Guidelines Workflow

A complete workflow for harvesting and processing FDA regulatory guidance documents with LLM-powered feature extraction.

## Overview

This project provides a complete workflow for FDA regulatory intelligence:

1. **Data Harvesting** - Crawls FDA's guidance documents database (2,786+ documents), extracts metadata, and downloads PDFs
2. **Data Processing** - Extracts structured regulatory information from PDFs using GPT-4.1 and stores as queryable JSON

**Target Website:** https://www.fda.gov/regulatory-information/search-fda-guidance-documents

## Architecture

This project consists of two main components:

### 1. FDA Crawler (Data Harvesting)
```
fda_crawler/
├── crawler.py      # All crawling, parsing, downloading, and database logic
├── models.py       # SQLAlchemy ORM models  
├── config.py       # Pydantic settings
└── cli.py          # Typer CLI interface
```

### 2. Data Processing Pipeline (Feature Extraction)
```
data_cleaning/
├── processor.py        # Main processing pipeline
├── pdf_extractor.py    # PDF text extraction with PDFplumber
├── llm_processor.py    # GPT-4.1 feature extraction
├── models.py          # Database and Pydantic models
├── config.py          # Configuration settings
└── cli.py             # CLI interface
```

## Features

### Data Harvesting (FDA Crawler)
✅ **Complete Data Extraction**
- Document metadata (title, issue date, FDA organization, topic, status)
- Detail page information (docket numbers, summaries, regulated products)
- Direct PDF downloads stored in PostgreSQL with integrity verification

✅ **Simple & Fast**
- Uses FDA JSON API for document discovery (much faster than scraping)
- Async processing with configurable concurrency
- Rate limiting and polite crawling (1 req/sec default)
- Resume functionality for interrupted crawls
- Idempotent operations (no duplicates)

### Data Processing Pipeline
✅ **PDF Processing**
- Extract text from stored PDFs using PDFplumber
- Handle various PDF formats and encodings
- Structured content extraction (tables, metadata)

✅ **LLM-Powered Analysis**
- GPT-4.1 integration for regulatory feature extraction
- Pydantic schema validation for structured outputs
- Medical device regulatory focus (expandable to other product types)
- Confidence scoring and error handling

✅ **Scalable Processing**
- Async processing with configurable concurrency
- Batch processing with rate limiting
- Resume capability for interrupted sessions
- Comprehensive logging and monitoring

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# Create PostgreSQL database and run migrations
psql -h localhost -U your_user -d your_db -f fda_crawler/migrate.sql
```

### 3. Configure

Set environment variables:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db"
```

### 4. Test Run

```bash
# Step 1: Test crawler with 5 documents
python -m fda_crawler.cli test --limit 5

# Step 2: Test data processing pipeline
python -m data_cleaning.cli test

# Step 3: Process the crawled documents
python -m data_cleaning.cli process --limit 5

# Check status
python -m fda_crawler.cli status <session-id>
python -m data_cleaning.cli status <session-id>
```

## CLI Commands

### FDA Crawler Commands
```bash
# Initialize database schema
python -m fda_crawler.cli init

# Full crawl
python -m fda_crawler.cli crawl --concurrency 4 --rate-limit 1.0

# Test run
python -m fda_crawler.cli test --limit 10

# Resume interrupted crawl
python -m fda_crawler.cli resume <session-id>

# Check session status
python -m fda_crawler.cli status <session-id>
```

### Data Processing Commands
```bash
# Initialize processing database schema
python -m data_cleaning.cli init

# Test processing pipeline components
python -m data_cleaning.cli test

# Process documents (medical devices focus)
python -m data_cleaning.cli process --product-type "medical devices"

# Test processing with limited documents
python -m data_cleaning.cli process --limit 10

# Resume interrupted processing
python -m data_cleaning.cli process --resume <session-id>

# Check processing status
python -m data_cleaning.cli status <session-id>

# Show configuration
python -m data_cleaning.cli config
```

## Docker Usage

### Complete Workflow
```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your_openai_api_key"

# Build and run crawler
docker-compose up --build fda-crawler

# Run data processing
docker-compose run --rm data-processor python -m data_cleaning.cli init
docker-compose run --rm data-processor python -m data_cleaning.cli test
docker-compose run --rm data-processor python -m data_cleaning.cli process --limit 5
```

### Individual Components
```bash
# Crawler only
docker run --rm -e DATABASE_URL="your_db_url" fda-crawler python -m fda_crawler.cli test --limit 5

# Data processor only  
docker run --rm \
  -e DATABASE_URL="your_db_url" \
  -e OPENAI_API_KEY="your_api_key" \
  fda-data-processor python -m data_cleaning.cli process --limit 5
```

## Architecture Details

**Single Pipeline:**
1. Fetch document URLs from FDA JSON API (fast!)
2. For each URL: fetch page → parse metadata → download PDF → save to DB
3. Async processing with concurrency control
4. All data stored in PostgreSQL (no file system dependencies)

**Database Schema:**

*Source Data (from crawler):*
- `source.crawl_sessions` - Track crawl sessions for resume functionality
- `source.documents` - FDA guidance document metadata with enhanced sidebar data
- `source.document_attachments` - PDF files stored as binary data with integrity verification

*Processed Data (from pipeline):*
- `processed.processing_sessions` - Track data processing sessions
- `processed.document_features` - Extracted structured features as JSON
- `processed.processing_logs` - Processing logs and error tracking

**Configuration:**

*FDA Crawler:*
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
SCHEMA_NAME=source
MAX_CONCURRENCY=4
RATE_LIMIT=1.0
USER_AGENT=FDA-Crawler/1.0
```

*Data Processing:*
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4-1106-preview
MAX_CONCURRENCY=4
BATCH_SIZE=10
RATE_LIMIT_REQUESTS_PER_MINUTE=50
```

## Project Structure

```
regulatory_guidelines_wf/
├── fda_crawler/                # Data harvesting package
│   ├── crawler.py              # All crawling logic
│   ├── models.py               # Database models
│   ├── config.py               # Settings
│   ├── cli.py                  # CLI interface
│   ├── migrate.sql             # Database schema
│   └── README.md               # Package documentation
├── data_cleaning/              # Data processing package
│   ├── processor.py            # Main processing pipeline
│   ├── pdf_extractor.py        # PDF text extraction
│   ├── llm_processor.py        # LLM feature extraction
│   ├── models.py               # Database and Pydantic models
│   ├── config.py               # Configuration settings
│   ├── cli.py                  # CLI interface
│   ├── migrate.sql             # Database schema
│   ├── requirements.txt        # Processing dependencies
│   ├── env_example.txt         # Environment configuration example
│   ├── PRD.md                  # Product Requirements Document
│   └── README.md               # Package documentation
├── docker-compose.yml          # Container orchestration
├── Dockerfile                  # Crawler container image
├── Dockerfile.data_cleaning    # Data processor container image
├── requirements.txt            # Shared dependencies
└── setup.py                    # Package setup
```

## Example: Extracted Medical Device Features

The data processing pipeline extracts structured regulatory information:

```json
{
  "device_classification": "Class II",
  "product_code": "LRH", 
  "device_type": "Blood Glucose Monitor",
  "device_category": "Clinical Chemistry",
  "intended_use": "For quantitative measurement of glucose in whole blood",
  "regulatory_pathway": "510(k)",
  "standards_referenced": ["ISO 15197:2013", "IEC 62304"],
  "testing_requirements": ["Clinical accuracy studies", "Shelf life testing"],
  "submission_requirements": ["510(k) premarket notification", "Clinical data"],
  "quality_system_requirements": ["QSR 820.30"],
  "labeling_requirements": ["21 CFR 801"],
  "confidence_score": 0.85
}
```

## Why This Architecture Works

- **Modular Design** - Separate harvesting and processing for flexibility
- **Shared Database** - Seamless integration between components
- **LLM Integration** - GPT-4.1 provides sophisticated regulatory analysis
- **Scalable Processing** - Async pipelines handle large document volumes
- **Simple Deployment** - Docker containers for easy setup
- **Resume Capability** - Robust handling of interruptions
- **Comprehensive Logging** - Full visibility into processing status

This architecture provides enterprise-grade regulatory intelligence while maintaining simplicity and ease of maintenance.