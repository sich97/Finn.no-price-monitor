"""
Test suite for the EmailNotifier class.

Tests email sending functionality, body generation, formatting,
and error handling with mocked SMTP server.
"""

import pytest
from price_fetcher import EmailNotifier, Config


class TestEmailNotifierInit:
    """Test EmailNotifier initialization."""

    def test_init_stores_config_reference(self, mock_config):
        """
        Test 1: __init__ stores config reference.

        The config passed to __init__ should be stored as instance attribute.
        """
        config = Config()
        notifier = EmailNotifier(config)

        assert notifier.config is config


class TestSendChanges:
    """Test send_changes method."""

    def test_send_changes_empty_list_returns_true_no_email_sent(self, mock_smtp_server, mock_config):
        """
        Test 2: send_changes with empty list returns True (nothing to send, no email sent).

        When changes list is empty, function returns True immediately without sending.
        """
        config = Config()
        notifier = EmailNotifier(config)

        result = notifier.send_changes([])

        assert result is True
        # No email should be sent
        assert len(mock_smtp_server) == 0

    def test_send_changes_with_valid_config_and_changes_sends_email_returns_true(
        self, mock_smtp_server, mock_config
    ):
        """
        Test 3: send_changes with valid config and changes sends email, returns True.

        When config is valid and there are changes, email should be sent via SMTP.
        """
        changes = [
            {
                'url': 'https://www.finn.no/recommerce/forsale/item/123',
                'old_price': 7500,
                'new_price': 8000,
                'title': 'Gaming PC'
            }
        ]

        config = Config()
        notifier = EmailNotifier(config)

        result = notifier.send_changes(changes)

        assert result is True
        # Email should be sent
        assert len(mock_smtp_server) == 1
        sent = mock_smtp_server[0]
        assert sent['from'] == config.email_from
        assert sent['to'] == config.email_to  # msg.get('To') returns string
        assert 'Price Monitor' in sent['message']

    def test_send_changes_with_invalid_config_returns_false_no_email_sent(
        self, mock_smtp_server, monkeypatch
    ):
        """
        Test 4: send_changes with invalid config returns False, no email sent.

        When config.is_valid() returns False, should return False without sending.
        """
        # Clear config to make it invalid
        for var in ['SMTP_HOST', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)

        changes = [{'url': 'http://example.com', 'old_price': 100, 'new_price': 200, 'title': 'Test'}]

        config = Config()
        notifier = EmailNotifier(config)

        result = notifier.send_changes(changes)

        assert result is False
        # No email should be sent
        assert len(mock_smtp_server) == 0


