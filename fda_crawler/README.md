# FDA Guidance Documents Harvester - Simple Version

A minimal, straightforward web crawler for collecting FDA Guidance documents with full metadata and PDF downloads.

## Overview

This is the **simplified version** with just 4 essential files:
- `crawler.py` - All crawling, parsing, downloading, and database logic
- `models.py` - SQLAlchemy ORM models  
- `config.py` - Pydantic settings
- `cli.py` - Typer CLI interface

**Target Website:** https://www.fda.gov/regulatory-information/search-fda-guidance-documents

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# Create PostgreSQL database and run migrations
psql -h localhost -U your_user -d your_db -f migrate.sql
```

### 3. Configure

Set environment variables:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db"
```

### 4. Test Run

```bash
# Test with 5 documents
python -m fda_crawler_simple.cli test --limit 5

# Full crawl
python -m fda_crawler_simple.cli crawl

# Check status
python -m fda_crawler_simple.cli status <session-id>
```

## CLI Commands

```bash
# Initialize database schema
fda-crawler init

# Full crawl
fda-crawler crawl --concurrency 4 --rate-limit 1.0

# Test run
fda-crawler test --limit 10

# Resume interrupted crawl
fda-crawler resume <session-id>

# Check session status
fda-crawler status <session-id>
```

## Docker Usage

```bash
# Build and run
docker-compose up --build

# Test run
docker run --rm -e DATABASE_URL="your_db_url" fda-crawler-simple fda-crawler test --limit 5
```

## Features

✅ **Complete Data Extraction**
- Document metadata (title, issue date, FDA organization, topic, status)
- Detail page information (docket numbers, summaries, regulated products)
- Direct PDF downloads stored in PostgreSQL

✅ **Simple & Fast**
- Uses FDA JSON API for document discovery (much faster than scraping)
- Async processing with configurable concurrency
- Rate limiting and polite crawling
- Resume functionality for interrupted crawls

✅ **Minimal Dependencies**
- httpx, BeautifulSoup, SQLAlchemy, Typer, Pydantic
- No browser automation needed
- No complex folder structures

## Architecture

**Single Pipeline:**
1. Fetch document URLs from FDA JSON API
2. For each URL: fetch page → parse metadata → download PDF → save to DB
3. Async processing with concurrency control
4. All data stored in PostgreSQL (no file system dependencies)

**Database Schema:**
- `crawl_sessions` - Track crawl sessions for resume functionality
- `documents` - FDA guidance document metadata
- `document_attachments` - PDF files stored as binary data

This simplified version maintains all the functionality of the complex version but with 80% fewer files and much easier maintenance.
