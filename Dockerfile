# FDA Guidance Documents Harvester - Simple Docker Image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY fda_crawler/ ./fda_crawler/
COPY setup.py .

# Install the package in development mode
RUN pip install -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash crawler
RUN chown -R crawler:crawler /app

# Switch to non-root user
USER crawler

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["fda-crawler", "crawl"]
