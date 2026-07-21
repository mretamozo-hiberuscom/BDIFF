"""Qualified name abstraction supporting optional catalog and schema names."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QualifiedName:
    """Canonical representation of a database object name.

    Supports single-part (`table`), two-part (`schema.table`), and three-part
    (`catalog.schema.table`) qualified names.
    """

    object_name: str
    schema_name: str | None = None
    catalog_name: str | None = None

    def format_qualified(self) -> str:
        """Return dot-separated qualified name string omitting None components."""
        if self.catalog_name is not None and self.schema_name is None:
            return f"{self.catalog_name}..{self.object_name}"
        parts = [p for p in (self.catalog_name, self.schema_name, self.object_name) if p is not None]
        return ".".join(parts)
