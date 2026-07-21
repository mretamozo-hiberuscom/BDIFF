"""Unit tests for ProviderRegistry."""

import pytest

from schema_comparator.discovery.errors import DriverUnavailableError
from schema_comparator.infrastructure.providers.registry import (
    ProviderNotFoundError,
    ProviderRegistry,
)
from schema_comparator.infrastructure.providers.sqlserver.provider import SqlServerProvider


def test_provider_registry_register_and_require() -> None:
    registry = ProviderRegistry()
    provider = SqlServerProvider()
    registry.register(provider)

    assert registry.get("sqlserver") is provider
    assert registry.get("SQLSERVER") is provider
    assert registry.require("sqlserver") is provider
    assert "sqlserver" in registry.list_providers()


def test_provider_registry_lazy_factory() -> None:
    registry = ProviderRegistry()
    provider = SqlServerProvider()
    registry.register_factory("sqlserver", lambda: provider)

    assert "sqlserver" in registry.list_providers()
    assert registry.get("sqlserver") is provider


def test_provider_registry_lazy_factory_import_error() -> None:
    registry = ProviderRegistry()

    def failing_factory():
        raise ImportError("No module named 'missing_driver'")

    registry.register_factory("oracle", failing_factory)

    with pytest.raises(DriverUnavailableError, match="El proveedor 'oracle' requiere dependencias"):
        registry.get("oracle")


def test_provider_registry_missing_provider_raises_error() -> None:
    registry = ProviderRegistry()
    assert registry.get("unknown") is None
    with pytest.raises(ProviderNotFoundError, match="No database provider registered for 'unknown'"):
        registry.require("unknown")
