-- Database migration script for FDA data processing pipeline
-- This adds processing tables to the existing source schema

-- Ensure source schema exists (should already exist from crawler)
CREATE SCHEMA IF NOT EXISTS source;

-- Processing sessions table
CREATE TABLE IF NOT EXISTS source.processing_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    
    -- Processing configuration
    product_type VARCHAR(50) NOT NULL,
    total_documents INTEGER,
    processed_documents INTEGER NOT NULL DEFAULT 0,
    failed_documents INTEGER NOT NULL DEFAULT 0,
    configuration JSONB,
    
    -- Error tracking
    last_error TEXT,
    error_count INTEGER NOT NULL DEFAULT 0
);

-- Document features table
CREATE TABLE IF NOT EXISTS source.document_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id UUID NOT NULL, -- References source.documents.id
    processing_session_id UUID NOT NULL REFERENCES source.processing_sessions(id),
    
    -- Processing metadata
    product_type VARCHAR(50) NOT NULL,
    extracted_text TEXT,
    features JSONB NOT NULL,
    confidence_score FLOAT,
    processing_metadata JSONB,
    
    -- Status tracking
    processing_status VARCHAR(20) NOT NULL DEFAULT 'completed',
    processing_error TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Processing logs table
CREATE TABLE IF NOT EXISTS source.processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processing_session_id UUID NOT NULL REFERENCES source.processing_sessions(id),
    document_id UUID, -- Optional reference to source document
    
    -- Log details
    level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    error_details JSONB,
    
    -- Timestamp
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_processing_sessions_status 
    ON source.processing_sessions(status);

CREATE INDEX IF NOT EXISTS idx_processing_sessions_product_type 
    ON source.processing_sessions(product_type);

CREATE INDEX IF NOT EXISTS idx_document_features_source_id 
    ON source.document_features(source_document_id);

CREATE INDEX IF NOT EXISTS idx_document_features_session_id 
    ON source.document_features(processing_session_id);

CREATE INDEX IF NOT EXISTS idx_document_features_product_type 
    ON source.document_features(product_type);

CREATE INDEX IF NOT EXISTS idx_document_features_confidence 
    ON source.document_features(confidence_score);

-- GIN index for JSONB features column for efficient querying
CREATE INDEX IF NOT EXISTS idx_document_features_features_gin 
    ON source.document_features USING GIN(features);

CREATE INDEX IF NOT EXISTS idx_processing_logs_session_id 
    ON source.processing_logs(processing_session_id);

CREATE INDEX IF NOT EXISTS idx_processing_logs_level 
    ON source.processing_logs(level);

CREATE INDEX IF NOT EXISTS idx_processing_logs_created_at 
    ON source.processing_logs(created_at);

-- Create updated_at trigger for document_features
CREATE OR REPLACE FUNCTION source.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_document_features_updated_at 
    BEFORE UPDATE ON source.document_features 
    FOR EACH ROW EXECUTE FUNCTION source.update_updated_at_column();

-- Create useful views for querying

-- View for session summary
CREATE OR REPLACE VIEW source.session_summary AS
SELECT 
    ps.id,
    ps.status,
    ps.product_type,
    ps.started_at,
    ps.completed_at,
    ps.total_documents,
    ps.processed_documents,
    ps.failed_documents,
    CASE 
        WHEN ps.total_documents > 0 THEN 
            ROUND((ps.processed_documents::FLOAT / ps.total_documents::FLOAT) * 100, 2)
        ELSE 0 
    END as progress_percentage,
    ps.error_count,
    ps.last_error,
    EXTRACT(EPOCH FROM (COALESCE(ps.completed_at, NOW()) - ps.started_at)) as duration_seconds
FROM source.processing_sessions ps;

-- View for document features with extracted key information
CREATE OR REPLACE VIEW source.document_features_summary AS
SELECT 
    df.id,
    df.source_document_id,
    df.processing_session_id,
    df.product_type,
    df.confidence_score,
    df.processing_status,
    df.created_at,
    
    -- Extract key features from JSON
    df.features->>'device_classification' as device_classification,
    df.features->>'device_type' as device_type,
    df.features->>'regulatory_pathway' as regulatory_pathway,
    df.features->>'intended_use' as intended_use,
    df.features->>'product_code' as product_code,
    
    -- Array fields lengths
    COALESCE(jsonb_array_length(df.features->'standards_referenced'), 0) as standards_count,
    COALESCE(jsonb_array_length(df.features->'testing_requirements'), 0) as testing_requirements_count,
    COALESCE(jsonb_array_length(df.features->'submission_requirements'), 0) as submission_requirements_count,
    
    -- Text length
    LENGTH(df.extracted_text) as extracted_text_length
FROM source.document_features df;

-- View for processing statistics
CREATE OR REPLACE VIEW source.processing_stats AS
SELECT 
    product_type,
    COUNT(*) as total_sessions,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_sessions,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_sessions,
    COUNT(*) FILTER (WHERE status = 'running') as running_sessions,
    SUM(processed_documents) as total_processed_documents,
    SUM(failed_documents) as total_failed_documents,
    AVG(confidence_score) as avg_confidence_score
FROM source.processing_sessions ps
LEFT JOIN source.document_features df ON ps.id = df.processing_session_id
GROUP BY product_type;

-- Grant permissions (adjust as needed for your setup)
-- GRANT USAGE ON SCHEMA processed TO your_application_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA processed TO your_application_user;
-- GRANT SELECT ON ALL TABLES IN SCHEMA source TO your_application_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA processed TO your_application_user;
