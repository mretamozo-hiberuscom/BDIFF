"""Translate ADO.NET/`SqlClient`-style connection-string keywords to ODBC form.

Translation is a pure keyword-spelling rewrite performed once, at
config-load time, before a `ConnectionProfile` is constructed (see
`config/loader.py`). It never decomposes the string into host/user/
password/auth fields, never validates connectivity or credentials, and
never touches any call site outside the loader.

Limitation: ODBC/`SqlClient` braces are not nestable, so a second
unescaped `{` while already inside a brace group is not itself an error
condition; it is passed through literally as a plain character, matching
real ODBC driver manager behavior. Only an *unterminated* `{` (the string
ends while still inside a brace group) is rejected.
"""

from schema_comparator.config.errors import ProfileValidationError

# Case-folded ADO.NET/legacy keyword -> canonical ODBC keyword. Keys already
# in ODBC form (Server, Database, UID, PWD, Trusted_Connection, Driver,
# Encrypt, TrustServerCertificate, ...) are intentionally absent: absence
# means "pass through unchanged", which is the fail-open default for any
# keyword not in this dict (including genuinely unknown/driver-specific
# ones).
_RENAME_MAP: dict[str, str] = {
    "data source": "Server",
    "initial catalog": "Database",
    "user id": "UID",
    "uid": "UID",
    "password": "PWD",
    "pwd": "PWD",
}

# Keys recognized as already-valid ODBC keywords (pass through unchanged,
# but still count as "recognized" for the zero-recognized-tokens error
# check).
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

# Encrypt/TrustServerCertificate are pass-through keywords (same spelling in
# both dialects), but their *values* are not: ADO.NET/SqlClient writes
# True/False, while the Microsoft ODBC Driver for SQL Server only documents
# yes/mandatory and no/optional (plus strict, 18.0+) -- passing "True"
# verbatim raises SQLSTATE 08001 ("invalid value specified for connection
# string attribute") at connect time. Only the literal true/false spelling is
# normalized; already-ODBC values (yes/no/mandatory/optional/strict) are
# left untouched.
_BOOLEAN_VALUE_KEYS = {"encrypt", "trustservercertificate"}
_BOOLEAN_TRUE_VALUES = {"true"}
_BOOLEAN_FALSE_VALUES = {"false"}

_DEFAULT_DRIVER_TOKEN = "Driver={ODBC Driver 17 for SQL Server}"


def _tokenize(raw: str, *, name: str) -> list[str]:
    """Split `raw` on ';' into raw 'key=value' segments, respecting {...}
    brace grouping. Returns segments with surrounding whitespace stripped;
    empty segments (from a trailing ';' or ';;') are dropped.
    """
    segments: list[str] = []
    buf: list[str] = []
    depth = 0  # 0 = outside braces, 1 = inside a single non-nested brace group
    i = 0
    length = len(raw)
    while i < length:
        ch = raw[i]
        if ch == "{" and depth == 0:
            depth = 1
            buf.append(ch)
        elif ch == "}" and depth == 1:
            # Doubled '}}' inside a brace group is a literal '}'; only a
            # single '}' followed by a non-'}' (or end of string) closes
            # the group.
            if i + 1 < length and raw[i + 1] == "}":
                buf.append("}")
                i += 1  # consume both characters of the doubled pair
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
        # Unterminated '{': hard error, no partial/best-effort parse.
        raise ProfileValidationError.unrecognized_connection_string_format(name)

    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _split_token(token: str) -> tuple[str, str] | None:
    """Split one 'key=value' segment on the first '=' only. Returns None
    if the token has no '=' at all (unrecognized-format signal upstream).
    """
    if "=" not in token:
        return None
    key, _, value = token.partition("=")
    return key.strip(), value.strip()


def translate(raw: str, *, name: str) -> str:
    """Translate an ADO.NET/ODBC-mixed connection string into pure ODBC form.

    `name` is the owning profile's name, used only to build a secret-safe
    error message if `raw` cannot be tokenized. Never logged, never
    included in any exception's message body beyond the name itself.
    """
    tokens = _tokenize(raw, name=name)

    recognized_any = False
    has_driver = False
    # dict preserves insertion order; pop-then-set on every write ensures a
    # key's position always reflects the order of its own last write, which
    # is exactly last-occurrence-wins semantics regardless of dict-
    # reassignment ordering nuances.
    output: dict[str, str] = {}

    for token in tokens:
        split = _split_token(token)
        if split is None:
            # A bare no-'=' segment cannot be represented in the output
            # dict's key=value shape; it never sets recognized_any, and if
            # it is the only token, translate() falls through to the
            # unrecognized-format error below.
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
                # Any other value (yes/no/mandatory/optional/strict/...) is
                # already valid ODBC vocabulary and passes through as-is.
            output.pop(key, None)
            output[key] = value  # preserve original casing for passthrough
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
                output.pop("Trusted_Connection", None)  # dropped, no-op if absent
            else:
                # Spec defines only true/sspi/yes and false/no; an
                # unrecognized value is treated as an unknown keyword+value
                # pair and preserved verbatim under its original key,
                # matching the fail-open default elsewhere.
                output.pop(key, None)
                output[key] = value
        else:
            # Fail-open: unknown keyword, preserved verbatim under its
            # original (non-case-folded) key. Does NOT count toward
            # recognized_any.
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
