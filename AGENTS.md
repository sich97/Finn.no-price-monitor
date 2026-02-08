# Finn.no Price Monitor - AGENTS.md

## Project Overview

A Python-based price monitoring service for the Norwegian marketplace **Finn.no**. Scrapes prices and titles from three listing categories (realestate, mobility, recommerce), tracks changes over time, and sends consolidated email alerts.

**Current Version:** v1.1.3
**Repository:** https://github.com/sich97/Finn.no-price-monitor
**Runtime:** Docker container with Python 3.13
**Test Suite:** 95 tests, 100% passing

---

## History & Major Decisions

### v1.0.0 - v1.0.4: Initial Development
- Basic price extraction for realestate/mobility
- Individual email notifications per change
- Stored prices as formatted strings ("5 434 496 kr")

### v1.0.5: Critical Bug Fix
**Problem:** All extraction failed due to non-breaking spaces (U+00A0) in HTML
**Solution:** `_normalize()` method to convert NBSP to regular spaces
**Status:** Deployed and stable

### v1.1.0: Architecture Update
1. **Numeric Price Storage** - Integer prices (1500) instead of strings ("1 500 kr")
   - Auto-migration from legacy data
2. **Combined Email Notifications** - Single summary HTML email with changes
3. **Title Extraction** - Store listing titles alongside prices

### v1.1.1 - v1.1.2: Recommerce Title Fix
**Problem:** Recommerce titles empty despite correct selectors
**Root Cause:** BeautifulSoup quirk where `.get_text()` empty but `.string` has value
**Solution:** Fallback: `if not raw_text: raw_text = str(elem.string).strip()`
**Standard:** `data-testid="object-title"` as primary selector for all categories

### v1.1.3: Comprehensive Refactoring (2026-02-08)

**Sprint A: Test Suite Foundation**
- 95 tests created across 4 test modules
- Real HTML fixtures for integration testing
- Parameter order bug fixed (was `html, soup`, now `soup, html`)
- Selector order fixed (data-testid first for all categories)

**Sprint B: Architecture Refinement**
- **FinnNoParser:** @staticmethod → Instance methods with classmethod wrappers
- **PriceHistory:** _migrate simplified with Entry dataclass
- **Pattern Extraction:** Unified `_extract_price_with_patterns_impl()` method
- **NBSP Bug:** Explicit `\xa0` replace instead of buggy empty replace

**Sprint C: Code Polish**
- Organized imports (stdlib vs third-party)
- Google-style docstrings throughout
- Modern type hints (`int | float` for Python 3.10+)
- Released to GitHub with v1.1.3 tag

---

## Current Architecture / System State

### Core Components

```
price_fetcher.py
├── Config                 # SMTP settings from env vars / config file
├── PriceHistory           # JSON-backed storage with auto-migration
│   └── Entry (dataclass)  # Validated price/title/timestamp entry
├── FinnNoParser           # HTML parsing with pattern-based extraction
│   ├── parse_listing()    # Main orchestrator (price + title + error)
│   ├── _extract_price_with_patterns_impl()  # Unified extraction
│   └── Category Pattern Configs:
│       - REALESTATE_PATTERNS: data_testid_search, label_search
│       - MOBILITY_PATTERNS: label_search, t2_span_search
│       - RECOMMERCE_PATTERNS: html_regex_search, dom_traversal
└── EmailNotifier          # SMTP encryption, HTML/text formatting

tests/
├── conftest.py            # 30+ fixtures (temp dirs, mock SMTP, HTML)
├── test_config.py         # 16 tests - Config loading, env vars
├── test_price_history.py  # 13 tests - Migration, persistence
├── test_parser.py         # 46 tests - HTML parsing, real fixtures
├── test_email.py          # 20 tests - SMTP, MIME, formatting
└── fixtures/              # 3 real HTML samples from debug_dumps
```

### Data Format

**price_history.json (Current):**
```json
{
  "https://www.finn.no/recommerce/forsale/item/445195639": [
    {
      "price": 1500,
      "title": "Gaming pc selges",
      "timestamp": "2026-02-08T13:54:22+00:00"
    }
  ]
}
```

