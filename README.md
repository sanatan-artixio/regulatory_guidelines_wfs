# FDA Guidance Documents Harvester

A minimal, straightforward web crawler for collecting FDA Guidance documents with full metadata and PDF downloads.

## Overview

This project crawls the FDA's guidance documents database (2,786+ documents), extracts comprehensive metadata, downloads PDFs, and stores everything in a PostgreSQL database with resume capability.

**Target Website:** https://www.fda.gov/regulatory-information/search-fda-guidance-documents

## Simplified Architecture

This project follows the **lean implementation strategy** with just **4 core files**:

```
fda_crawler/
├── crawler.py      # All crawling, parsing, downloading, and database logic
├── models.py       # SQLAlchemy ORM models
├── config.py       # Pydantic settings
└── cli.py          # Typer CLI interface
```

## Features

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

✅ **Minimal Dependencies**
- httpx, BeautifulSoup, SQLAlchemy, Typer, Pydantic
- No browser automation needed
- No complex folder structures

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
# Test with 5 documents
python -m fda_crawler.cli test --limit 5

# Full crawl
python -m fda_crawler.cli crawl

# Check status
python -m fda_crawler.cli status <session-id>
```

## CLI Commands

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

## Docker Usage

```bash
# Build and run
docker-compose up --build

# Test run
docker run --rm -e DATABASE_URL="your_db_url" fda-crawler python -m fda_crawler.cli test --limit 5
```

## Architecture Details

**Single Pipeline:**
1. Fetch document URLs from FDA JSON API (fast!)
2. For each URL: fetch page → parse metadata → download PDF → save to DB
3. Async processing with concurrency control
4. All data stored in PostgreSQL (no file system dependencies)

**Database Schema:**
- `crawl_sessions` - Track crawl sessions for resume functionality
- `documents` - FDA guidance document metadata with enhanced sidebar data
- `document_attachments` - PDF files stored as binary data with integrity verification

**Configuration:**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
SCHEMA_NAME=source
MAX_CONCURRENCY=4
RATE_LIMIT=1.0
USER_AGENT=FDA-Crawler/1.0
```

## Project Structure

```
regulatory_guidelines_wf/
├── fda_crawler/            # Main package (4 files only!)
│   ├── crawler.py          # All crawling logic
│   ├── models.py           # Database models
│   ├── config.py           # Settings
│   ├── cli.py              # CLI interface
│   ├── migrate.sql         # Database schema
│   └── README.md           # Package documentation
├── docker-compose.yml      # Container orchestration
├── Dockerfile             # Container image
├── requirements.txt        # Dependencies
└── setup.py               # Package setup
```

## Why This Works

- **Single crawler.py** handles all HTTP, parsing, and DB logic in one place
- **No separate services** - everything in one async pipeline
- **Minimal dependencies** - only what's absolutely needed
- **Simple deployment** - just run the CLI command
- **Easy maintenance** - all logic is in one place, easy to understand and modify

This simplified version maintains 100% of the functionality of complex multi-file architectures but with 80% fewer files and much easier maintenance.