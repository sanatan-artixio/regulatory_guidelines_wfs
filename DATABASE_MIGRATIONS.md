# FDA Crawler Database Migrations

This document explains the database schema and migration process for the FDA Guidance Documents Crawler.

## Database Schema Overview

The crawler uses PostgreSQL with the following main tables:

- **`crawl_sessions`** - Tracks crawl sessions for resume functionality
- **`documents`** - FDA guidance document metadata
- **`document_attachments`** - Document attachments (PDFs and other files)

## Recent Schema Changes

### New Sidebar Metadata Fields (Latest Update)

Added new columns to capture enhanced metadata from FDA document detail page sidebars:

- **`regulated_products`** (TEXT) - JSON array of regulated products (e.g., `["Biologics", "Medical Devices"]`)
- **`topics`** (TEXT) - JSON array of topics from sidebar (e.g., `["User Fees", "Administrative / Procedural"]`)
- **`content_current_date`** (VARCHAR(50)) - Content current as of date (e.g., `"07/30/2025"`)

**Note:** The existing `topic` field is kept for backward compatibility but is now considered legacy.

## Migration Files

### 1. `migrate.sql` - Fresh Installation
- **Purpose**: Creates all tables from scratch
- **Use when**: Setting up a new database
- **Safe**: Yes, uses `CREATE TABLE IF NOT EXISTS`

### 2. `migrate_add_sidebar_metadata.sql` - Add Sidebar Metadata
- **Purpose**: Adds new sidebar metadata columns to existing tables
- **Use when**: Upgrading existing database to support sidebar data extraction
- **Safe**: Yes, checks if columns exist before adding them

### 3. `init-db.sh` - Complete Reset
- **Purpose**: ⚠️ **DESTROYS ALL DATA** and recreates tables
- **Use when**: You want to start completely fresh
- **Safe**: NO - This will delete all your crawled documents!

## How to Run Migrations

### Option 1: Use the Migration Runner (Recommended)

```bash
# Make sure DATABASE_URL is set
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"

# Run the migration runner
./run_migration.sh
```

The script will guide you through the available options.

### Option 2: Manual Migration

```bash
# For fresh installation
psql "$DATABASE_URL" -f migrate.sql

# For adding sidebar metadata to existing database
psql "$DATABASE_URL" -f migrate_add_sidebar_metadata.sql

# For complete reset (⚠️ DESTROYS DATA)
bash init-db.sh
```

## Migration Strategy

### For Existing Deployments

If you have an existing FDA crawler deployment:

1. **Backup your database first!**
2. Run the sidebar metadata migration:
   ```bash
   ./run_migration.sh
   # Choose option 2
   ```
3. Your existing data will be preserved and new columns will be added

### For New Deployments

1. Use the fresh installation migration:
   ```bash
   ./run_migration.sh
   # Choose option 1
   ```

### For Development/Testing

1. If you want to start fresh with test data:
   ```bash
   ./run_migration.sh
   # Choose option 3 (⚠️ This deletes everything!)
   ```

## Verifying Migration Success

After running migrations, you can verify the schema:

```sql
-- Check if new columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'source' 
  AND table_name = 'documents' 
  AND column_name IN ('regulated_products', 'topics', 'content_current_date');

-- Check indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE schemaname = 'source' 
  AND tablename = 'documents'
  AND indexname LIKE '%regulated%' OR indexname LIKE '%topics%';
```

## Data Access

### Using the ORM

```python
from fda_crawler.models import Document

# Get regulated products as a list
document = session.query(Document).first()
products = document.get_regulated_products_list()  # Returns ['Biologics', 'Medical Devices']
topics = document.get_topics_list()  # Returns ['User Fees', 'Administrative / Procedural']
```

### Direct SQL Queries

```sql
-- Query documents with specific regulated products
SELECT title, regulated_products 
FROM source.documents 
WHERE regulated_products::jsonb ? 'Biologics';

-- Query documents with specific topics
SELECT title, topics 
FROM source.documents 
WHERE topics::jsonb ? 'User Fees';

-- Get all unique regulated products
SELECT DISTINCT jsonb_array_elements_text(regulated_products::jsonb) as product
FROM source.documents 
WHERE regulated_products IS NOT NULL;
```

## Troubleshooting

### Common Issues

1. **Column already exists error**
   - This is normal if you run migrations multiple times
   - The migration scripts check for existing columns

2. **Permission denied**
   - Make sure your database user has CREATE/ALTER permissions
   - Check that the `source` schema exists

3. **Connection refused**
   - Verify your `DATABASE_URL` is correct
   - Ensure PostgreSQL is running

### Rollback Strategy

If you need to rollback the sidebar metadata migration:

```sql
-- Remove the new columns (⚠️ This will lose the sidebar data)
ALTER TABLE source.documents DROP COLUMN IF EXISTS regulated_products;
ALTER TABLE source.documents DROP COLUMN IF EXISTS topics;
ALTER TABLE source.documents DROP COLUMN IF EXISTS content_current_date;

-- Remove the indexes
DROP INDEX IF EXISTS source.idx_documents_regulated_products;
DROP INDEX IF EXISTS source.idx_documents_topics;
DROP INDEX IF EXISTS source.idx_documents_content_date;
```

## Best Practices

1. **Always backup before migrations**
2. **Test migrations on a copy first**
3. **Use the migration runner script for consistency**
4. **Monitor the logs during migration**
5. **Verify data integrity after migration**
