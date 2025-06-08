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
        new_field_name (str | None, optional): The new name for the field.
            If not provided, only the column name will be changed if new_column_name is set.
        new_column_name (str | None, optional): The new name for the database column.
            If not provided, no column rename will be performed.

    Raises:
        ValueError: If neither new_field_name nor new_column_name are provided.
    """

    def __init__(
        self,
        model: str,
        field_name: str,
        new_field_name: str | None = None,
        new_column_name: str | None = None,
    ):
        if new_field_name is None and new_column_name is None:
            raise ValueError("Either new_field_name or new_column_name must be provided")

        super().__init__(model)
        self.field_name = field_name
        self.new_field_name = new_field_name
        self.new_column_name = new_column_name

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for renaming a column."""
        if not self.new_column_name:
            return ""

        column_name = state.get_column_name(self.app_name, self.model_name, self.field_name)

        return schema_manager.rename_column(
            self.get_table_name(state), column_name, self.new_column_name
        )

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for reverting a column rename."""
        if not self.new_column_name:
            return ""

        old_name = state.prev().get_column_name(self.app_name, self.model_name, self.field_name)

        return schema_manager.rename_column(
            self.get_table_name(state), self.new_column_name, old_name
        )

    def to_migration(self) -> str:
        """Generate Python code to rename a field in a migration."""
        lines = []
        lines.append("RenameField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')
        if self.new_field_name:
            lines.append(f'    new_field_name="{self.new_field_name}",')
        if self.new_column_name:
            lines.append(f'    new_column_name="{self.new_column_name}",')
        lines.append(")")
        return "\n".join(lines)
