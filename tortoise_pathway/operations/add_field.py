"""
AddField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING
from tortoise.fields import Field
from tortoise.fields.relational import RelationalField

from tortoise_pathway.field_ext import field_db_column, field_to_migration
from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

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
        self._db_column = field_db_column(field_object, field_name)

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for adding a column."""
        # Handle foreign key fields
        if isinstance(self.field_object, RelationalField):
            related_model_ref = getattr(self.field_object, "model_name", "")
            related_model_app, related_model_name = self._split_model_reference(related_model_ref)
            model = state.get_model(related_model_app, related_model_name)
            related_table = model["table"]
            to_field = getattr(self.field_object, "to_field", None) or "id"
            return schema_manager.add_foreign_key_column(
                self.get_table_name(state),
                self._db_column,
                related_table,
                to_field,
                getattr(self.field_object, "null", False),
            )

        return schema_manager.add_column(
            self.get_table_name(state),
            self._db_column,
            self.field_object,
        )

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for dropping a column."""
        return schema_manager.drop_column(
            self.get_table_name(state),
            self._db_column,
        )

    def to_migration(self) -> str:
        """Generate Python code to add a field in a migration."""
        lines = []
        lines.append("AddField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f"    field_object={field_to_migration(self.field_object)},")
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(")")
        return "\n".join(lines)
