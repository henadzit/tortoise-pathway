"""
RenameField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation

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

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for renaming a column."""
        column_name = state.get_column_name(self.model_name, self.field_name)

        return f"ALTER TABLE {self.get_table_name(state)} RENAME COLUMN {column_name} TO {self.new_name}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for reverting a column rename."""
        old_name = state.prev().get_column_name(self.model_name, self.field_name)

        return (
            f"ALTER TABLE {self.get_table_name(state)} RENAME COLUMN {self.new_name} TO {old_name}"
        )

    def to_migration(self) -> str:
        """Generate Python code to rename a field in a migration."""
        lines = []
        lines.append("RenameField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(")")
        return "\n".join(lines)
