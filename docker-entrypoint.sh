#!/bin/bash
set -e

# FDA Guidance Documents Harvester - Docker Entrypoint
echo "🚀 Starting FDA Guidance Documents Harvester"

# Validate required environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is required"
    echo "   Example: postgresql+asyncpg://user:password@host:5432/database"
    exit 1
fi

echo "📋 Configuration:"
echo "   Database URL: ${DATABASE_URL}"
echo "   Schema: ${SCHEMA_NAME:-source}"
echo "   Max Concurrency: ${MAX_CONCURRENCY:-4}"
echo "   Rate Limit: ${RATE_LIMIT:-1.0} req/sec"
echo "   Browser Headless: ${BROWSER_HEADLESS:-true}"

# Wait for database to be ready (simple retry mechanism)
echo "🔍 Checking database connectivity..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if python -c "
import asyncio
from fda_crawler.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_connection():
    try:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text('SELECT 1'))
        await engine.dispose()
        return True
    except Exception as e:
        print(f'Connection failed: {e}')
        return False

result = asyncio.run(test_connection())
exit(0 if result else 1)
"; then
        echo "✅ Database connection successful"
        break
    else
        echo "⏳ Database not ready, attempt $attempt/$max_attempts"
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Failed to connect to database after $max_attempts attempts"
            exit 1
        fi
        sleep 2
        attempt=$((attempt + 1))
    fi
done

# Initialize database schema if needed (idempotent)
echo "🔧 Checking database schema..."
python -c "
import asyncio
from fda_crawler.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_and_init_schema():
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        # Check if tables exist
        result = await conn.execute(text(
            \"SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_schema = '{}' AND table_name IN ('crawl_sessions', 'documents', 'document_attachments')\"
            .format(settings.schema_name)
        ))
        table_count = result.scalar()
        
        if table_count == 3:
            print('✅ Database schema already exists, skipping initialization')
        else:
            print('🔧 Initializing database schema for the first time...')
            # Create schema if not exists
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {settings.schema_name}'))
            
            # Only run the parts of migration that create tables (not drop them)
            from fda_crawler.models import Base
            await conn.run_sync(Base.metadata.create_all)
            print('✅ Database schema initialized')
    
    await engine.dispose()

asyncio.run(check_and_init_schema())
"

# Execute the requested command
case "$1" in
    "crawl")
        echo "🕷️ Starting full crawl..."
        python -m fda_crawler.cli crawl ${@:2}
        ;;
    "test")
        echo "🧪 Starting test crawl..."
        python -m fda_crawler.cli test ${@:2}
        ;;
    "resume")
        if [ -z "$2" ]; then
            echo "❌ ERROR: Session ID required for resume command"
            echo "   Usage: docker run ... resume <session-id>"
            exit 1
        fi
        echo "🔄 Resuming crawl session: $2"
        python -m fda_crawler.cli resume ${@:2}
        ;;
    "status")
        if [ -z "$2" ]; then
            echo "❌ ERROR: Session ID required for status command"
            echo "   Usage: docker run ... status <session-id>"
            exit 1
        fi
        echo "📊 Checking status for session: $2"
        python -m fda_crawler.cli status ${@:2}
        ;;
    "export-pdfs")
        echo "📁 Exporting PDFs from database..."
        python -m fda_crawler.cli export-pdfs ${@:2}
        ;;
    "config")
        echo "⚙️ Showing configuration..."
        python -m fda_crawler.cli config
        ;;
    "shell")
        echo "🐚 Starting interactive shell..."
        /bin/bash
        ;;
    *)
        echo "❓ Unknown command: $1"
        echo ""
        echo "Available commands:"
        echo "  crawl           - Start full crawl of FDA guidance documents"
        echo "  test [--limit N] - Test crawl with limited documents"
        echo "  resume <id>     - Resume interrupted crawl session"
        echo "  status <id>     - Check status of crawl session"
        echo "  export-pdfs     - Export PDFs from database to files"
        echo "  config          - Show current configuration"
        echo "  shell           - Start interactive shell"
        echo ""
        echo "Examples:"
        echo "  docker run fda-crawler crawl"
        echo "  docker run fda-crawler test --limit 10"
        echo "  docker run fda-crawler resume abc123-def456"
        exit 1
        ;;
esac

echo "✅ FDA Guidance Documents Harvester completed successfully"
