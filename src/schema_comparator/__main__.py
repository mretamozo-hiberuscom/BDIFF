"""Enables `python -m schema_comparator.cli` style invocation from
run.py's relaunch step, and `python -m schema_comparator` directly."""

import sys

from schema_comparator.cli import main

if __name__ == "__main__":
    sys.exit(main())
