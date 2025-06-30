"""
RenameModel operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class RenameModel(Operation):
    """Operation to rename an existing Tortoise ORM model.

    This operation allows renaming either the model name, the table name, or both.
    At least one of new_model_name or new_table_name must be provided.

    Args:
        model (str): The name of the model to rename.
        new_model_name (str | None, optional): The new name for the model. Defaults to None.
        new_table_name (str | None, optional): The new name for the database table. Defaults to None.
    """

    def __init__(
        self,
        model: str,
        new_model_name: str | None = None,
        new_table_name: str | None = None,
    ):
        if not new_model_name and not new_table_name:
            raise ValueError("new_model_name or new_table_name must be provided")

        super().__init__(model)
        self.new_model_name = new_model_name
        self.new_table_name = new_table_name

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for renaming the table."""

        if not self.new_table_name:
            return ""

        return schema_manager.rename_table(self.get_table_name(state), self.new_table_name)

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for reverting the table rename."""
        if not self.new_table_name:
            return ""

        old_table_name = state.prev().get_table_name(self.app_name, self.model_name)

        return schema_manager.rename_table(self.new_table_name, old_table_name)

    def to_migration(self) -> str:
        """Generate Python code to rename a model in a migration."""
        lines = []
        lines.append("RenameModel(")
        lines.append(f'    model="{self.model}",')
        if self.new_model_name:
            lines.append(f'    new_model_name="{self.new_model_name}",')
        if self.new_table_name:
            lines.append(f'    new_table_name="{self.new_table_name}",')
        lines.append(")")
        return "\n".join(lines)
