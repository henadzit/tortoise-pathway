"""
RenameModel operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class RenameModel(Operation):
    """Rename an existing model."""

    def __init__(
        self,
        model: str,
        new_name: str,
    ):
        super().__init__(model)
        self.new_name = new_name

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for renaming the table."""
        return schema_manager.rename_table(self.get_table_name(state), self.new_name)

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for reverting the table rename."""
        return schema_manager.rename_table(self.new_name, self.get_table_name(state))

    def to_migration(self) -> str:
        """Generate Python code to rename a model in a migration."""
        lines = []
        lines.append("RenameModel(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(")")
        return "\n".join(lines)
