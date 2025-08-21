"""Command line interface for the data processing pipeline"""
import asyncio
import logging
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn

from .processor import DataProcessor
from .config import settings

# Setup rich console and logging
console = Console()
app = typer.Typer(name="data-processor", help="FDA Data Processing Pipeline")

# Configure logging with rich
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

logger = logging.getLogger(__name__)


@app.command()
def init():
    """Initialize the database schema for processed data"""
    async def _init():
        async with DataProcessor() as processor:
            await processor.init_database()
            console.print("✅ Database schema initialized", style="green")
    
    asyncio.run(_init())


@app.command()
def process(
    product_type: str = typer.Option(
        "medical devices", 
        "--product-type", "-p",
        help="Product type to process"
    ),
    limit: Optional[int] = typer.Option(
        None, 
        "--limit", "-l",
        help="Maximum number of documents to process (for testing)"
    ),
    resume: Optional[str] = typer.Option(
        None,
        "--resume", "-r", 
        help="Resume processing from existing session ID"
    )
):
    """Process FDA documents to extract structured features"""
    
    async def _process():
        console.print(f"🚀 Starting data processing pipeline", style="bold blue")
        console.print(f"Product type: {product_type}")
        if limit:
            console.print(f"Limit: {limit} documents")
        if resume:
            console.print(f"Resuming session: {resume}")
        
        try:
            async with DataProcessor() as processor:
                session_id = await processor.process_documents(
                    product_type=product_type,
                    limit=limit,
                    resume_session_id=resume
                )
                
                console.print(f"✅ Processing completed!", style="green")
                console.print(f"Session ID: {session_id}")
                
                # Show final status
                status = await processor.get_session_status(session_id)
                if status:
                    _display_session_status(status)
                    
        except Exception as e:
            console.print(f"❌ Processing failed: {e}", style="red")
            logger.error(f"Processing error: {e}")
            raise typer.Exit(1)
    
    asyncio.run(_process())


@app.command()
def status(session_id: str):
    """Check the status of a processing session"""
    
    async def _status():
        try:
            async with DataProcessor() as processor:
                status = await processor.get_session_status(session_id)
                
                if not status:
                    console.print(f"❌ Session {session_id} not found", style="red")
                    raise typer.Exit(1)
                
                _display_session_status(status)
                
        except Exception as e:
            console.print(f"❌ Error getting status: {e}", style="red")
            raise typer.Exit(1)
    
    asyncio.run(_status())


@app.command()
def test(
    components: bool = typer.Option(
        True,
        "--components/--no-components",
        help="Test individual components"
    ),
    api: bool = typer.Option(
        True,
        "--api/--no-api", 
        help="Test LLM API connection"
    )
):
    """Test the processing pipeline components"""
    
    async def _test():
        console.print("🔧 Testing pipeline components...", style="bold yellow")
        
        try:
            async with DataProcessor() as processor:
                if components:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console
                    ) as progress:
                        task = progress.add_task("Testing components...", total=None)
                        
                        results = await processor.test_components()
                        
                        progress.update(task, completed=True)
                    
                    # Display results table
                    table = Table(title="Component Test Results")
                    table.add_column("Component", style="cyan")
                    table.add_column("Status", style="bold")
                    
                    for component, success in results.items():
                        status = "✅ PASS" if success else "❌ FAIL"
                        style = "green" if success else "red"
                        table.add_row(component.replace('_', ' ').title(), status)
                    
                    console.print(table)
                    
                    # Check if all tests passed
                    all_passed = all(results.values())
                    if all_passed:
                        console.print("✅ All tests passed!", style="green")
                    else:
                        console.print("❌ Some tests failed!", style="red")
                        raise typer.Exit(1)
                
        except Exception as e:
            console.print(f"❌ Test failed: {e}", style="red")
            logger.error(f"Test error: {e}")
            raise typer.Exit(1)
    
    asyncio.run(_test())


@app.command()
def config():
    """Show current configuration settings"""
    
    table = Table(title="Configuration Settings")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")
    
    # Database settings
    table.add_row("Database URL", settings.database_url.replace(settings.database_url.split('@')[0].split('//')[1], '***'))
    table.add_row("Source Schema", settings.source_schema)
    table.add_row("Processed Schema", settings.processed_schema)
    
    # Processing settings
    table.add_row("Max Concurrency", str(settings.max_concurrency))
    table.add_row("Batch Size", str(settings.batch_size))
    table.add_row("Rate Limit (req/min)", str(settings.rate_limit_requests_per_minute))
    
    # LLM settings
    table.add_row("OpenAI Model", settings.openai_model)
    table.add_row("Max Tokens", str(settings.openai_max_tokens))
    table.add_row("Temperature", str(settings.openai_temperature))
    
    # PDF settings
    table.add_row("Max PDF Pages", str(settings.max_pdf_pages))
    table.add_row("Max Text Length", str(settings.max_text_length))
    
    console.print(table)


def _display_session_status(status: dict):
    """Display session status in a formatted table"""
    
    table = Table(title=f"Processing Session: {status['id']}")
    table.add_column("Attribute", style="cyan")
    table.add_column("Value", style="yellow")
    
    # Basic info
    table.add_row("Status", status['status'].upper())
    table.add_row("Product Type", status['product_type'])
    table.add_row("Started At", status.get('started_at', 'N/A'))
    table.add_row("Completed At", status.get('completed_at', 'N/A'))
    
    # Progress
    total = status.get('total_documents', 0)
    processed = status.get('processed_documents', 0)
    failed = status.get('failed_documents', 0)
    
    if total:
        progress_pct = (processed / total) * 100
        table.add_row("Progress", f"{processed}/{total} ({progress_pct:.1f}%)")
    else:
        table.add_row("Progress", f"{processed} processed")
    
    table.add_row("Failed Documents", str(failed))
    
    if status.get('last_error'):
        table.add_row("Last Error", status['last_error'])
    
    console.print(table)


if __name__ == "__main__":
    app()
