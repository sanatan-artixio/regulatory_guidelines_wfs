#!/bin/bash
# FDA Guidance Documents Harvester - Database Reset Script
# Run this script ONLY when you want to completely reset the database

set -e

echo "⚠️  WARNING: This script will DROP ALL EXISTING DATA!"
echo "   This should only be used for:"
echo "   - Complete database reset (removes all crawled documents)"
echo "   - Development/testing fresh start"
echo "   - When you want to start crawling from scratch"
echo ""
echo "📊 Current database will be completely wiped!"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Database reset cancelled"
    exit 1
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

echo "🗑️  Dropping existing tables and data..."

# Create a temporary reset script
cat > /tmp/reset_db.sql << 'EOF'
-- Reset database tables for fresh crawl
-- WARNING: This will DELETE all existing data!

-- Drop tables in correct order (respecting foreign keys)
DROP TABLE IF EXISTS source.document_attachments CASCADE;
DROP TABLE IF EXISTS source.documents CASCADE;
DROP TABLE IF EXISTS source.crawl_sessions CASCADE;

-- Drop and recreate schema to be sure
DROP SCHEMA IF EXISTS source CASCADE;
CREATE SCHEMA source;

-- Set search path
SET search_path TO source;

-- Recreate tables
CREATE TABLE crawl_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    
    -- Progress tracking
    total_documents INTEGER,
    processed_documents INTEGER DEFAULT 0,
    successful_downloads INTEGER DEFAULT 0,
    failed_documents INTEGER DEFAULT 0,
    
    -- Error handling
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_session_id UUID NOT NULL REFERENCES crawl_sessions(id) ON DELETE CASCADE,
    
    -- Core metadata
    document_url VARCHAR(500) NOT NULL UNIQUE,
    title TEXT,
    summary TEXT,
    issue_date TEXT,
    fda_organization TEXT,
    topic TEXT,
    guidance_status TEXT,
    open_for_comment BOOLEAN,
    comment_closing_date TEXT,
    docket_number VARCHAR(100),
    guidance_type VARCHAR(100),
    
    -- Processing metadata
    processing_status VARCHAR(20) DEFAULT 'pending',
    processed_at TIMESTAMP,
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE document_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- File metadata
    filename VARCHAR(255) NOT NULL,
    original_url VARCHAR(500) NOT NULL,
    content_type VARCHAR(100),
    
    -- Download info
    local_path VARCHAR(500),
    pdf_content BYTEA,
    checksum VARCHAR(64),
    size_bytes INTEGER,
    
    -- Processing status
    download_status VARCHAR(20) DEFAULT 'pending',
    downloaded_at TIMESTAMP,
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_documents_url ON documents(document_url);
CREATE INDEX idx_documents_session ON documents(crawl_session_id);
CREATE INDEX idx_documents_status ON documents(processing_status);
CREATE INDEX idx_attachments_document ON document_attachments(document_id);
CREATE INDEX idx_attachments_status ON document_attachments(download_status);

-- Success message
SELECT 'Database reset complete - ready for fresh crawl!' as message;
EOF

# Execute the reset
psql "$DATABASE_URL" -f /tmp/reset_db.sql

# Clean up
rm /tmp/reset_db.sql

echo "✅ Database completely reset - all previous data removed"
echo "🚀 You can now run the crawler to start fresh:"
echo "   docker-compose up -d"
echo ""
echo "💡 Note: For normal operation (preserving data), just use 'docker-compose up -d'"
