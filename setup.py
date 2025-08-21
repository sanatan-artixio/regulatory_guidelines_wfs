"""Setup script for FDA Regulatory Guidelines Workflow"""
from setuptools import setup, find_packages

setup(
    name="regulatory-guidelines-wf",
    version="1.0.0",
    description="FDA Regulatory Guidelines Workflow: Crawling and Data Processing",
    packages=find_packages(),
    install_requires=[
        # Core crawler dependencies
        "httpx>=0.25.0",
        "beautifulsoup4>=4.12.0", 
        "lxml>=4.9.0",
        "sqlalchemy>=2.0.0",
        "asyncpg>=0.29.0",
        "typer>=0.9.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
        # Data processing dependencies
        "pdfplumber>=0.10.0",
        "openai>=1.6.0"
    ],
    entry_points={
        "console_scripts": [
            "fda-crawler=fda_crawler.cli:app",
            "data-processor=data_cleaning.cli:app",
        ],
    },
    python_requires=">=3.8",
)
