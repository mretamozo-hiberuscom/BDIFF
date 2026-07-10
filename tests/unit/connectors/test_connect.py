"""Unit tests for connectors.connect: timeout wiring and guaranteed cleanup."""

import pytest

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.connectors import DEFAULT_TIMEOUT_SECONDS, connect


class _FakeConnection:
    def __init__(self):
        self._timeout = None
        self.closed = False

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        # Mirrors real pyodbc.Connection.timeout: it also only accepts a
        # plain int, not a float (this fake previously accepted anything,
        # which let a real TypeError reach production undetected).
        if not isinstance(value, int):
            raise TypeError("'float' object cannot be interpreted as an integer")
        self._timeout = value

    def close(self):
        self.closed = True


def test_connect_fn_invoked_with_default_timeout() -> None:
    profile = ConnectionProfile(name="claims-service", connection_string="X")
    calls = []

    def fake_connect_fn(conn_str, timeout):
        calls.append((conn_str, timeout))
        return _FakeConnection()

    with connect(profile, connect_fn=fake_connect_fn):
        pass

    assert calls == [("X", DEFAULT_TIMEOUT_SECONDS)]


def test_connection_timeout_attribute_set_after_connect() -> None:
    profile = ConnectionProfile(name="claims-service", connection_string="X")

    def fake_connect_fn(conn_str, timeout):
        return _FakeConnection()

    with connect(profile, connect_fn=fake_connect_fn) as conn:
        assert conn.timeout == DEFAULT_TIMEOUT_SECONDS


def test_connection_closed_even_when_caller_block_raises() -> None:
    profile = ConnectionProfile(name="claims-service", connection_string="X")
    fake_conn = _FakeConnection()

    def fake_connect_fn(conn_str, timeout):
        return fake_conn

    with pytest.raises(ValueError):
        with connect(profile, connect_fn=fake_connect_fn):
            raise ValueError("caller failure")

    assert fake_conn.closed is True
