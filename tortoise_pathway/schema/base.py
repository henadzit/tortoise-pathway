from hashlib import sha256
from typing import Any
from tortoise.fields import Field, IntField
from tortoise.fields.relational import RelationalField
from tortoise.converters import encoders


class BaseSchemaManager:
    """A base class for managing database schema operations across different database dialects.

    This class provides methods to generate SQL statements for various schema operations
    such as creating tables, adding/removing columns, managing foreign keys, and handling
    indexes. It serves as a foundation for dialect-specific schema managers.

    Attributes:
        dialect (str): The database dialect being used (e.g., 'postgres', 'sqlite', 'mysql').

    Create a subclass for each dialect and override the methods as needed.
    """
    def __init__(self, dialect: str):
        self.dialect = dialect

    def create_table(
        self, table_name: str, columns: dict[str, Field], foreign_keys: list[tuple[str, str, str]]
    ) -> str:
        column_defs = []
        constraints = []
        indexes = []

        for column_name, field in columns.items():
            column_def = self._field_definition_to_sql(field)
            column_defs.append(f"{column_name} {column_def}")

            # Add indexes to non-primary key fields
            if field.index and not field.pk:
                index_name = self._get_index_name(table_name, column_name)
                indexes.append(self.add_index(table_name, index_name, [column_name], unique=field.unique))

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

        if indexes:
            sql += "\n" + ";\n".join(indexes)

        return sql

    def drop_table(self, table_name: str) -> str:
        return f"DROP TABLE {table_name}"

    def rename_table(self, old_name: str, new_name: str) -> str:
        return f"ALTER TABLE {old_name} RENAME TO {new_name}"

    def add_column(self, table_name: str, column_name: str, field: Field) -> str:
        column_def = self._field_definition_to_sql(field)
        statement = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
        if field.index and not field.pk:
            index_name = self._get_index_name(table_name, column_name)
            statement += ";\n" + self.add_index(table_name, index_name, [column_name], unique=field.unique)
        return statement

    def drop_column(self, table_name: str, column_name: str) -> str:
        return f"ALTER TABLE {table_name} DROP COLUMN {column_name}"

    def alter_column(
        self, table_name: str, column_name: str, prev_field: Field, new_field: Field
    ) -> str:
        statements = []
        # Get SQL type using the get_for_dialect method
        column_type = new_field.get_for_dialect(self.dialect, "SQL_TYPE")

        # Special case for primary keys
        field_type = new_field.__class__.__name__
        is_pk = getattr(new_field, "pk", False)
        unique = getattr(new_field, "unique", False)
        index = getattr(new_field, "index", False)

        if is_pk and field_type == "IntField" and self.dialect == "postgres":
            column_type = "SERIAL"

        # Type change
        if column_type != prev_field.get_for_dialect(self.dialect, "SQL_TYPE"):
            statements.append(
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {column_type};"
            )

        # Nullability change
        if prev_field.null != new_field.null:
            if new_field.null:
                statements.append(
                    f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP NOT NULL;"
                )
            else:
                statements.append(
                    f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET NOT NULL;"
                )

        # Default value change
        if prev_field.default != new_field.default:
            if not callable(new_field.default):
                default_value = self.default_value_to_sql(new_field.default)
                statements.append(
                    f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT {default_value};"
                )
            else:
                statements.append(
                    f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT;"
                )

        # Unique change
        if unique != prev_field.unique:
            if unique:
                statements.append(
                    f"ALTER TABLE {table_name} ADD CONSTRAINT {column_name}_key UNIQUE ({column_name});"
                )
            else:
                statements.append(f"ALTER TABLE {table_name} DROP CONSTRAINT {column_name}_key;")

        # Index change
        if index != prev_field.index and not is_pk:
            index_name = self._get_index_name(table_name, column_name)
            if index:
                statements.append(self.add_index(table_name, index_name, [column_name], unique=unique))
            else:
                statements.append(self.drop_index(index_name))

        return "\n".join(statements)

    def rename_column(self, table_name: str, column_name: str, new_column_name: str) -> str:
        return f"ALTER TABLE {table_name} RENAME COLUMN {column_name} TO {new_column_name}"

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

        if pk and isinstance(field, IntField):
            sql_type = self._default_pk_type()

        column_def = f"{sql_type}"

        if pk:
            column_def += " " + self._default_pk_keyword(field)

        if not nullable and not pk:
            column_def += " NOT NULL"

        if unique and not pk:
            column_def += " UNIQUE"

        column_def += self.field_default_to_sql(field)

        return column_def
    
    def _get_index_name(self, table_name: str, column_name: str, prefix: str = "idx") -> str:
        """
        Generates a unique index name for a column.  Implementation is based on tortoise's schema generator.

        NOTE: for compatibility, index name should not be longer than 30 characters (Oracle limit).
        """
        
        full_index_name = f"{prefix}_{table_name}_{column_name}"
        if len(full_index_name) <= 30:
            return full_index_name
        else:
            hashed = self._make_hash(table_name, column_name, length=6)
            return f"{prefix}_{table_name[:11]}_{column_name[:7]}_{hashed}"

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

    def _default_pk_type(self):
        return "INT"

    def _default_pk_keyword(self, pk_field: Field):
        return "PRIMARY KEY"

    @staticmethod
    def _make_hash(*args: str, length: int) -> str:
        # Hash a set of string values and get a digest of the given length.
        return sha256(";".join(args).encode("utf-8")).hexdigest()[:length]
