# FDA Guidance Documents Harvester - Docker Image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg2 \
    software-properties-common \
    htop \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright system dependencies (requires root)
RUN playwright install-deps chromium

# Copy application code
COPY fda_crawler/ ./fda_crawler/
COPY migrate.sql .
COPY setup.py .

# Install the package in development mode
RUN pip install -e .

# Copy entrypoint script
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash crawler
RUN chown -R crawler:crawler /app

# Switch to non-root user
USER crawler

# Install Playwright browsers as the crawler user
RUN playwright install chromium

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["crawl"]
