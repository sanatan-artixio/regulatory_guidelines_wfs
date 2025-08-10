-- Database migration: Add sidebar metadata columns
-- This migration adds new columns to capture regulated products and topics from FDA document sidebars

-- Set search path
SET search_path TO source;

-- Add new columns to documents table for enhanced metadata extraction
-- These columns will store data from the FDA document detail page sidebars

-- Add regulated_products column (JSON array stored as TEXT)
-- Example: ["Biologics", "Medical Devices"]
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'source' 
        AND table_name = 'documents' 
        AND column_name = 'regulated_products'
    ) THEN
        ALTER TABLE documents ADD COLUMN regulated_products TEXT;
        COMMENT ON COLUMN documents.regulated_products IS 'JSON array of regulated products (e.g., ["Biologics", "Medical Devices"])';
    END IF;
END $$;

-- Add topics column (JSON array stored as TEXT) 
-- Note: This is different from the existing 'topic' column which stores a single topic
-- Example: ["User Fees", "Administrative / Procedural"]
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'source' 
        AND table_name = 'documents' 
        AND column_name = 'topics'
    ) THEN
        ALTER TABLE documents ADD COLUMN topics TEXT;
        COMMENT ON COLUMN documents.topics IS 'JSON array of topics from sidebar (e.g., ["User Fees", "Administrative / Procedural"])';
    END IF;
END $$;

-- Add content_current_date column
-- Example: "07/30/2025"
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'source' 
        AND table_name = 'documents' 
        AND column_name = 'content_current_date'
    ) THEN
        ALTER TABLE documents ADD COLUMN content_current_date VARCHAR(50);
        COMMENT ON COLUMN documents.content_current_date IS 'Content current as of date from sidebar';
    END IF;
END $$;

-- Create indexes for the new columns to improve query performance
CREATE INDEX IF NOT EXISTS idx_documents_regulated_products ON documents USING GIN ((regulated_products::jsonb));
CREATE INDEX IF NOT EXISTS idx_documents_topics ON documents USING GIN ((topics::jsonb));
CREATE INDEX IF NOT EXISTS idx_documents_content_date ON documents(content_current_date);

-- Add comments explaining the difference between old and new topic fields
COMMENT ON COLUMN documents.topic IS 'Legacy single topic field (kept for backward compatibility)';
COMMENT ON COLUMN documents.topics IS 'New JSON array of topics extracted from document sidebar';

PRINT 'Migration completed: Added regulated_products, topics, and content_current_date columns to documents table';
