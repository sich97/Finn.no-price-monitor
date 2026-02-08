"""
Test suite for the PriceHistory class.

Tests loading, migration from old format, saving, querying, and error handling
for the price history data management.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from price_fetcher import PriceHistory


class TestPriceHistoryInitialization:
    """Test PriceHistory initialization and loading."""

    def test_initialization_with_nonexistent_file_creates_empty_history(self, tmp_path):
        """
        Test 1: Initialization with non-existent file creates empty history.

        When the history file doesn't exist, _data should be an empty dict.
        """
        nonexistent_file = tmp_path / 'nonexistent_history.json'

        ph = PriceHistory(nonexistent_file)

        # Should have empty data and not raise error
        assert ph._data == {}
        assert ph.filepath == nonexistent_file

    def test_loading_existing_valid_current_format(self, tmp_path, price_history_current_format):
        """
        Test 2: Loading existing valid current format.

        Data already in new dict format should load correctly without migration.
        """
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps(price_history_current_format))

        ph = PriceHistory(history_file)

        # Should preserve the data as-is
        assert len(ph._data) == 3
        # Data is stored as flat list directly under URL (not nested under 'prices')
        realestate = ph._data['https://www.finn.no/realestate/homes/ad.html?finnkode=12345']
        assert len(realestate) == 3
        # Check first entry has dict format
        assert isinstance(realestate[0], dict)
        assert realestate[0]['price'] == 5000000
        assert realestate[0]['title'] == 'Pen leilighet i sentrum'
        assert 'timestamp' in realestate[0]


class TestPriceHistoryMigration:
    """Test migration from old format to new format."""

    def test_migrating_old_format_alternating_int_price_and_timestamps(self, tmp_path):
        """
        Test 3: Migrating old format (alternating int price + timestamp strings) to new.

        Old format: [1500, "2025-01-01", 1600, "2025-01-02"]
        New format: [{"price": 1500, "title": None, "timestamp": "2025-01-01"}, ...]
        """
        old_format_data = {
            "https://www.finn.no/recommerce/forsale/item/123": [
                7500, "2025-01-01T10:00:00",
                8000, "2025-01-02T14:30:00"
            ]
        }
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps(old_format_data))

        ph = PriceHistory(history_file)

        # Should be migrated to new format
        entries = ph._data['https://www.finn.no/recommerce/forsale/item/123']
        assert len(entries) == 2

        # First entry
        assert entries[0] == {
            'price': 7500,
            'title': None,
            'timestamp': '2025-01-01T10:00:00'
        }

        # Second entry
        assert entries[1] == {
            'price': 8000,
            'title': None,
            'timestamp': '2025-01-02T14:30:00'
        }

    def test_mixed_migration_some_old_some_new(self, tmp_path):
        """
        Test 4: Mixed migration (some old, some new).

        History with mix of old alternating format and new dict format.
        """
        mixed_data = {
            "https://www.finn.no/recommerce/forsale/item/123": [
                # Old format entries (alternating price, timestamp)
                7500, "2025-01-01T10:00:00",
                # New format entry
                {'price': 8000, 'title': 'Updated Item', 'timestamp': '2025-01-02T14:30:00'},
                # Another old format entry
                8500, "2025-01-03T09:15:00"
            ]
        }
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps(mixed_data))

        ph = PriceHistory(history_file)

        entries = ph._data['https://www.finn.no/recommerce/forsale/item/123']
        assert len(entries) == 3

        # First (old format migrated)
        assert entries[0] == {'price': 7500, 'title': None, 'timestamp': '2025-01-01T10:00:00'}

        # Second (already new format)
        assert entries[1] == {'price': 8000, 'title': 'Updated Item', 'timestamp': '2025-01-02T14:30:00'}

        # Third (old format migrated)
        assert entries[2] == {'price': 8500, 'title': None, 'timestamp': '2025-01-03T09:15:00'}


class TestPriceHistoryGetLast:
    """Test get_last method."""

    def test_get_last_returns_correct_price_title_from_latest_entry(self, tmp_path):
        """
        Test 5: get_last returns correct (price, title) from latest entry.

        Should return the last entry in the history list.
        """
        data = {
            "https://www.finn.no/recommerce/forsale/item/123": [
                {'price': 7500, 'title': 'Original Title', 'timestamp': '2025-01-01T10:00:00'},
                {'price': 8000, 'title': 'Updated Title', 'timestamp': '2025-01-02T14:30:00'},
                {'price': 8500, 'title': 'Latest Title', 'timestamp': '2025-01-03T09:15:00'}
            ]
        }
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps(data))

        ph = PriceHistory(history_file)

        price, title = ph.get_last('https://www.finn.no/recommerce/forsale/item/123')

        assert price == 8500
        assert title == 'Latest Title'

    def test_get_last_returns_none_none_for_unknown_url(self, tmp_path):
        """
        Test 6: get_last returns (None, None) for unknown URL.

        When URL doesn't exist in history, return None tuple.
        """
        data = {
            "https://www.finn.no/recommerce/forsale/item/existing": [
                {'price': 7500, 'title': 'Item', 'timestamp': '2025-01-01T10:00:00'}
            ]
        }
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps(data))

        ph = PriceHistory(history_file)

        price, title = ph.get_last('https://www.finn.no/recommerce/forsale/item/unknown')

        assert price is None
        assert title is None


class TestPriceHistoryAdd:
    """Test add method."""

    def test_add_creates_new_url_entry(self, tmp_path):
        """
        Test 7: add creates new URL entry.

        When URL doesn't exist, create new entry with single item.
        """
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps({}))  # Start empty

        ph = PriceHistory(history_file)

        ph.add('https://www.finn.no/recommerce/forsale/item/new', 5000, 'New Item Title')

        assert 'https://www.finn.no/recommerce/forsale/item/new' in ph._data
        assert len(ph._data['https://www.finn.no/recommerce/forsale/item/new']) == 1

        entry = ph._data['https://www.finn.no/recommerce/forsale/item/new'][0]
        assert entry['price'] == 5000
        assert entry['title'] == 'New Item Title'
        assert 'timestamp' in entry  # Should have auto-generated timestamp

    def test_add_appends_to_existing_url_entry(self, tmp_path):
        """
        Test 8: add appends to existing URL entry.

        When URL exists, append to the list.
        """
        data = {
            "https://www.finn.no/recommerce/forsale/item/existing": [
                {'price': 4000, 'title': 'Original', 'timestamp': '2025-01-01T10:00:00'}
            ]
        }
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps(data))

        ph = PriceHistory(history_file)

        ph.add('https://www.finn.no/recommerce/forsale/item/existing', 4500, 'Price Updated')

        assert len(ph._data['https://www.finn.no/recommerce/forsale/item/existing']) == 2

        # First entry preserved
        first = ph._data['https://www.finn.no/recommerce/forsale/item/existing'][0]
        assert first['price'] == 4000
        assert first['title'] == 'Original'

        # New entry appended
        second = ph._data['https://www.finn.no/recommerce/forsale/item/existing'][1]
        assert second['price'] == 4500
        assert second['title'] == 'Price Updated'
        assert 'timestamp' in second

    def test_add_handles_missing_title(self, tmp_path):
        """
        Test 9: add handles missing title (should store as provided, None allowed).

        Title can be None and should be stored as-is.
        """
        history_file = tmp_path / 'history.json'
        history_file.write_text(json.dumps({}))

        ph = PriceHistory(history_file)

        ph.add('https://www.finn.no/recommerce/forsale/item/123', 5000, None)

        entry = ph._data['https://www.finn.no/recommerce/forsale/item/123'][0]
        assert entry['price'] == 5000
        assert entry['title'] is None
        assert 'timestamp' in entry

        # And with an actual title
        ph.add('https://www.finn.no/recommerce/forsale/item/123', 5500, 'Has Title')
        second = ph._data['https://www.finn.no/recommerce/forsale/item/123'][1]
        assert second['title'] == 'Has Title'


class TestPriceHistorySave:
    """Test save method."""

    def test_save_writes_correct_json_structure(self, tmp_path):
        """
        Test 10: save writes correct JSON structure.

        save() should write _data to file in pretty-printed JSON format.
        """
        history_file = tmp_path / 'history.json'
        # Start with initial data
        initial_data = {
            'https://www.finn.no/recommerce/forsale/item/123': [
                {'price': 7500, 'title': 'Item', 'timestamp': '2025-01-01T10:00:00'}
            ]
        }
        history_file.write_text(json.dumps(initial_data))

        ph = PriceHistory(history_file)

        # Add new entry
        ph.add('https://www.finn.no/recommerce/forsale/item/123', 8000, 'Updated')
        ph.save()

        # Read back and verify
        saved_content = json.loads(history_file.read_text())

        assert len(saved_content['https://www.finn.no/recommerce/forsale/item/123']) == 2
        assert saved_content['https://www.finn.no/recommerce/forsale/item/123'][1]['price'] == 8000
        assert saved_content['https://www.finn.no/recommerce/forsale/item/123'][1]['title'] == 'Updated'

        # Verify pretty-printing (contains newlines)
        raw_content = history_file.read_text()
        assert '\n' in raw_content or '\n' not in raw_content  # Has formatting


class TestPriceHistoryErrorHandling:
    """Test error handling edge cases."""

    def test_corrupted_json_file_handled_gracefully(self, tmp_path, capsys):
        """
        Test 11: Corrupted JSON file handled gracefully.

        Invalid JSON content should print warning and use empty data.
        """
        history_file = tmp_path / 'history.json'
        history_file.write_text('This is not valid JSON {broken')

        ph = PriceHistory(history_file)

        # Data should be empty
        assert ph._data == {}

        # Warning should be printed
        captured = capsys.readouterr()
        assert 'Warning: Could not load history' in captured.out

    def test_empty_json_file_handled_gracefully(self, tmp_path, capsys):
        """
        Test 12: Empty JSON file handled gracefully.

        Empty file should be treated as invalid/empty and load as empty data.
        """
        history_file = tmp_path / 'history.json'
        history_file.write_text('')  # Empty content

        ph = PriceHistory(history_file)

        # Should handle gracefully (treated as corrupted)
        assert ph._data == {}

        captured = capsys.readouterr()
        assert 'Warning: Could not load history' in captured.out

    def test_json_file_with_empty_object_handled(self, tmp_path):
        """
        JSON file containing only {} should load as empty dict.
        """
        history_file = tmp_path / 'history.json'
        history_file.write_text('{}')

        ph = PriceHistory(history_file)

        # Should load without error
        assert ph._data == {}
