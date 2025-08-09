#!/bin/bash
# FDA Guidance Documents Harvester - Database Initialization Script
# Run this script ONLY for initial database setup or if you need to reset the database

set -e

echo "⚠️  WARNING: This script will DROP ALL EXISTING DATA!"
echo "   This should only be used for:"
echo "   - Initial database setup"
echo "   - Development/testing database reset"
echo "   - When you want to completely start over"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Database initialization cancelled"
    exit 1
fi

echo "🗑️  Dropping existing tables..."
echo "🔧 Recreating database schema..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

# Run the migration script with DROP statements
psql "$DATABASE_URL" -f migrate-fresh.sql

echo "✅ Database initialized with fresh schema"
echo "🚀 You can now run the crawler to populate data"
