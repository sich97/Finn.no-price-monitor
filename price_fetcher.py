#!/usr/bin/env python3
"""Finn.no Price Monitor with Verbose Error Logging"""

import argparse
import json
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Optional, Tuple
import textwrap

import requests
from bs4 import BeautifulSoup


# Determine data directory from environment or fallback to app directory
DATA_DIR = Path(os.environ.get('DATA_DIR', Path(__file__).parent))
APP_DIR = Path(__file__).parent

# Debug mode configuration
DEBUG = os.environ.get('DEBUG', '0').lower() in ('1', 'true', 'yes', 'on')
DEBUG_DUMPS_DIR = DATA_DIR / 'debug_dumps'
if DEBUG:
    DEBUG_DUMPS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure DATA_DIR exists and set URLS_FILE correctly
DATA_DIR.mkdir(parents=True, exist_ok=True)
URLS_FILE = DATA_DIR / 'urls.txt'

HISTORY_FILE = DATA_DIR / 'price_history.json'
CONFIG_FILE = DATA_DIR / 'config.env'
if not CONFIG_FILE.exists():
    CONFIG_FILE = APP_DIR / 'config.env'

HTTP_TIMEOUT = 30
HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def log_verbose(message: str, indent: int = 0) -> None:
    """Print verbose log message with timestamp."""
    prefix = ' ' * (indent * 2)
    print(f"[{get_timestamp()}] {prefix}{message}")


def save_debug_html(url: str, html: str, category: str) -> Optional[Path]:
    """Save HTML to debug dumps directory when DEBUG=1."""
    if not DEBUG:
        return None
    try:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        safe_url = re.sub(r'[^a-zA-Z0-9]', '_', url[:50])
        filename = f"{timestamp}_{category}_{safe_url}.html"
        filepath = DEBUG_DUMPS_DIR / filename
        filepath.write_text(html, encoding='utf-8')
        return filepath
    except Exception as e:
        log_verbose(f"Failed to save debug HTML: {e}")
        return None


class Config:
    def __init__(self) -> None:
        self.smtp_host: Optional[str] = None
        self.smtp_port: int = 587
        self.smtp_user: Optional[str] = None
        self.smtp_pass: Optional[str] = None
        self.email_from: Optional[str] = None
        self.email_to: Optional[str] = None
        self._load()

    def _load(self) -> None:
        self.smtp_host = os.environ.get('SMTP_HOST', self.smtp_host)
        self.smtp_port = int(os.environ.get('SMTP_PORT', self.smtp_port))
        self.smtp_user = os.environ.get('SMTP_USER', self.smtp_user)
        self.smtp_pass = os.environ.get('SMTP_PASS', self.smtp_pass)
        self.email_from = os.environ.get('EMAIL_FROM', self.email_from)
        self.email_to = os.environ.get('EMAIL_TO', self.email_to)

        if CONFIG_FILE.exists():
            try:
                cfg = CONFIG_FILE.read_text()
                for line in cfg.splitlines():
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip()
                        while v and v[0] in "'\"":
                            v = v[1:]
                        while v and v[-1] in "'\"":
                            v = v[:-1]
                        if os.environ.get(k) is None:
                            if k == 'SMTP_HOST':
                                self.smtp_host = v
                            elif k == 'SMTP_PORT':
                                self.smtp_port = int(v)
                            elif k == 'SMTP_USER':
                                self.smtp_user = v
                            elif k == 'SMTP_PASS':
                                self.smtp_pass = v
                            elif k == 'EMAIL_FROM':
                                self.email_from = v
                            elif k == 'EMAIL_TO':
                                self.email_to = v
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")

    def is_valid(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_pass,
                    self.email_from, self.email_to])


class PriceHistory:
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                self._data = json.loads(self.filepath.read_text())
            except Exception as e:
                print(f"Warning: Could not load history: {e}")

    def save(self) -> None:
        self.filepath.write_text(json.dumps(self._data, indent=2))

    def get_last_price(self, url: str) -> Optional[str]:
        hist = self._data.get(url, [])
        return hist[-2] if len(hist) >= 2 else None

    def add_entry(self, url: str, price: str) -> None:
        if url not in self._data:
            self._data[url] = []
        self._data[url].extend([price, datetime.now(timezone.utc).isoformat()])


