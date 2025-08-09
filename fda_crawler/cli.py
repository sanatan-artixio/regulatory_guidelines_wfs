"""Typer CLI interface for FDA crawler"""
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlalchemy import select

from .crawler import FDACrawler
from .config import settings
from .models import Document

app = typer.Typer(help="FDA Guidance Documents Harvester - Lean Implementation")
console = Console()


@app.command()
def init(
    database_url: Optional[str] = typer.Option(
        None, 
        "--database-url", 
        help="PostgreSQL database URL (uses config default if not provided)"
    )
):
    """Initialize database schema"""
    async def _init():
        if database_url:
            # Temporarily override database URL
            original_url = settings.database_url
            settings.database_url = database_url
            
        async with FDACrawler() as crawler:
            await crawler.init_database()
            console.print("✅ Database initialized successfully", style="green")
            
        if database_url:
            settings.database_url = original_url
            
    asyncio.run(_init())


@app.command()
def crawl(
    test_limit: Optional[int] = typer.Option(
        None, 
        "--test-limit", 
        help="Limit number of documents for testing (default: crawl all)"
    ),
    max_concurrency: Optional[int] = typer.Option(
        None, 
        "--max-concurrency", 
        help="Maximum concurrent requests"
    ),
    rate_limit: Optional[float] = typer.Option(
        None, 
        "--rate-limit", 
        help="Requests per second rate limit"
    )
):
    """Start a new crawl session"""
    async def _crawl():
        # Override settings if provided
        if max_concurrency:
            settings.max_concurrency = max_concurrency
        if rate_limit:
            settings.rate_limit = rate_limit
            
        console.print("🚀 Starting FDA guidance documents crawl...", style="blue")
        
        if test_limit:
            console.print(f"📝 Test mode: limiting to {test_limit} documents", style="yellow")
            
        async with FDACrawler() as crawler:
            try:
                session_id = await crawler.crawl(test_limit=test_limit)
                console.print(f"✅ Crawl completed successfully!", style="green")
                console.print(f"📋 Session ID: {session_id}")
                
                # Show final status
                status = await crawler.get_session_status(session_id)
                if status:
                    _display_status(status)
                    
            except Exception as e:
                console.print(f"❌ Crawl failed: {e}", style="red")
                raise typer.Exit(1)
                
    asyncio.run(_crawl())


@app.command()
def resume(
    session_id: str = typer.Argument(help="Crawl session ID to resume")
):
    """Resume an interrupted crawl session"""
    async def _resume():
        console.print(f"🔄 Resuming crawl session: {session_id}", style="blue")
        
        async with FDACrawler() as crawler:
            try:
                completed_session_id = await crawler.crawl(resume_session_id=session_id)
                console.print(f"✅ Crawl resumed and completed successfully!", style="green")
                
                # Show final status
                status = await crawler.get_session_status(completed_session_id)
                if status:
                    _display_status(status)
                    
            except Exception as e:
                console.print(f"❌ Resume failed: {e}", style="red")
                raise typer.Exit(1)
                
    asyncio.run(_resume())


@app.command()
def status(
    session_id: str = typer.Argument(help="Crawl session ID to check")
):
    """Check status of a crawl session"""
    async def _status():
        async with FDACrawler() as crawler:
            status = await crawler.get_session_status(session_id)
            
            if not status:
                console.print(f"❌ Session {session_id} not found", style="red")
                raise typer.Exit(1)
                
            _display_status(status)
            
    asyncio.run(_status())


@app.command()
def test(
    limit: int = typer.Option(5, "--limit", help="Number of documents to test with")
):
    """Test crawl with limited number of documents"""
    console.print(f"🧪 Testing crawler with {limit} documents...", style="cyan")
    
    async def _test():
        async with FDACrawler() as crawler:
            try:
                # Initialize database first
                await crawler.init_database()
                console.print("📋 Database initialized", style="green")
                
                # Run test crawl
                session_id = await crawler.crawl(test_limit=limit)
                console.print(f"✅ Test crawl completed!", style="green")
                console.print(f"📋 Session ID: {session_id}")
                
                # Show results
                status = await crawler.get_session_status(session_id)
                if status:
                    _display_status(status)
                    
            except Exception as e:
                console.print(f"❌ Test failed: {e}", style="red")
                raise typer.Exit(1)
                
    asyncio.run(_test())


def _display_status(status: dict):
    """Display crawl session status in a nice table"""
    table = Table(title=f"Crawl Session Status: {status['session_id']}")
    
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    # Format status with emoji
    status_emoji = {
        "running": "🟡",
        "completed": "✅", 
        "failed": "❌",
        "paused": "⏸️"
    }
    
    status_display = f"{status_emoji.get(status['status'], '❓')} {status['status'].title()}"
    
    table.add_row("Status", status_display)
    table.add_row("Started", str(status['started_at']) if status['started_at'] else "N/A")
    table.add_row("Completed", str(status['completed_at']) if status['completed_at'] else "N/A")
    
    if status['total_documents']:
        progress = f"{status['processed_documents']}/{status['total_documents']}"
        percentage = f"({status['processed_documents']/status['total_documents']*100:.1f}%)"
        table.add_row("Progress", f"{progress} {percentage}")
    else:
        table.add_row("Processed", str(status['processed_documents']))
        
    table.add_row("Successful Downloads", str(status['successful_downloads']))
    table.add_row("Failed Documents", str(status['failed_documents']))
    
    if status['error_count'] > 0:
        table.add_row("Errors", str(status['error_count']))
        if status['last_error']:
            table.add_row("Last Error", status['last_error'][:100] + "..." if len(status['last_error']) > 100 else status['last_error'])
    
    console.print(table)


