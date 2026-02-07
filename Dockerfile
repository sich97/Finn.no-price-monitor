FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests beautifulsoup4

# Create data directory for persistent storage
RUN mkdir -p /data

# Copy urls.txt to data directory (where DATA_DIR points)
COPY urls.txt /data/

# Copy other project files to app directory
COPY price_fetcher.py .
COPY AGENTS.md .

# Set environment variable for data directory
ENV DATA_DIR=/data

# Default entrypoint runs the script
ENTRYPOINT ["python", "price_fetcher.py"]

# Default command shows help, pass --run to execute
CMD ["--run"]
