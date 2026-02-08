#!/usr/bin/env python3
"""Finn.no Price Monitor v1.1.0 - Combined emails and title tracking"""

import argparse
import json
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional, Tuple, Union, Dict, List, Any

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(os.environ.get('DATA_DIR', Path(__file__).parent))
APP_DIR = Path(__file__).parent
DEBUG = os.environ.get('DEBUG', '0').lower() in ('1', 'true', 'yes', 'on')
DEBUG_DUMPS_DIR = DATA_DIR / 'debug_dumps'

if DEBUG:
    DEBUG_DUMPS_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR.mkdir(parents=True, exist_ok=True)
URLS_FILE = DATA_DIR / 'urls.txt'
HISTORY_FILE = DATA_DIR / 'price_history.json'
CONFIG_FILE = DATA_DIR / 'config.env' if (DATA_DIR / 'config.env').exists() else APP_DIR / 'config.env'

HTTP_TIMEOUT = 30
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def get_timestamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def log_verbose(message: str, indent: int = 0) -> None:
    prefix = ' ' * (indent * 2)
    print(f"[{get_timestamp()}] {prefix}{message}")

def save_debug_html(url: str, html: str, category: str) -> Optional[Path]:
    if not DEBUG:
        return None
    try:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        safe_url = re.sub(r'[^a-zA-Z0-9]', '_', url[:50])
        filepath = DEBUG_DUMPS_DIR / f"{timestamp}_{category}_{safe_url}.html"
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
        for k, v in os.environ.items():
            if k == 'SMTP_HOST': self.smtp_host = v
            elif k == 'SMTP_PORT': self.smtp_port = int(v)
            elif k == 'SMTP_USER': self.smtp_user = v
            elif k == 'SMTP_PASS': self.smtp_pass = v
            elif k == 'EMAIL_FROM': self.email_from = v
            elif k == 'EMAIL_TO': self.email_to = v
        
        if CONFIG_FILE.exists():
            try:
                for line in CONFIG_FILE.read_text().splitlines():
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if not os.environ.get(k):
                            if k == 'SMTP_HOST': self.smtp_host = v
                            elif k == 'SMTP_PORT': self.smtp_port = int(v)
                            elif k == 'SMTP_USER': self.smtp_user = v
                            elif k == 'SMTP_PASS': self.smtp_pass = v
                            elif k == 'EMAIL_FROM': self.email_from = v
                            elif k == 'EMAIL_TO': self.email_to = v
            except Exception as e:
                print(f"Warning: Failed to load config: {e}")
    
    def is_valid(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_pass, self.email_from, self.email_to])

