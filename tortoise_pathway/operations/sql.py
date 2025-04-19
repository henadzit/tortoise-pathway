from typing import Any

from tortoise.converters import encoders


def default_value_to_sql(default: Any, dialect: str) -> Any:
    """
    Convert a default value to its SQL representation.
    """
    if dialect == "postgres" and isinstance(default, bool):
        return default

    return encoders.get(type(default))(default)
