from typing import Any

from tortoise.converters import encoders
from tortoise.fields import Field, IntField
from tortoise.fields.relational import RelationalField


def field_definition_to_sql(field: Field, dialect: str) -> str:
    nullable = getattr(field, "null", False)
    unique = getattr(field, "unique", False)
    pk = getattr(field, "pk", False)

    if isinstance(field, RelationalField):
        sql_type = IntField().get_for_dialect(dialect, "SQL_TYPE")
    else:
        sql_type = field.get_for_dialect(dialect, "SQL_TYPE")

    # Handle special cases for primary keys
    if pk:
        if dialect == "sqlite" and isinstance(field, IntField):
            # For SQLite, INTEGER PRIMARY KEY AUTOINCREMENT must use exactly "INTEGER" type
            sql_type = "INTEGER"
        elif pk and isinstance(field, IntField) and dialect == "postgres":
            sql_type = "SERIAL"

    # Build column definition
    column_def = f"{sql_type}"

    if pk:
        if dialect == "sqlite":
            column_def += " PRIMARY KEY"
            if isinstance(field, IntField):
                column_def += " AUTOINCREMENT"
        else:
            column_def += " PRIMARY KEY"
            if isinstance(field, IntField) and dialect == "postgres":
                # For PostgreSQL, we'd use SERIAL instead
                column_def = f"{sql_type} PRIMARY KEY"

    if not nullable and not pk:
        column_def += " NOT NULL"

    if unique and not pk:
        column_def += " UNIQUE"

    column_def += field_default_to_sql(field, dialect)

    return column_def


def field_default_to_sql(field: Field, dialect: str) -> str:
    default = getattr(field, "default", None)
    auto_now = getattr(field, "auto_now", False)
    auto_now_add = getattr(field, "auto_now_add", False)

    if default is not None and not callable(default):
        value = default_value_to_sql(default, dialect)
        return f" DEFAULT {value}"

    if auto_now or auto_now_add:
        return " DEFAULT CURRENT_TIMESTAMP"

    return ""


def default_value_to_sql(default: Any, dialect: str) -> Any:
    """
    Convert a default value to its SQL representation.
    """
    if dialect == "postgres" and isinstance(default, bool):
        return default

    return encoders.get(type(default))(default)
