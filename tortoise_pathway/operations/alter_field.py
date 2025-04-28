"""
AlterField operation for Tortoise ORM migrations.
"""

from typing import TYPE_CHECKING

from tortoise.fields import Field

from tortoise_pathway.field_ext import field_db_column, field_to_migration
from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.operations.sql import default_value_to_sql

if TYPE_CHECKING:
    from tortoise_pathway.state import State


class AlterField(Operation):
    """Alter the properties of an existing field."""

    def __init__(
        self,
        model: str,
        field_object: Field,
        field_name: str,
    ):
        super().__init__(model)
        self.field_object = field_object
        self.field_name = field_name

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for altering a column."""
        db_column = field_db_column(self.field_object, self.field_name)

        if dialect == "sqlite":
            return self._forward_sql_sqlite(state)
        elif dialect == "postgres":
            statements = []
            # Get SQL type using the get_for_dialect method
            column_type = self.field_object.get_for_dialect(dialect, "SQL_TYPE")

            # Special case for primary keys
            field_type = self.field_object.__class__.__name__
            is_pk = getattr(self.field_object, "pk", False)
            unique = getattr(self.field_object, "unique", False)
            table_name = self.get_table_name(state)

            if is_pk and field_type == "IntField" and dialect == "postgres":
                column_type = "SERIAL"

            field_from_state = state.get_field(self.model_name, self.field_name)
            assert field_from_state is not None

            # Type change
            if column_type != field_from_state.get_for_dialect(dialect, "SQL_TYPE"):
                statements.append(
                    f"ALTER TABLE {table_name} ALTER COLUMN {db_column} TYPE {column_type};"
                )

            # Nullability change
            if self.field_object.null != field_from_state.null:
                if self.field_object.null:
                    statements.append(
                        f"ALTER TABLE {table_name} ALTER COLUMN {db_column} DROP NOT NULL;"
                    )
                else:
                    statements.append(
                        f"ALTER TABLE {table_name} ALTER COLUMN {db_column} SET NOT NULL;"
                    )

            # Default value change
            if self.field_object.default != field_from_state.default:
                if not callable(self.field_object.default):
                    default_value = default_value_to_sql(self.field_object.default, dialect)
                    statements.append(
                        f"ALTER TABLE {table_name} ALTER COLUMN {db_column} SET DEFAULT {default_value};"
                    )
                else:
                    statements.append(
                        f"ALTER TABLE {table_name} ALTER COLUMN {db_column} DROP DEFAULT;"
                    )

            # Unique change
            if unique != field_from_state.unique:
                if unique:
                    statements.append(
                        f"ALTER TABLE {table_name} ADD CONSTRAINT {db_column}_key UNIQUE ({db_column});"
                    )
                else:
                    statements.append(f"ALTER TABLE {table_name} DROP CONSTRAINT {db_column}_key;")

            return "\n".join(statements)
        else:
            return f"-- Alter column not implemented for dialect: {dialect}"

    def _forward_sql_sqlite(self, state: "State") -> str:
        """Generate SQL for altering a column in SQLite. SQLite has a limited set of ALTER TABLE commands,
        so we need to create a new table and copy the data over."""
        table_name = self.get_table_name(state)
        temp_table_name = f"__new__{table_name}"

        # Step 1: Begin transaction
        sql = "BEGIN TRANSACTION;\n"

        # Step 2: Create a new table with the desired schema
        # First, get all fields from the model
        model_fields = state.get_fields(self.model_name)
        if model_fields is None:
            raise ValueError(f"Model {self.model_name} not found in state")

        # Replace the altered field with the new field object
        model_fields[self.field_name] = self.field_object

        # Create temporary model with the updated fields
        from tortoise_pathway.operations.create_model import CreateModel

        temp_model = CreateModel(self.model, temp_table_name, model_fields)

        # Generate CREATE TABLE statement for the new table
        sql += temp_model.forward_sql(state, "sqlite") + ";\n"

        # Step 3: Copy data from old table to new table
        # Get all column names from the model
        column_names = [
            state.get_column_name(self.model_name, field_name) or field_name
            for field_name in model_fields.keys()
            if model_fields[field_name].__class__.__name__ != "BackwardFKRelation"
        ]

        # Create INSERT statement to copy data
        source_columns = ", ".join(column_names)
        target_columns = source_columns  # In SQLite rename, columns keep same names

        sql += f"INSERT INTO {temp_table_name} ({target_columns})\n"
        sql += f"SELECT {source_columns} FROM {table_name};\n"

        # Step 4: Drop the old table
        sql += f"DROP TABLE {table_name};\n"

        # Step 5: Rename the new table to the original name
        sql += f"ALTER TABLE {temp_table_name} RENAME TO {table_name};\n"

        # Complete the transaction
        sql += "COMMIT;"
        return sql

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        prev_field = state.prev().get_field(self.model_name, self.field_name)
        if prev_field is None:
            raise ValueError(f"Field {self.field_name} not found in model {self.model_name}")
        return AlterField(self.model, prev_field, self.field_name).forward_sql(state, dialect)

    def to_migration(self) -> str:
        """Generate Python code to alter a field in a migration."""
        lines = []
        lines.append("AlterField(")
        lines.append(f'    model="{self.model}",')
        lines.append(f"    field_object={field_to_migration(self.field_object)},")
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(")")
        return "\n".join(lines)
