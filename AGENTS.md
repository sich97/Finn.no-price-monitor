# Finn.no Price Monitor - Developer Guide

A Python script that monitors Finn.no listing prices across realestate, mobility, and recommerce categories. The script runs statelessly, checks all configured URLs, compares against historical data, and sends email alerts on price changes.

**Repository**: https://github.com/sich97/Finn.no-price-monitor.git  
**Validated CI/CD**: https://github.com/sich97/Finn.no-price-monitor/actions

---

## Quick Reference

| Task | Command |
|------|---------|
| Run locally (basic check) | `python price_fetcher.py` |
| Run locally (with scraping) | `python price_fetcher.py --run` |
| Run with Docker | `docker-compose up price-monitor` |
| Build Docker image | `docker build -t finn-price-monitor .` |
| Run tests (GitHub Actions) | Validated on every push |

---

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

---

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

---

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
- [x] **Docker containerization** with persistent volume support
- [x] **GitHub Actions CI/CD** with automated Docker build and test validation
- [x] **GitHub Container Registry (GHCR)** integration

### 🔄 Development Roadmap
Future enhancements (not yet implemented):
- Multi-item per listing support (some recommerce has multiple items)
- SMS notifications via Twilio integration
- Web dashboard for price visualization
- Support for additional Norwegian marketplaces (e.g., Finn.no jobbsøk)
- Kubernetes Helm chart for cluster deployment

---

## File Structure
| File | Purpose |
|------|---------|
| `price_fetcher.py` | Main monitoring script with category-specific parsers |
| `urls.txt` | Newline-separated Finn.no listing URLs to monitor |
| `price_history.json` | Historical price records with ISO timestamps |
| `Dockerfile` | Python 3.11 slim-based container definition |
| `docker-compose.yml` | Service orchestration with volume mounts and optional scheduler |
| `.dockerignore` | Build context exclusions |
| `.env.example` | SMTP configuration template |
| `data/` | Persistent storage for price_history.json (gitignored) |
| `AGENTS.md` | This developer documentation |
| `.github/workflows/docker-test.yml` | CI validation workflow |

---

## Configuration

Environment variables take precedence over config file. Required settings for email alerts:
- `SMTP_HOST`: Mail server hostname (e.g., smtp.gmail.com)
- `SMTP_PORT`: Mail server port (typically 587 for TLS, 465 for SSL)
- `SMTP_USER`: Username for authentication
- `SMTP_PASS`: Password for authentication
- `EMAIL_FROM`: Sender address for alerts
- `EMAIL_TO`: Recipient address for alerts (comma-separated for multiple)
- `DATA_DIR`: Container path for data persistence (default: `/app/`)

Config file example (`config.env`):
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
EMAIL_FROM=alerts@gmail.com
EMAIL_TO=recipient@example.com
DATA_DIR=/data
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

---

## Docker Deployment

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

### Cron Scheduling Options

**Option 1: Docker Compose with ofelia (built-in)**
```bash
docker-compose --profile cron up -d
```

**Option 2: External system cron**
```bash
0 */4 * * * cd /path/to/project && docker-compose up price-monitor >> /var/log/price_monitor.log 2>&1
```

**Option 3: Kubernetes CronJob** (example in AGENTS.md)

---

## CI/CD & Docker Validation

### GitHub Actions Workflow

**File**: `.github/workflows/docker-test.yml`

**Triggers**: Push to main, PRs, workflow_dispatch