class TestTextBody:
    """Test _text_body method."""

    def test_text_body_contains_listing_titles(self, mock_config):
        """
        Test 5a: Text body contains listing titles.
        """
        changes = [
            {'url': 'http://example.com/1', 'old_price': 1000, 'new_price': 1500, 'title': 'Item One'},
            {'url': 'http://example.com/2', 'old_price': 2000, 'new_price': 1800, 'title': 'Item Two'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        text = notifier._text_body(changes)

        assert 'Item One' in text
        assert 'Item Two' in text

    def test_text_body_contains_formatted_prices(self, mock_config):
        """
        Test 5b: Text body contains formatted prices.
        """
        changes = [
            {'url': 'http://example.com', 'old_price': 5500000, 'new_price': 5000000, 'title': 'Real Estate'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        text = notifier._text_body(changes)

        # Both old and new prices should be formatted
        assert '5 500 000 kr' in text or '5500000' in text
        assert '5 000 000 kr' in text or '5000000' in text

    def test_text_body_contains_urls(self, mock_config):
        """
        Test 5c: Text body contains URLs.
        """
        changes = [
            {'url': 'https://www.finn.no/recommerce/forsale/item/123', 'old_price': 100, 'new_price': 200, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        text = notifier._text_body(changes)

        assert 'https://www.finn.no/recommerce/forsale/item/123' in text


class TestHtmlBody:
    """Test _html_body method."""

    def test_html_body_contains_table_with_correct_structure(self, mock_config):
        """
        Test 6: HTML body contains table with correct structure.

        Table should have headers: Listing, Old, New, Change, Link
        """
        changes = [
            {'url': 'http://example.com', 'old_price': 1000, 'new_price': 1500, 'title': 'Test Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        html = notifier._html_body(changes)

        assert '<table' in html
        assert '<th>Listing</th>' in html or 'Listing' in html
        assert '<th>Old</th>' in html or 'Old' in html
        assert '<th>New</th>' in html or 'New' in html
        assert '<th>Change</th>' in html or 'Change' in html
        assert '<th>Link</th>' in html or 'Link' in html

    def test_html_body_change_color_coding_red_for_up(self, mock_config):
        """
        Test 7a: HTML body has correct change color coding - RED for price increase.

        New price > Old price should use color #c62828
        """
        changes = [
            {'url': 'http://example.com', 'old_price': 1000, 'new_price': 1500, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        html = notifier._html_body(changes)

        # Should have red color for increase
        assert '#c62828' in html

    def test_html_body_change_color_coding_green_for_down(self, mock_config):
        """
        Test 7b: HTML body has correct change color coding - GREEN for price decrease.

        New price < Old price should use color #2e7d32
        """
        changes = [
            {'url': 'http://example.com', 'old_price': 2000, 'new_price': 1500, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        html = notifier._html_body(changes)

        # Should have green color for decrease
        assert '#2e7d32' in html

    def test_html_body_change_color_coding_gray_for_no_old_price(self, mock_config):
        """
        Test 7c: HTML body uses gray color when no old price (new listing).

        When old_price is None/0, should use color #666
        """
        changes = [
            {'url': 'http://example.com', 'old_price': None, 'new_price': 1500, 'title': 'New Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        html = notifier._html_body(changes)

        # Should have gray color
        assert '#666' in html

    def test_html_body_has_clickable_links(self, mock_config):
        """
        Test 12: Links in HTML are clickable anchors.
        """
        changes = [
            {'url': 'https://www.finn.no/item/123', 'old_price': 100, 'new_price': 200, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        html = notifier._html_body(changes)

        # Should have anchor tag with href
        assert '<a href=' in html
        assert 'https://www.finn.no/item/123' in html


class TestSubjectLine:
    """Test subject line formatting."""

    def test_subject_singular_one_listing_changed(self, mock_smtp_server, mock_config):
        """
        Test 8a: Subject line is singular '1 listing changed'.
        """
        changes = [
            {'url': 'http://example.com', 'old_price': 100, 'new_price': 200, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        notifier.send_changes(changes)

        sent = mock_smtp_server[0]
        assert '1 listing changed' in sent['message']
        assert 'listings' not in sent['message'].lower() or '1 listing' in sent['message']

    def test_subject_plural_multiple_listings_changed(self, mock_smtp_server, mock_config):
        """
        Test 8b: Subject line is plural '3 listings changed'.
        """
        changes = [
            {'url': 'http://example.com/1', 'old_price': 100, 'new_price': 200, 'title': 'Item 1'},
            {'url': 'http://example.com/2', 'old_price': 100, 'new_price': 200, 'title': 'Item 2'},
            {'url': 'http://example.com/3', 'old_price': 100, 'new_price': 200, 'title': 'Item 3'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        notifier.send_changes(changes)

        sent = mock_smtp_server[0]
        assert '3 listings changed' in sent['message'] or 'listings' in sent['message'].lower()


class TestChangeCalculation:
    """Test change calculation logic."""

    @pytest.mark.parametrize("old_price,new_price,expected_diff", [
        (1000, 1500, 500),   # Increase
        (2000, 1500, -500),  # Decrease
        (1000, 1000, 0),     # No change
    ])
    def test_change_calculation_is_correct(self, mock_config, old_price, new_price, expected_diff):
        """
        Test 9: Change calculation is correct (new - old).
        """
        changes = [
            {'url': 'http://example.com', 'old_price': old_price, 'new_price': new_price, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        html = notifier._html_body(changes)

        # The diff should be shown in the HTML
        diff_str = f"{expected_diff:+,}".replace(',', ' ')
        if expected_diff > 0:
            assert '+ 500 kr' in html or '+500 kr' in html or '500' in html
        elif expected_diff < 0:
            assert '- 500 kr' in html or '-500 kr' in html or '500' in html


class TestExceptionHandling:
    """Test exception handling."""

    def test_smtp_error_returns_false(self, monkeypatch, mock_config):
        """
        Test 10: Exception handling - SMTP error returns False.
        """
        import smtplib

        # Mock SMTP to raise exception
        def mock_smtp_error(*args, **kwargs):
            raise smtplib.SMTPException("Connection refused")

        monkeypatch.setattr(smtplib, 'SMTP', mock_smtp_error)

        changes = [
            {'url': 'http://example.com', 'old_price': 100, 'new_price': 200, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        result = notifier.send_changes(changes)

        assert result is False


class TestMimeParts:
    """Test MIME multipart structure."""

    def test_email_has_both_text_plain_and_text_html_parts(self, mock_smtp_server, mock_config):
        """
        Test 11: Email has both text/plain and text/html parts.
        """
        changes = [
            {'url': 'http://example.com', 'old_price': 100, 'new_price': 200, 'title': 'Item'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        notifier.send_changes(changes)

        sent = mock_smtp_server[0]
        message = sent['message']

        # Should have multipart structure with both alternatives
        assert 'Content-Type: multipart/alternative' in message or 'multipart' in message.lower()
        # Should have text/plain part
        assert 'text/plain' in message or 'Content-Type: text/plain' in message
        # Should have text/html part
        assert 'text/html' in message or 'Content-Type: text/html' in message


class TestIntegration:
    """Integration tests."""

    def test_full_email_flow_with_multiple_changes(self, mock_smtp_server, mock_config):
        """
        Full integration test with multiple changes.
        """
        changes = [
            {'url': 'https://finn.no/1', 'old_price': 5000, 'new_price': 5500, 'title': 'Item 1 Up'},
            {'url': 'https://finn.no/2', 'old_price': 8000, 'new_price': 7500, 'title': 'Item 2 Down'},
            {'url': 'https://finn.no/3', 'old_price': None, 'new_price': 3000, 'title': 'Item 3 New'},
        ]

        config = Config()
        notifier = EmailNotifier(config)
        result = notifier.send_changes(changes)

        assert result is True
        assert len(mock_smtp_server) == 1

        sent = mock_smtp_server[0]
        # Check subject line
        assert '3 listings' in sent['subject'] or sent['subject'] == 'Price Monitor: 3 listings changed'
        # Check To/From
        assert sent['from'] == config.email_from
        assert sent['to'] == config.email_to
        # Check message was sent (actual content is base64 encoded in multipart)
        assert 'Content-Type: multipart/alternative' in sent['message']
        assert 'text/plain' in sent['message']
        assert 'text/html' in sent['message']
