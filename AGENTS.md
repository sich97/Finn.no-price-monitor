# Finn.no Price Monitor - AGENTS.md

**Version:** v1.1.3 | **Status:** Production Ready | **Tests:** 95/95 passing

## 1. Project Overview

Price monitoring service for [Finn.no](https://finn.no), Norway's largest marketplace. Scrapes prices from real estate, vehicles, and classifieds, tracks historical changes, and sends consolidated email alerts.

**Repository:** https://github.com/sich97/Finn.no-price-monitor  
**Runtime:** Python 3.11+ in Docker container  
**Registry:** GitHub Container Registry (`ghcr.io/sich97/finn-price-monitor`)

### Core Capabilities
- Extract prices from 3 Finn.no categories: `realestate`, `mobility`, `recommerce`
- Track price history in JSON format with automatic migration
- Send consolidated HTML email alerts for price changes
- Run as one-time check or scheduled loop

---

## 2. System Architecture

```
price_fetcher.py (main entrypoint)
├── Config                    # SMTP settings from env vars/config file
├── PriceHistory              # JSON-backed storage with migration
│   └── Entry (dataclass)     # Validated price/title/timestamp
├── FinnNoParser              # HTML parsing with pattern fallback
│   ├── parse_listing()       # Main orchestrator
│   └── _extract_price_with_patterns_impl()
│       ├── REALESTATE_PATTERNS   # data_testid + label_search
│       ├── MOBILITY_PATTERNS     # label_search + t2_span_search  
│       └── RECOMMERCE_PATTERNS   # html_regex + dom_traversal
└── EmailNotifier             # SMTP with TLS, HTML/text formatting

tests/
├── conftest.py               # 30+ fixtures (mocks, temp dirs, HTML)
├── test_parser.py            # 46 tests - extraction logic
├── test_price_history.py     # 13 tests - storage & migration
├── test_config.py            # 16 tests - configuration loading
└── test_email.py             # 20 tests - SMTP formatting
```

### Data Format (Current)
```json
{
  "https://finn.no/.../item/123": [
    {"price": 1500, "title": "Gaming PC", "timestamp": "2026-02-09T07:00:00Z"}
  ]
}
```

**Legacy format auto-migrated:** Flat list `[price1, timestamp1, price2, ...]` → Structured objects

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SMTP_HOST` | Yes* | Mail server hostname |
| `SMTP_PORT` | Yes* | Mail server port (default: 587) |
| `SMTP_USER` | Yes* | SMTP username |
| `SMTP_PASS` | Yes* | SMTP password |
| `EMAIL_FROM` | Yes* | Sender address |
| `EMAIL_TO` | Yes* | Recipient(s), comma-separated |
| `DATA_DIR` | No | Data directory (default: `/data` Docker, `.` local) |
| `SCHEDULE_MODE` | No | `once` or `loop` (default: `once`) |
| `CHECK_INTERVAL_HOURS` | No | Loop interval (default: 4) |
| `DEBUG` | No | `1` to enable debug logging & HTML dumps |

*Required only for email alerts. Script runs without SMTP for data collection only.

### Docker Paths
- `/data/urls.txt` - URL list (one per line)
- `/data/price_history.json` - Price history storage
- `/data/debug_dumps/` - HTML snapshots when `DEBUG=1`

---

## 3. Development Workflow (CRITICAL)

### 3.1 Pre-Commit VPS Testing (MANDATORY)

> **CONSTRAINT:** Agent Zero runs in a Docker container. **Cannot use Docker-in-Docker.** All Docker builds MUST execute on a remote VPS via SSH.

**NEVER commit code without testing Docker build on VPS first.**

```bash
# 1. Setup SSH connection (ephemeral)
mkdir -p /tmp/ssh && chmod 700 /tmp/ssh
echo "$VPS_SSH_KEY" > /tmp/ssh/vps_key && chmod 600 /tmp/ssh/vps_key
export SSH="ssh -i /tmp/ssh/vps_key -o StrictHostKeyChecking=accept-new"

# 2. Transfer source to VPS (use isolated directory)
$SSH "$VPS_USER@$VPS_HOST" "rm -rf /tmp/build && mkdir -p /tmp/build"
tar czf /tmp/source.tar.gz --exclude='.git' --exclude='venv' --exclude='debug_dumps' --exclude='data' .
scp -i /tmp/ssh/vps_key /tmp/source.tar.gz "$VPS_USER@$VPS_HOST:/tmp/build/"

# 3. Extract and build
$SSH "$VPS_USER@$VPS_HOST" "cd /tmp/build && tar xzf source.tar.gz"
$SSH "$VPS_USER@$VPS_HOST" "cd /tmp/build && docker build -t finn-price-monitor:local-test ." 2>&1
# Expected: ~140MB image, successful build

# 4. Verify container starts
$SSH "$VPS_USER@$VPS_HOST" "docker run --rm finn-price-monitor:local-test --help"
# Expected: Shows usage options

# 5. Cleanup VPS resources
$SSH "$VPS_USER@$VPS_HOST" "docker rmi finn-price-monitor:local-test && rm -rf /tmp/build"
rm -rf /tmp/ssh /tmp/source.tar.gz
```

**If VPS build fails:** Fix code locally, repeat steps 2-5. **Do not commit.**

### 3.2 Local Testing (Fast Feedback)

```bash
# Run all tests (fast, no Docker needed)
pytest tests/ -v

# Run specific test file
pytest tests/test_parser.py -v -k recommerce

# Run with coverage
coverage run -m pytest tests/
coverage report -m price_fetcher.py

# Debug mode (saves HTML to debug_dumps/)
DEBUG=1 python price_fetcher.py --run
```

### 3.3 GitHub Actions (Automatic on Push)

**DO NOT modify these workflows to use VPS.** They run on GitHub's infrastructure.

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `docker-test.yml` | Push/PR to `main` | Build image, run pytest |
| `release.yml` | Push tag `v*` | Build, sign with cosign, push to GHCR, create release |

**Release process:**
```bash
# After VPS tests pass and code is committed:
git tag v1.1.4
git push origin v1.1.4
# GitHub Actions handles the rest
```

---

## 4. Architecture Decisions & History

### Major Versions

| Version | Date | Key Changes |
|---------|------|-------------|
| v1.0.5 | 2025 | **NBSP Bug Fix** - Fixed `\xa0` (non-breaking space) normalization causing all parsing to fail |
| v1.1.0 | 2025 | **Numeric Prices** - Integer storage instead of strings; combined email notifications; title extraction |
| v1.1.2 | 2025 | **Title Fix** - BeautifulSoup quirk: `elem.get_text()` empty but `elem.string` had value. Added fallback. |
| v1.1.3 | 2026-02-08 | **Refactoring** - Instance-based parser, unified price patterns, 95 tests, full docstrings |

### Key Technical Decisions

1. **Pattern-Based Extraction** - Different selectors per category (realestate/mobility/recommerce use different HTML)
2. **Statelessness** - No runtime state; data flows: URLs → HTTP → Parse → JSON → (Optional: Email)
3. **Entry Dataclass** - Structured storage with validation; auto-migrates legacy flat lists
4. **Unified Selectors** - All categories try `data-testid="object-title"` first, then fall back to h1/h1.t1
5. **VPS Pre-Commit** - Agent Zero Docker constraint requires remote builds for testing

---

## 5. Current Status

### ✅ Completed
- All 3 categories parse correctly (95 tests)
- NBSP normalization fixed (`\xa0` → space)
- Price history auto-migration from legacy format
- BeautifulSoup quirk handling for empty `.get_text()`
- Instance-based FinnNoParser with classmethod wrappers
- Comprehensive test suite with real HTML fixtures
- Google-style docstrings, modern type hints (`int | None`)
- GitHub Container Registry distribution with cosign signing
- VPS pre-commit testing workflow documented and validated

### ⚠️ Known Limitations

1. **HTML Dependency** - If Finn.no changes markup, parsing breaks. Fix: Update patterns in `FinnNoParser` category configs. Detection: Run `pytest tests/test_parser.py -v`
2. **Norwegian Language Assumption** - Hardcoded text: "Til salgs", "Totalpris", "Solgt". International versions need pattern updates.
3. **No Retry Logic** - Network failures skip to next URL without exponential backoff. Recommended next priority (see Section 6).
4. **Single Threaded** - Sequential URL processing. For many URLs, implement `concurrent.futures.ThreadPoolExecutor`.
5. **Debug Data** - `debug_dumps/` and `price_history.json` contain real data. Never commit these files.

---

## 6. Next Steps (Prioritized)

### P1: High Priority (Recommended Next)

#### 6.1 Add Exponential Backoff for Network Failures
**Problem:** Network errors fail silently; script continues  
**Solution:** Implement `urllib3.util.retry` or custom wrapper in `fetch_and_parse()`  
**Tests:** Add to `test_parser.py` for retry success/failure scenarios

#### 6.2 Health Monitoring Endpoint
**Problem:** No visibility into system health  
**Solution:** Add simple HTTP health endpoint or log structured metrics  
**Track:** Success rate, parse failures, email send status

### P2: Medium Priority

#### 6.3 Parallel URL Fetching
**Problem:** Sequential processing slow for many URLs  
**Solution:** `concurrent.futures.ThreadPoolExecutor` with 2-3 workers and rate limiting

#### 6.4 Configuration File Support
**Problem:** Environment variables only  
**Solution:** Support `config.yaml` with per-URL settings (custom headers, intervals)

### P3: Low Priority (Nice to Have)

#### 6.5 Web Dashboard
FastAPI/Flask app showing price charts. Requires persistent storage beyond JSON.

#### 6.6 Price Anomaly Detection
Statistical alerts for unusual price drops (>2σ deviation). Requires time-series analysis.

---

## 7. Operational Notes

### Debugging Failed Parsing

1. Enable debug: `DEBUG=1 python price_fetcher.py --run`
2. Check `debug_dumps/` for saved HTML
3. Inspect selectors: `grep -n 'data-testid\|h1' debug_dumps/*.html`
4. Test extraction manually:
   ```python
   from price_fetcher import FinnNoParser
   parser = FinnNoParser()
   soup = parser._soup_from_html(open('debug_dumps/xxx.html').read())
   print(parser.extract_title_reimpl(soup, 'mobility'))
   ```

### Troubleshooting Checklist

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| All prices return None | Finn.no changed HTML | Update patterns in `FinnNoParser` |
| Email not sending | SMTP config missing | Check env vars, test SMTP connection |
| Container exits immediately | Missing `urls.txt` | Ensure `/data/urls.txt` exists |
| `\xa0` in output | NBSP not normalized | Check `_normalize_impl()` method |
| Title empty for recommerce | BeautifulSoup quirk | Verify `elem.string` fallback exists |

### Code Style
- **Docstrings:** Google style (Args, Returns, Raises)
- **Types:** Python 3.10+ syntax (`int | None`, `list[str]`)
- **Imports:** stdlib first, then third-party, then local
- **Naming:** `snake_case` for functions/variables, `CamelCase` for classes

### Security
- Never commit `debug_dumps/` or `price_history.json`
- No SMTP credentials in AGENTS.md (use `§§secret()` placeholders)
- Use `.env.example` for config template, never `.env` with real values

---

## 8. Quick Reference

### Build & Test (Local)
```bash
pytest tests/ -v                              # Run all tests
pytest tests/test_parser.py -v -k recommerce  # Specific tests
python price_fetcher.py --help                # Usage
DEBUG=1 python price_fetcher.py --run         # Debug mode
```

### Docker Commands
```bash
docker build -t finn-price-monitor:dev .      # Local build (not for agents)
docker run --rm finn-price-monitor:dev --help # Test run
docker-compose up --build                     # Compose workflow
```

### Release
```bash
# After VPS tests pass:
git add AGENTS.md price_fetcher.py
git commit -m "feat: description"
git tag v1.1.4
git push origin main
git push origin v1.1.4  # Triggers release workflow
```

---

## 9. Critical Constraint Summary

> **Agent Zero Cannot Use Docker-in-Docker**

- ✅ **Test builds on VPS via SSH** before git commit
- ❌ **Never modify GitHub Actions** to use VPS
- ❌ **Never run `docker build` locally** inside container
- ✅ **Use isolated dirs** (`/tmp/build/`, not `/tmp/` directly)
- ✅ **Use `wait` tool** after starting containers before checking logs

---

*Handover Document: v1.1.3-handover*  
*Last Updated: 2026-02-09*  
*Maintainer: Agent Zero → (new agent)*
