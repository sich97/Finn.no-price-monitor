"""
Test suite for the Config class.

Tests configuration loading from environment variables and config.env files,
validation logic, and error handling.
"""

import os
from pathlib import Path

import pytest

from price_fetcher import Config


class TestConfigDefaults:
    """Test default initialization behavior."""

    def test_default_initialization_all_none_except_port(self, monkeypatch):
        """
        Test 1: Default initialization - all None except smtp_port=587.

        When no environment variables or config file exists,
        Config should initialize with None values and default port.
        """
        # Clear any existing env vars
        for var in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)
        # Ensure CONFIG_FILE doesn't exist by pointing to temp

        config = Config()

        assert config.smtp_host is None
        assert config.smtp_port == 587
        assert config.smtp_user is None
        assert config.smtp_pass is None
        assert config.email_from is None
        assert config.email_to is None


class TestConfigFromEnvironment:
    """Test loading configuration from environment variables."""

    def test_loading_from_environment_variables(self, monkeypatch):
        """
        Test 2: Loading from environment variables.

        All SMTP settings should be loaded from environment variables.
        """
        monkeypatch.setenv('SMTP_HOST', 'smtp.gmail.com')
        monkeypatch.setenv('SMTP_PORT', '465')
        monkeypatch.setenv('SMTP_USER', 'sender@gmail.com')
        monkeypatch.setenv('SMTP_PASS', 'secret_password')
        monkeypatch.setenv('EMAIL_FROM', 'sender@gmail.com')
        monkeypatch.setenv('EMAIL_TO', 'receiver@gmail.com')

        config = Config()

        assert config.smtp_host == 'smtp.gmail.com'
        assert config.smtp_port == 465
        assert config.smtp_user == 'sender@gmail.com'
        assert config.smtp_pass == 'secret_password'
        assert config.email_from == 'sender@gmail.com'
        assert config.email_to == 'receiver@gmail.com'


class TestConfigFromFile:
    """Test loading configuration from config.env file."""

    def test_loading_from_config_file(self, monkeypatch, tmp_path):
        """
        Test 3: Loading from config.env file.

        When environment variables are not set, Config should load from config.env.
        """
        # Clear env vars
        for var in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)

        # Create temp config file
        config_file = tmp_path / 'config.env'
        config_file.write_text("""SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASS=SG.xxxx
EMAIL_FROM=noreply@example.com
EMAIL_TO=admin@example.com
""")

        # Monkeypatch CONFIG_FILE path in price_fetcher
        monkeypatch.setattr('price_fetcher.CONFIG_FILE', config_file)

        config = Config()

        assert config.smtp_host == 'smtp.sendgrid.net'
        assert config.smtp_port == 587
        assert config.smtp_user == 'apikey'
        assert config.smtp_pass == 'SG.xxxx'
        assert config.email_from == 'noreply@example.com'
        assert config.email_to == 'admin@example.com'

    def test_environment_variables_override_config_file(self, monkeypatch, tmp_path):
        """
        Test 4: Environment variables override config file.

        Environment variables should take precedence over config file values.
        """
        # Set some env vars
        monkeypatch.setenv('SMTP_HOST', 'env-smtp.example.com')
        monkeypatch.setenv('SMTP_USER', 'env-user')
        # Leave others to be loaded from file
        monkeypatch.delenv('SMTP_PORT', raising=False)
        monkeypatch.delenv('SMTP_PASS', raising=False)
        monkeypatch.delenv('EMAIL_FROM', raising=False)
        monkeypatch.delenv('EMAIL_TO', raising=False)

        # Create config file with different values
        config_file = tmp_path / 'config.env'
        config_file.write_text("""SMTP_HOST=file-smtp.example.com
SMTP_PORT=465
SMTP_USER=file-user
SMTP_PASS=file-pass
EMAIL_FROM=file@example.com
EMAIL_TO=fileto@example.com
""")

        monkeypatch.setattr('price_fetcher.CONFIG_FILE', config_file)

        config = Config()

        # Env vars should take precedence
        assert config.smtp_host == 'env-smtp.example.com'  # from env
        assert config.smtp_user == 'env-user'  # from env
        # Others should come from file
        assert config.smtp_port == 465  # from file
        assert config.smtp_pass == 'file-pass'  # from file
        assert config.email_from == 'file@example.com'  # from file
        assert config.email_to == 'fileto@example.com'  # from file


