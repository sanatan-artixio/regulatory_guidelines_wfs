# FDA Guidance Documents Harvester - Docker Image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Chrome
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg2 \
    software-properties-common \
    htop \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome based on architecture
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
        apt-get update && \
        apt-get install -y google-chrome-stable && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        apt-get update && \
        apt-get install -y chromium chromium-driver && \
        rm -rf /var/lib/apt/lists/*; \
    fi

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
