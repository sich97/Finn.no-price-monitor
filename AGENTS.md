# Finn.no Price Monitor - Developer Guide

A Python script that monitors Finn.no listing prices across realestate, mobility, and recommerce categories. The script runs statelessly, checks all configured URLs, compares against historical data, and sends email alerts on price changes.

## Build/Lint/Test Commands

```bash
# Basic import check (no network calls made)
python price_fetcher.py

# Full execution with web scraping and email alerts
python price_fetcher.py --run

# Run all tests
pytest test_*.py -v

# Run single test by name
pytest test_price_fetcher.py::test_extract_price -v

# Lint code
flake8 price_fetcher.py --max-line-length=100

# Type check
mypy price_fetcher.py --strict

# Format code (if black installed)
black price_fetcher.py --line-length=100
```

## Code Style Guidelines

### Formatting
- PEP8 compliance (max line length: 100 characters)
- Black formatter preferred with --line-length=100
- 4 spaces for indentation, no tabs
- One import per line for clarity

### Naming Conventions
- Constants: `UPPER_SNAKE_CASE` (e.g., `HISTORY_FILE`, `SMTP_HOST`)
- Functions/variables: `snake_case` (e.g., `fetch_price`, `price_history`)
- Classes: `CamelCase` (e.g., `PriceFetcher`)
- Private functions: leading underscore `_internal_func`

### Type Hints
- All function parameters and return types must be annotated
- Use `Optional[Type]` for nullable values
- Use `Union[Type1, Type2]` for multiple possible types
- Use `List[T]`, `Dict[K, V]`, `Tuple[T, ...]` for collections

### Imports
Order: standard library → third-party → local modules. Alphabetical within each group.

```python
import json
import os
import re  # stdlib alphabetical

import requests  # third-party
from bs4 import BeautifulSoup
```

### Error Handling
- Use `try/except` blocks for external operations (HTTP, file I/O, parsing)
- Log errors with print() for visibility but continue execution when processing multiple URLs
- Never crash on a single failing URL
- Use specific exception types, avoid bare `except:`

## Project Plan

### ✅ Implemented Features
- [x] URL reading from newline-separated text file (`urls.txt`)
- [x] Price extraction for all 3 Finn.no categories:
  - Realestate (homes/finnkode=): extracts "Totalpris" via data-testid='pricing-total-price'
  - Mobility (mobility/item/): extracts "Totalpris" from label + next sibling span.t2
  - Recommerce (recommerce/forsale/item/): extracts "Til salgs" price via regex on raw HTML
- [x] JSON price history storage with ISO8601 timestamps at `price_history.json`
- [x] Price change detection by comparing current vs last stored price
- [x] SMTP email alerts on price changes with TLS encryption
- [x] Environment variable configuration (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, EMAIL_TO)
- [x] Config file fallback (`config.env`) when env vars not set
- [x] Per-URL error handling - continues processing other URLs if one fails
- [x] Stateless design - no runtime state, script reads, processes, exits

### 🔄 Development Roadmap
Future enhancements (not yet implemented):
- Multi-item per listing support (some recommerce has multiple items)
- SMS notifications via Twilio integration
- Web dashboard for price visualization
- Docker containerization for easier deployment
- Support for additional Norwegian marketplaces (e.g., Finn.no jobbsøk)

### 📋 File Structure
| File | Purpose |
|------|---------|
| `price_fetcher.py` | Main monitoring script with category-specific parsers |
| `urls.txt` | Newline-separated Finn.no listing URLs to monitor |
| `price_history.json` | Historical price records with ISO timestamps |
| `AGENTS.md` | This developer documentation |

### Configuration
Environment variables take precedence over config file. Required settings:
- `SMTP_HOST`: Mail server hostname (e.g., smtp.gmail.com)
- `SMTP_PORT`: Mail server port (typically 587 for TLS, 465 for SSL)
- `SMTP_USER`: Username for authentication
- `SMTP_PASS`: Password for authentication
- `EMAIL_FROM`: Sender address for alerts
- `EMAIL_TO`: Recipient address for alerts (comma-separated for multiple)

Config file example (`config.env`):
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
EMAIL_FROM=alerts@gmail.com
EMAIL_TO=recipient@example.com
```

### Price History Format
```json
{
  "https://www.finn.no/realestate/homes/ad.html?finnkode=426213000": [
    "5 434 496 kr",
    "2026-02-06T18:05:12.592857+00:00",
    "5 400 000 kr",
    "2026-02-07T18:05:12.123456+00:00"
  ],
  "https://www.finn.no/mobility/item/447730470": [
    "59 990 kr",
    "2026-02-06T18:05:12.837047+00:00"
  ]
}
```

## Testing Strategy

Since Finn.no is a live site with changing content, tests should:
1. Mock HTTP responses for unit tests
2. Use test fixtures from saved HTML for parser tests
3. Run minimal integration tests with `--run` flag on demand only

### Local Development
```bash
cd /a0/usr/projects/finn_no_price_monitor
source venv/bin/activate  # if using venv
python price_fetcher.py --run
```

## Cron/Scheduling Example

Run every 4 hours via cron:
```bash
0 */4 * * * cd /a0/usr/projects/finn_no_price_monitor && /usr/bin/python3 price_fetcher.py --run >> /var/log/price_monitor.log 2>&1
```

## Docker Deployment

The project is fully containerized with Docker support.

### Docker Build
```bash
# Build the image
docker build -t finn-price-monitor .
```

### Docker Run (Manual Execution)
```bash
# Create .env file from example
cp .env.example .env
# Edit .env with your SMTP credentials

# Create data directory for persistence
mkdir -p data

# Run once with --run flag
docker run --rm \
  -v $(pwd)/data:/data \
  --env-file .env \
  finn-price-monitor --run
```

### Docker Compose (Recommended)
```bash
# Simple execution (run once)
docker-compose up price-monitor

# With cron scheduler (runs every 4 hours)
docker-compose --profile cron up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f price-monitor
```

### Docker File Structure
| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.11 slim-based image with requests, beautifulsoup4 |
| `docker-compose.yml` | Service definition with volume mounts and ofelia scheduler |
| `.dockerignore` | Excludes venv, .git, data/, .env from build context |
| `data/` | Persistent volume for price_history.json |

### Environment Variables
All configuration is loaded from environment variables (Docker sets these from .env):
- `DATA_DIR=/data` - Where history file is stored (container internal path)
- `SMTP_*` - Email configuration

### Cron Scheduling Options

**Option 1: Docker Compose with ofelia (built-in)**
```bash
docker-compose --profile cron up -d
```
This runs the container every 4 hours using the ofelia cron scheduler.

**Option 2: External system cron**
Add to host's crontab:
```bash
0 */4 * * * cd /path/to/project && docker-compose up price-monitor >> /var/log/price_monitor.log 2>&1
```

**Option 3: Kubernetes CronJob**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: finn-price-monitor
spec:
  schedule: "0 */4 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: monitor
            image: finn-price-monitor:latest
            args: ["--run"]
            envFrom:
            - configMapRef:
                name: finn-monitor-config
            volumeMounts:
            - name: data
              mountPath: /data
          restartPolicy: OnFailure
```
