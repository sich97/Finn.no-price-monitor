"""
Pytest configuration and fixtures for the Finn.no Price Monitor test suite.

This module provides fixtures for testing the price monitoring service,
including HTML fixtures, temporary data directories, mock configurations,
and sample price history data in various formats.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory path."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def tests_dir(project_root: Path) -> Path:
    """Return the tests directory path."""
    return project_root / "tests"


@pytest.fixture(scope="session")
def fixtures_dir(tests_dir: Path) -> Path:
    """Return the fixtures directory path containing HTML sample files."""
    return tests_dir / "fixtures"


# ============================================================================
# HTML Fixture Loaders
# ============================================================================

@pytest.fixture(scope="session")
def realestate_html(fixtures_dir: Path) -> str:
    """
    Load the real estate listing HTML fixture.

    Returns:
        Raw HTML content from a Finn.no real estate listing page.
    """
    fixture_path = fixtures_dir / "20260208_085719_realestate_https___www_finn_no_realestate_homes_ad_html_finnk.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def mobility_html(fixtures_dir: Path) -> str:
    """
    Load the mobility/motor vehicle listing HTML fixture.

    Returns:
        Raw HTML content from a Finn.no mobility listing page.
    """
    fixture_path = fixtures_dir / "20260208_085719_mobility_https___www_finn_no_mobility_item_447730470.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def recommerce_html(fixtures_dir: Path) -> str:
    """
    Load the recommerce/used item listing HTML fixture.

    Returns:
        Raw HTML content from a Finn.no recommerce listing page.
    """
    fixture_path = fixtures_dir / "20260208_085719_recommerce_https___www_finn_no_recommerce_forsale_item_445195.html"
    return fixture_path.read_text(encoding="utf-8")


# ============================================================================
# Temporary Environment Fixtures
# ============================================================================

@pytest.fixture
def temp_data_dir() -> Path:
    """
    Create a temporary directory for DATA_DIR.

    Provides an isolated temporary directory that simulates the /data
    directory used in production/Docker environments. Automatically
    cleaned up after test completion.

    Yields:
        Path to the temporary data directory.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_path = Path(tmp_dir)
        yield data_path


@pytest.fixture
def data_dir_with_files(temp_data_dir: Path) -> Path:
    """
    Create a temporary DATA_DIR with urls.txt and price_history.json files.

    Returns a temporary data directory pre-populated with empty/minimal
    versions of the required data files.

    Yields:
        Path to the temporary data directory with files.
    """
    # Create empty urls.txt
    urls_file = temp_data_dir / "urls.txt"
    urls_file.write_text("", encoding="utf-8")

    # Create empty price_history.json
    history_file = temp_data_dir / "price_history.json"
    history_file.write_text("{}", encoding="utf-8")

    yield temp_data_dir


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_config(monkeypatch) -> dict[str, str]:
    """
    Provide mock SMTP configuration via environment variables.

    Sets test SMTP settings as environment variables that take precedence
    over config files. Automatically cleaned up after test.

    Note: Config class uses SMTP_USER (not SMTP_USERNAME) and 
    SMTP_PASS (not SMTP_PASSWORD).

    Returns:
        Dictionary containing test SMTP configuration values.
    """
    config = {
        "SMTP_HOST": "smtp.test.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "test_user@example.com",
        "SMTP_PASS": "test_password_123",
        "EMAIL_FROM": "test_sender@example.com",
        "EMAIL_TO": "test_recipient@example.com",
    }

    for key, value in config.items():
        monkeypatch.setenv(key, value)

    return config


@pytest.fixture
def mock_config_with_port_as_int(mock_config: dict[str, str], monkeypatch) -> dict[str, Any]:
    """
    Provide mock SMTP configuration with SMTP_PORT as integer.

    Some components may expect SMTP_PORT as an integer. This fixture
    provides the same configuration but with SMTP_PORT as int.

    Returns:
        Dictionary with SMTP_PORT as integer.
    """
    config = mock_config.copy()
    config["SMTP_PORT"] = 587  # Config class uses strings from env but converts to int
    return config


# ============================================================================
# PriceHistory Fixtures
# ============================================================================

@pytest.fixture
def price_history_fixture(data_dir_with_files: Path) -> "PriceHistory":
    """
    Create a PriceHistory instance pointing to a temporary file.

    Provides an isolated PriceHistory instance for testing that operates
    on temporary files, preventing test pollution.

    Note: Import of PriceHistory is deferred to avoid import-time dependencies.

    Returns:
        PriceHistory instance configured to use temporary data directory.
    """
    # Deferred import to avoid circular dependencies
    from price_fetcher import PriceHistory

    return PriceHistory(str(data_dir_with_files))


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_realestate_url() -> str:
    """Return a sample real estate listing URL."""
    return "https://www.finn.no/realestate/homes/ad.html?finnkode=12345"


