"""
CreateModel operation for Tortoise ORM migrations.
"""

from typing import Dict, TYPE_CHECKING

from tortoise.fields import Field
from tortoise.fields.relational import RelationalField

from tortoise_pathway.field_ext import field_db_column, field_to_migration
from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.operations.sql import field_definition_to_sql

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class CreateModel(Operation):
    """Create a new model."""

    def __init__(
        self,
        model: str,
        table: str,
        fields: Dict[str, Field],
    ):
        super().__init__(model)
        self.table = table
        self.fields = fields

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for creating the table."""
        return self._generate_sql_from_fields(state, dialect)

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping the table."""
        return f"DROP TABLE {self.table}"

    def _generate_sql_from_fields(self, state: "State", dialect: str = "sqlite") -> str:
        """
        Generate SQL to create a table from the fields dictionary.

        Args:
            state: State object that contains schema information.
            dialect: SQL dialect to use (default: "sqlite").

        Returns:
            SQL string for table creation.
        """
        columns = []
        constraints = []

        # Process each field
        for field_name, field in self.fields.items():
            field_type = field.__class__.__name__

            # Skip if this is a reverse relation
            if field_type == "BackwardFKRelation":
                continue

            db_column = field_db_column(field, field_name)

            # Handle ForeignKey fields
            if isinstance(field, RelationalField):
                related_app_model_name = field.model_name
                related_model_name = related_app_model_name.split(".")[-1]
                model = state.get_model(related_model_name)
                related_table = model["table"]
                to_field = field.to_field or "id"
                constraints.append(
                    f'FOREIGN KEY ({db_column}) REFERENCES "{related_table}" ({to_field})'
                )

            column_def = field_definition_to_sql(field, dialect)
            columns.append(f"{db_column} {column_def}")

        # Build the CREATE TABLE statement
        sql = f'CREATE TABLE "{self.table}" (\n'
        sql += ",\n".join(["    " + col for col in columns])

        if constraints:
            sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

        sql += "\n);"

        return sql

    def to_migration(self) -> str:
        """Generate Python code to create a model in a migration."""
        lines = []
        lines.append("CreateModel(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    table="{self.table}",')

        # Include fields
        lines.append("    fields={")
        for field_name, field_obj in self.fields.items():
            # Skip reverse relations
            if field_obj.__class__.__name__ == "BackwardFKRelation":
                continue

            # Use field_to_migration to generate the field representation
            lines.append(f'        "{field_name}": {field_to_migration(field_obj)},')
        lines.append("    },")

        lines.append(")")
        return "\n".join(lines)
