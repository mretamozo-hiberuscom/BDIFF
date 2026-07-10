"""Unit tests for the ConfigError exception hierarchy."""

from schema_comparator.config.errors import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigParseError,
    ProfileValidationError,
)


def test_config_file_not_found_error_is_config_error() -> None:
    assert issubclass(ConfigFileNotFoundError, ConfigError)
    assert issubclass(ConfigError, Exception)


def test_config_parse_error_is_config_error() -> None:
    assert issubclass(ConfigParseError, ConfigError)
    assert issubclass(ConfigError, Exception)


def test_profile_validation_error_is_config_error() -> None:
    assert issubclass(ProfileValidationError, ConfigError)
    assert issubclass(ConfigError, Exception)


def test_empty_name_factory_returns_actionable_message() -> None:
    exc = ProfileValidationError.empty_name()
    assert isinstance(exc, ProfileValidationError)
    assert str(exc).strip() != ""


def test_duplicate_name_factory_contains_given_name() -> None:
    exc = ProfileValidationError.duplicate_name("X")
    assert isinstance(exc, ProfileValidationError)
    assert "X" in str(exc)


def test_empty_connection_string_factory_contains_given_name() -> None:
    exc = ProfileValidationError.empty_connection_string("X")
    assert isinstance(exc, ProfileValidationError)
    assert "X" in str(exc)
