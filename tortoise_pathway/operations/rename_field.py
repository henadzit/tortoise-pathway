"""
RenameField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class RenameField(Operation):
    """Operation to rename a field in a Tortoise ORM model.

    This operation handles both the forward and backward migration of renaming a field
    in a database table. It can rename both the Python field name and the underlying
    database column name.

    Args:
        model (str): The name of the model containing the field to rename.
        field_name (str): The current name of the field to be renamed.
        new_field_name (str): The new name for the field.
        new_column_name (str | None, optional): The new name for the database column.
            If not provided, defaults to new_field_name. This allows for cases where
            the Python field name and database column name should be different.
    """

    def __init__(
        self,
        model: str,
        field_name: str,
        new_field_name: str,
        new_column_name: str | None = None,
    ):
        super().__init__(model)
        self.field_name = field_name
        self.new_field_name = new_field_name
        self.new_column_name = new_column_name

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for renaming a column."""
        column_name = state.get_column_name(self.model_name, self.field_name)
        new_column_name = self.new_column_name or self.new_field_name

        if new_column_name != column_name:
            return schema_manager.rename_column(
                self.get_table_name(state), column_name, new_column_name
            )
        return ""

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for reverting a column rename."""
        old_name = state.prev().get_column_name(self.model_name, self.field_name)
        new_column_name = self.new_column_name or self.new_field_name

        if old_name != new_column_name:
            return schema_manager.rename_column(
                self.get_table_name(state), new_column_name, old_name
            )
        return ""

    def to_migration(self) -> str:
        """Generate Python code to rename a field in a migration."""
        lines = []
        lines.append("RenameField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(f'    new_field_name="{self.new_field_name}",')
        if self.new_column_name:
            lines.append(f'    new_column_name="{self.new_column_name}",')
        lines.append(")")
        return "\n".join(lines)
