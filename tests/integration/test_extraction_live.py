"""Optional live-database integration verification for schema extraction.

Skipped entirely unless SCHEMA_COMPARATOR_TEST_DSN is set, so the normal
unit test run never attempts a live SQL Server connection.
"""

import os

import pytest

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.service import extract_schema

_TEST_DSN = os.environ.get("SCHEMA_COMPARATOR_TEST_DSN")


@pytest.mark.skipif(
    not _TEST_DSN,
    reason="SCHEMA_COMPARATOR_TEST_DSN not set; skipping live extraction test",
)
def test_extract_schema_against_live_database() -> None:
    profile = ConnectionProfile(name="integration-test", connection_string=_TEST_DSN)

    snapshot = extract_schema(profile)

    assert snapshot.profile_name == "integration-test"