**Migration Supported:**
- Old format: `[price1, timestamp1, price2, timestamp2, ...]` (alternating)
- New format: `[{"price":..., "title":..., "timestamp":...}, ...]`

### Statelessness
The script has **no internal runtime state**. All data flows through:
1. **Input:** `urls.txt` + HTTP fetch
2. **Processing:** Parse HTML → extract price/title (via patterns)
3. **Storage:** `price_history.json`
4. **Output:** Email notifications (if prices changed)

### CSS Selector Strategy (Unified)

```python
selectors = {
    'realestate': ['[data-testid="object-title"]', 'h1', 'h1.t1'],
    'mobility': ['[data-testid="object-title"]', 'h1', 'h1.t1'],
    'recommerce': ['[data-testid="object-title"]', 'h1', 'h1.t1']
}
```

### Text Extraction with BeautifulSoup Quirk Handling

```python
raw_text = elem.get_text(strip=True)
if not raw_text:  # Handle quirk
    raw_text = str(elem.string).strip() if elem.string else ''
# Remove common prefixes
title = re.sub(r'^(Til salgs|Utleie|Solgt)\s*[-–]?\s*', '', raw_text, flags=re.I)
```

### NBSP Normalization (Fixed in v1.1.3)

```python
def _normalize_impl(self, text: str) -> str:
    """Replace Norwegian non-breaking spaces (U+00A0) with regular spaces."""
    return text.replace('\xa0', ' ')  # Fixed: was replace('', ' ')
```

### Environment Configuration

**Required for Email Alerts:**
- `SMTP_HOST` - Mail server hostname
- `SMTP_PORT` - Mail server port (default: 587)
- `SMTP_USER` / `SMTP_PASS` - Authentication credentials
- `EMAIL_FROM` - Sender address
- `EMAIL_TO` - Recipient(s), comma-separated

**Optional:**
- `DEBUG=1` - Enable verbose logging and HTML dumps
- `DATA_DIR` - Data directory path (default: `/data` in Docker, `.` locally)
- `SCHEDULE_MODE` - `once` or `loop` (default: `once`)
- `CHECK_INTERVAL_HOURS` - Hours between checks in loop mode (default: 4)

### Docker Environment

**Key Paths:**
- `/data/urls.txt` - URL list
- `/data/price_history.json` - Historical data
- `/data/debug_dumps/` - HTML snapshots (when DEBUG=1)

**Image:** `ghcr.io/sich97/finn-price-monitor:v1.1.3`
**Registry:** GitHub Container Registry
**Signing:** Cosign with key verified in CI/CD

---

## Completed Work

- [x] Price extraction for all 3 categories (realestate, mobility, recommerce)
- [x] NBSP normalization bug fix (proper `\xa0` handling)
- [x] Integer price storage with auto-migration
- [x] Combined summary email notifications (HTML table with change indicators)
- [x] Title extraction for all categories with BeautifulSoup quirk handling
- [x] Parameter order consistency (all parsers use `soup, html` order)
- [x] Selector order consistency (data-testid first for all categories)
- [x] Instance-based FinnNoParser with classmethod wrappers
- [x] Entry dataclass for PriceHistory migration
- [x] Unified pattern-based price extraction
- [x] Comprehensive test suite (95 tests across 4 modules)
- [x] Real HTML fixtures for integration testing
- [x] Google-style docstrings throughout
- [x] Modern type hints (Python 3.10+ `int | float`)
- [x] Docker containerization
- [x] GitHub Actions CI/CD with cosign signing and SPDX SBOM
- [x] GitHub Release v1.1.3

---

## Work In Progress

None. All reported issues resolved. System is production-ready.

---

## Known Issues / Limitations

### 1. HTML Structure Dependency
The parser relies on Finn.no's HTML markup. If Finn.no changes structure:
- **Symptom:** Price/title extraction returns None
- **Detection:** Check logs, debug_dumps/, or run `pytest tests/test_parser.py -v`
- **Resolution:** Update patterns in FinnNoParser category configs

### 2. Norwegian Language Assumption
Parsing assumes Norwegian text ("Til salgs", "Totalpris", "Solgt"). International versions require pattern updates.