class PriceHistory:
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._load()
    
    def _load(self) -> None:
        if self.filepath.exists():
            try:
                raw = json.loads(self.filepath.read_text())
                self._data = self._migrate(raw)
            except Exception as e:
                print(f"Warning: Could not load history: {e}")
    
    def _migrate(self, data: dict) -> Dict[str, List[Dict[str, Any]]]:
        migrated: Dict[str, List[Dict[str, Any]]] = {}
        for url, entries in data.items():
            migrated[url] = []
            i = 0
            while i < len(entries):
                entry = entries[i]
                if isinstance(entry, dict) and 'price' in entry:
                    migrated[url].append(entry)
                    i += 1
                elif isinstance(entry, (int, float)):
                    price = int(entry) if isinstance(entry, (int, float)) else 0
                    ts = entries[i+1] if i+1 < len(entries) else datetime.now(timezone.utc).isoformat()
                    migrated[url].append({'price': price, 'title': None, 'timestamp': ts})
                    i += 2
                else:
                    i += 1
        return migrated
    
    def save(self) -> None:
        self.filepath.write_text(json.dumps(self._data, indent=2))
    
    def get_last(self, url: str) -> Tuple[Optional[int], Optional[str]]:
        hist = self._data.get(url, [])
        if hist:
            latest = hist[-1]
            return latest.get('price'), latest.get('title')
        return None, None
    
    def add(self, url: str, price: int, title: Optional[str]) -> None:
        if url not in self._data:
            self._data[url] = []
        self._data[url].append({
            'price': price,
            'title': title,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

class FinnNoParser:
    @staticmethod
    def _parse_price_value(price_str: str) -> Optional[int]:
        if not price_str:
            return None
        cleaned = price_str.replace('kr', '').replace('\xa0', ' ').strip()
        numeric = cleaned.replace(' ', '')
        try:
            return int(numeric)
        except ValueError:
            return None
    
    @staticmethod
    def _format_price(price: Optional[int]) -> str:
        if price is None:
            return 'N/A'
        return f"{price:,} kr".replace(',', ' ')
    
    @staticmethod
    def detect_category(url: str) -> str:
        if '/realestate/' in url: return 'realestate'
        elif '/mobility/' in url: return 'mobility'
        elif '/recommerce/' in url: return 'recommerce'
        return 'unknown'
    
    @staticmethod
    def _normalize(text: str) -> str:
        return text.replace('\xa0', ' ')
    
    @staticmethod
    def _parse_title(soup: BeautifulSoup, category: str) -> Optional[str]:
        selectors = {
            'realestate': ['h1', 'h1.t1', '[data-testid="object-title"]'],
            'mobility': ['h1', 'h1.t1'],
            'recommerce': ['h1', 'h1.t1']
        }
        for sel in selectors.get(category, ['h1']):
            elem = soup.select_one(sel)
            if elem:
                title = elem.get_text(strip=True)
                title = re.sub(r'^(Til salgs|Utleie|Solgt)\s*[-–]?\s*', '', title, flags=re.I)
                if title and len(title) > 3:
                    return title
        return None
    
    @staticmethod
    def parse_listing(html: str, category: str, url: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        soup = BeautifulSoup(html, 'html.parser')
        title = FinnNoParser._parse_title(soup, category)
        
        if category == 'realestate':
            price_str = FinnNoParser._parse_realestate_price(soup, html)
        elif category == 'mobility':
            price_str = FinnNoParser._parse_mobility_price(soup, html)
        elif category == 'recommerce':
            price_str = FinnNoParser._parse_recommerce_price(html, soup)
        else:
            return None, title, f"Unknown category: {category}"
        
        if not price_str:
            return None, title, "Could not extract price"
        
        price = FinnNoParser._parse_price_value(price_str)
        if price is None:
            return None, title, f"Failed to parse: {price_str}"
        
        return price, title, None
    
    @staticmethod
    def _parse_realestate_price(soup: BeautifulSoup, html: str) -> Optional[str]:
        elem = soup.find(attrs={'data-testid': 'pricing-total-price'})
        if elem:
            m = re.search(r'([0-9][ 0-9]* kr)', FinnNoParser._normalize(elem.get_text(strip=True)))
            if m:
                return m.group(1).strip()
        for dt in soup.find_all(['dt', 'p', 'span']):
            if 'Totalpris' in dt.get_text():
                parent = dt.find_parent()
                if parent:
                    m = re.search(r'([0-9][ 0-9]* kr)', FinnNoParser._normalize(parent.get_text()))
                    if m:
                        return m.group(1).strip()
        return None
    
    @staticmethod
    def _parse_mobility_price(soup: BeautifulSoup, html: str) -> Optional[str]:
        for el in soup.find_all(['p', 'span', 'div']):
            if el.get_text(strip=True) == 'Totalpris':
                parent = el.find_parent()
                if parent:
                    span = parent.find('span', class_='t2')
                    if span:
                        m = re.search(r'([0-9][ 0-9]* kr)', FinnNoParser._normalize(span.get_text(strip=True)))
                        if m:
                            return m.group(1).strip()
        for span in soup.find_all('span', class_='t2'):
            if 'kr' in span.get_text():
                m = re.search(r'([0-9][ 0-9]* kr)', FinnNoParser._normalize(span.get_text(strip=True)))
                if m:
                    return m.group(1).strip()
        return None
    
    @staticmethod
    def _parse_recommerce_price(html: str, soup: BeautifulSoup) -> Optional[str]:
        patterns = [
            r'Til\s+salgs.*?<p[^>]*class="[^"]*m-0[^"]*h2[^"]*"[^>]*>([^<]*[0-9][ 0-9]*\s*kr)</p>',
            r'"priceText"\s*:\s*"([0-9][ 0-9]* kr)"',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, re.I | re.DOTALL)
            if m:
                price_text = m.group(1).strip()
                if 'priceText' in pattern:
                    return price_text
                pm = re.search(r'([0-9][ 0-9]* kr)', FinnNoParser._normalize(price_text))
                if pm:
                    return pm.group(1).strip()
        for header in soup.find_all('h2'):
            if 'Til salgs' in header.get_text(strip=True):
                parent = header.find_parent()
                if parent:
                    p = parent.find('p', class_='h2')
                    if p:
                        text = p.get_text(strip=True)
                        m = re.search(r'([0-9][ 0-9]* kr)', FinnNoParser._normalize(text))
                        if m:
                            return m.group(1).strip()
        return None

class EmailNotifier:
    def __init__(self, config: Config) -> None:
        self.config = config
    
    def send_changes(self, changes: List[Dict[str, Any]]) -> bool:
        if not changes:
            return True
        if not self.config.is_valid():
            print(" Email config incomplete")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            count = len(changes)
            msg['Subject'] = f'Price Monitor: {count} listing{"s" if count != 1 else ""} changed'
            msg['From'] = self.config.email_from
            msg['To'] = self.config.email_to
            
            msg.attach(MIMEText(self._text_body(changes), 'plain'))
            msg.attach(MIMEText(self._html_body(changes), 'html'))
            
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(self.config.smtp_user, self.config.smtp_pass)
                smtp.send_message(msg)
            
            print(f" Email sent: {count} change(s)")
            return True
        except Exception as e:
            print(f" Failed to send: {e}")
            return False
    
    def _text_body(self, changes: List[Dict[str, Any]]) -> str:
        lines = ["Price changes detected:", ""]
        for i, c in enumerate(changes, 1):
            title = c.get('title') or 'Unknown'
            old_p = FinnNoParser._format_price(c.get('old_price'))
            new_p = FinnNoParser._format_price(c.get('new_price'))
            lines.append(f"{i}. {title}")
            lines.append(f"   {old_p} → {new_p}")
            lines.append(f"   {c.get('url', '')}")
            lines.append("")
        lines.append("---\nFinn.no Price Monitor v1.1.0")
        return "\n".join(lines)
    
    def _html_body(self, changes: List[Dict[str, Any]]) -> str:
        rows = []
        for c in changes:
            title = c.get('title') or 'Unknown'
            old_p = c.get('old_price') or 0
            new_p = c.get('new_price') or 0
            diff = new_p - old_p if old_p else 0
            diff_str = f"{diff:+,} kr".replace(',', ' ') if old_p else "—"
            diff_color = "#c62828" if diff > 0 else "#2e7d32" if diff < 0 else "#666"
            display_title = title[:60] + ('...' if len(title) > 60 else '')
            rows.append(f"<tr><td>{display_title}</td>"
                       f"<td>{FinnNoParser._format_price(c.get('old_price'))}</td>"
                       f"<td><b>{FinnNoParser._format_price(new_p)}</b></td>"
                       f"<td style='color:{diff_color}'>{diff_str}</td>"
                       f"<td><a href='{c.get('url')}'>View</a></td></tr>")
        
        count = len(changes)
        return f"""<html><body style='font-family:sans-serif;max-width:700px'>
<h2>{'🔔' if count else '✓'} {count} Price Change(s)</h2>
<table border='0' cellpadding='8' style='border-collapse:collapse;width:100%'>
<tr style='background:#1976d2;color:white'><th>Listing</th><th>Old</th><th>New</th><th>Change</th><th>Link</th></tr>
{''.join(rows)}</table>
<p style='color:#666;font-size:12px'>v1.1.0</p></body></html>"""

def read_urls(filepath: Path) -> list:
    if not filepath.exists():
        return []
    try:
        return [l.strip() for l in filepath.read_text().splitlines() if l.strip() and not l.startswith('#')]
    except Exception as e:
        print(f"Error reading URLs: {e}")
        return []

def fetch_and_parse(url: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    category = FinnNoParser.detect_category(url)
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        save_debug_html(url, r.text, category)
        r.raise_for_status()
    except requests.HTTPError:
        return None, None, f"HTTP {r.status_code}"
    except requests.Timeout:
        return None, None, "Timeout"
    except Exception as e:
        return None, None, str(e)
    
    try:
        return FinnNoParser.parse_listing(r.text, category, url)
    except Exception as e:
        return None, None, f"Parse error: {e}"

def run_check(history: PriceHistory, notifier: EmailNotifier, config: Config) -> int:
    urls = read_urls(URLS_FILE)
    if not urls:
        print("No URLs to process")
        return 0
    
    print(f"Processing {len(urls)} URLs...\n")
    changes: List[Dict[str, Any]] = []
    
    for url in urls:
        print(f"URL: {url}")
        price, title, error = fetch_and_parse(url)
        
        if error:
            print(f" Error: {error}")
            continue
        
        print(f" Price: {FinnNoParser._format_price(price)}")
        if title:
            print(f" Title: {title[:60]}..." if len(title) > 60 else f" Title: {title}")
        
        last_price, last_title = history.get_last(url)
        
        if last_price is None:
            print(" First entry")
        elif price != last_price:
            print(f" ✓ CHANGED: {FinnNoParser._format_price(last_price)} → {FinnNoParser._format_price(price)}")
            changes.append({
                'url': url,
                'old_price': last_price,
                'new_price': price,
                'title': title or last_title or 'Unknown'
            })
        else:
            print(" Unchanged")
        
        history.add(url, price, title)
        print()
    
    history.save()
    
    if changes:
        print(f"Found {len(changes)} change(s)")
        notifier.send_changes(changes)
    else:
        print("No changes")
    
    return len(changes)

def main() -> int:
    p = argparse.ArgumentParser(description='Finn.no Price Monitor v1.1.0')
    p.add_argument('--run', action='store_true', help='Execute')
    p.add_argument('--schedule-mode', choices=['once', 'loop'], default=os.environ.get('SCHEDULE_MODE', 'once'))
    p.add_argument('--check-interval-hours', type=float, default=float(os.environ.get('CHECK_INTERVAL_HOURS', 4)))
    p.add_argument('-v', '--verbose', action='store_true')
    args = p.parse_args()
    
    global DEBUG
    if args.verbose:
        DEBUG = True
    
    if not args.run:
        print("Finn.no Price Monitor v1.1.0")
        return 0
    
    config = Config()
    history = PriceHistory(HISTORY_FILE)
    notifier = EmailNotifier(config)
    
    if args.schedule_mode == 'once':
        run_check(history, notifier, config)
        return 0
    else:
        try:
            while True:
                print("\n--- Starting check ---\n")
                run_check(history, notifier, config)
                time.sleep(int(args.check_interval_hours * 3600))
        except KeyboardInterrupt:
            print("\nShutting down...")
            return 0

if __name__ == '__main__':
    sys.exit(main())
