# Architecture

## Lean Implementation Strategy
Keep it simple: **4 core files** + CLI + config. No over-engineering.

## Core Components
```
fda_crawler/
├── cli.py          # Typer CLI - entry point
├── crawler.py      # Main crawling logic (HTTP + parsing + DB)
├── models.py       # SQLAlchemy models only
└── config.py       # Pydantic settings
```

## Essential Libraries (Minimal Set)
- **httpx** - Async HTTP client
- **beautifulsoup4** + **lxml** - HTML parsing  
- **sqlalchemy** + **asyncpg** - Database ORM
- **typer** - CLI framework
- **pydantic** - Configuration

## Data Flow (Single Pipeline)
1. **CLI** → Start crawl session
2. **crawler.py** → Fetch listing pages → Extract document URLs
3. **crawler.py** → For each URL: fetch → parse → download PDF → save to DB
4. **Async processing** → Handle 4-8 concurrent documents
5. **Rate limiting** → Built-in delays between requests

## Database Schema (3 Tables)
```sql
-- Schema: source
documents (id, url, title, summary, issue_date, status, pdf_path, created_at)
attachments (id, document_id, filename, url, checksum, downloaded_at)
crawl_sessions (id, started_at, completed_at, docs_processed, errors)
```

## Configuration (.env)
```
DATABASE_URL=postgresql://sanatanupmanyu:ksDq2jazKmxxzv.VxXbkwR6Uxz@localhost:5432/quriousri_db

use schema named "source"
PDF_ROOT=./data/pdfs
MAX_CONCURRENCY=4
RATE_LIMIT=1.0
USER_AGENT=FDA-Crawler/1.0
```

## Why This Works
- **Single crawler.py** handles all HTTP, parsing, and DB logic
- **No separate services** - everything in one async pipeline  
- **Minimal dependencies** - only what's absolutely needed
- **Simple deployment** - just run the CLI command
