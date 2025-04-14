"""
AddIndex operation for Tortoise ORM migrations.
"""

import re
from typing import List, Optional, TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class AddIndex(Operation):
    """Add an index to a table."""

    def __init__(
        self,
        model: str,
        field_name: str,
        index_name: Optional[str] = None,
        unique: bool = False,
        fields: Optional[List[str]] = None,
    ):
        super().__init__(model)
        self.field_name = field_name
        # Convert model name from CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        self.index_name = index_name or f"idx_{table_name}_{field_name}"
        self.unique = unique
        self.fields = fields or [field_name]

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding an index."""
        # Get actual column names from field names
        column_names = []
        for field_name in self.fields:
            column_name = state.get_column_name(self.model_name, field_name)
            # Fall back to field name if column name is None
            if column_name is None:
                column_name = field_name
            column_names.append(column_name)

        unique_prefix = "UNIQUE " if self.unique else ""
        columns_str = ", ".join(column_names)
        return f"CREATE {unique_prefix}INDEX {self.index_name} ON {self.get_table_name(state)} ({columns_str})"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX {self.index_name}"

    def to_migration(self) -> str:
        """Generate Python code to add an index in a migration."""
        lines = []
        lines.append("AddIndex(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')

        # Convert model name to snake_case for default index name
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        default_index_name = f"idx_{table_name}_{self.field_name}"

        if self.index_name != default_index_name:
            lines.append(f'    index_name="{self.index_name}",')

        if self.unique:
            lines.append("    unique=True,")

        if self.fields != [self.field_name]:
            fields_repr = "[" + ", ".join([f'"{field}"' for field in self.fields]) + "]"
            lines.append(f"    fields={fields_repr},")

        lines.append(")")
        return "\n".join(lines)