### 3. Email Requires SMTP
Script runs without email, but no alerts sent. Only user hears about price changes via JSON file inspection.

### 4. Single Threaded
Sequential URL processing. Slow for large URL lists. No parallel fetching implemented.

### 5. No Retry Logic
Network failures skip to next URL. No exponential backoff. (See Next Steps)

---

## Next Steps / Roadmap

### Priority 1: High (Recommended Next)

#### 1. Add Retry Logic with Exponential Backoff
**Problem:** Network requests fail silently; script continues
**Solution:** Add `urllib3.util.retry` or custom wrapper in `fetch_and_parse()`
**Test Impact:** Add tests in `test_parser.py` for retry scenarios

#### 2. Implement Health Checks / Monitoring
**Problem:** No visibility into system health
**Solution:**
- Prometheus metrics endpoint (HTTP `/metrics`)
- Or simple HTTP health endpoint for healthchecks.io
- Track: success rate, parse failures, email send status

### Priority 2: Medium

#### 3. Add More Test Fixtures
**Problem:** Only 3 HTML fixtures (one per category)
**Solution:** Save additional debug_dumps over time for broader coverage

#### 4. Configuration File Support (YAML/JSON)
**Problem:** Environment variables only
**Solution:** Support `config.yaml` with per-URL settings (headers, intervals)

#### 5. Parallel URL Fetching
**Problem:** Sequential processing slow
**Solution:** `concurrent.futures.ThreadPoolExecutor` with rate limiting

### Priority 3: Low (Nice to Have)

#### 6. Web Dashboard
**Description:** Flask/FastAPI app showing price charts
**Complexity:** Medium (requires persistent data, web server)

#### 7. Price Prediction / Anomaly Detection
**Description:** Statistical alerts for unusual price drops (>2σ deviation)
**Complexity:** High (requires time-series analysis)

---

## Operational Notes

### Running Tests

```bash
cd /a0/usr/projects/finn_no_price_monitor

# Run all tests
pytest tests/ -v

# Run with coverage
coverage run -m pytest tests/
coverage report -m price_fetcher.py

# Run single test file
pytest tests/test_parser.py -v

# Run filtered tests
pytest tests/ -v -k recommerce
```

### Development Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
pip install pytest pytest-cov responses beautifulsoup4 lxml requests

