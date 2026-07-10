"""Shared test doubles for pyodbc-free discovery/connectors unit tests.

`pyodbc.Connection`/`pyodbc.Cursor` are C-extension types that do not
support `autospec=True` cleanly, so hand-written fakes conforming to the
subset of the pyodbc API this package actually calls are used instead.
"""


class FakeCursor:
    def __init__(self, rows, *, execute_error=None):
        self._rows = rows
        self._execute_error = execute_error
        self.closed = False
        self.executed_sql = None

    def execute(self, sql):
        self.executed_sql = sql
        if self._execute_error is not None:
            raise self._execute_error

    def fetchall(self):
        return self._rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows, *, execute_error=None):
        self._rows = rows
        self._execute_error = execute_error
        self.timeout = None
        self.closed = False
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = FakeCursor(self._rows, execute_error=self._execute_error)
        return self.last_cursor

    def close(self):
        self.closed = True


def fake_connect_fn(rows=(), *, raise_on_connect=None, execute_error=None):
    """Build a `connect_fn` seam replacement.

    - `raise_on_connect`: an exception raised by the returned callable
      itself (simulates a connect-phase failure).
    - `execute_error`: an exception raised by the resulting connection's
      cursor `execute()` call (simulates a query-phase failure).
    """
    connection_holder: dict = {}

    def _connect(conn_str, timeout):
        if raise_on_connect is not None:
            raise raise_on_connect
        connection = FakeConnection(rows, execute_error=execute_error)
        connection_holder["connection"] = connection
        return connection

    _connect.connection_holder = connection_holder
    return _connect