**Validation Results** (Run: https://github.com/sich97/Finn.no-price-monitor/actions/runs/21778877607):
| Step | Status |
|------|--------|
| Checkout repository | ✅ success |
| Set up Docker Buildx | ✅ success |
| Build Docker image | ✅ success |
| Test basic import check | ✅ success |
| Test full execution | ✅ success |
| Verify data persistence | ✅ success |
| Upload image artifact | ✅ success |

**Duration**: 28 seconds  
**Artifact**: 50.5 MB tar.gz (retained 7 days)

---

## Public Image Release Plan (Next Agent Task)

**Status**: Research complete, ready for implementation

### Overview
Make the Docker image publicly available via GitHub Container Registry (GHCR) while maintaining **manual control** over which image is considered "stable" (production).

### Registry Selection
| Option | Choice |
|--------|--------|
| Registry | **GHCR** (ghcr.io/sich97/finn-price-monitor) |
| Authentication | Uses GITHUB_TOKEN (no additional secrets) |
| Cost | FREE for public repos |
| Anonymous Pulls | Unlimited, no rate limits |

### Tagging Strategy
| Tag | Purpose | Mutable |
|-----|---------|---------|
| `stable` | Production release (manually controlled) | ✅ Yes |
| `v1.2.3` | Specific version (immutable) | ❌ No |
| `v1.2`, `v1` | Rolling minor/major | ✅ Yes |
| `sha-abc123` | Commit SHA for debugging | ❌ No |
| `main` | Latest development | ✅ Yes |

**Key**: `stable` tag only updates after **manual approval via GitHub Environment Protection**

### Release Process
```
Developer Push → Build SHA+main tags (auto)
     ↓
Git Tag v1.2.3 → Triggers Release Workflow
     ↓
PAUSES for Manual Approval (GitHub UI)
     ↓
You Click "Approve" → Pushes v1.2.3, v1.2, v1, stable
     ↓
Images Signed + SBOM Generated + GitHub Release Created
```

### Implementation Checklist

- [x] Create `.github/workflows/release.yml` (~completed~)
- [ ] Configure GitHub Environment `production`:
  - Settings → Environments → New environment → Name: `production`
  - Required reviewers: yourself
  - Deployment branches: `main`, tags: `v*`
- [ ] Set up branch protection on `main`:
  - Require PR reviews (1)
  - Require status checks
  - Dismiss stale approvals
- [ ] Push changes and test with `git tag v1.0.0 && git push origin v1.0.0`
- [ ] Verify deployment pauses for approval in Actions tab
- [ ] Approve deployment
- [ ] Verify images appear at: https://github.com/users/sich97/packages

### Release Workflow (`.github/workflows/release.yml`)

```yaml
name: Build and Release

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to release (e.g., 1.2.3)'
        required: false

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      attestations: write
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix=sha-
            type=ref,event=branch
            type=ref,event=pr

      - name: Build and push
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: ${{ steps.build.outputs.imageid }}
          format: spdx-json

  release:
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v') || github.event_name == 'workflow_dispatch'
    environment: production  # Triggers approval gate
    permissions:
      contents: write
      packages: write
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract release metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=raw,value=stable

      - name: Build and push release
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

      - name: Install cosign
        uses: sigstore/cosign-installer@v3

      - name: Sign image
        env:
          TAGS: ${{ steps.meta.outputs.tags }}
          DIGEST: ${{ steps.build.outputs.digest }}
        run: |
          images=""
          for tag in ${TAGS}; do
            images+="${tag}@${DIGEST} "
          done
          cosign sign --yes ${images}

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

### User Pull Commands (After Release)

```bash
# Pull stable release (production)
docker pull ghcr.io/sich97/finn-price-monitor:stable

# Pull specific version
docker pull ghcr.io/sich97/finn-price-monitor:v1.0.0

# Verify image signature
cosign verify ghcr.io/sich97/finn-price-monitor:stable \
  --certificate-identity-regexp='^https://github.com/sich97/Finn.no-price-monitor/.github/workflows/.*$' \
  --certificate-oidc-issuer='https://token.actions.githubusercontent.com'
```

### Documentation for Users (Add to README)

```markdown
## Public Docker Image

Images are published to GitHub Container Registry:
`ghcr.io/sich97/finn-price-monitor`

### Image Tags
- `stable` - Latest stable release (recommended for production)
- `v1.2.3` - Specific version (immutable)
- `v1.2`, `v1` - Rolling minor/major versions
- `sha-abc123` - Specific commit (for debugging)
- `main` - Latest development build

### Quick Start
\`\`\`bash
docker run --rm \
  -v $(pwd)/data:/data \
  -e SMTP_HOST=smtp.gmail.com \
  -e SMTP_PORT=587 \
  -e SMTP_USER=user@gmail.com \
  -e SMTP_PASS=password \
  -e EMAIL_FROM=user@gmail.com \
  -e EMAIL_TO=recipient@example.com \
  ghcr.io/sich97/finn-price-monitor:stable --run
\`\`\`
```

---

## Testing Strategy

Since Finn.no is a live site with changing content:
1. Mock HTTP responses for unit tests
2. Use test fixtures from saved HTML for parser tests
3. Run minimal integration tests with `--run` flag on demand only
4. Rely on GitHub Actions for Docker build validation

### Local Development
```bash
cd /a0/usr/projects/finn_no_price_monitor
source venv/bin/activate  # if using venv
python price_fetcher.py --run
```

---

## Cron/Scheduling Example

Run every 4 hours via host cron:
```bash
0 */4 * * * cd /a0/usr/projects/finn_no_price_monitor && /usr/bin/python3 price_fetcher.py --run >> /var/log/price_monitor.log 2>&1
```
