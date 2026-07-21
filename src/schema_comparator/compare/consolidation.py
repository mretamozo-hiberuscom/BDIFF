"""Logic for schema consolidation decisions and SQL Server DDL generation (Enterprise-grade)."""

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from schema_comparator.domain.comparison.models import ColumnAttributes, NamedColumnAttributes
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
    extract_database_name,
    format_sql_column_definition,
    generate_ddl_for_profile,
)


@dataclass(frozen=True, slots=True)
class ColumnResolution:
    """Represents a decision to consolidate a single column mismatch or missing column."""

    schema_name: str
    table_name: str
    column_name: str
    target_attributes: ColumnAttributes
    profiles_to_update: tuple[str, ...]
    is_missing_column: bool


@dataclass(frozen=True, slots=True)
class TableResolution:
    """Represents a decision to create a missing table with the full column definition."""

    schema_name: str
    table_name: str
    columns: tuple[NamedColumnAttributes, ...]
    profiles_to_update: tuple[str, ...]


class TableAction(str, Enum):
    """Actions available for a table-level consolidation decision."""

    DROP = "drop"


@dataclass(frozen=True, slots=True)
class TableDeletionResolution:
    """Represents a decision to remove a table from selected profiles."""

    schema_name: str
    table_name: str
    profiles_to_update: tuple[str, ...]


class ColumnAction(str, Enum):
    """Actions available for a column-level consolidation decision."""

    DROP = "drop"


@dataclass(frozen=True, slots=True)
class ColumnDeletionResolution:
    """Represents a decision to remove a column from selected profiles."""

    schema_name: str
    table_name: str
    column_name: str
    profiles_to_update: tuple[str, ...]


def write_sql_scripts(
    resolutions: list[ColumnResolution],
    repo_root: str | Path,
    profiles: list[ConnectionProfile],
    timestamp: datetime.datetime | None = None,
    table_resolutions: list[TableResolution] | None = None,
    table_deletions: list[TableDeletionResolution] | None = None,
    column_deletions: list[ColumnDeletionResolution] | None = None,
) -> list[str]:
    """Create the 'scripts-db' directory and write transactional DDL files for all affected profiles."""
    root_path = Path(repo_root)
    output_dir = root_path / "scripts-db"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ts = timestamp or datetime.datetime.now()
    profile_map = {p.name: p for p in profiles}
    
    all_profiles_names = set()
    for res in resolutions:
        all_profiles_names.update(res.profiles_to_update)
    for tres in (table_resolutions or []):
        all_profiles_names.update(tres.profiles_to_update)
    for deletion in (table_deletions or []):
        all_profiles_names.update(deletion.profiles_to_update)
    for deletion in (column_deletions or []):
        all_profiles_names.update(deletion.profiles_to_update)
        
    written_files = []
    for profile_name in sorted(all_profiles_names):
        profile = profile_map.get(
            profile_name, 
            ConnectionProfile(name=profile_name, connection_string=f"Database={profile_name};")
        )
        ddl = generate_ddl_for_profile(
            resolutions,
            profile,
            timestamp=ts,
            table_resolutions=table_resolutions,
            table_deletions=table_deletions,
            column_deletions=column_deletions,
        )
        safe_profile = Path(profile_name).name
        file_path = output_dir / f"{safe_profile}.sql"
        file_path.write_text(ddl, encoding="utf-8")
        written_files.append(str(file_path.resolve()))
        
    return written_files
