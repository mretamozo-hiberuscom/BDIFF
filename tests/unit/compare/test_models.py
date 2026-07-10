"""Unit tests for compare.models: qualified identity and immutability."""

import dataclasses

import pytest

from schema_comparator.compare.models import ComparisonResult, MissingTable


def test_qualified_name_returns_schema_and_table_pair() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Invoice", missing_from_profile="staging"
    )
    assert entry.qualified_name == ("sales", "Invoice")


def test_missing_table_is_immutable() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Invoice", missing_from_profile="staging"
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.table_name = "Changed"  # type: ignore[misc]


def test_comparison_result_is_immutable() -> None:
    result = ComparisonResult(compared_profiles=("a", "b"), entries=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.entries = ()  # type: ignore[misc]
