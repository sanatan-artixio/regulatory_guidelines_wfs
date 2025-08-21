"""Simple CLI interface for FDA crawler"""
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from .crawler import FDACrawler
from .config import settings

app = typer.Typer(help="FDA Guidance Documents Harvester - Simple Implementation")
console = Console()


@app.command()
def init():
    """Initialize database schema"""
    async def _init():
        async with FDACrawler() as crawler:
            await crawler.init_database()
            console.print("✅ Database initialized successfully")
    
    asyncio.run(_init())


@app.command()
def crawl(
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of documents for testing"),
    concurrency: int = typer.Option(4, "--concurrency", help="Max concurrent requests"),
    rate_limit: float = typer.Option(1.0, "--rate-limit", help="Requests per second")
):
    """Run the full crawl process"""
    async def _crawl():
        # Override settings if provided
        if concurrency != 4:
            settings.max_concurrency = concurrency
        if rate_limit != 1.0:
            settings.rate_limit = rate_limit
        
        async with FDACrawler() as crawler:
            session_id = await crawler.crawl(test_limit=limit)
            console.print(f"✅ Crawl completed. Session ID: {session_id}")
    
    asyncio.run(_crawl())


@app.command()
def resume(session_id: str):
    """Resume an interrupted crawl session"""
    async def _resume():
        async with FDACrawler() as crawler:
            resumed_session_id = await crawler.crawl(resume_session_id=session_id)
            console.print(f"✅ Session resumed. Session ID: {resumed_session_id}")
    
    asyncio.run(_resume())


@app.command()
def status(session_id: str):
    """Check the status of a crawl session"""
    async def _status():
        async with FDACrawler() as crawler:
            status_data = await crawler.get_session_status(session_id)
            if not status_data:
                console.print(f"❌ Session {session_id} not found")
                return
            
            table = Table(title=f"Session {session_id} Status")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Status", status_data['status'])
            table.add_row("Started At", status_data['started_at'] or 'N/A')
            table.add_row("Completed At", status_data['completed_at'] or 'N/A')
            table.add_row("Processed Documents", str(status_data['processed_documents']))
            table.add_row("Successful Downloads", str(status_data['successful_downloads']))
            table.add_row("Failed Documents", str(status_data['failed_documents']))
            table.add_row("Error Count", str(status_data['error_count']))
            
            console.print(table)
    
    asyncio.run(_status())


@app.command()
def test(limit: int = 5):
    """Quick test run with limited documents"""
    console.print(f"🧪 Running test crawl with {limit} documents...")
    
    async def _test():
        async with FDACrawler() as crawler:
            session_id = await crawler.crawl(test_limit=limit)
            console.print(f"✅ Test completed. Session ID: {session_id}")
            
            # Show results
            status_data = await crawler.get_session_status(session_id)
            console.print(f"📊 Processed {status_data['processed_documents']} documents")
            console.print(f"📁 Downloaded {status_data['successful_downloads']} PDFs")
    
    asyncio.run(_test())


if __name__ == "__main__":
    app()
