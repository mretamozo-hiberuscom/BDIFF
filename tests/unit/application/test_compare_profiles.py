"""Unit tests for CompareProfilesUseCase."""

from schema_comparator.application.use_cases.compare_profiles import CompareProfilesUseCase
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ComparisonResult
from schema_comparator.domain.schema.models import ColumnSnapshot, SchemaSnapshot, TableSnapshot


def test_compare_profiles_use_case_execution() -> None:
    profile_a = ConnectionProfile(name="profileA", connection_string="Server=A;")
    profile_b = ConnectionProfile(name="profileB", connection_string="Server=B;")

    col1 = ColumnSnapshot("id", "int", None, None, None, False, 1)
    table_a = TableSnapshot("dbo", "users", (col1,))

    snapshot_a = SchemaSnapshot("profileA", (table_a,))
    snapshot_b = SchemaSnapshot("profileB", ())

    fake_extractor_called = []

    def fake_extractor(profile: ConnectionProfile) -> SchemaSnapshot:
        fake_extractor_called.append(profile.name)
        if profile.name == "profileA":
            return snapshot_a
        return snapshot_b

    use_case = CompareProfilesUseCase(extractor=fake_extractor)
    result = use_case.execute([profile_a, profile_b])

    assert isinstance(result, ComparisonResult)
    assert fake_extractor_called == ["profileA", "profileB"]
    assert result.compared_profiles == ("profileA", "profileB")
    assert len(result.entries) == 1
