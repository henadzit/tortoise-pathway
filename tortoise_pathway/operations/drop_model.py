"""
DropModel operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class DropModel(Operation):
    """Drop an existing model."""

    def __init__(
        self,
        model: str,
    ):
        super().__init__(model)

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for dropping the table."""
        return schema_manager.drop_table(self.get_table_name(state))

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for recreating the table."""

        # Since model is now a string instead of a Model class,
        # we need to provide guidance for handling this in migrations
        return f"-- To recreate table {self.get_table_name(state)}, import the model class from '{self.model}' first"

    def to_migration(self) -> str:
        """Generate Python code to drop a model in a migration."""
        lines = []
        lines.append("DropModel(")
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)