# Run with debug
DEBUG=1 python price_fetcher.py --run
```

### Debugging Failed Parsing

1. Enable debug mode: `DEBUG=1 python price_fetcher.py --run`
2. Check `debug_dumps/` for saved HTML
3. Inspect structure: `grep -n 'data-testid\|h1' debug_dumps/*.html`
4. Test specific extraction: Use `python -c` with FinnNoParser directly

### CI/CD Pipeline

**Trigger:** Push tag `v*` to main branch
**Workflow:** `.github/workflows/release.yml`

**Steps:**
1. Run tests (implicit in build)
2. Build Docker image
3. Push to GHCR: `ghcr.io/sich97/finn-price-monitor:v{VERSION}`
4. Generate SPDX SBOM
5. Sign with cosign
6. Create GitHub Release

**Release:** Push tag: `git tag v1.1.4 && git push origin v1.1.4`

---

## Critical Information for New Agent

### Immediate Context
- **Version:** v1.1.3 - Production ready
- **Last Update:** 2026-02-08 (all sprints complete)
- **System Status:** Operational, well-tested, documented
- **Test Results:** 95/95 passing, real HTML fixtures validated

### If Parsing Breaks
1. Check if Finn.no changed HTML structure
2. Run tests: `pytest tests/test_parser.py -v`
3. Use `DEBUG=1` to save debug HTML
4. Update pattern configs in FinnNoParser (not individual methods)

### Single Source of Truth
- **Configuration:** Environment variables (`.env.example` template)
- **Documentation:** This file (AGENTS.md) overrides all conflicting instructions
- **Code Style:** Google-style docstrings, modern type hints (`int | None`)
- **Tests:** Located in `tests/` directory - must pass before commit
- **Data Format:** `price_history.json` is authoritative for historical data

### Technology Stack
- **Python:** 3.13 with `requests`, `beautifulsoup4`, `pytest`
- **Type Hints:** Python 3.10+ syntax (`|`, `list[str]` available but not required)
- **Docker:** Multi-stage build, GHCR distribution
- **CI/CD:** GitHub Actions, cosign signing

### Never Do
- Never commit debug_dumps or price_history.json with real data
- Never expose SMTP credentials in AGENTS.md
- Never skip tests before pushing to main

### Always Do
- Run `pytest tests/ -q` before claiming work complete
- Update AGENTS.md when making architectural changes
- Use §§secret placeholders for sensitive data
- Test with real HTML if changing FinnNoParser patterns

---

*Document Version: v1.1.3-final
Last Updated: 2026-02-08
Maintainer: Agent Zero (handing over)*

---

## Agent Development Workflow

### Pre-Commit Testing on VPS (CRITICAL)

> **Constraint**: Agent Zero runs inside a Docker container and **cannot use Docker-in-Docker**. All Docker builds MUST execute on the remote VPS via SSH.

**Before any commit**, you MUST build and test on the VPS:

```bash
# Setup SSH connection
mkdir -p /tmp/ssh && chmod 700 /tmp/ssh
echo "$VPS_SSH_KEY" > /tmp/ssh/vps_key && chmod 600 /tmp/ssh/vps_key
export SSH="ssh -i /tmp/ssh/vps_key -o StrictHostKeyChecking=accept-new"

# Clean and prepare VPS build directory
$SSH "$VPS_USER@$VPS_HOST" "rm -rf /tmp/build && mkdir -p /tmp/build"

# Transfer source code via tarball
tar czf /tmp/source.tar.gz --exclude='.git' --exclude='venv' --exclude='debug_dumps' .
scp -i /tmp/ssh/vps_key /tmp/source.tar.gz "$VPS_USER@$VPS_HOST:/tmp/build/"

# Extract on VPS
$SSH "$VPS_USER@$VPS_HOST" "cd /tmp/build && tar xzf source.tar.gz"

# Build Docker image
$SSH "$VPS_USER@$VPS_HOST" "cd /tmp/build && docker build -t finn-price-monitor:local-test ."

# Run container to verify it starts
$SSH "$VPS_USER@$VPS_HOST" "docker run --rm finn-price-monitor:local-test --help"

# Run tests (pytest must be installed in container or run locally)
# Option 1: If pytest is installed in container:
# $SSH "$VPS_USER@$VPS_HOST" "docker run --rm --entrypoint pytest finn-price-monitor:local-test /app/tests/"

# Option 2: Install dependencies and run tests on VPS host:
# $SSH "$VPS_USER@$VPS_HOST" "cd /tmp/build && pip install pytest beautifulsoup4 requests && python -m pytest tests/"
```

### GitHub Actions (Separate from VPS)

**Note**: GitHub Actions runs on GitHub's infrastructure, NOT the VPS. The VPS is for **local agent testing only**.

Workflow files:
- `.github/workflows/docker-test.yml` — runs on GitHub runners
- `.github/workflows/release.yml` — runs on GitHub runners

These workflows do NOT access the VPS. They use standard GitHub Actions infrastructure.

### Important: Test Before Commit

**NEVER commit without testing on VPS first.** The build might fail due to:
- Missing dependencies in Dockerfile
- Python version incompatibilities
- Broken imports
- Syntax errors

### Accessing VPS Logs

```bash
# View Docker build logs
$SSH "$VPS_USER@$VPS_HOST" "docker logs <container-id>"

# Check running containers
$SSH "$VPS_USER@$VPS_HOST" "docker ps -a"

# Inspect image
$SSH "$VPS_USER@$VPS_HOST" "docker history finn-price-monitor:local-test"

# Cleanup after testing
$SSH "$VPS_USER@$VPS_HOST" "docker rmi finn-price-monitor:local-test && rm -rf /tmp/build"
rm -rf /tmp/ssh /tmp/source.tar.gz
```

---

November 2025: Added local VPS testing workflow documentation to increase agent autonomy and ensure builds are validated before commit.
