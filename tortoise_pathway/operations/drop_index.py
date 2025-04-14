"""
DropIndex operation for Tortoise ORM migrations.
"""

import re
from typing import Optional, TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class DropIndex(Operation):
    """Drop an index from a table."""

    def __init__(
        self,
        model: str,
        field_name: str,
        index_name: Optional[str] = None,
    ):
        super().__init__(model)
        self.field_name = field_name
        # Convert model name from CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        self.index_name = index_name or f"idx_{table_name}_{field_name}"

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX {self.index_name}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding an index."""
        column_name = state.get_column_name(self.model_name, self.field_name)
        # Fall back to field name if column name is None
        if column_name is None:
            column_name = self.field_name
        return f"CREATE INDEX {self.index_name} ON {self.get_table_name(state)} ({column_name})"

    def to_migration(self) -> str:
        """Generate Python code to drop an index in a migration."""
        lines = []
        lines.append("DropIndex(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')

        # Convert model name to snake_case for default index name
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        default_index_name = f"idx_{table_name}_{self.field_name}"

        if self.index_name != default_index_name:
            lines.append(f'    index_name="{self.index_name}",')

        lines.append(")")
        return "\n".join(lines)
