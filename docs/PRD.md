# Product Requirements Document (PRD)

## Product: FDA Guidance Documents Harvester

### Goal
Collect all FDA Guidance documents (2,786+), capture full metadata and attachments (primarily PDFs), store in PostgreSQL (`source` schema) and local filesystem, and keep content up to date via idempotent crawls.

### Users
- Research/Data teams needing a structured, queryable corpus of FDA guidances
- Internal apps that display guidance detail pages and downloadable PDFs

**Target Website:** https://www.fda.gov/regulatory-information/search-fda-guidance-documents

### Technical Overview
This is a **static content web scraping** project targeting FDA's guidance document listing and detail pages. The FDA website serves primarily static HTML content with some JavaScript enhancements, making it suitable for efficient HTTP-based crawling without browser automation.



### Scope (MVP)
- Crawl the master Guidance listing and enumerate all document detail pages
- Parse each detail page for metadata:
  - Title, Summary, Issue Date, FDA Organization, Topic, Guidance Status, Open for Comment, Comment Closing Date, Docket Number, Guidance Type
- Download all attachments (PDF and others), rename deterministically, and store in a managed folder
- Persist metadata and attachment info in PostgreSQL tables under schema `source`
- Provide a CLI to init DB, crawl, resume, and repair

### Non-Goals (MVP)
- UI/web app for browsing (can be added later)
- Advanced duplicate detection across different pages beyond canonical URL

### Functional Requirements
- **Discovery**: Enumerate all document URLs via website's listing pages with pagination support
- **Extraction**: Parse each detail page for structured metadata and attachment links
- **Download**: Fetch PDFs with integrity verification (checksums), resume capability, and retry logic
- **Storage**: Idempotent upserts by `document_url`, attachments unique by `(document_id, source_url)`
- **Politeness**: Configurable rate limits, user agent rotation, and respect for robots.txt
- **Monitoring**: Comprehensive logging, metrics collection, and crawl session tracking
- **Recovery**: Resume interrupted crawls and handle partial failures gracefully

### Data Model
- `documents`, `document_attachments`, `crawl_jobs`, `crawl_log` under schema `source`
- Store primary PDF local path and text extraction (optional in MVP)

### File Storage
- Local path: `data/pdfs` with safe, deterministic filenames: `{issue_date}_{slug(title)}_{mediaid}.pdf`

### Technical Stack (Minimal & Functional)

#### Essential Dependencies Only
- **httpx**: Async HTTP client with built-in retry and timeout
- **beautifulsoup4 + lxml**: Fast HTML parsing
- **sqlalchemy + asyncpg**: Database ORM with async support
- **typer**: CLI framework
- **pydantic**: Configuration management

#### Built-in Python (No Extra Deps)
- **asyncio**: Concurrency and rate limiting
- **pathlib**: File path handling
- **hashlib**: PDF checksum verification
- **logging**: Simple structured logging

### Performance & Reliability
- **Rate Limiting**: Default 1-2 requests/sec using `asyncio.Semaphore` and `asyncio.sleep()`
- **Concurrency**: 4-8 concurrent workers with connection pooling via httpx
- **Retries**: Exponential backoff (2^n seconds) with jitter, max 3 retries per request
- **Timeouts**: 30s connection, 60s read timeout per request
- **Circuit Breaker**: Pause crawling after consecutive failures (10+ in 5min window)
- **Memory Management**: Stream large PDF downloads, limit in-memory queue size
- **Monitoring**: Structured logs, per-session metrics, and crawl health checks

### Constraints & Compliance
- **Robots.txt**: Parse and respect crawl delays and disallowed paths
- **User Agent**: Rotate between legitimate browser user agents
- **Politeness**: Minimum 500ms delay between requests to same domain
- **HTML Resilience**: Graceful degradation when page structure changes
- **Legal Compliance**: Respect FDA website terms of service

### CLI Interface Design

```bash
# Initialize database schema
fda-crawler init --database-url postgresql://...

# Full crawl (discovery + extraction + download)
fda-crawler crawl --max-concurrency 4 --rate-limit 1.5

# Resume interrupted crawl
fda-crawler resume --session-id abc123

# Discovery only (enumerate URLs)
fda-crawler discover --output urls.json

# Download missing PDFs only
fda-crawler download --filter missing

# Health check and statistics
fda-crawler status --session-id abc123
```

### Lean Project Structure
```
fda_crawler/
├── cli.py          # Typer CLI + main entry point
├── crawler.py      # All crawling logic (HTTP + parsing + DB)
├── models.py       # SQLAlchemy ORM models
├── config.py       # Pydantic settings
└── __init__.py

requirements.txt    # Minimal dependencies
.env               # Configuration
migrate.sql        # Database schema setup
```

### Acceptance Criteria
- **Coverage**: 100% of currently visible listing pages enumerated
- **Parsing Success**: > 95% of detail pages parsed with key metadata populated
- **Download Success**: > 95% of PDFs downloaded successfully with integrity verification
- **Idempotency**: CLI runs idempotently; re-running does not duplicate rows or re-download existing files
- **Performance**: Complete crawl of 2,786+ documents within 4-6 hours (respecting rate limits)
- **Reliability**: Handle network failures gracefully with automatic retry and resume capability
- **Data Quality**: All required metadata fields populated for > 90% of documents

### Future Enhancements
- **API Integration**: Use DataTables JSON API for stable pagination and faster discovery
- **Content Processing**: Full-text extraction of PDFs using PyPDF2/pdfplumber and search indexing
- **Incremental Updates**: Smart updates by comparing last_seen timestamps and content hashes
- **Monitoring**: Web dashboard for crawl monitoring and data quality metrics
- **Export Utilities**: Data export to various formats (JSON, CSV, Parquet)
- **Distributed Crawling**: Scale to multiple workers using Celery or similar task queue
