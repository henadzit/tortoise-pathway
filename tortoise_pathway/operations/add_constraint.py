"""
AddConstraint operation for Tortoise ORM migrations.
"""

from typing import Optional, TYPE_CHECKING

from tortoise_pathway.operations.operation import Operation

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class AddConstraint(Operation):
    """Add a constraint to a table."""

    def __init__(
        self,
        model: str,
        field_name: str,
        constraint_name: Optional[str] = None,
        constraint_type: str = "CHECK",
        constraint_clause: Optional[str] = None,
    ):
        super().__init__(model)
        self.field_name = field_name
        self.constraint_name = (
            constraint_name or f"constraint_{self.model_name.lower()}_{field_name}"
        )
        self.constraint_type = constraint_type
        # Ensure constraint_clause is always a string
        self.constraint_clause = (
            constraint_clause if constraint_clause is not None else f"{field_name} IS NOT NULL"
        )

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding a constraint."""
        column_name = state.get_column_name(self.model_name, self.field_name)

        # We need to ensure self.constraint_clause is not None and replace field_name with column_name
        constraint_clause = self.constraint_clause.replace(
            self.field_name, column_name if column_name else self.field_name
        )

        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Adding constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.get_table_name(state)} ADD CONSTRAINT {self.constraint_name} {self.constraint_type} ({constraint_clause})"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a constraint."""
        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Dropping constraints in SQLite may require table recreation"
        else:
            return (
                f"ALTER TABLE {self.get_table_name(state)} DROP CONSTRAINT {self.constraint_name}"
            )

    def to_migration(self) -> str:
        """Generate Python code to add a constraint in a migration."""
        lines = []
        lines.append("AddConstraint(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')

        # Instead of comparing with get_table_name(state), use default constraint name pattern
        default_constraint_name = f"constraint_{self.model_name.lower()}_{self.field_name}"
        if self.constraint_name != default_constraint_name:
            lines.append(f'    constraint_name="{self.constraint_name}",')

        if self.constraint_type != "CHECK":
            lines.append(f'    constraint_type="{self.constraint_type}",')

        if self.constraint_clause != f"{self.field_name} IS NOT NULL":
            lines.append(f'    constraint_clause="{self.constraint_clause}",')

        lines.append(")")
        return "\n".join(lines)
