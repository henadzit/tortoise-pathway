"""
RenameModel operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation

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

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for renaming the table."""
        if dialect == "sqlite" or dialect == "postgres":
            return f"ALTER TABLE {self.get_table_name(state)} RENAME TO {self.new_name}"
        else:
            return f"-- Rename table not implemented for dialect: {dialect}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for reverting the table rename."""
        if dialect == "sqlite" or dialect == "postgres":
            return f"ALTER TABLE {self.new_name} RENAME TO {self.get_table_name(state)}"
        else:
            return f"-- Rename table not implemented for dialect: {dialect}"

    def to_migration(self) -> str:
        """Generate Python code to rename a model in a migration."""
        lines = []
        lines.append("RenameModel(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(")")
        return "\n".join(lines)
