"""Unit tests for compare.errors precondition validation ordering."""

import pytest

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.compare.errors import (
    DuplicateProfileNameError,
    InsufficientSnapshotsError,
)
from compare.conftest import make_snapshot


def test_fewer_than_two_snapshots_is_rejected() -> None:
    single = make_snapshot("a", ("sales", "Invoice"))
    with pytest.raises(InsufficientSnapshotsError):
        compare_snapshots([single])


def test_duplicate_profile_names_is_rejected() -> None:
    first = make_snapshot("staging", ("sales", "Invoice"))
    second = make_snapshot("staging", ("sales", "Invoice"))
    with pytest.raises(DuplicateProfileNameError):
        compare_snapshots([first, second])


def test_count_check_happens_before_duplicate_check() -> None:
    # A single-element input can never trigger the duplicate-name branch;
    # InsufficientSnapshotsError must be raised regardless of name content.
    single = make_snapshot("staging", ("sales", "Invoice"))
    with pytest.raises(InsufficientSnapshotsError):
        compare_snapshots([single])
