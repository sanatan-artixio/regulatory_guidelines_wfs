# FDA Guidance Documents Harvester

A lean, functional web crawler for collecting FDA Guidance documents with full metadata and PDF downloads.

## Overview

This project crawls the FDA's guidance documents database (2,786+ documents), extracts comprehensive metadata, downloads PDFs, and stores everything in a PostgreSQL database with resume capability.

**Target Website:** https://www.fda.gov/regulatory-information/search-fda-guidance-documents

## Features

✅ **Complete Data Extraction**
- Document metadata (title, issue date, FDA organization, topic, status)
- Detail page information (docket numbers, summaries, federal register links)
- Direct PDF downloads stored in PostgreSQL with integrity verification

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
# Note: PDFs are stored directly in PostgreSQL, no file system storage needed
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

# Export PDFs from database to files
python -m fda_crawler.cli export-pdfs --output-dir ./exported_pdfs

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
- **document_attachments**: PDF binary data stored directly in PostgreSQL with download tracking

### Data Flow

1. **Discovery**: Extract document URLs and metadata from FDA listing
2. **Detail Parsing**: Fetch additional metadata from individual document pages
3. **PDF Download**: Download PDF binary data with integrity verification
4. **Database Storage**: Save all data including PDF content directly to PostgreSQL

## Example Output

```
🧪 Testing crawler with 5 documents...
📋 Database initialized
INFO: Processing document: Medical Device User Fee Small Business Qualification...
INFO: Downloaded and stored PDF in database: 07/31/2025_medical_device_user_fee_small_business_qualificati_176439.pdf (428737 bytes)
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
- `DATABASE_URL`: PostgreSQL connection string
- `PDF_ROOT`: Export directory for PDF files (optional)

## Database Storage Benefits

✅ **No File System Dependencies**: All PDFs stored directly in PostgreSQL
✅ **Simplified Deployment**: Single database contains everything
✅ **ACID Compliance**: Transactional consistency for PDF downloads
✅ **Easy Backup/Restore**: Standard PostgreSQL backup tools
✅ **Scalable**: Handle thousands of small PDFs efficiently
✅ **Export on Demand**: Extract PDFs to files only when needed

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

PDFs are stored in database with deterministic filenames for reference:
```
{issue_date}_{title_slug}_{media_id}.pdf
```

Example: `07/31/2025_medical_device_user_fee_small_business_qualificati_176439.pdf`

Use `export-pdfs` command to extract files with these names when needed.

## Docker Deployment

### Quick Start with Docker

1. **Build the Docker image:**
```bash
docker build -t fda-crawler .
```

2. **Run with your database:**
```bash
docker run -e DATABASE_URL="postgresql+asyncpg://user:password@host:5432/database" fda-crawler
```

### Docker Compose (Recommended)

1. **Update environment variables in `docker-compose.yml`:**
```yaml
environment:
  DATABASE_URL: postgresql+asyncpg://your_user:your_password@your_host:5432/your_database
```

2. **Run the crawler:**
```bash
# Full crawl
docker-compose up

# Test with limited documents
docker-compose run fda-crawler test --limit 10

# Resume interrupted session
docker-compose run fda-crawler resume <session-id>

# Export PDFs to local directory
docker-compose run fda-crawler export-pdfs --output-dir /app/exported_pdfs
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | - | PostgreSQL connection string |
| `SCHEMA_NAME` | ❌ | `source` | Database schema name |
| `MAX_CONCURRENCY` | ❌ | `4` | Concurrent HTTP requests |
| `RATE_LIMIT` | ❌ | `1.0` | Requests per second |
| `BROWSER_HEADLESS` | ❌ | `true` | Run browser in headless mode |
| `BROWSER_TIMEOUT` | ❌ | `30000` | Browser timeout (milliseconds) |
| `CONNECT_TIMEOUT` | ❌ | `30` | HTTP connect timeout (seconds) |
| `READ_TIMEOUT` | ❌ | `60` | HTTP read timeout (seconds) |

### Docker Commands

```bash
# Full crawl (default)
docker run -e DATABASE_URL="..." fda-crawler

# Test crawl with 10 documents
docker run -e DATABASE_URL="..." fda-crawler test --limit 10

# Resume interrupted crawl
docker run -e DATABASE_URL="..." fda-crawler resume <session-id>

# Check crawl status
docker run -e DATABASE_URL="..." fda-crawler status <session-id>

# Export PDFs from database
docker run -e DATABASE_URL="..." -v ./pdfs:/app/exported_pdfs fda-crawler export-pdfs

# Show configuration
docker run -e DATABASE_URL="..." fda-crawler config

# Interactive shell for debugging
docker run -e DATABASE_URL="..." -it fda-crawler shell
```

### Idempotent Behavior

✅ **The crawler is designed to be idempotent:**
- **Database schema**: Tables created with `IF NOT EXISTS` - no data loss on restart
- **Documents**: Already processed documents are automatically skipped
- **PDFs**: Already downloaded PDFs are not re-downloaded
- **Resume functionality**: Interrupted crawls can be continued
- **Safe restarts**: Running multiple times only processes new/updated content

⚠️ **Important**: The migration script (`migrate.sql`) is now safe and idempotent. It will NOT drop existing tables or data when containers restart.

### Database Management

**Normal Operation (Idempotent):**
```bash
# Safe to run multiple times - preserves existing data
docker-compose up -d
```

**Fresh Database Setup (Data Loss!):**
```bash
# ONLY use this for initial setup or complete reset
export DATABASE_URL="your_database_url_here"
./init-db.sh  # This will DROP all existing data!
```

### Production Deployment

For production use:
1. Use external PostgreSQL database
2. Set appropriate resource limits in docker-compose.yml
3. Configure monitoring and logging
4. Use restart policies for reliability

```bash
# Production example
docker run -d \
  --name fda-crawler \
  --restart unless-stopped \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@prod-db:5432/fda" \
  -e MAX_CONCURRENCY=2 \
  -e RATE_LIMIT=0.5 \
  fda-crawler
```

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
