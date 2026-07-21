"""Application ports contracts (Protocols)."""

from schema_comparator.application.ports.database_provider import DatabaseProvider
from schema_comparator.application.ports.profile_repository import ProfileRepository
from schema_comparator.application.ports.report_sink import ReportSink
from schema_comparator.application.ports.script_sink import ScriptSink

__all__ = [
    "DatabaseProvider",
    "ProfileRepository",
    "ReportSink",
    "ScriptSink",
]