@pytest.fixture
def sample_mobility_url() -> str:
    """Return a sample mobility/motor vehicle listing URL."""
    return "https://www.finn.no/mobility/item/447730470"


@pytest.fixture
def sample_recommerce_url() -> str:
    """Return a sample recommerce/used item listing URL."""
    return "https://www.finn.no/recommerce/forsale/item/445195"


@pytest.fixture(params=["realestate", "mobility", "recommerce"])
def listing_category(request) -> str:
    """
    Parametrize tests across all three listing categories.

    Yields: "realestate", "mobility", or "recommerce"
    """
    return request.param


@pytest.fixture
def sample_listing_url(listing_category: str) -> str:
    """
    Return a sample URL for the parameterized listing category.
    """
    urls = {
        "realestate": "https://www.finn.no/realestate/homes/ad.html?finnkode=12345",
        "mobility": "https://www.finn.no/mobility/item/447730470",
        "recommerce": "https://www.finn.no/recommerce/forsale/item/445195",
    }
    return urls[listing_category]


# ============================================================================
# Old String Format Fixtures (Legacy Migration Testing)
# ============================================================================

@pytest.fixture
def price_history_old_string_format() -> dict[str, Any]:
    """
    Sample price history data in legacy format.

    Old format uses alternating price integer and timestamp string.
    Used for testing migration from old format to new dict format.

    Returns:
        Dictionary with URLs as keys and old-format price history as lists.
    """
    return {
        "https://www.finn.no/realestate/homes/ad.html?finnkode=12345": [
            5000000, "2026-02-01T10:00:00",
            4900000, "2026-02-05T10:00:00",
            4800000, "2026-02-08T10:00:00"
        ],
        "https://www.finn.no/mobility/item/447730470": [
            150000, "2026-02-06T14:30:00",
            145000, "2026-02-08T09:15:00"
        ]
    }


@pytest.fixture
def price_history_with_single_string_price() -> dict[str, Any]:
    """
    Price history with single old-format entry (edge case for migration).

    Returns:
        Dictionary simulating a price history that needs migration
        from old alternating format to new dict format.
    """
    return {
        "https://www.finn.no/recommerce/forsale/item/445195": [
            7500, "2026-02-08T08:57:19"
        ]
    }


# ============================================================================
# New Dict Format Fixtures (Current Format)
# ============================================================================

@pytest.fixture
def sample_price_entry_realestate() -> dict[str, Any]:
    """
    Sample price entry in current dict format for real estate.

    Real estate uses "Totalpris" (total price) combining downpayment,
    remaining mortgage, and fees.

    Returns:
        Dict with price, title, and timestamp fields.
    """
    return {
        "price": 4800000,
        "title": "Pen leilighet i sentrum - 3 roms med balkong",
        "timestamp": "2026-02-08T10:00:00"
    }


@pytest.fixture
def sample_price_entry_mobility() -> dict[str, Any]:
    """
    Sample price entry in current dict format for mobility.

    Mobility (motor vehicles) also uses "Totalpris" format.

    Returns:
        Dict with price, title, and timestamp fields.
    """
    return {
        "price": 145000,
        "title": "BMW 3-serie 320d xDrive Touring",
        "timestamp": "2026-02-08T09:15:00"
    }


@pytest.fixture
def sample_price_entry_recommerce() -> dict[str, Any]:
    """
    Sample price entry in current dict format for recommerce.

    Recommerce has single price ("Til salgs" price).

    Returns:
        Dict with price, title, and timestamp fields.
    """
    return {
        "price": 7500,
        "title": "PlayStation 5 med to kontrollere",
        "timestamp": "2026-02-08T08:57:19"
    }


@pytest.fixture
def price_history_current_format(
    sample_price_entry_realestate: dict,
    sample_price_entry_mobility: dict,
    sample_price_entry_recommerce: dict,
) -> dict[str, Any]:
    """
    Complete price history data in current dict format (post-migration).

    Represents the expected structure after all data has been migrated
    from old string format to new dict format.

    Note: PriceHistory stores data as a flat list directly under each URL,
    not nested under a "prices" key.

    Returns:
        Dictionary with all listing types in current format.
    """
    return {
        "https://www.finn.no/realestate/homes/ad.html?finnkode=12345": [
            {"price": 5000000, "title": "Pen leilighet i sentrum", "timestamp": "2026-02-01T10:00:00"},
            {"price": 4900000, "title": "Pen leilighet i sentrum - prisreduksjon!", "timestamp": "2026-02-05T10:00:00"},
            {"price": 4800000, "title": "Pen leilighet i sentrum - 3 roms med balkong", "timestamp": "2026-02-08T10:00:00"},
        ],
        "https://www.finn.no/mobility/item/447730470": [
            {"price": 150000, "title": "BMW 3-serie 320d xDrive Touring", "timestamp": "2026-02-06T14:30:00"},
            {"price": 145000, "title": "BMW 3-serie 320d xDrive Touring", "timestamp": "2026-02-08T09:15:00"},
        ],
        "https://www.finn.no/recommerce/forsale/item/445195": [
            {"price": 7500, "title": "PlayStation 5 med to kontrollere", "timestamp": "2026-02-08T08:57:19"},
        ]
    }


