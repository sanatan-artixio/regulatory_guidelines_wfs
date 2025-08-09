-- Database migration script for FDA Crawler
-- Create schema and tables

-- Create source schema
CREATE SCHEMA IF NOT EXISTS source;

-- Set search path
SET search_path TO source;

-- Create crawl_sessions table
CREATE TABLE IF NOT EXISTS crawl_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    
    -- Progress tracking
    total_documents INTEGER,
    processed_documents INTEGER NOT NULL DEFAULT 0,
    successful_downloads INTEGER NOT NULL DEFAULT 0,
    failed_documents INTEGER NOT NULL DEFAULT 0,
    
    -- Settings used for this session
    max_concurrency INTEGER NOT NULL,
    rate_limit FLOAT NOT NULL,
    test_limit INTEGER,
    
    -- Error tracking
    last_error TEXT,
    error_count INTEGER NOT NULL DEFAULT 0
);

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_session_id UUID NOT NULL REFERENCES crawl_sessions(id),
    
    -- Core metadata
    document_url VARCHAR(500) NOT NULL UNIQUE,
    title TEXT,
    summary TEXT,
    issue_date VARCHAR(50),
    fda_organization VARCHAR(200),
    topic VARCHAR(200),
    guidance_status VARCHAR(100),
    open_for_comment BOOLEAN,
    comment_closing_date VARCHAR(50),
    docket_number VARCHAR(100),
    guidance_type VARCHAR(100),
    
    -- Processing status
    processed_at TIMESTAMP,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    processing_error TEXT,
    
    -- PDF info
    pdf_path VARCHAR(500),
    pdf_checksum VARCHAR(64),
    pdf_size_bytes INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create document_attachments table
CREATE TABLE IF NOT EXISTS document_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Attachment metadata
    filename VARCHAR(255) NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    file_type VARCHAR(20),
    
    -- Download info
    local_path VARCHAR(500),
    checksum VARCHAR(64),
    size_bytes INTEGER,
    
    -- Status
    download_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    download_error TEXT,
    downloaded_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Ensure unique attachment per document
    UNIQUE(document_id, source_url)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_documents_session_id ON documents(crawl_session_id);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(document_url);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_attachments_document_id ON document_attachments(document_id);
CREATE INDEX IF NOT EXISTS idx_attachments_status ON document_attachments(download_status);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON crawl_sessions(status);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for documents table
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at 
    BEFORE UPDATE ON documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON SCHEMA source IS 'FDA Guidance Documents Harvester - Source data schema';
COMMENT ON TABLE crawl_sessions IS 'Track crawl sessions for resume functionality';
COMMENT ON TABLE documents IS 'FDA guidance document metadata';
COMMENT ON TABLE document_attachments IS 'Document attachments (PDFs and other files)';
