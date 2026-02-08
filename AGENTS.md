# Finn.no Price Monitor - Agent Handover Document

## Project Overview

A production-ready Python service monitoring Norwegian marketplace (Finn.no) listing prices across real estate, mobility, and recommerce categories. Fetches prices from configured URLs, compares against JSON history, sends SMTP email alerts on changes.

**Repository:** https://github.comich97/Finn.no-price-monitor.git  
**CI/CD:** https://github.com/sich97/Finn.no-price-monitor/actions  
**Container Registry:** `ghcr.io/sich97/finn-price-monitor:stable`  
**Current Version:** v1.0.4 (syntax fixes committed, awaiting approval)

---

## History & Major Decisions

### Architectural Decisions (Locked)

| Decision | Rationale |
|----------|-----------|
| **Stateless design** | No runtime state; reads URLs, fetches, updates JSON, exits/loops |
| **JSON price history** | File-based storage with ISO8601 timestamps; simple, sufficient |
| **Category-specific parsers** | Finn.no uses different DOM structures per category |
| **Environment variable config** | 12-factor app; no hardcoded secrets |
| **Dual scheduling modes** | `SCHEDULE_MODE=once` for external cron, `SCHEDULE_MODE=loop` for container-native |
| **Manual release approval** | GitHub Environment `production` requires UI approval |

### Evolution

- **v1.0.0**: Initial Docker + GHCR + cosign signing
- **v1.0.1**: Fixed Dockerfile COPY paths for CI volume mount
- **v1.0.2**: Added `python -u` unbuffered mode for Docker logs
- **v1.0.3**: Added verbose logging (`DEBUG=1`, `--verbose`, HTML dumps)
- **v1.0.4**: Fixed f-string syntax errors (commit bc39c68)

---

## Current Architecture

### Runtime Flow

```
urls.txt → Fetch prices → Compare history → Price changed?
                                              ↓
                    ┌─────────────────────────┼─────────────────────────┐
                    ↓                         ↓                         ↓
                Yes: Send email          No: Continue              Error: Log
                Update JSON               Wait/Exit                   Continue
```

### Category Extraction Logic

| Category | URL Pattern | Method |
|----------|-------------|--------|
| **Real estate** | `/realestate/homes/` | `data-testid='pricing-total-price'` → regex clean |
| **Mobility** | `/mobility/item/` | "Totalpris" label → next sibling `span.t2` |
| **Recommerce** | `/recommerce/forsale/` | Regex on raw HTML, DOM fallback |

### File Locations (Docker)

| Path | Purpose | Managed By |
|------|---------|------------|
| `/data/urls.txt` | Monitored URLs | User (volume mount) |
| `/data/price_history.json` | Price history | Auto-created |
| `/data/debug_dumps/` | HTML captures (DEBUG=1) | Auto-created |
| `/app/price_fetcher.py` | Main script | Container |

---

## Completed Work

- [x] Dual scheduling modes (`SCHEDULE_MODE=once|loop`)
- [x] Docker containerization with unbuffered stdout
- [x] GitHub Actions CI/CD with manual approval gates
- [x] GHCR publishing with multi-tag strategy
- [x] Cosign image signing + SBOM generation
- [x] Verbose logging (`DEBUG=1`, `--verbose`)
- [x] Category-specific price parsers (3 categories)
- [x] JSON price history with ISO8601 timestamps
- [x] SMTP email alerts with TLS
- [x] Deploy key authentication

---

## CRITICAL: Active Issues

### **Price Extraction Broken (P0)**

**Status:** All three categories failing in production  
**Symptoms:** "Could not extract price for category: X" in logs  
**Suspected Causes:**
- Finn.no blocking automated requests (403/429, Cloudflare)
- DOM structure changes
- Missing User-Agent or rate limiting headers

**Next Agent Action:**
1. Deploy with `DEBUG=1 SCHEDULE_MODE=once`
2. Inspect logs for HTTP status codes
3. Check `/data/debug_dumps/` for captured HTML
4. Implement fixes (User-Agent rotation, delays, Playwright if needed)

---

## Next Steps (Priority Order)

1. **Fix price extraction** (P0) - See Active Issues
2. **Add retry logic** with exponential backoff
3. **Health check endpoint** for Docker HEALTHCHECK
4. **Add unit tests** with mocked HTTP responses
5. **Expand to additional marketplaces**

---

## Operational Notes

### Quick Commands

```bash
# Local build/test
docker build -t finn-price-monitor .
python -m py_compile price_fetcher.py

# Run with debugging
docker run --rm -v ./data:/data -e DEBUG=1 -e SCHEDULE_MODE=once finn-price-monitor --run --verbose

# Push release
git tag v1.0.5 && git push origin v1.0.5
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | Yes | - | Mail server |
| `SMTP_PORT` | Yes | - | Port (587/465) |
| `SMTP_USER` | Yes | - | Auth username |
| `SMTP_PASS` | Yes | - | Auth password |
| `EMAIL_FROM` | Yes | - | Sender |
| `EMAIL_TO` | Yes | - | Recipient(s) |
| `DATA_DIR` | No | `/app` | Data path |
| `SCHEDULE_MODE` | No | `once` | `once` or `loop` |
| `CHECK_INTERVAL_HOURS` | No | `4` | Loop wait (1-168) |
| `DEBUG` | No | `0` | Verbose logging |

### CI/CD Tags

| Tag | Purpose | Mutable |
|-----|---------|---------|
| `sha-xxx` | Every push | Yes |
| `main` | Development | Yes |
| `stable` | Production | **Yes** |
| `v1.0.5` | Version | **No** |

---

## Critical Information

### Secrets
- Deploy key: Use replacement syntax

### Secrets
- Deploy key: Available via secret replacement (FINN_NO_PRICE_MONITOR_GITHUB_DEPLOY_KEY)
- SSH config: `~/.ssh/config` with `StrictHostKeyChecking no`

### Code Standards
- PEP8, 100 char lines, type hints
- Validate: `python -m py_compile price_fetcher.py`
- Use `+ repr(var)` for f-strings (avoid nested quotes)

- Validate: `python -m py_compile price_fetcher.py`
- Use `+ repr(var)` for f-strings (avoid nested quotes)

### Security Reminders
- **NEVER store actual secrets in repo files** - Use placeholders like "Configure via env var"
- Never include: private keys, passwords, tokens, API keys in any committed file
- Secret references: use descriptive names only
- Before committing: scan for "BEGIN OPENSSH PRIVATE KEY" or base64 patterns


### DO NOT Change
- Manual approval gate
- Stateless design
- JSON storage (discuss if changing)

### Finn.no Constraints
- May block bots (403/429)
- DOM changes periodically
- Norwegian text parsing
- Respect rate limits

---

**Version:** v1.0.4-handover  
**Updated:** 2026-02-08  
**Status:** Price extraction broken, fix is P0
