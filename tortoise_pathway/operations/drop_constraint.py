"""
DropConstraint operation for Tortoise ORM migrations.
"""

from typing import Optional, TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class DropConstraint(Operation):
    """Drop a constraint from a table."""

    def __init__(
        self,
        model: str,
        field_name: str,
        constraint_name: Optional[str] = None,
    ):
        super().__init__(model)
        self.field_name = field_name
        self.constraint_name = (
            constraint_name or f"constraint_{self.model_name.lower()}_{field_name}"
        )

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a constraint."""
        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Dropping constraints in SQLite may require table recreation"
        else:
            return (
                f"ALTER TABLE {self.get_table_name(state)} DROP CONSTRAINT {self.constraint_name}"
            )

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding a constraint."""
        column_name = state.get_column_name(self.model_name, self.field_name)

        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Adding constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.get_table_name(state)} ADD CONSTRAINT {self.constraint_name} CHECK ({column_name} IS NOT NULL)"

    def to_migration(self) -> str:
        """Generate Python code to drop a constraint in a migration."""
        lines = []
        lines.append("DropConstraint(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')

        # Instead of comparing with get_table_name(state), use default constraint name pattern
        default_constraint_name = f"constraint_{self.model_name.lower()}_{self.field_name}"
        if self.constraint_name != default_constraint_name:
            lines.append(f'    constraint_name="{self.constraint_name}",')

        lines.append(")")
        return "\n".join(lines)