@app.command()
def config():
    """Show current configuration"""
    table = Table(title="FDA Crawler Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Database URL", settings.database_url)
    table.add_row("PDF Root", str(settings.pdf_root))
    table.add_row("Max Concurrency", str(settings.max_concurrency))
    table.add_row("Rate Limit", f"{settings.rate_limit} req/sec")
    table.add_row("User Agent", settings.user_agent)
    table.add_row("Schema Name", settings.schema_name)
    table.add_row("Connect Timeout", f"{settings.connect_timeout}s")
    table.add_row("Read Timeout", f"{settings.read_timeout}s")
    table.add_row("Max Retries", str(settings.max_retries))
    
    if settings.test_limit:
        table.add_row("Test Limit", str(settings.test_limit))
    
    console.print(table)


@app.command()
def export_pdfs(
    output_dir: str = typer.Option("./exported_pdfs", "--output-dir", help="Directory to export PDFs to"),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Export PDFs from specific session only")
):
    """Export PDFs from database to files"""
    async def _export():
        from pathlib import Path
        from .models import DocumentAttachment, CrawlSession
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        async with FDACrawler() as crawler:
            async with crawler.async_session() as session:
                # Build query
                query = select(DocumentAttachment).where(
                    DocumentAttachment.download_status == "completed",
                    DocumentAttachment.pdf_content.isnot(None)
                )
                
                if session_id:
                    query = query.join(Document).where(Document.crawl_session_id == session_id)
                
                result = await session.execute(query)
                attachments = result.scalars().all()
                
                console.print(f"📁 Exporting {len(attachments)} PDFs to {output_path}")
                
                exported = 0
                for attachment in attachments:
                    try:
                        file_path = output_path / attachment.filename
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(file_path, 'wb') as f:
                            f.write(attachment.pdf_content)
                        
                        exported += 1
                        console.print(f"✅ Exported: {attachment.filename}")
                        
                    except Exception as e:
                        console.print(f"❌ Failed to export {attachment.filename}: {e}", style="red")
                
                console.print(f"🎉 Successfully exported {exported}/{len(attachments)} PDFs")
    
    asyncio.run(_export())


@app.command()
def test_browser():
    """Test browser automation in isolation to debug cloud deployment issues"""
    async def _test_browser():
        console.print("🧪 Testing browser automation...")
        
        try:
            async with FDACrawler() as crawler:
                # Test just the browser automation part
                documents = await crawler.get_listing_data_with_browser(limit=1)
                
                if documents:
                    console.print(f"✅ Browser automation successful! Found {len(documents)} documents")
                    for doc in documents[:3]:  # Show first 3
                        console.print(f"  📄 {doc.get('title', 'No title')}")
                else:
                    console.print("⚠️ Browser automation returned no documents")
                    
        except Exception as e:
            console.print(f"❌ Browser automation failed: {e}", style="red")
            import traceback
            console.print(f"📋 Full traceback:\n{traceback.format_exc()}", style="dim")
    
    asyncio.run(_test_browser())


@app.command()
def test_page_content():
    """Test what content we're actually getting from the FDA page"""
    async def _test_content():
        from playwright.async_api import async_playwright
        from fda_crawler.config import settings
        
        console.print("🧪 Testing FDA page content retrieval...")
        
        async with async_playwright() as p:
            browser_args = [
                '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
                '--disable-gpu', '--single-process'
            ]
            
            browser = await p.chromium.launch(headless=settings.browser_headless, args=browser_args)
            page = await browser.new_page()
            
            # Set realistic headers
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            try:
                console.print("📄 Loading FDA page...")
                await page.goto("https://www.fda.gov/regulatory-information/search-fda-guidance-documents", 
                               timeout=60000, wait_until="networkidle")
                
                # Get basic page info
                title = await page.title()
                url = page.url
                content = await page.content()
                
                console.print(f"📄 Page Title: {title}")
                console.print(f"🔗 Page URL: {url}")
                console.print(f"📝 Content Length: {len(content)} characters")
                
                # Check for key content
                if 'guidance' in content.lower():
                    console.print("✅ 'guidance' text found in content")
                else:
                    console.print("❌ 'guidance' text NOT found")
                    
                if 'entries' in content.lower():
                    console.print("✅ 'entries' text found in content")
                else:
                    console.print("❌ 'entries' text NOT found")
                
                # Count elements
                all_elements = await page.query_selector_all('*')
                tables = await page.query_selector_all('table')
                scripts = await page.query_selector_all('script')
                
                console.print(f"🔍 Total elements: {len(all_elements)}")
                console.print(f"📊 Tables: {len(tables)}")
                console.print(f"📜 Scripts: {len(scripts)}")
                
                # Show first 500 chars of content for debugging
                console.print(f"\n📋 First 500 characters of content:")
                console.print(content[:500])
                
            except Exception as e:
                console.print(f"❌ Error: {e}", style="red")
            finally:
                await browser.close()
    
    asyncio.run(_test_content())


if __name__ == "__main__":
    app()
