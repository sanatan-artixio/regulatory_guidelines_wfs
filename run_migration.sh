#!/bin/bash
# FDA Crawler Database Migration Runner
# This script applies database migrations safely

set -e

echo "🔄 FDA Crawler Database Migration Runner"
echo "========================================"

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is required"
    echo "   Example: DATABASE_URL='postgresql://sanatanupmanyu:ksDq2jazKmxxzv.VxXbkwR6Uxz@host.docker.internal:5432/quriousri_db'"
    exit 1
fi

echo "📊 Database URL: ${DATABASE_URL}"
echo ""

# Function to run a SQL file
run_sql_file() {
    local file=$1
    local description=$2
    
    echo "🔧 Running: $description"
    echo "   File: $file"
    
    if [ ! -f "$file" ]; then
        echo "❌ ERROR: Migration file not found: $file"
        exit 1
    fi
    
    # Run the SQL file
    psql "$DATABASE_URL" -f "$file"
    
    if [ $? -eq 0 ]; then
        echo "✅ SUCCESS: $description completed"
    else
        echo "❌ ERROR: $description failed"
        exit 1
    fi
    echo ""
}

# Show available migration options
echo "Available migration options:"
echo "1. Fresh installation (migrate.sql) - Creates all tables from scratch"
echo "2. Add sidebar metadata (migrate_add_sidebar_metadata.sql) - Adds new columns to existing tables"
echo "3. Complete reset (init-db.sh) - ⚠️  DESTROYS ALL DATA and recreates tables"
echo ""

read -p "Which migration would you like to run? (1/2/3): " choice

case $choice in
    1)
        echo "🚀 Running fresh installation migration..."
        run_sql_file "migrate.sql" "Fresh database installation"
        echo "🎉 Fresh installation complete!"
        ;;
    2)
        echo "🔄 Running sidebar metadata migration..."
        run_sql_file "migrate_add_sidebar_metadata.sql" "Add sidebar metadata columns"
        echo "🎉 Sidebar metadata migration complete!"
        echo "   New columns added:"
        echo "   - regulated_products (JSON array of regulated products)"
        echo "   - topics (JSON array of topics from sidebar)"
        echo "   - content_current_date (content current as of date)"
        ;;
    3)
        echo "⚠️  WARNING: This will DESTROY ALL EXISTING DATA!"
        read -p "Are you absolutely sure? Type 'DELETE_ALL_DATA' to confirm: " confirm
        if [ "$confirm" = "DELETE_ALL_DATA" ]; then
            echo "🗑️  Running complete database reset..."
            bash init-db.sh
            echo "🎉 Complete database reset complete!"
        else
            echo "❌ Reset cancelled - confirmation text did not match"
            exit 1
        fi
        ;;
    *)
        echo "❌ Invalid choice. Please select 1, 2, or 3."
        exit 1
        ;;
esac

echo ""
echo "✅ Migration completed successfully!"
echo "   You can now run the FDA crawler with the updated schema."
