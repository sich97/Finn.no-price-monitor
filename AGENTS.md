# Finn.no Price Monitor - Agent Handover Document

## Project Overview

A production-ready Python service monitoring Norwegian marketplace (Finn.no) listing prices across real estate, mobility, and recommerce categories. Fetches prices from configured URLs, compares against JSON history, sends SMTP email alerts on changes.

**Repository:** https://github.com/sich97/Finn.no-price-monitor.git 
**CI/CD:** https://github.com/sich97/Finn.no-price-monitor/actions 
**Container Registry:** `ghcr.io/sich97/finn-price-monitor:stable` 
**Current Version:** v1.1.0 (Numeric price storage, cleaner comparison)

---

## Version v1.1.0 - Numeric Price Storage Feature 1

### Overview
Converted price storage from formatted strings ("5 434 496 kr") to pure integers (5434496) for easier comparison and processing.

### Implementation Details

#### New Static Methods
| Method | Description |
|----------|-----------|
| `FinnNoParser._parse_price_value(price_str)` | Converts "5 434 496 kr" -> 5434496 |
| `FinnNoParser._format_price_display(price)` | Converts 5434496 -> "5 434 496 kr" |

#### Data Type Changes
| Before | After |
|--------|-------|
| Parsers return `Optional[str]` | Parsers return `Optional[int]` |
| Price comparison on strings | Price comparison on integers |
| Stored: `"5 434 496 kr"` | Stored: `5434496` |
| Email subject: raw string | Email subject: formatted via `_format_price_display()` |

#### Auto-Migration
- `PriceHistory._migrate_data()` auto-converts old JSON entries on load
- `PriceHistory._normalize_price_entry()` handles string->int conversion
- Backward compatible: old data automatically migrated, new entries stored as int

#### Logging
- Shows both integer and human-readable format: `Current price: 5434496 (5 434 496 kr)`
- Price changes display: `PRICE CHANGED: 5434495 -> 5434496 (5 434 495 kr -> 5 434 496 kr)`

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
| **Numeric price storage** (v1.1.0) | Integer comparison eliminates string format issues, enables arithmetic |

### Evolution

- **v1.0.0**: Initial Docker + GHCR + cosign signing
- **v1.0.1**: Fixed Dockerfile COPY paths for CI volume mount
- **v1.0.2**: Added `python -u` unbuffered mode for Docker logs
- **v1.0.3**: Added verbose logging (`DEBUG=1`, `--verbose`)
- **v1.0.4**: Fixed f-string syntax errors (commit bc39c68)
- **v1.0.5**: Fixed NBSP normalization bug causing price extraction to fail on all categories (Feb 8, 2026)
- **v1.1.0**: Numeric price storage - prices now stored as integers, auto-migration for old data, human-readable logging preserved

---

## Current Architecture

### Runtime Flow

```
urls.txt -> Fetch prices -> Parse to int -> Compare history -> Price changed?
                                              |
                                    Auto-migrate old strings
                                              |
                         +--------------------+--------------------+
                         |                    |                    |
                    Yes: Send email      No: Continue        Error: Log
                    Update JSON          Wait/Exit           Continue
```

### Category Extraction Logic

| Category | URL Pattern | Method |
|----------|-------------|--------|
| **Real estate** | `/realestate/homes/` | `data-testid='pricing-total-price'` -> regex clean -> int |
| **Mobility** | `/mobility/item/` | "Totalpris" label -> next sibling `span.t2` -> int |
| **Recommerce** | `/recommerce/forsale/` | Regex on raw HTML, DOM fallback -> int |

### File Locations (Docker)

| Path | Purpose | Managed By |
|------|---------|------------|
| `/data/urls.txt` | Monitored URLs | User (volume mount) |
| `/data/price_history.json` | Price history (now stores integers) | Auto-created |
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
- [x] **v1.1.0: Numeric price storage** - prices stored as integers
- [x] **v1.1.0: Auto-migration** - old string data automatically converted on load
- [x] **v1.1.0: Human-readable logging** - format integers back to display format

---

## Planned Work (v1.2.0+)

1. **Refactored price flow** - Consolidate category parsers, remove redundancy
2. **Add retry logic** with exponential backoff (3 attempts)
3. **Health check endpoint** for Docker HEALTHCHECK
4. **Add unit tests** with mocked HTTP responses
5. **Expand to additional marketplaces**
6. **Add metrics endpoint** for monitoring price change rates

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
git tag v1.1.0 && git push origin v1.1.0
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
| `v1.1.0` | Version | **No** |

---

## Critical Information

### Secrets
- Deploy key: Available via secret replacement (FINN_NO_PRICE_MONITOR_GITHUB_DEPLOY_KEY)
- SSH config: `~/.ssh/config` with `StrictHostKeyChecking no`

### Code Standards
- PEP8, 100 char lines, type hints
- Validate: `python -m py_compile price_fetcher.py`
- Use `+ repr(var)` for f-strings (avoid nested quotes)
- Type hints: parsers return `Optional[int]`, helpers use `Union[int, str]`

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

**Version:** v1.1.0 
**Updated:** 2026-02-08 
**Status:** v1.1.0 - Numeric price storage feature complete