class FinnNoParser:
    @staticmethod
    def detect_category(url: str) -> str:
        if '/realestate/' in url:
            return 'realestate'
        elif '/mobility/' in url:
            return 'mobility'
        elif '/recommerce/' in url:
            return 'recommerce'
        return 'unknown'

    @staticmethod
    def parse_price(html: str, category: str, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse price from HTML with verbose logging.
        Returns (price, error_message) tuple.
        """
        log_verbose(f"Looking for {category} price...")
        soup = BeautifulSoup(html, 'html.parser')

        if category == 'realestate':
            price = FinnNoParser._parse_realestate_price(soup, html, url)
        elif category == 'mobility':
            price = FinnNoParser._parse_mobility_price(soup, html, url)
        elif category == 'recommerce':
            price = FinnNoParser._parse_recommerce_price(html, soup, url)
        else:
            log_verbose(f"Unknown category: {category}", indent=1)
            return None, f"Unknown category: {category}"

        if price:
            log_verbose(f"Cleaned price: '{price}'", indent=1)
            return price, None
        else:
            return None, f"Could not extract price for category: {category}"

    @staticmethod
    def _get_html_snippet(html: str, max_len: int = 500) -> str:
        """Get first N characters of HTML for debugging."""
        snippet = html[:max_len].replace('\n', ' ').replace('\r', ' ')
        return snippet.strip()

    @staticmethod
    def _parse_realestate_price(soup: BeautifulSoup, html: str, url: str) -> Optional[str]:
        """Parse realestate price with verbose logging."""
        log_verbose("Using data-testid='pricing-total-price' selector", indent=1)
        elem = soup.find(attrs={'data-testid': 'pricing-total-price'})

        if elem:
            log_verbose("Element found: Yes", indent=1)
            text = elem.get_text(strip=True)
            log_verbose(f"Raw text: '{text[:100]}...'", indent=1)
            m = re.search(r'([0-9][ 0-9]* kr)', text.replace('', ' '))
            if m:
                log_verbose(f"Price regex matched: '{m.group(1).strip()}'", indent=1)
                return m.group(1).strip()
            else:
                log_verbose("Price regex did not match in element text", indent=1)
        else:
            log_verbose("Element found: No", indent=1)
            log_verbose("HTML snippet (first 500 chars):", indent=1)
            log_verbose(FinnNoParser._get_html_snippet(html), indent=2)

        # Fallback search
        log_verbose("Trying fallback: searching for 'Totalpris' text", indent=1)
        for dt in soup.find_all(['dt', 'p', 'span']):
            if 'Totalpris' in dt.get_text():
                log_verbose("Found element containing 'Totalpris'", indent=1)
                parent = dt.find_parent()
                if parent:
                    parent_text = parent.get_text()
                    log_verbose(f"Parent text: '{parent_text[:100]}'", indent=2)
                    m = re.search(r'([0-9][ 0-9]* kr)', parent_text.replace('', ' '))
                    if m:
                        log_verbose(f"Fallback regex matched: '{m.group(1).strip()}'", indent=2)
                        return m.group(1).strip()

        log_verbose("All realestate parsing attempts failed", indent=1)
        return None

    @staticmethod
    def _parse_mobility_price(soup: BeautifulSoup, html: str, url: str) -> Optional[str]:
        """Parse mobility price with verbose logging."""
        log_verbose("Searching for 'Totalpris' label", indent=1)
        found_label = False

        for el in soup.find_all(['p', 'span', 'div']):
            if el.get_text(strip=True) == 'Totalpris':
                log_verbose("Label 'Totalpris' found: Yes", indent=1)
                found_label = True
                parent = el.find_parent()
                if parent:
                    log_verbose("Parent element exists: Yes", indent=1)
                    span = parent.find('span', class_='t2')
                    if span:
                        log_verbose("Sibling span with class 't2' found: Yes", indent=1)
                        text = span.get_text(strip=True)
                        log_verbose(f"Raw text: '{text[:100]}'", indent=1)
                        m = re.search(r'([0-9][ 0-9]* kr)', text.replace('', ' '))
                        if m:
                            log_verbose(f"Price regex matched: '{m.group(1).strip()}'", indent=1)
                            return m.group(1).strip()
                        else:
                            log_verbose("Price regex did not match", indent=1)
                    else:
                        log_verbose("Sibling span with class 't2' found: No", indent=1)
                else:
                    log_verbose("Parent element exists: No", indent=1)
                break

        if not found_label:
            log_verbose("Label 'Totalpris' found: No", indent=1)

        # Fallback
        log_verbose("Trying fallback: searching all spans with class 't2'", indent=1)
        for span in soup.find_all('span', class_='t2'):
            text = span.get_text(strip=True)
            if 'kr' in text:
                log_verbose(f"Found span with 'kr': '{text[:100]}'", indent=2)
                m = re.search(r'([0-9][ 0-9]* kr)', text.replace('', ' '))
                if m:
                    log_verbose(f"Fallback regex matched: '{m.group(1).strip()}'", indent=2)
                    return m.group(1).strip()

        log_verbose("All mobility parsing attempts failed", indent=1)
        return None

    @staticmethod
    def _parse_recommerce_price(html: str, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Parse recommerce price with verbose logging."""
        patterns = [
            (
                r'Til\s+salgs.*?<p[^>]*class="[^"]*m-0[^"]*h2[^"]*"[^>]*>'
                r'([^<]*[0-9][ 0-9]*\s*kr)</p>',
            "Pattern 1: Til salgs...<p class='+repr('m-0 h2')+'>N kr</p>'"
            ),
            (
                r'Til\s+salgs</h2>\s*<p[^>]*class="[^"]*h2[^"]*"[^>]*>'
                r'([ 0-9]*kr)</p?',
            "Pattern 2: Til salgs</h2><p class='+repr('h2')+'>Nkr'"
            ),
            (
                r'"priceText"\s*:\s*"([0-9][ 0-9]* kr)"',
                "Pattern 3: JSON field 'priceText'"
            ),
        ]

        for pattern, desc in patterns:
            log_verbose(f"{desc}", indent=1)
            m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if m:
                log_verbose(f"Pattern matched", indent=2)
                price_text = m.group(1).strip()
                log_verbose(f"Matched text: '{price_text[:50]}'", indent=2)
                if 'priceText' in pattern:
                    return price_text
                else:
                    pm = re.search(r'([0-9][ 0-9]* kr)', price_text.replace('', ' '))
                    if pm:
                        log_verbose(f"Cleaned price: '{pm.group(1).strip()}'", indent=2)
                        return pm.group(1).strip()
            else:
                log_verbose("Pattern did not match", indent=2)

        # Fallback to DOM parsing
        log_verbose("Trying fallback: DOM parsing near 'Til salgs' header", indent=1)
        for header in soup.find_all('h2'):
            if 'Til salgs' in header.get_text(strip=True):
                log_verbose("Found 'Til salgs' header", indent=2)
                parent = header.find_parent()
                if parent:
                    p = parent.find('p', class_='h2')
                    if p:
                        text = p.get_text(strip=True)
                        log_verbose(f"Found p.h2: '{text[:100]}'", indent=2)
                        m = re.search(r'([0-9][ 0-9]* kr)', text.replace('', ' '))
                        if m:
                            log_verbose(f"DOM fallback matched: '{m.group(1).strip()}'", indent=2)
                            return m.group(1).strip()

        log_verbose("All recommerce parsing attempts failed", indent=1)
        return None


class EmailNotifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def send_price_change(self, url: str, old_price: Optional[str],
                          new_price: str) -> bool:
        if not self.config.is_valid():
            print(" Email config incomplete, skipping notification")
            return False
        try:
            msg = EmailMessage()
            msg['Subject'] = f'Price Change Alert: {new_price}'
            msg['From'] = self.config.email_from
            msg['To'] = self.config.email_to
            body = (
                f"Price change detected for Finn.no listing:\n\n"
                f"URL: {url}\nOld: {old_price or 'N/A'}\nNew: {new_price}\n"
            )
            msg.set_content(body)
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(self.config.smtp_user, self.config.smtp_pass)
                smtp.send_message(msg)
            print(f" Notification sent to {self.config.email_to}")
            return True
        except Exception as e:
            print(f" Failed to send email: {e}")
            return False


def read_urls(filepath: Path) -> list:
    if not filepath.exists():
        print(f"Error: URLs file not found: {filepath}")
        return []
    try:
        content = filepath.read_text()
        return [line.strip() for line in content.splitlines()
                if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"Error reading URLs: {e}")
        return []


def fetch_and_parse(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch URL and parse price with verbose logging.
    Returns (price, error_message) tuple.
    """
    log_verbose("=" * 60)
    log_verbose(f"Fetching: {url}")
    category = FinnNoParser.detect_category(url)
    log_verbose(f"Detected category: {category}")

    # HTTP Request with detailed logging
    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        log_verbose(f"HTTP Status: {response.status_code}")
        log_verbose(f"Content length: {len(response.text)} bytes")

        # Save HTML for debugging if DEBUG=1
        debug_file = save_debug_html(url, response.text, category)
        if debug_file:
            log_verbose(f"Full HTML saved to: {debug_file}", indent=1)

        response.raise_for_status()
    except requests.HTTPError as e:
        log_verbose(f"HTTP Error: {response.status_code}")
        error_msg = f"Request failed: HTTP {response.status_code}"
        if response.status_code == 403:
            error_msg += "\n -> Page may be blocking automated requests"
            log_verbose(" -> Page may be blocking automated requests", indent=1)
        elif response.status_code == 404:
            error_msg += "\n -> Page not found"
            log_verbose(" -> Page not found", indent=1)
        return None, error_msg
    except requests.Timeout as e:
        log_verbose(f"Request Timeout: {e}")
        return None, f"Request failed: Connection timeout after {HTTP_TIMEOUT}s"
    except requests.RequestException as e:
        log_verbose(f"Request Exception: {e}")
        return None, f"Request failed: {e}"

    # Parse price with verbose logging
    try:
        price, error = FinnNoParser.parse_price(response.text, category, url)
        if error:
            log_verbose(f"Parsing failed: {error}")
        return price, error
    except Exception as e:
        log_verbose(f"Unexpected parsing error: {e}")
        log_verbose(f"Error type: {type(e).__name__}", indent=1)
        import traceback
        log_verbose(f"Traceback: {traceback.format_exc()}", indent=1)
        return None, f"Parsing error: {e}"


def run_check(history: PriceHistory, notifier: EmailNotifier,
              config: Config) -> int:
    """Run a single check cycle. Returns number of price changes."""
    urls = read_urls(URLS_FILE)
    if not urls:
        print("No URLs to process")
        return 0

    print(f"Processing {len(urls)} URLs...\n")
    changed = []

    for url in urls:
        print(f"URL: {url}")
        current, error = fetch_and_parse(url)
        if error:
            print(f" Error: {error}")
            continue
        print(f" Current price: {current}")
        last = history.get_last_price(url)
        if last is None:
            print(" First entry, no comparison")
        elif current != last:
            print(f" PRICE CHANGED: {last} -> {current}")
            changed.append((url, last, current))
        else:
            print(f" Price unchanged: {current}")
        history.add_entry(url, current)
        print()

    history.save()
    if changed:
        print(f"Found {len(changed)} price change(s)")
        for url, old, new in changed:
            notifier.send_price_change(url, old, new)
    else:
        print("No price changes detected")

    return len(changed)


def main() -> int:
    parser = argparse.ArgumentParser(description='Finn.no Price Monitor')
    parser.add_argument('--run', action='store_true',
                        help='Execute with network requests')
    parser.add_argument('--schedule-mode', choices=['once', 'loop'],
                        default=os.environ.get('SCHEDULE_MODE', 'once'),
                        help='Run once and exit, or loop continuously')
    parser.add_argument('--check-interval-hours', type=float,
                        default=float(os.environ.get('CHECK_INTERVAL_HOURS', 4)),
                        help='Hours between checks in loop mode (1-168)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output (same as DEBUG=1)')
    args = parser.parse_args()

    global DEBUG
    if args.verbose:
        DEBUG = True

    if not args.run:
        print("Finn.no Price Monitor")
        print("Add --run flag to execute with network requests")
        print(f"DATA_DIR: {DATA_DIR}")
        print(f"URLS_FILE: {URLS_FILE}")
        print(f"HISTORY_FILE: {HISTORY_FILE}")
        print(f"DEBUG: {DEBUG}")
        print(f"DEBUG_DUMPS_DIR: {DEBUG_DUMPS_DIR}")
        return 0

    # Validate check_interval_hours
    if args.check_interval_hours < 1 or args.check_interval_hours > 168:
        print(f"Error: --check-interval-hours must be between 1 and 168, "
              f"got {args.check_interval_hours}")
        return 1

    config = Config()
    history = PriceHistory(HISTORY_FILE)
    notifier = EmailNotifier(config)

    if args.schedule_mode == 'once':
        run_check(history, notifier, config)
        return 0
    else:
        # Loop mode
        try:
            while True:
                print("\n--- Starting new check cycle ---\n")
                run_check(history, notifier, config)
                hours = args.check_interval_hours
                seconds = hours * 3600
                print(f"\nWaiting {hours} hours until next check...")
                print("Press Ctrl+C to shut down")
                time.sleep(seconds)
        except KeyboardInterrupt:
            print("\nShutting down...")
            return 0


if __name__ == '__main__':
    sys.exit(main())
