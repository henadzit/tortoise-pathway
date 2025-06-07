"""
AddIndex operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise.indexes import Index
from tortoise_pathway.index_ext import UniqueIndex

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class AddIndex(Operation):
    """Add an index to a table."""

    def __init__(
        self,
        model: str,
        index: Index,
    ):
        if not index.name:
            raise ValueError("Index name is required")

        super().__init__(model)
        self.index = index
        self.index_name = index.name
        self.unique = isinstance(index, UniqueIndex)
        self.fields = index.fields

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for adding an index."""
        table_name = state.get_table_name(self.app_name, self.model_name)
        column_names = []
        for field_name in self.index.fields:
            column_name = state.get_column_name(self.app_name, self.model_name, field_name)
            # Fall back to field name if column name is None
            if column_name is None:
                column_name = field_name
            column_names.append(column_name)  # Get actual column names from field names
        return schema_manager.add_index(
            table_name, self.index_name, column_names, self.unique, self.index.INDEX_TYPE
        )

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Generate SQL for dropping an index."""
        return schema_manager.drop_index(self.index_name)

    def to_migration(self) -> str:
        """Generate Python code to add an index in a migration."""
        lines = []
        lines.append("AddIndex(")
        lines.append(f'    model="{self.model}",')
        lines.append(f"    index={self.index.__class__.__name__}(")

        if self.index.fields:
            fields_repr = "[" + ", ".join([f'"{field}"' for field in self.index.fields]) + "]"
            lines.append(f"        fields={fields_repr},")

        if self.index.name:
            lines.append(f'        name="{self.index.name}",')

        lines.append("    ),")
        lines.append(")")
        return "\n".join(lines)