# ============================================================================
# Price Change Scenarios
# ============================================================================

@pytest.fixture
def price_history_with_no_changes() -> dict[str, Any]:
    """
    Price history where no prices have changed (no email expected).

    Returns:
        Dict with stable prices across all listings.
    """
    return {
        "https://www.finn.no/recommerce/forsale/item/445195": [
            {"price": 7500, "title": "PlayStation 5 med to kontrollere", "timestamp": "2026-02-08T08:57:19"},
        ]
    }


@pytest.fixture
def price_history_with_price_increase() -> dict[str, Any]:
    """
    Price history where price has increased.

    Returns:
        Dict with increasing price trend.
    """
    return {
        "https://www.finn.no/recommerce/forsale/item/445195": [
            {"price": 7500, "title": "PlayStation 5 med to kontrollere", "timestamp": "2026-02-08T08:57:19"},
            {"price": 8000, "title": "PlayStation 5 med to kontrollere (inkludert spill!)", "timestamp": "2026-02-08T11:14:11"},
        ]
    }


@pytest.fixture
def price_history_with_new_listing() -> dict[str, Any]:
    """
    New listing with no prior price history.

    Returns:
        Empty history dict simulating a brand new URL.
    """
    return {}


# ============================================================================
# Edge Case Fixtures
# ============================================================================

@pytest.fixture
def empty_price_history() -> dict[str, Any]:
    """Return an empty price history dict."""
    return {}


@pytest.fixture
def malformed_html() -> str:
    """
    Malformed/broken HTML content for error handling tests.

    Returns:
        String containing invalid HTML.
    """
    return '<html><body><div class="unclosed"'


@pytest.fixture
def empty_html() -> str:
    """Return empty HTML content."""
    return ""


@pytest.fixture
def html_with_missing_selectors() -> str:
    """
    Valid HTML but missing Finn.no specific selectors.

    Used to test graceful handling when expected elements are not found.

    Returns:
        Generic HTML without Finn.no structure.
    """
    return """
    <html>
    <body>
        <div class="some-random-content">
            <h1>This is not a Finn.no page</h1>
            <p>No price information here</p>
        </div>
    </body>
    </html>
    """


# ============================================================================
# SMTP Mocking Fixtures
# ============================================================================

@pytest.fixture
def mock_smtp_server(monkeypatch):
    """
    Mock SMTP server for email notification tests.

    Prevents actual email sending during tests and captures
    sent messages for verification. EmailNotifier uses send_message(),
    not sendmail(), so we mock send_message.

    Yields:
        List that will contain captured sent messages.
    """
    import smtplib
    from email.mime.text import MIMEText
    from unittest.mock import MagicMock

    sent_messages = []
    mock_smtp = MagicMock()

    def mock_send_message(msg):
        # msg is a MIMEText or MIMEMultipart object
        sent_messages.append({
            "from": msg.get('From'),
            "to": msg.get('To'),
            "subject": msg.get('Subject'),
            "message": msg.as_string()
        })
        return {}

    mock_smtp.send_message = mock_send_message
    mock_smtp.starttls = MagicMock()
    mock_smtp.login = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    monkeypatch.setattr(smtplib, "SMTP", lambda *args, **kwargs: mock_smtp)

    yield sent_messages


# ============================================================================
# URL List Fixtures
# ============================================================================

@pytest.fixture
def sample_urls_file_content() -> str:
    """
    Sample content for urls.txt file.

    Returns:
        Newline-separated URLs for testing.
    """
    return """https://www.finn.no/realestate/homes/ad.html?finnkode=12345
https://www.finn.no/mobility/item/447730470
https://www.finn.no/recommerce/forsale/item/445195
"""


@pytest.fixture
def sample_urls_with_empty_lines() -> str:
    """
    Sample URLs with empty lines and whitespace (common edge case).

    Returns:
        URLs with various whitespace issues to test robust parsing.
    """
    return """
https://www.finn.no/realestate/homes/ad.html?finnkode=12345

https://www.finn.no/mobility/item/447730470

https://www.finn.no/recommerce/forsale/item/445195

"""


# ============================================================================
# Debug/Environment Fixtures
# ============================================================================

@pytest.fixture
def debug_enabled(monkeypatch):
    """
    Enable DEBUG mode for testing debug functionality.

    Sets DEBUG environment variable and cleans up after test.
    """
    monkeypatch.setenv("DEBUG", "1")
    yield True
    # Cleanup is automatic via monkeypatch fixture


@pytest.fixture
def debug_disabled(monkeypatch):
    """
    Ensure DEBUG mode is disabled.

    Explicitly unsets DEBUG environment variable.
    """
    monkeypatch.delenv("DEBUG", raising=False)
    yield False
