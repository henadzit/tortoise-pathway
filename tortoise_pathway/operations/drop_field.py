"""
DropField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.operations.add_field import AddField
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class DropField(Operation):
    """Drop a field from an existing model."""

    def __init__(
        self,
        model: str,
        field_name: str,
    ):
        super().__init__(model)
        self.field_name = field_name

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        # Get actual column name from state
        column_name = state.get_column_name(self.app_name, self.model_name, self.field_name)
        if column_name is None:
            raise ValueError(f"Column {self.field_name} not found in model {self.model_name}")

        return schema_manager.drop_column(self.get_table_name(state), column_name)

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        field = state.prev().get_field(self.model_name, self.field_name)
        if field is None:
            raise ValueError(f"Field {self.field_name} not found in model {self.model_name}")
        return AddField(self.model, field, self.field_name).forward_sql(state, schema_manager)

    def to_migration(self) -> str:
        """Generate Python code to drop a field in a migration."""
        lines = []
        lines.append("DropField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(")")
        return "\n".join(lines)
