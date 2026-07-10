"""Load and validate connection profiles from a local YAML config file.

Phase 3 (happy path only): file-existence and malformed-YAML handling are
added in Phase 4; trim/duplicate/validation are added in Phase 5.
"""

import os

import yaml

from schema_comparator.config.models import ConnectionProfile


def load_profiles(config_path: str | os.PathLike[str]) -> list[ConnectionProfile]:
    """Load connection profiles from the YAML file at `config_path`.

    `config_path` is a required positional parameter with no default: the
    loader performs no implicit path resolution (no cwd/repo-root default,
    no environment-variable-derived path). Omitting it raises the natural
    `TypeError` from Python's argument binding.
    """
    with open(config_path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    profiles: list[ConnectionProfile] = []
    for name, connection_string in document["databases"].items():
        profiles.append(ConnectionProfile(name=name, connection_string=connection_string))
    return profiles
