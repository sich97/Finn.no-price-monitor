# Finn.no Price Monitor - AGENTS.md

## Project Overview

A Python-based price monitoring service for the Norwegian marketplace Finn.no. The system scrapes prices and titles from three categories of listings (real estate, mobility/motor vehicles, and recommerce/used items), tracks price changes over time, and sends consolidated email alerts when prices change.

**Current Version:** v1.1.2  
**Repository:** https://github.com/sich97/Finn.no-price-monitor  
**Runtime:** Docker container with Python 3.13

---

## History & Major Decisions

### v1.0.0 - v1.0.4 (Initial Development)
- Basic price extraction for realestate and mobility categories
- Individual email notifications per price change
- Price stored as formatted strings ("5 434 496 kr")

### v1.0.5 (Critical Bug Fix)
**Problem:** All price extraction failed due to non-breaking spaces (U+00A0) in HTML  
**Solution:** Implemented `_normalize_price_text()` to convert NBSP to regular spaces before regex matching  
**Status:** Deployed and stable

### v1.1.0 (Major Architecture Update)
**Changes:**
1. **Numeric Price Storage** - Prices now stored as integers (1500) instead of strings ("1 500 kr")
   - Auto-migration of legacy string data on load
   - Enables accurate price comparisons and data analysis

2. **Combined Email Notifications** - Single summary email per run instead of individual alerts
   - HTML table format with title, old price, new price, change indicator (↑↓), and links
   - Sorted by category and change magnitude

3. **Title Extraction** - Listing titles now extracted and stored alongside prices
   - Unified `_parse_title()` method with category-specific CSS selectors

### v1.1.1 (Partial Fix)
Attempted to fix recommerce title extraction by adding `[data-testid="object-title"]` selector.

### v1.1.2 (Complete Fix)
**Problem:** Recommerce titles still missing - BeautifulSoup's `.get_text()` returned empty string even though `.string` contained the title.

**Root Cause:** 
1. Empty `<h1 class="branding">` element matched before correct element
2. BeautifulSoup quirk where `.get_text(strip=True)` returns `""` but `.string` is `"Gaming pc selges"`

**Solution:**
- Put `[data-testid="object-title"]` selector first for all categories
- Added fallback: `if not raw_text: raw_text = str(elem.string).strip() if elem.string else ''`

**Decision:** Use attribute-based selectors (`data-testid`) as primary, with tag-based fallbacks. Handle BeautifulSoup quirks explicitly rather than relying on single extraction method.

---

## Current Architecture / System State

### Core Components

```
price_fetcher.py          # Main entry point and parsing logic
├── FinnNoParser          # HTML parsing class
│   ├── _parse_title()    # Unified title extraction with selectors
│   ├── _parse_*_price()  # Category-specific price extraction
│   └── parse_listing()   # Main parsing orchestrator
├── PriceHistory          # JSON data management with migration
└── EmailNotifier         # SMTP-based alert system

urls.txt                  # Newline-separated listing URLs
price_history.json        # Historical price/title data
debug_dumps/              # HTML snapshots (DEBUG=1)
```

### Data Format

**price_history.json:**
```json
{
  "https://www.finn.no/recommerce/forsale/item/445195639": [
    {
      "price": 1500,
      "title": "Gaming pc selges",
      "timestamp": "2026-02-08T08:57:29.328060+00:00"
    }
  ]
}
```

### Statelessness
The script has no internal runtime state. All data flows through:
1. Input: `urls.txt` + HTTP fetch
2. Processing: Parse HTML → extract price/title
3. Storage: `price_history.json`
4. Output: Email notifications (if prices changed)

### CSS Selector Strategy

**Unified selector dictionary (line 184-186 of price_fetcher.py):**
```python
selectors = {
    'realestate': ['[data-testid="object-title"]', 'h1', 'h1.t1'],
    'mobility': ['[data-testid="object-title"]', 'h1', 'h1.t1'],
    'recommerce': ['[data-testid="object-title"]', 'h1', 'h1.t1']
}
```

