"""Setup script for FDA Crawler"""
from setuptools import setup, find_packages

setup(
    name="fda-crawler",
    version="1.0.0",
    description="FDA Guidance Documents Harvester - Lean Implementation",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.25.0",
        "beautifulsoup4>=4.12.0", 
        "lxml>=4.9.0",
        "sqlalchemy>=2.0.0",
        "asyncpg>=0.29.0",
        "typer>=0.9.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0"
    ],
    entry_points={
        "console_scripts": [
            "fda-crawler=fda_crawler.cli:app",
        ],
    },
    python_requires=">=3.8",
)
