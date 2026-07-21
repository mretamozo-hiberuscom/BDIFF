"""Translate ADO.NET/`SqlClient`-style connection-string keywords to ODBC form for SQL Server."""

from schema_comparator.config.errors import ProfileValidationError

_RENAME_MAP: dict[str, str] = {
    "data source": "Server",
    "initial catalog": "Database",
    "user id": "UID",
    "uid": "UID",
    "password": "PWD",
    "pwd": "PWD",
}

_ODBC_PASSTHROUGH_KEYS = {
    "server",
    "database",
    "trusted_connection",
    "encrypt",
    "trustservercertificate",
    "driver",
}

_INTEGRATED_SECURITY_KEY = "integrated security"
_INTEGRATED_SECURITY_TRUE_VALUES = {"true", "sspi", "yes"}
_INTEGRATED_SECURITY_FALSE_VALUES = {"false", "no"}

_BOOLEAN_VALUE_KEYS = {"encrypt", "trustservercertificate"}
_BOOLEAN_TRUE_VALUES = {"true"}
_BOOLEAN_FALSE_VALUES = {"false"}

_DEFAULT_DRIVER_TOKEN = "Driver={ODBC Driver 17 for SQL Server}"


def _tokenize(raw: str, *, name: str) -> list[str]:
    segments: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    length = len(raw)
    while i < length:
        ch = raw[i]
        if ch == "{" and depth == 0:
            depth = 1
            buf.append(ch)
        elif ch == "}" and depth == 1:
            if i + 1 < length and raw[i + 1] == "}":
                buf.append("}")
                i += 1
            else:
                depth = 0
                buf.append(ch)
        elif ch == ";" and depth == 0:
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1

    if depth != 0:
        raise ProfileValidationError.unrecognized_connection_string_format(name)

    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _split_token(token: str) -> tuple[str, str] | None:
    if "=" not in token:
        return None
    key, _, value = token.partition("=")
    return key.strip(), value.strip()


def translate(raw: str, *, name: str) -> str:
    """Translate an ADO.NET/ODBC-mixed connection string into pure ODBC form for SQL Server."""
    tokens = _tokenize(raw, name=name)

    recognized_any = False
    has_driver = False
    output: dict[str, str] = {}

    for token in tokens:
        split = _split_token(token)
        if split is None:
            continue

        key, value = split
        folded_key = key.casefold()

        if folded_key in _RENAME_MAP:
            output.pop(_RENAME_MAP[folded_key], None)
            output[_RENAME_MAP[folded_key]] = value
            recognized_any = True
        elif folded_key in _ODBC_PASSTHROUGH_KEYS:
            if folded_key in _BOOLEAN_VALUE_KEYS:
                folded_value = value.casefold()
                if folded_value in _BOOLEAN_TRUE_VALUES:
                    value = "yes"
                elif folded_value in _BOOLEAN_FALSE_VALUES:
                    value = "no"
            output.pop(key, None)
            output[key] = value
            recognized_any = True
            if folded_key == "driver":
                has_driver = True
        elif folded_key == _INTEGRATED_SECURITY_KEY:
            recognized_any = True
            folded_value = value.casefold()
            if folded_value in _INTEGRATED_SECURITY_TRUE_VALUES:
                output.pop("Trusted_Connection", None)
                output["Trusted_Connection"] = "yes"
            elif folded_value in _INTEGRATED_SECURITY_FALSE_VALUES:
                output.pop("Trusted_Connection", None)
            else:
                output.pop(key, None)
                output[key] = value
        else:
            output.pop(key, None)
            output[key] = value

    if not recognized_any:
        raise ProfileValidationError.unrecognized_connection_string_format(name)

    result = ";".join(f"{k}={v}" for k, v in output.items())
    if result and not result.endswith(";"):
        result += ";"

    if not has_driver:
        result = f"{_DEFAULT_DRIVER_TOKEN};{result}"

    return result
