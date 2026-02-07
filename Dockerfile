FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests beautifulsoup4

# Copy project files
COPY price_fetcher.py .
COPY urls.txt .
COPY AGENTS.md .

# Create data directory for persistent storage
RUN mkdir -p /data

# Set environment variable for data directory
ENV DATA_DIR=/data

# Default entrypoint runs the script
ENTRYPOINT ["python", "price_fetcher.py"]

# Default command shows help, pass --run to execute
CMD ["--run"]
