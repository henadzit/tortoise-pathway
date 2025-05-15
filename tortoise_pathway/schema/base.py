from typing import Any
from tortoise.fields import Field, IntField
from tortoise.fields.relational import RelationalField
from tortoise.converters import encoders


class BaseSchemaManager:
    def __init__(self, dialect: str):
        self.dialect = dialect

    def create_table(
        self, table_name: str, columns: dict[str, Field], foreign_keys: list[tuple[str, str, str]]
    ) -> str:
        column_defs = []
        constraints = []

        for column_name, field in columns.items():
            column_def = self._field_definition_to_sql(field)
            column_defs.append(f"{column_name} {column_def}")

        for from_column, related_table, to_column in foreign_keys:
            constraints.append(
                f'FOREIGN KEY ({from_column}) REFERENCES "{related_table}" ({to_column})'
            )
        # Build the CREATE TABLE statement
        sql = f'CREATE TABLE "{table_name}" (\n'
        sql += ",\n".join(["    " + col for col in column_defs])

        if constraints:
            sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

        sql += "\n);"

        return sql

    def drop_table(self, table_name: str) -> str:
        return f"DROP TABLE {table_name}"

    def add_column(self, table_name: str, column_name: str, field: Field) -> str:
        column_def = self._field_definition_to_sql(field)
        return f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"

    def drop_column(self, table_name: str, column_name: str) -> str:
        return f"ALTER TABLE {table_name} DROP COLUMN {column_name}"

    def add_foreign_key_column(
        self, table_name: str, column_name: str, related_table: str, to_column: str, null: bool
    ) -> str:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} INT"
        if not null:
            sql += " NOT NULL"

        sql += f",\nADD CONSTRAINT fk_{table_name}_{column_name} "
        sql += f"FOREIGN KEY ({column_name}) REFERENCES {related_table}({to_column})"
        return sql

    def add_foreign_key_constraint(
        self, table_name: str, column_name: str, related_table: str, to_column: str
    ) -> str:
        return (
            f"ALTER TABLE {table_name} ADD CONSTRAINT fk_{table_name}_{column_name} FOREIGN KEY ({column_name})"
            f" REFERENCES {related_table} ({to_column})"
        )

    def add_index(
        self,
        table_name: str,
        index_name: str,
        columns: list[str],
        unique: bool = False,
        index_type: str | None = None,
    ) -> str:
        unique_prefix = "UNIQUE " if unique else ""
        columns_str = ", ".join(columns)
        index_type_str = f"USING {index_type}" if index_type else ""
        return f"CREATE {unique_prefix}INDEX {index_name} ON {table_name} ({columns_str}) {index_type_str}".strip()

    def drop_index(self, index_name: str) -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX {index_name}"

    def _field_definition_to_sql(self, field: Field) -> str:
        # TODO: subclasses should override this method
        nullable = getattr(field, "null", False)
        unique = getattr(field, "unique", False)
        pk = getattr(field, "pk", False)

        if isinstance(field, RelationalField):
            sql_type = IntField().get_for_dialect(self.dialect, "SQL_TYPE")
        else:
            sql_type = field.get_for_dialect(self.dialect, "SQL_TYPE")

        # Handle special cases for primary keys
        if pk:
            if self.dialect == "sqlite" and isinstance(field, IntField):
                # For SQLite, INTEGER PRIMARY KEY AUTOINCREMENT must use exactly "INTEGER" type
                sql_type = "INTEGER"
            elif pk and isinstance(field, IntField) and self.dialect == "postgres":
                sql_type = "SERIAL"

        # Build column definition
        column_def = f"{sql_type}"

        if pk:
            if self.dialect == "sqlite":
                column_def += " PRIMARY KEY"
                if isinstance(field, IntField):
                    column_def += " AUTOINCREMENT"
            else:
                column_def += " PRIMARY KEY"
                if isinstance(field, IntField) and self.dialect == "postgres":
                    # For PostgreSQL, we'd use SERIAL instead
                    column_def = f"{sql_type} PRIMARY KEY"

        if not nullable and not pk:
            column_def += " NOT NULL"

        if unique and not pk:
            column_def += " UNIQUE"

        column_def += self.field_default_to_sql(field)

        return column_def

    def field_default_to_sql(self, field: Field) -> str:
        default = getattr(field, "default", None)
        auto_now = getattr(field, "auto_now", False)
        auto_now_add = getattr(field, "auto_now_add", False)

        if default is not None and not callable(default):
            value = self.default_value_to_sql(default)
            return f" DEFAULT {value}"

        if auto_now or auto_now_add:
            return " DEFAULT CURRENT_TIMESTAMP"

        return ""

    def default_value_to_sql(self, default: Any) -> Any:
        """
        Convert a default value to its SQL representation.
        """
        if self.dialect == "postgres" and isinstance(default, bool):
            return default

        return encoders.get(type(default))(default)
