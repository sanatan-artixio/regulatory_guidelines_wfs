# FDA Guidance Documents Harvester

A lean, functional web crawler for collecting FDA Guidance documents with full metadata and PDF downloads.

## Overview

This project crawls the FDA's guidance documents database (2,786+ documents), extracts comprehensive metadata, downloads PDFs, and stores everything in a PostgreSQL database with resume capability.

**Target Website:** https://www.fda.gov/regulatory-information/search-fda-guidance-documents

## Features

✅ **Complete Data Extraction**
- Document metadata (title, issue date, FDA organization, topic, status)
- Detail page information (docket numbers, summaries, federal register links)
- Direct PDF downloads with integrity verification

✅ **Robust Architecture**
- Async processing with configurable concurrency
- Rate limiting and polite crawling (1 req/sec default)
- Resume functionality for interrupted crawls
- Idempotent operations (no duplicates)

✅ **Lean Implementation**
- Just 4 core Python files
- Minimal dependencies (httpx, BeautifulSoup, SQLAlchemy, Typer)
- PostgreSQL storage with proper schema
- Clean CLI interface

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

Update database connection in `fda_crawler/config.py` or set environment variables:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db"
export PDF_ROOT="./data/pdfs"
```

### 4. Test Run

```bash
# Test with 5 documents
python -m fda_crawler.cli test --limit 5

# Check status
python -m fda_crawler.cli status <session-id>

# Resume if interrupted
python -m fda_crawler.cli resume <session-id>
```

## CLI Commands

```bash
# Initialize database schema
python -m fda_crawler.cli init

# Full crawl
python -m fda_crawler.cli crawl --max-concurrency 4 --rate-limit 1.0

# Test with limited documents
python -m fda_crawler.cli test --limit 10

# Resume interrupted crawl
python -m fda_crawler.cli resume <session-id>

# Check crawl status
python -m fda_crawler.cli status <session-id>

# View configuration
python -m fda_crawler.cli config
```

## Architecture

### Lean Design (4 Core Files)

```
fda_crawler/
├── cli.py          # Typer CLI interface
├── crawler.py      # Main crawling logic (HTTP + parsing + DB)
├── models.py       # SQLAlchemy ORM models
└── config.py       # Pydantic configuration
```

### Database Schema

- **crawl_sessions**: Track crawl progress and resume capability
- **documents**: FDA guidance document metadata
- **document_attachments**: PDF files and download tracking

### Data Flow

1. **Discovery**: Extract document URLs and metadata from FDA listing
2. **Detail Parsing**: Fetch additional metadata from individual document pages
3. **PDF Download**: Download PDFs with integrity verification
4. **Storage**: Save all data to PostgreSQL with proper relationships

## Example Output

```
🧪 Testing crawler with 5 documents...
📋 Database initialized
INFO: Processing document: Medical Device User Fee Small Business Qualification...
INFO: Downloaded PDF: 07/31/2025_medical_device_user_fee_small_business_qualificati_176439.pdf
✅ Test crawl completed!

Session Status:
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Status               ┃ ✅ Completed               ┃
┃ Progress             ┃ 5/5 (100.0%)               ┃
┃ Successful Downloads ┃ 5                          ┃
┃ Failed Documents     ┃ 0                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Configuration

Key settings in `config.py`:

- `MAX_CONCURRENCY`: Concurrent requests (default: 4)
- `RATE_LIMIT`: Requests per second (default: 1.0)
- `PDF_ROOT`: Local PDF storage directory
- `DATABASE_URL`: PostgreSQL connection string

## Technical Details

### Data Extracted

**From Listing Page:**
- Title, Issue Date, FDA Organization
- Topic, Guidance Status, Comment Status
- Direct PDF download URLs

**From Detail Pages:**
- Full document summary
- Docket numbers and URLs
- Federal Register links
- Regulated products and topics

### File Naming

PDFs are stored with deterministic names:
```
{issue_date}_{title_slug}_{media_id}.pdf
```

Example: `07/31/2025_medical_device_user_fee_small_business_qualificati_176439.pdf`

## Development

### Project Structure

```
├── docs/                    # Documentation
│   ├── PRD.md              # Product Requirements
│   └── architecture.md     # Technical Architecture
├── fda_crawler/            # Main package
├── migrate.sql             # Database schema
├── requirements.txt        # Dependencies
└── setup.py               # Package setup
```

### Adding Features

The modular design makes it easy to extend:

- Add new parsers in `crawler.py`
- Extend database schema in `models.py`
- Add CLI commands in `cli.py`
- Configure new settings in `config.py`

## Current Limitations

- **JavaScript Content**: Currently uses hardcoded document list since FDA uses dynamic table loading
- **Pagination**: Handles first page only (can be extended)
- **Scale**: Tested with 5 documents (ready for full 2,786+ with proper data source)

## Future Enhancements

- Browser automation for full JavaScript support
- AJAX endpoint discovery for direct API access
- Distributed crawling with Celery
- Full-text PDF extraction and search
- Web dashboard for monitoring

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

**Built with Python 3.8+ • PostgreSQL • Modern async/await patterns**