**Text extraction with BeautifulSoup quirk handling:**
```python
raw_text = elem.get_text(strip=True)
if not raw_text:
    raw_text = str(elem.string).strip() if elem.string else ''
title = re.sub(r'^(Til salgs|Utleie|Solgt)\s*[-–]?\s*', '', raw_text, flags=re.I)
```

### Environment Configuration

Required environment variables for email alerts (loaded from env or .env file):
- `SMTP_HOST` - Mail server hostname
- `SMTP_PORT` - Mail server port (usually 587)
- `SMTP_USERNAME` - SMTP authentication user
- `SMTP_PASSWORD` - SMTP authentication password
- `EMAIL_FROM` - Sender address
- `EMAIL_TO` - Recipient address(es), comma-separated

Optional:
- `DEBUG=1` - Enable verbose logging and HTML dump generation
- `DATA_DIR` - Data directory path (default: `/data` in Docker, `.` locally)

### Docker Environment

**Key paths:**
- `/data/urls.txt` - URL list
- `/data/price_history.json` - Historical data
- `/data/debug_dumps/` - HTML snapshots (when DEBUG=1)

**Build/lint/test:**
```bash
# Local development
python -m py_compile price_fetcher.py          # Syntax check
DEBUG=1 SMTP_HOST=localhost python price_fetcher.py  # Test run

# Docker
docker compose up --build                       # Local test
docker build -t finn-price-monitor .            # Production build
```

---

## Completed Work

- [x] Price extraction for all three categories (realestate, mobility, recommerce)
- [x] NBSP normalization bug fix (v1.0.5)
- [x] Integer price storage with auto-migration (v1.1.0)
- [x] Combined summary email notifications (v1.1.0)
- [x] Title extraction for all categories (v1.1.2)
- [x] BeautifulSoup quirk handling (v1.1.2)
- [x] Legacy data migration system
- [x] Debug mode with HTML dumping
- [x] Docker containerization
- [x] GitHub Actions CI/CD with cosign signing and SPDX SBOM
- [x] GitHub deploy key configuration

---

## Work In Progress

None - all reported issues resolved.

---

## Known Issues / Limitations

### 1. HTML Structure Dependency
The parsing relies on Finn.no's HTML structure. If Finn.no changes their markup:
- **Symptom:** Price/title extraction fails (returns None)
- **Detection:** Errors in logs, missing data in price_history.json
- **Mitigation:** Enable DEBUG=1, inspect saved HTML in debug_dumps/, update selectors in `_parse_title()` or `_parse_*_price()` methods

### 2. Stateful Data Migration
The auto-migration from string prices to integers happens on load. If you manually edit `price_history.json` with invalid legacy formats, the migration may fail silently.

### 3. Email Sending
Email notifications require valid SMTP credentials. Without them, the script will still run and track prices, but no alerts will be sent. Check logs for SMTP errors.

### 4. Norwegian Language Assumptions
The parsing assumes Norwegian text ("Til salgs", "Totalpris", "Solgt"). Finnish or English versions of Finn.no would require selector/text adjustments.

---

## Next Steps / Roadmap

Priority-ordered tasks for future development:

### 1. Add Retry Logic with Exponential Backoff
**Priority:** High  
**Reason:** Network requests occasionally fail; current implementation skips to next URL  
**Implementation:** Add `requests` with `urllib3.util.retry` or custom retry wrapper in `FinnNoParser.fetch_page()`

### 2. Implement Health Checks / Monitoring
**Priority:** High  
**Reason:** No visibility into system health (silent failures possible)  
**Implementation:** 
- Add Prometheus metrics endpoint or simple HTTP health check
- Track: success rate per URL, parse failure count, email send status
- Consider healthchecks.io integration

