"""
CreateModel operation for Tortoise ORM migrations.
"""

from typing import Dict, TYPE_CHECKING

from tortoise.fields import Field
from tortoise.fields.relational import RelationalField

from tortoise_pathway.field_ext import field_db_column, field_to_migration
from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

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

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for creating the table."""
        columns = {}
        foreign_keys = []

        # Process each field
        for field_name, field in self.fields.items():
            field_type = field.__class__.__name__

            # Skip if this is a reverse relation
            if field_type == "BackwardFKRelation":
                continue

            db_column = field_db_column(field, field_name)
            columns[db_column] = field

            # Handle ForeignKey fields
            if isinstance(field, RelationalField):
                related_model_app, related_model_name = self._split_model_reference(
                    field.model_name
                )
                model = state.get_model(related_model_app, related_model_name)
                related_table = model["table"]
                to_field = field.to_field or "id"
                foreign_keys.append((db_column, related_table, to_field))
        return schema_manager.create_table(self.table, columns, foreign_keys)

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for dropping the table."""
        return schema_manager.drop_table(self.table)

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
