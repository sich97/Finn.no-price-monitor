#!/usr/bin/env python3
"""Finn.no Price Monitor"""

import argparse
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup


# Determine data directory from environment or fallback to app directory
DATA_DIR = Path(os.environ.get('DATA_DIR', Path(__file__).parent))
APP_DIR = Path(__file__).parent

# URL file is usually in app dir, but can be in data dir
URLS_FILE = DATA_DIR / 'urls.txt'
if not URLS_FILE.exists():
    URLS_FILE = APP_DIR / 'urls.txt'

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
        return all([self.smtp_host, self.smtp_user, self.smtp_pass, self.email_from, self.email_to])


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
    def parse_price(html: str, category: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        if category == 'realestate':
            return FinnNoParser._parse_realestate_price(soup)
        elif category == 'mobility':
            return FinnNoParser._parse_mobility_price(soup)
        elif category == 'recommerce':
            return FinnNoParser._parse_recommerce_price(html, soup)
        return None

    @staticmethod
    def _parse_realestate_price(soup: BeautifulSoup) -> Optional[str]:
        elem = soup.find(attrs={'data-testid': 'pricing-total-price'})
        if elem:
            text = elem.get_text(strip=True)
            m = re.search(r'([0-9][ 0-9]* kr)', text.replace('\xa0', ' '))
            if m:
                return m.group(1).strip()
        for dt in soup.find_all(['dt', 'p', 'span']):
            if 'Totalpris' in dt.get_text():
                parent = dt.find_parent()
                if parent:
                    m = re.search(r'([0-9][ 0-9]* kr)', parent.get_text().replace('\xa0', ' '))
                    if m:
                        return m.group(1).strip()
        return None

    @staticmethod
    def _parse_mobility_price(soup: BeautifulSoup) -> Optional[str]:
        for el in soup.find_all(['p', 'span', 'div']):
            if el.get_text(strip=True) == 'Totalpris':
                parent = el.find_parent()
                if parent:
                    span = parent.find('span', class_='t2')
                    if span:
                        text = span.get_text(strip=True)
                        m = re.search(r'([0-9][ 0-9]* kr)', text.replace('\xa0', ' '))
                        if m:
                            return m.group(1).strip()
        for span in soup.find_all('span', class_='t2'):
            text = span.get_text(strip=True)
            if 'kr' in text:
                m = re.search(r'([0-9][ 0-9]* kr)', text.replace('\xa0', ' '))
                if m:
                    return m.group(1).strip()
        return None

    @staticmethod
    def _parse_recommerce_price(html: str, soup: BeautifulSoup) -> Optional[str]:
        pattern = r'Til\s+salgs.*?<p[^>]*class="[^"]*m-0[^"]*h2[^"]*"[^>]*>([^<]*[0-9][ 0-9]*\s*kr)</p>'
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            price_text = m.group(1).strip()
            pm = re.search(r'([0-9][ 0-9]* kr)', price_text.replace('\xa0', ' '))
            if pm:
                return pm.group(1).strip()
        
        pattern2 = r'Til\s+salgs</h2>\s*<p[^>]*class="[^"]*h2[^"]*"[^>]*>([ 0-9]*kr)</'
        m = re.search(pattern2, html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        
        json_pattern = r'"priceText"\s*:\s*"([0-9][ 0-9]* kr)"'
        m = re.search(json_pattern, html)
        if m:
            return m.group(1).strip()
        
        for header in soup.find_all('h2'):
            if 'Til salgs' in header.get_text(strip=True):
                parent = header.find_parent()
                if parent:
                    p = parent.find('p', class_='h2')
                    if p:
                        text = p.get_text(strip=True)
                        m = re.search(r'([0-9][ 0-9]* kr)', text.replace('\xa0', ' '))
                        if m:
                            return m.group(1).strip()
        
        return None


class EmailNotifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def send_price_change(self, url: str, old_price: Optional[str], new_price: str) -> bool:
        if not self.config.is_valid():
            print("  Email config incomplete, skipping notification")
            return False
        try:
            msg = EmailMessage()
            msg['Subject'] = f'Price Change Alert: {new_price}'
            msg['From'] = self.config.email_from
            msg['To'] = self.config.email_to
            body = f"Price change detected for Finn.no listing:\n\nURL: {url}\nOld: {old_price or 'N/A'}\nNew: {new_price}\n"
            msg.set_content(body)
            with smtplib.SMTP(self.config.smtp_host, self.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(self.config.smtp_user, self.config.smtp_pass)
                smtp.send_message(msg)
            print(f"  Notification sent to {self.config.email_to}")
            return True
        except Exception as e:
            print(f"  Failed to send email: {e}")
            return False


def read_urls(filepath: Path) -> list:
    if not filepath.exists():
        print(f"Error: URLs file not found: {filepath}")
        return []
    try:
        content = filepath.read_text()
        return [line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"Error reading URLs: {e}")
        return []


def fetch_and_parse(url: str) -> tuple:
    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        category = FinnNoParser.detect_category(url)
        price = FinnNoParser.parse_price(response.text, category)
        if price is None:
            return None, f"Could not extract price for category: {category}"
        return price, None
    except requests.RequestException as e:
        return None, f"Request failed: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description='Finn.no Price Monitor')
    parser.add_argument('--run', action='store_true', help='Execute with network requests')
    args = parser.parse_args()

    if not args.run:
        print("Finn.no Price Monitor")
        print("Add --run flag to execute with network requests")
        print(f"DATA_DIR: {DATA_DIR}")
        print(f"URLS_FILE: {URLS_FILE}")
        print(f"HISTORY_FILE: {HISTORY_FILE}")
        return 0

    config = Config()
    history = PriceHistory(HISTORY_FILE)
    notifier = EmailNotifier(config)

    urls = read_urls(URLS_FILE)
    if not urls:
        print("No URLs to process")
        return 1

    print(f"Processing {len(urls)} URLs...\n")
    changed = []

    for url in urls:
        print(f"URL: {url}")
        current, error = fetch_and_parse(url)
        if error:
            print(f"  Error: {error}")
            continue
        print(f"  Current price: {current}")
        last = history.get_last_price(url)
        if last is None:
            print("  First entry, no comparison")
        elif current != last:
            print(f"  PRICE CHANGED: {last} -> {current}")
            changed.append((url, last, current))
        else:
            print(f"  Price unchanged: {current}")
        history.add_entry(url, current)
        print()

    history.save()
    if changed:
        print(f"Found {len(changed)} price change(s)")
        for url, old, new in changed:
            notifier.send_price_change(url, old, new)
    else:
        print("No price changes detected")
    return 0


if __name__ == '__main__':
    sys.exit(main())
