"""Structure-only smoke test for the integration test layer.

No real DB connection is exercised here — that is out of scope for the
scaffold change per proposal-lite.md boundaries. This test only proves the
integration test layout is collected and runnable by pytest.
"""


def test_integration_layer_is_collectible() -> None:
    assert True
