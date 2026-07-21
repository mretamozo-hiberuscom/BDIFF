"""Load and validate connection profiles from a local YAML config file (v1 & v2).

Fail-fast gates: missing file, malformed/wrong-shape YAML, exact-duplicate
YAML keys, blank name, case-insensitive duplicate name, blank connection
string. Leading/trailing whitespace is trimmed from both `name` and
`connection_string` before validation.
"""

import os
from typing import Any

import yaml

from schema_comparator.config.connection_string import translate
from schema_comparator.config.errors import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ProfileValidationError,
)
from schema_comparator.config.models import ConnectionProfile


class _DuplicateKeyLoader(yaml.SafeLoader):
    """A SafeLoader that raises on exact-duplicate mapping keys."""


def _no_duplicate_keys(loader: yaml.SafeLoader, node: yaml.Node, deep: bool = False) -> dict:
    seen: set[object] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ProfileValidationError.duplicate_name(str(key))
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def load_profiles(config_path: str | os.PathLike[str]) -> list[ConnectionProfile]:
    """Load connection profiles from the YAML file at `config_path`.

    Supports legacy v1 (`databases:` dictionary mapping) and v2 (`profiles:`
    or structured dictionary values with `provider`, `connection_string`, `options`).
    """
    if not os.path.exists(config_path):
        raise ConfigFileNotFoundError.at_path(str(config_path))

    with open(config_path, encoding="utf-8") as handle:
        try:
            document = yaml.load(handle, Loader=_DuplicateKeyLoader)
        except yaml.YAMLError as exc:
            raise ConfigParseError.invalid_yaml() from exc

    if not isinstance(document, dict):
        raise ConfigParseError.invalid_shape()

    raw_profiles: dict[str, Any] | None = None
    if isinstance(document.get("profiles"), dict):
        raw_profiles = document["profiles"]
    elif isinstance(document.get("databases"), dict):
        raw_profiles = document["databases"]
    else:
        raise ConfigParseError.invalid_shape()

    profiles: list[ConnectionProfile] = []
    seen_casefolded_names: set[str] = set()
    for raw_name, entry in raw_profiles.items():
        name = str(raw_name).strip()

        if not name:
            raise ProfileValidationError.empty_name()

        casefolded_name = name.casefold()
        if casefolded_name in seen_casefolded_names:
            raise ProfileValidationError.duplicate_name(name)
        seen_casefolded_names.add(casefolded_name)

        provider = "sqlserver"
        connection_string = ""
        options: dict[str, Any] = {}

        if isinstance(entry, dict):
            raw_provider = entry.get("provider")
            provider = str(raw_provider).strip() if raw_provider is not None else "sqlserver"
            if not provider:
                provider = "sqlserver"

            raw_conn = entry.get("connection_string")
            connection_string = str(raw_conn).strip() if raw_conn is not None else ""

            raw_options = entry.get("options")
            if isinstance(raw_options, dict):
                options = dict(raw_options)
        else:
            connection_string = str(entry).strip() if entry is not None else ""

        if not connection_string:
            raise ProfileValidationError.empty_connection_string(name)

        if provider.casefold() == "sqlserver":
            connection_string = translate(connection_string, name=name)

        profiles.append(
            ConnectionProfile(
                name=name,
                connection_string=connection_string,
                provider=provider,
                options=options,
            )
        )
    return profiles
