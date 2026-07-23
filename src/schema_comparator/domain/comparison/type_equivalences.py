"""Type equivalences matrix for cross-provider semantic comparison."""

import re

# Canonical type families mapping
_TYPE_FAMILY_MAP: dict[str, str] = {
    # Integer family
    "int": "INTEGER",
    "integer": "INTEGER",
    "int2": "INTEGER",
    "int4": "INTEGER",
    "int8": "INTEGER",
    "bigint": "INTEGER",
    "smallint": "INTEGER",
    "tinyint": "INTEGER",
    "mediumint": "INTEGER",
    "serial": "INTEGER",
    "serial4": "INTEGER",
    "bigserial": "INTEGER",
    "serial8": "INTEGER",
    "smallserial": "INTEGER",
    "number(10,0)": "INTEGER",
    "number(38,0)": "INTEGER",
    # String family
    "varchar": "STRING",
    "nvarchar": "STRING",
    "varchar2": "STRING",
    "nvarchar2": "STRING",
    "character varying": "STRING",
    "char": "STRING",
    "nchar": "STRING",
    "character": "STRING",
    "text": "STRING",
    "clob": "STRING",
    "nclob": "STRING",
    "longtext": "STRING",
    "mediumtext": "STRING",
    "tinytext": "STRING",
    # Boolean family
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "tinyint(1)": "BOOLEAN",
    "bit": "BOOLEAN",
    "number(1,0)": "BOOLEAN",
    # Floating point & Decimal family
    "decimal": "DECIMAL",
    "numeric": "DECIMAL",
    "money": "DECIMAL",
    "smallmoney": "DECIMAL",
    "number": "DECIMAL",
    "float": "FLOAT",
    "double": "FLOAT",
    "double precision": "FLOAT",
    "real": "FLOAT",
    "float4": "FLOAT",
    "float8": "FLOAT",
    "binary_float": "FLOAT",
    "binary_double": "FLOAT",
    # DateTime family
    "date": "DATETIME",
    "datetime": "DATETIME",
    "datetime2": "DATETIME",
    "timestamp": "DATETIME",
    "timestamptz": "DATETIME",
    "timetz": "DATETIME",
    "time": "DATETIME",
    "interval": "DATETIME",
    "timestamp with time zone": "DATETIME",
    "timestamp without time zone": "DATETIME",
    # Binary family
    "blob": "BINARY",
    "bytea": "BINARY",
    "binary": "BINARY",
    "varbinary": "BINARY",
    "image": "BINARY",
    "raw": "BINARY",
    # UUID & Identifier family
    "uuid": "UUID",
    "uniqueidentifier": "UUID",
    # JSON family
    "json": "JSON",
    "jsonb": "JSON",
}


def get_type_family(data_type: str) -> str:
    """Return the canonical type family string for a given native data type."""
    # Normalize spaces around commas/parentheses
    clean_type = re.sub(r"\s+", " ", data_type.strip().lower())
    clean_type = re.sub(r"\s*,\s*", ",", clean_type)

    if clean_type in _TYPE_FAMILY_MAP:
        return _TYPE_FAMILY_MAP[clean_type]

    # Non-greedy parameter stripping
    type_no_params = re.sub(r"\s*\([^)]*\)", "", clean_type).strip()
    if type_no_params in _TYPE_FAMILY_MAP:
        return _TYPE_FAMILY_MAP[type_no_params]

    return type_no_params.upper()


def are_types_semantically_equivalent(type1: str, type2: str) -> bool:
    """Return True if two native data types belong to the same semantic type family."""
    fam1 = get_type_family(type1)
    fam2 = get_type_family(type2)
    return fam1 == fam2