### 3. Unit Tests
**Priority:** Medium  
**Reason:** No automated test coverage; regressions possible on HTML structure changes  
**Implementation:**
- Create `tests/` directory with pytest
- Mock HTML responses for each category
- Test: price extraction, title extraction, price comparison, email formatting
- Run in CI/CD pipeline

### 4. Configuration Management
**Priority:** Medium  
**Reason:** Environment variables become unwieldy for complex configs  
**Implementation:** 
- Support YAML/JSON config file (e.g., `config.yaml`)
- Allow per-URL settings (custom headers, different check intervals)
- Maintain backward compatibility with env vars

### 5. Web Dashboard
**Priority:** Low  
**Reason:** Nice-to-have for visualizing price trends  
**Implementation:** Simple Flask/FastAPI app serving price_history.json as charts

### 6. Price Prediction / Anomaly Detection
**Priority:** Low  
**Reason:** Advanced feature for identifying unusual price drops  
**Implementation:** Statistical analysis of price history, alert on deviations >2σ

---

## Operational Notes

### Running Locally (Development)
```bash
cd /a0/usr/projects/finn_no_price_monitor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install beautifulsoup4 lxml requests

# Configure environment
cp .env.example .env
# Edit .env with your SMTP settings

# Run with debug
DEBUG=1 python price_fetcher.py

# Check results
cat price_history.json | python -m json.tool
ls debug_dumps/  # HTML snapshots if DEBUG=1
```

### Debugging Failed Parsing
1. Enable debug mode: `DEBUG=1 python price_fetcher.py`
2. Check `debug_dumps/` for saved HTML
3. Inspect HTML structure: `grep -n "h1\|data-testid" debug_dumps/*.html`
4. Test specific extraction:
   ```python
   from price_fetcher import FinnNoParser
   with open('debug_dumps/file.html') as f:
       html = f.read()
   price, title, err = FinnNoParser.parse_listing(html, 'recommerce', 'test')
   print(f"Price: {price}, Title: {title}, Error: {err}")
   ```

### CI/CD Pipeline
The `.github/workflows/release.yml` triggers on tag push (v*.*.*):
1. Runs Docker build test
2. Builds and pushes image to GHCR
3. Generates SPDX SBOM
4. Signs image with cosign
5. Creates GitHub Release

**Releasing:** Push a tag: `git tag v1.1.3 && git push origin v1.1.3`

---

## Critical Information for New Agent

### IMMEDIATE CONTEXT
- **Last reported issue:** Recommerce title extraction (RESOLVED in v1.1.2)
- **System status:** Operational, all features working
- **Last verified:** Debug dump `20260208_085719_recommerce_https___www_finn_no_recommerce_forsale_item_445195.html` correctly extracts title "Gaming pc selges"

### IF PARSING BREAKS
The most likely cause is Finn.no HTML structure changes. Check:
1. Do debug dumps exist? (`DEBUG=1` to generate)
2. Does `data-testid="object-title"` still exist in HTML?
   - If yes: Check BeautifulSoup quirk (get_text vs string)
   - If no: Update selectors in `_parse_title()` method

### SINGLE SOURCE OF TRUTH
- **Configuration:** Environment variables (see .env.example)
- **Code style:** AGENTS.md overrides any conflicting instructions
- **Data:** `price_history.json` is authoritative for historical prices
- **URLs:** `urls.txt` (one per line)

### NEVER DO
- Do not expose secrets in AGENTS.md (use §§secret placeholders)
- Do not commit debug_dumps/ or price_history.json with real data to public repos
- Do not change DATA_DIR structure without updating Docker volumes

### ALWAYS DO
- Test parsing with actual debug dumps before claiming fix works
- Verify both `.get_text()` and `.string` when debugging BeautifulSoup issues
- Run `python -m py_compile price_fetcher.py` before committing
- Update AGENTS.md when making architectural changes

---

*Document Version: v1.1.2*  
*Last Updated: 2026-02-08*  
*Maintainer: Agent Zero (handing over to next agent)*