class TestConfigValidation:
    """Test the is_valid() method."""

    def test_is_valid_true_when_all_required_fields_present(self, monkeypatch):
        """
        Test 5: is_valid=true when all required fields present.

        Required fields: smtp_host, smtp_user, smtp_pass, email_from, email_to
        """
        monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
        monkeypatch.setenv('SMTP_USER', 'user')
        monkeypatch.setenv('SMTP_PASS', 'pass')
        monkeypatch.setenv('EMAIL_FROM', 'from@example.com')
        monkeypatch.setenv('EMAIL_TO', 'to@example.com')

        config = Config()

        assert config.is_valid() is True

    @pytest.mark.parametrize("missing_field", [
        'SMTP_HOST',
        'SMTP_USER',
        'SMTP_PASS',
        'EMAIL_FROM',
        'EMAIL_TO'
    ])
    def test_is_valid_false_when_required_field_missing(self, monkeypatch, missing_field):
        """
        Test 6: is_valid=false when any required field missing.

        Test each required field being missing individually.
        """
        # Set all env vars first
        env_vars = {
            'SMTP_HOST': 'smtp.example.com',
            'SMTP_USER': 'user',
            'SMTP_PASS': 'pass',
            'EMAIL_FROM': 'from@example.com',
            'EMAIL_TO': 'to@example.com'
        }

        for key, value in env_vars.items():
            if key != missing_field:
                monkeypatch.setenv(key, value)
            else:
                monkeypatch.delenv(key, raising=False)

        # Also clear smtp_port to ensure we're not accidentally satisfying a check
        monkeypatch.delenv('SMTP_PORT', raising=False)

        config = Config()

        assert config.is_valid() is False


class TestConfigErrorHandling:
    """Test error handling for edge cases."""

    def test_invalid_port_handling_non_integer_in_env(self, monkeypatch):
        """
        Test 7: Invalid port handling (non-integer in env).

        Should raise ValueError when SMTP_PORT is not a valid integer.
        """
        monkeypatch.setenv('SMTP_PORT', 'not-a-number')

        with pytest.raises(ValueError, match="invalid literal for int"):
            Config()

    def test_invalid_port_handling_non_integer_in_file(self, monkeypatch, tmp_path, capsys):
        """
        Test 7b: Invalid port handling (non-integer in config file).

        Config gracefully handles invalid port in file by printing warning
        and continuing with remaining values unset (since exception breaks parsing).
        """
        # Clear env vars
        for var in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / 'config.env'
        config_file.write_text("""SMTP_HOST=smtp.example.com
SMTP_PORT=abc123
SMTP_USER=user
SMTP_PASS=pass
EMAIL_FROM=from@example.com
EMAIL_TO=to@example.com
""")

        monkeypatch.setattr('price_fetcher.CONFIG_FILE', config_file)

        # Should print warning but not crash (exception is caught)
        config = Config()

        # Check warning was printed
        captured = capsys.readouterr()
        assert "Warning: Failed to load config" in captured.out
        assert "invalid literal for int" in captured.out

    def test_missing_config_file_handled_gracefully(self, monkeypatch, tmp_path):
        """
        Test 8: Missing config file is handled gracefully.

        When no env vars are set and config file doesn't exist,
        Config should initialize with default/None values without errors.
        """
        # Clear all env vars
        for var in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)

        # Point to non-existent file
        non_existent_file = tmp_path / 'nonexistent.env'
        monkeypatch.setattr('price_fetcher.CONFIG_FILE', non_existent_file)

        # Should not raise any exception
        config = Config()

        assert config.smtp_host is None
        assert config.smtp_port == 587
        assert config.smtp_user is None
        assert config.is_valid() is False


class TestConfigFileParsing:
    """Test parsing edge cases in config file format."""

    def test_config_file_with_comments_and_empty_lines(self, monkeypatch, tmp_path):
        """
        Config file with comments and empty lines should be parsed correctly.
        """
        for var in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / 'config.env'
        config_file.write_text("""# This is a comment
SMTP_HOST=smtp.example.com

# Another comment
SMTP_PORT=587
SMTP_USER=user

EMAIL_FROM=from@example.com
EMAIL_TO=to@example.com
""")

        monkeypatch.setattr('price_fetcher.CONFIG_FILE', config_file)

        config = Config()

        # Should have loaded the values and skipped comments/empty lines
        assert config.smtp_host == 'smtp.example.com'
        assert config.smtp_user == 'user'
        assert config.email_from == 'from@example.com'

    def test_config_file_with_quoted_values(self, monkeypatch, tmp_path):
        """
        Config file with quoted values should have quotes stripped.
        """
        for var in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / 'config.env'
        config_file.write_text("""SMTP_HOST='smtp.example.com'
SMTP_PORT="587"
SMTP_USER="user with spaces"
SMTP_PASS='pass123'
EMAIL_FROM="from@example.com"
EMAIL_TO='to@example.com'
""")

        monkeypatch.setattr('price_fetcher.CONFIG_FILE', config_file)

        config = Config()

        assert config.smtp_host == 'smtp.example.com'
        assert config.smtp_port == 587
        assert config.smtp_user == 'user with spaces'

    def test_config_file_corrupted_graceful_handling(self, monkeypatch, tmp_path):
        """
        Corrupted config file should print warning but not crash.
        """
        for var in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_FROM', 'EMAIL_TO']:
            monkeypatch.delenv(var, raising=False)

        config_file = tmp_path / 'config.env'
        config_file.write_text("This is not valid config content")

        monkeypatch.setattr('price_fetcher.CONFIG_FILE', config_file)

        # Should not raise exception, just print warning
        config = Config()

        # All values should remain None/default
        assert config.smtp_host is None
        assert config.smtp_port == 587
