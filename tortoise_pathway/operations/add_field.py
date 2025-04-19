"""
AddField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING
from tortoise.fields import Field
from tortoise.fields.relational import RelationalField


from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.operations.utils import default_to_sql, field_to_migration

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class AddField(Operation):
    """Add a new field to an existing model."""

    def __init__(
        self,
        model: str,
        field_object: Field,
        field_name: str,
    ):
        super().__init__(model)
        self.field_object = field_object
        self.field_name = field_name
        source_field = getattr(field_object, "source_field", None)
        if source_field:
            self._db_column = source_field
        elif isinstance(field_object, RelationalField):
            # Default to tortoise convention: field_name + "_id"
            self._db_column = f"{field_name}_id"
        else:
            self._db_column = field_name

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding a column."""
        field_type = self.field_object.__class__.__name__
        nullable = getattr(self.field_object, "null", False)
        default = getattr(self.field_object, "default", None)
        is_pk = getattr(self.field_object, "pk", False)
        is_foreign_key = isinstance(self.field_object, RelationalField)

        # Handle foreign key fields
        if is_foreign_key:
            return self._generate_foreign_key_sql(state, dialect)

        # Handle regular fields
        sql = f"ALTER TABLE {self.get_table_name(state)} ADD COLUMN {self._db_column}"

        # Get SQL type using the get_for_dialect method
        sql_type = self.field_object.get_for_dialect(dialect, "SQL_TYPE")

        # Special case for primary keys
        if is_pk:
            if dialect == "sqlite" and field_type == "IntField":
                # For SQLite, INTEGER PRIMARY KEY AUTOINCREMENT must use exactly "INTEGER" type
                sql_type = "INTEGER"
            elif field_type == "IntField" and dialect == "postgres":
                sql_type = "SERIAL"

        sql += f" {sql_type}"

        if not nullable:
            sql += " NOT NULL"

        if default is not None and not callable(default):
            default_val = default_to_sql(default, dialect)
            sql += f" DEFAULT {default_val}"

        return sql

    def _generate_foreign_key_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding a foreign key column."""
        field = self.field_object

        # Get related model information
        # In Tortoise ORM, RelationalField has a model_name attribute that contains the full model reference
        related_app_model_name = getattr(field, "model_name", "")
        related_model_name = related_app_model_name.split(".")[-1]
        model = state.get_models()[related_model_name]
        related_table = model["table"]
        to_field = getattr(field, "to_field", None) or "id"

        # SQLite doesn't support adding foreign key constraints with ALTER TABLE
        if dialect == "sqlite":
            sql = f"ALTER TABLE {self.get_table_name(state)} ADD COLUMN {self._db_column} INT"

            if not getattr(field, "null", False):
                sql += " NOT NULL"

            sql += f" REFERENCES {related_table}({to_field})"
            return sql

        # For other dialects like PostgreSQL, we can add the foreign key constraint
        if dialect == "postgres":
            # First add the column
            sql = f"ALTER TABLE {self.get_table_name(state)} ADD COLUMN {self._db_column} INT"

            if not getattr(field, "null", False):
                sql += " NOT NULL"

            # Then add the foreign key constraint
            sql += f",\nADD CONSTRAINT fk_{self.get_table_name(state)}_{self._db_column} "
            sql += f"FOREIGN KEY ({self._db_column}) REFERENCES {related_table}({to_field})"

            return sql

        # Default fallback for other dialects
        sql = f"ALTER TABLE {self.get_table_name(state)} ADD COLUMN {self._db_column} INT"

        if not getattr(field, "null", False):
            sql += " NOT NULL"

        return sql

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a column."""
        # For foreign keys, use the DB column name (field_name + "_id")
        return f"ALTER TABLE {self.get_table_name(state)} DROP COLUMN {self._db_column}"

    def to_migration(self) -> str:
        """Generate Python code to add a field in a migration."""
        lines = []
        lines.append("AddField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f"    field_object={field_to_migration(self.field_object)},")
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(")")
        return "\n".join(lines)
