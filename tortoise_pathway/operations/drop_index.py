"""
DropIndex operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.add_index import AddIndex
from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class DropIndex(Operation):
    """Drop an index from a table."""

    def __init__(
        self,
        model: str,
        index_name: str,
    ):
        if not index_name:
            raise ValueError("index_name is required")

        super().__init__(model)
        self.index_name = index_name

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        return schema_manager.drop_index(self.index_name)

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for adding an index."""
        index = state.prev().get_index(self.app_name, self.model_name, self.index_name)
        if index is None:
            raise ValueError(f"Index {self.index_name} not found in model {self.model}")
        return AddIndex(self.model, index).forward_sql(state, schema_manager)

    def to_migration(self) -> str:
        """Generate Python code to drop an index in a migration."""
        lines = []
        lines.append("DropIndex(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    index_name="{self.index_name}",')
        lines.append(")")
        return "\n".join(lines)
