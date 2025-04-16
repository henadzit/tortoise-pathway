"""
AddField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING
from tortoise.fields import Field


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
        # Determine column name from field object if available
        source_field = getattr(field_object, "source_field", None)
        model_field_name = getattr(field_object, "model_field_name", None)
        self.column_name = source_field or model_field_name or field_name

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding a column."""
        field_type = self.field_object.__class__.__name__
        nullable = getattr(self.field_object, "null", False)
        default = getattr(self.field_object, "default", None)
        is_pk = getattr(self.field_object, "pk", False)

        sql = f"ALTER TABLE {self.get_table_name(state)} ADD COLUMN {self.column_name}"

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

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a column."""
        return f"ALTER TABLE {self.get_table_name(state)} DROP COLUMN {self.column_name}"

    def to_migration(self) -> str:
        """Generate Python code to add a field in a migration."""
        lines = []
        lines.append("AddField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f"    field_object={field_to_migration(self.field_object)},")
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(")")
        return "\n".join(lines)
