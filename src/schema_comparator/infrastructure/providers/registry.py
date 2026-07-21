"""Internal registry for database providers with lazy import support."""

from typing import Callable

from schema_comparator.application.ports.database_provider import DatabaseProvider
from schema_comparator.discovery.errors import DriverUnavailableError


class ProviderNotFoundError(KeyError):
    """Raised when a requested provider_id is not registered."""

    pass


class ProviderRegistry:
    """Explicit internal registry for DatabaseProvider instances (supports lazy loading)."""

    def __init__(self) -> None:
        self._providers: dict[str, DatabaseProvider] = {}
        self._factories: dict[str, Callable[[], DatabaseProvider]] = {}

    def register(self, provider: DatabaseProvider) -> None:
        """Register an instantiated DatabaseProvider implementation."""
        self._providers[provider.provider_id.casefold()] = provider

    def register_factory(
        self, provider_id: str, factory_fn: Callable[[], DatabaseProvider]
    ) -> None:
        """Register a lazy factory function for deferred provider loading."""
        self._factories[provider_id.casefold()] = factory_fn

    def get(self, provider_id: str) -> DatabaseProvider | None:
        """Get provider by ID or None if absent (triggers lazy instantiation if registered via factory)."""
        pid = provider_id.casefold()
        if pid in self._providers:
            return self._providers[pid]
        if pid in self._factories:
            try:
                provider = self._factories[pid]()
                self._providers[pid] = provider
                return provider
            except ImportError as exc:
                raise DriverUnavailableError(
                    f"El proveedor '{provider_id}' requiere dependencias adicionales no instaladas: {exc}. "
                    f"Ejecuta 'pip install bdiff[{pid}]' para instalar las dependencias requeridas."
                ) from exc
        return None

    def require(self, provider_id: str) -> DatabaseProvider:
        """Get provider by ID or raise ProviderNotFoundError."""
        provider = self.get(provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"No database provider registered for {provider_id!r}")
        return provider

    def list_providers(self) -> list[str]:
        """Return pre-sorted list of all registered provider IDs."""
        all_ids = set(self._providers.keys()) | set(self._factories.keys())
        return sorted(all_ids)


def _load_sqlserver_provider() -> DatabaseProvider:
    from schema_comparator.infrastructure.providers.sqlserver import SqlServerProvider

    return SqlServerProvider()


def _load_postgresql_provider() -> DatabaseProvider:
    from schema_comparator.infrastructure.providers.postgresql import PostgreSqlProvider

    return PostgreSqlProvider()


def _load_sqlite_provider() -> DatabaseProvider:
    from schema_comparator.infrastructure.providers.sqlite import SqliteProvider

    return SqliteProvider()


def _load_mysql_provider() -> DatabaseProvider:
    from schema_comparator.infrastructure.providers.mysql import MySqlProvider

    return MySqlProvider()


def _load_mariadb_provider() -> DatabaseProvider:
    from schema_comparator.infrastructure.providers.mariadb import MariaDbProvider

    return MariaDbProvider()


def _load_oracle_provider() -> DatabaseProvider:
    from schema_comparator.infrastructure.providers.oracle import OracleProvider

    return OracleProvider()


def get_default_registry() -> ProviderRegistry:
    """Return a new ProviderRegistry populated with default built-in provider factories."""
    registry = ProviderRegistry()
    registry.register_factory("sqlserver", _load_sqlserver_provider)
    registry.register_factory("postgresql", _load_postgresql_provider)
    registry.register_factory("sqlite", _load_sqlite_provider)
    registry.register_factory("mysql", _load_mysql_provider)
    registry.register_factory("mariadb", _load_mariadb_provider)
    registry.register_factory("oracle", _load_oracle_provider)
    return registry



