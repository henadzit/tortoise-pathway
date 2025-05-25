"""
RunSQL operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING, Optional

from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class RunSQL(Operation):
    """
    Run arbitrary SQL queries.

    This operation can be used to execute SQL commands directly in the database.
    It takes forward and backward SQL statements to enable migrations to be applied and reverted.

    Args:
        forward_sql: SQL statement(s) to execute when applying the migration.
        backward_sql: SQL statement(s) to execute when reverting the migration.
            If None, the migration cannot be reverted.
    """

    def __init__(
        self,
        forward_sql: str,
        backward_sql: Optional[str] = None,
    ):
        self.forward_sql_str = forward_sql
        self.backward_sql_str = backward_sql

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Return the SQL statement(s) to execute when applying the migration."""
        return self.forward_sql_str

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """Return the SQL statement(s) to execute when reverting the migration."""
        if self.backward_sql_str is None:
            return ""
        return self.backward_sql_str

    def to_migration(self) -> str:
        """Generate Python code to run SQL in a migration."""
        lines = []
        lines.append("RunSQL(")

        # Format multi-line SQL as triple-quoted strings
        if "\n" in self.forward_sql_str:
            lines.append('    forward_sql="""')
            lines.append(self.forward_sql_str)
            lines.append('""",')
        else:
            lines.append(f'    forward_sql="{self.forward_sql_str}",')

        # Format backward SQL if provided
        if self.backward_sql_str:
            if "\n" in self.backward_sql_str:
                lines.append('    backward_sql="""')
                lines.append(self.backward_sql_str)
                lines.append('""",')
            else:
                lines.append(f'    backward_sql="{self.backward_sql_str}",')
        else:
            lines.append("    backward_sql=None,")

        lines.append(")")
        return "\n".join(lines)
