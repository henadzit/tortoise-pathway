"""
RenameField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class RenameField(Operation):
    """Rename an existing field."""

    def __init__(
        self,
        model: str,
        field_name: str,
        new_name: str,
    ):
        super().__init__(model)
        self.field_name = field_name
        self.new_name = new_name

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for renaming a column."""
        column_name = state.get_column_name(self.model_name, self.field_name)

        return schema_manager.rename_column(self.get_table_name(state), column_name, self.new_name)

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for reverting a column rename."""
        old_name = state.prev().get_column_name(self.model_name, self.field_name)

        return schema_manager.rename_column(self.get_table_name(state), self.new_name, old_name)

    def to_migration(self) -> str:
        """Generate Python code to rename a field in a migration."""
        lines = []
        lines.append("RenameField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(")")
        return "\n".join(lines)
