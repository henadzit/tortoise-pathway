"""
Schema difference detection for Tortoise ORM migrations.

This module provides functionality to detect differences between Tortoise models
and the actual database schema, generating migration operations.
"""

import re
from typing import Dict, Optional, List, TYPE_CHECKING

from tortoise import connections
from tortoise.fields import Field
from tortoise.fields.relational import RelationalField

if TYPE_CHECKING:
    from tortoise_pathway.state import State

def get_dialect(connection) -> str:
    """
    Determine the database dialect from a connection.

    Args:
        connection: The database connection.

    Returns:
        A string representing the dialect ('sqlite', 'postgres', etc.)
    """
    # Check connection attributes or class name to determine dialect
    connection_class = connection.__class__.__name__

    if "SQLite" in connection_class:
        return "sqlite"
    elif "Postgres" in connection_class:
        return "postgres"
    elif "MySQL" in connection_class:
        return "mysql"

    # Default to sqlite if unknown
    return "sqlite"


class SchemaChange:
    """Base class for all schema changes.

    Args:
        model: Model reference in the format "{app_name}.{model_name}".
    """

    def __init__(
        self,
        model: str,
    ):
        self.model = model
        self.app_name, self.model_name = self._split_model_reference(model)
        self._override_table_name = None

    def _split_model_reference(self, model_ref: str) -> tuple:
        """Split model reference into app and model name."""
        app, _, model_name = model_ref.rpartition(".")
        if not app or not model_name:
            raise ValueError(f"Invalid model reference: {model_ref}. Expected format: 'app.Model'")
        return app, model_name

    def get_table_name(self, state: "State") -> str:
        """
        Get the table name for this schema change.

        Args:
            state: State object that contains schema information.

        Returns:
            The table name for the model.
        """
        # First check if there's an override
        if self._override_table_name:
            return self._override_table_name

            # Use the state's get_table_name method
        table_name = state.get_table_name(self.app_name, self.model_name)
        if table_name:
            return table_name

        # Fall back to Tortoise.apps if available
        try:
            from tortoise import Tortoise

            if (
                Tortoise.apps
                and self.app_name in Tortoise.apps
                and self.model_name in Tortoise.apps[self.app_name]
            ):
                model_class = Tortoise.apps[self.app_name][self.model_name]
                if hasattr(model_class, "_meta") and hasattr(model_class._meta, "db_table"):
                    return model_class._meta.db_table
        except (ImportError, AttributeError):
            pass

        # Last resort: Convert from model name to table name using convention
        # (typically CamelCase to snake_case)
        import re

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def set_table_name(self, table_name: str) -> None:
        """
        Override the table name for testing or specific use cases.

        Args:
            table_name: The table name to use.
        """
        self._override_table_name = table_name

    async def apply(self, state: "State", connection_name: str = "default") -> None:
        """
        Apply this schema change to the database.

        Args:
            state: State object that contains schema information.
            connection_name: The database connection name to use.
        """
        connection = connections.get(connection_name)
        sql = self.forward_sql(state=state, dialect=get_dialect(connection))
        await connection.execute_script(sql)

    async def revert(self, state: "State", connection_name: str = "default") -> None:
        """
        Revert this schema change from the database.

        Args:
            state: State object that contains schema information.
            connection_name: The database connection name to use.
        """
        connection = connections.get(connection_name)
        sql = self.backward_sql(state=state, dialect=get_dialect(connection))
        await connection.execute_script(sql)

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """
        Generate SQL for applying this change forward.

        Args:
            state: State object that contains schema information.
            dialect: SQL dialect (default: "sqlite").

        Returns:
            SQL string for applying the change.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """
        Generate SQL for reverting this change.

        Args:
            state: State object that contains schema information.
            dialect: SQL dialect (default: "sqlite").

        Returns:
            SQL string for reverting the change.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def to_migration(self) -> str:
        """
        Generate Python code for this schema change to be included in a migration file.

        Returns:
            String with Python code that represents this schema change operation,
            suitable for inclusion in Migration.operations list.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def __str__(self) -> str:
        return self.to_migration().replace("\n", "")


class CreateTable(SchemaChange):
    """Create a new table."""

    def __init__(
        self,
        model: str,
        fields: Dict[str, Field],
    ):
        super().__init__(model)
        self.fields = fields

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for creating the table."""
        return self._generate_sql_from_fields(state, dialect)

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping the table."""
        return f"DROP TABLE {self.get_table_name(state)}"

    def _generate_sql_from_fields(self, state: "State", dialect: str = "sqlite") -> str:
        """
        Generate SQL to create a table from the fields dictionary.

        Args:
            state: State object that contains schema information.
            dialect: SQL dialect to use (default: "sqlite").

        Returns:
            SQL string for table creation.
        """
        columns = []
        constraints = []

        # Process each field
        for field_name, field in self.fields.items():
            field_type = field.__class__.__name__

            # Skip if this is a reverse relation
            if field_type == "BackwardFKRelation":
                continue

            # Handle ForeignKey fields
            if field_type == "ForeignKeyField":
                # For ForeignKeyField, use the actual db column name (typically field_name + "_id")
                db_field_name = getattr(field, "model_field_name", field_name)
                source_field = getattr(field, "source_field", None)
                if source_field:
                    db_column = source_field
                else:
                    # Default to tortoise convention: field_name + "_id"
                    db_column = f"{db_field_name}_id"

                # Add foreign key constraint if related table is known
                related_model_name = getattr(field, "model_name", None)
                related_table = getattr(field, "related_table", None)

                if related_table:
                    constraints.append(f"FOREIGN KEY ({db_column}) REFERENCES {related_table} (id)")
            else:
                # Use source_field if provided, otherwise use the field name
                source_field = getattr(field, "source_field", None)
                db_column = source_field if source_field is not None else field_name

            nullable = getattr(field, "null", False)
            unique = getattr(field, "unique", False)
            pk = getattr(field, "pk", False)
            default = getattr(field, "default", None)

            # Get SQL type using the get_for_dialect method
            sql_type = field.get_for_dialect(dialect, "SQL_TYPE")

            # Handle special cases for primary keys
            if pk:
                if dialect == "sqlite" and field_type == "IntField":
                    # For SQLite, INTEGER PRIMARY KEY AUTOINCREMENT must use exactly "INTEGER" type
                    sql_type = "INTEGER"
                elif pk and field_type == "IntField" and dialect == "postgres":
                    sql_type = "SERIAL"

            # Build column definition
            column_def = f"{db_column} {sql_type}"

            if pk:
                if dialect == "sqlite":
                    column_def += " PRIMARY KEY"
                    if field_type == "IntField":
                        column_def += " AUTOINCREMENT"
                else:
                    column_def += " PRIMARY KEY"
                    if field_type == "IntField" and dialect == "postgres":
                        # For PostgreSQL, we'd use SERIAL instead
                        column_def = f"{db_column} {sql_type} PRIMARY KEY"

            if not nullable and not pk:
                column_def += " NOT NULL"

            if unique and not pk:
                column_def += " UNIQUE"

            if default is not None and not callable(default):
                if isinstance(default, bool):
                    default_val = "1" if default else "0"
                elif isinstance(default, (int, float)):
                    default_val = str(default)
                elif isinstance(default, str):
                    default_val = f"'{default}'"
                else:
                    default_val = f"'{default}'"

                column_def += f" DEFAULT {default_val}"

            columns.append(column_def)

        # Build the CREATE TABLE statement
        sql = f"CREATE TABLE {self.get_table_name(state)} (\n"
        sql += ",\n".join(["    " + col for col in columns])

        if constraints:
            sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

        sql += "\n);"

        return sql

    def to_migration(self) -> str:
        """Generate Python code to create a table in a migration."""
        lines = []
        lines.append("CreateTable(")
        lines.append(f'    model="{self.model}",')

        # Include fields
        lines.append("    fields={")
        for field_name, field_obj in self.fields.items():
            # Skip reverse relations
            if field_obj.__class__.__name__ == "BackwardFKRelation":
                continue

            # Use field_to_migration to generate the field representation
            lines.append(f'        "{field_name}": {field_to_migration(field_obj)},')
        lines.append("    },")

        lines.append(")")
        return "\n".join(lines)


class DropTable(SchemaChange):
    """Drop an existing table."""

    def __init__(
        self,
        model: str,
    ):
        super().__init__(model)

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping the table."""
        return f"DROP TABLE {self.get_table_name(state)}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for recreating the table."""

        # Since model is now a string instead of a Model class,
        # we need to provide guidance for handling this in migrations
        return f"-- To recreate table {self.get_table_name(state)}, import the model class from '{self.model}' first"

    def to_migration(self) -> str:
        """Generate Python code to drop a table in a migration."""
        lines = []
        lines.append("DropTable(")
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class RenameTable(SchemaChange):
    """Rename an existing table."""

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
        """Generate Python code to rename a table in a migration."""
        lines = []
        lines.append("RenameTable(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(")")
        return "\n".join(lines)


class AddColumn(SchemaChange):
    """Add a new column to an existing table."""

    def __init__(
        self,
        model: str,
        field_object: Field,
        field_name: str,
    ):
        super().__init__(model)
        self.field_object = field_object
        self.field_name = field_name
        # Determine column name from field object if available
        source_field = getattr(field_object, "source_field", None)
        model_field_name = getattr(field_object, "model_field_name", None)
        self.column_name = source_field or model_field_name or field_name

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding a column."""
        field_type = self.field_object.__class__.__name__
        nullable = getattr(self.field_object, "null", False)
        default = getattr(self.field_object, "default", None)
        is_pk = getattr(self.field_object, "pk", False)

        sql = f"ALTER TABLE {self.get_table_name(state)} ADD COLUMN {self.column_name}"

        # Get SQL type using the get_for_dialect method
        sql_type = self.field_object.get_for_dialect(dialect, "SQL_TYPE")

        # Special case for primary keys
        if is_pk:
            if dialect == "sqlite" and field_type == "IntField":
                # For SQLite, INTEGER PRIMARY KEY AUTOINCREMENT must use exactly "INTEGER" type
                sql_type = "INTEGER"
            elif field_type == "IntField" and dialect == "postgres":
                sql_type = "SERIAL"

        sql += f" {sql_type}"

        if not nullable:
            sql += " NOT NULL"

        if default is not None and not callable(default):
            if isinstance(default, bool):
                default_val = "1" if default else "0"
            elif isinstance(default, (int, float)):
                default_val = str(default)
            elif isinstance(default, str):
                default_val = f"'{default}'"
            else:
                default_val = f"'{default}'"
            sql += f" DEFAULT {default_val}"

        return sql

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a column."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support DROP COLUMN directly. Create a new table without this column."
        else:
            return f"ALTER TABLE {self.get_table_name(state)} DROP COLUMN {self.column_name}"

    def to_migration(self) -> str:
        """Generate Python code to add a column in a migration."""
        lines = []
        lines.append("AddColumn(")
        lines.append(f'    model="{self.model}",')
        lines.append(f"    field_object={field_to_migration(self.field_object)},")
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(")")
        return "\n".join(lines)


class DropColumn(SchemaChange):
    """Drop a column from an existing table."""

    def __init__(
        self,
        model: str,
        field_name: str,
    ):
        super().__init__(model)
        self.field_name = field_name

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a column."""
        # Get actual column name from state
        column_name = state.get_column_name(self.app_name, self.model_name, self.field_name)

        if dialect == "sqlite":
            return "-- SQLite doesn't support DROP COLUMN directly. Create a new table without this column."
        else:
            return f"ALTER TABLE {self.get_table_name(state)} DROP COLUMN {column_name}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for recreating a column."""
        # With the model as a string, we can't directly access fields_map
        # An implementation would need to import the model dynamically
        column_name = state.get_column_name(self.app_name, self.model_name, self.field_name)
        return f"-- Recreating column {column_name} with string model reference requires implementation"

    def to_migration(self) -> str:
        """Generate Python code to drop a column in a migration."""
        lines = []
        lines.append("DropColumn(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    field_name="{self.field_name}",')
        lines.append(")")
        return "\n".join(lines)


class AlterColumn(SchemaChange):
    """Alter the properties of an existing column."""

    def __init__(
        self,
        model: str,
        column_name: str,
        field_object: Field,
        field_name: str,
        old_field_object: Optional[Field] = None,
    ):
        super().__init__(model)
        self.column_name = column_name
        self.field_object = field_object
        self.field_name = field_name
        self.old_field_object = old_field_object

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for altering a column."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support ALTER COLUMN directly. Create a new table with the new schema."
        elif dialect == "postgres":
            # Get SQL type using the get_for_dialect method
            column_type = self.field_object.get_for_dialect(dialect, "SQL_TYPE")

            # Special case for primary keys
            field_type = self.field_object.__class__.__name__
            is_pk = getattr(self.field_object, "pk", False)

            if is_pk and field_type == "IntField" and dialect == "postgres":
                column_type = "SERIAL"

            return f"ALTER TABLE {self.get_table_name(state)} ALTER COLUMN {self.column_name} TYPE {column_type}"
        else:
            return f"-- Alter column not implemented for dialect: {dialect}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for reverting a column alteration."""
        # This requires old column information
        if not self.old_field_object:
            return "-- Cannot revert column alteration: old column information not available"

        # Even with old info, SQLite doesn't support this directly
        if dialect == "sqlite":
            return "-- SQLite doesn't support ALTER COLUMN directly. Create a new table with the original schema."

        # For postgres and other databases that support ALTER COLUMN
        # This is a simplified version, would need more detailed logic for a real implementation
        return f"-- Reverting column alteration for {self.column_name} requires manual intervention"

    def to_migration(self) -> str:
        """Generate Python code to alter a column in a migration."""
        lines = []
        lines.append("AlterColumn(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f"    field_object={field_to_migration(self.field_object)},")
        lines.append(f'    field_name="{self.field_name}",')

        if self.old_field_object:
            lines.append(f"    old_field_object={field_to_migration(self.old_field_object)},")

        lines.append(")")
        return "\n".join(lines)


class RenameColumn(SchemaChange):
    """Rename an existing column."""

    def __init__(
        self,
        model: str,
        column_name: str,
        new_name: str,
    ):
        super().__init__(model)
        self.column_name = column_name
        self.new_name = new_name

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for renaming a column."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support RENAME COLUMN directly. Create a new table with the new schema."
        elif dialect == "postgres":
            return f"ALTER TABLE {self.get_table_name(state)} RENAME COLUMN {self.column_name} TO {self.new_name}"
        else:
            return f"-- Rename column not implemented for dialect: {dialect}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for reverting a column rename."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support RENAME COLUMN directly. Create a new table with the original schema."
        elif dialect == "postgres":
            return f"ALTER TABLE {self.get_table_name(state)} RENAME COLUMN {self.new_name} TO {self.column_name}"
        else:
            return f"-- Rename column not implemented for dialect: {dialect}"

    def to_migration(self) -> str:
        """Generate Python code to rename a column in a migration."""
        lines = []
        lines.append("RenameColumn(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(")")
        return "\n".join(lines)


class AddIndex(SchemaChange):
    """Add an index to a table."""

    def __init__(
        self,
        model: str,
        column_name: str,
        index_name: Optional[str] = None,
        unique: bool = False,
        columns: Optional[List[str]] = None,
    ):
        super().__init__(model)
        self.column_name = column_name
        # Convert model name from CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        self.index_name = index_name or f"idx_{table_name}_{column_name}"
        self.unique = unique
        self.columns = columns or [column_name]

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding an index."""
        unique_prefix = "UNIQUE " if self.unique else ""
        columns_str = ", ".join(self.columns)
        return f"CREATE {unique_prefix}INDEX {self.index_name} ON {self.get_table_name(state)} ({columns_str})"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX {self.index_name}"

    def to_migration(self) -> str:
        """Generate Python code to add an index in a migration."""
        lines = []
        lines.append("AddIndex(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    column_name="{self.column_name}",')

        # Convert model name to snake_case for default index name
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        default_index_name = f"idx_{table_name}_{self.column_name}"

        if self.index_name != default_index_name:
            lines.append(f'    index_name="{self.index_name}",')

        if self.unique:
            lines.append("    unique=True,")

        if self.columns != [self.column_name]:
            columns_repr = "[" + ", ".join([f'"{col}"' for col in self.columns]) + "]"
            lines.append(f"    columns={columns_repr},")

        lines.append(")")
        return "\n".join(lines)


class DropIndex(SchemaChange):
    """Drop an index from a table."""

    def __init__(
        self,
        model: str,
        column_name: str,
        index_name: Optional[str] = None,
    ):
        super().__init__(model)
        self.column_name = column_name
        # Convert model name from CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        self.index_name = index_name or f"idx_{table_name}_{column_name}"

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX {self.index_name}"

    def backward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding an index."""
        return (
            f"CREATE INDEX {self.index_name} ON {self.get_table_name(state)} ({self.column_name})"
        )

    def to_migration(self) -> str:
        """Generate Python code to drop an index in a migration."""
        lines = []
        lines.append("DropIndex(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    column_name="{self.column_name}",')

        # Convert model name to snake_case for default index name
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        table_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        default_index_name = f"idx_{table_name}_{self.column_name}"

        if self.index_name != default_index_name:
            lines.append(f'    index_name="{self.index_name}",')

        lines.append(")")
        return "\n".join(lines)


class AddConstraint(SchemaChange):
    """Add a constraint to a table."""

    def __init__(
        self,
        model: str,
        column_name: str,
        constraint_name: Optional[str] = None,
        constraint_type: str = "CHECK",
        constraint_clause: Optional[str] = None,
    ):
        super().__init__(model)
        self.column_name = column_name
        self.constraint_name = (
            constraint_name or f"constraint_{self.model_name.lower()}_{column_name}"
        )
        self.constraint_type = constraint_type
        self.constraint_clause = constraint_clause or f"{column_name} IS NOT NULL"

    def forward_sql(self, state: "State", dialect: str = "sqlite") -> str:
        """Generate SQL for adding a constraint."""
        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Adding constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.get_table_name(state)} ADD CONSTRAINT {self.constraint_name} {self.constraint_type} ({self.constraint_clause})"

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
        lines.append(f'    column_name="{self.column_name}",')

        # Instead of comparing with get_table_name(state), use default constraint name pattern
        default_constraint_name = f"constraint_{self.model_name.lower()}_{self.column_name}"
        if self.constraint_name != default_constraint_name:
            lines.append(f'    constraint_name="{self.constraint_name}",')

        if self.constraint_type != "CHECK":
            lines.append(f'    constraint_type="{self.constraint_type}",')

        if self.constraint_clause != f"{self.column_name} IS NOT NULL":
            lines.append(f'    constraint_clause="{self.constraint_clause}",')

        lines.append(")")
        return "\n".join(lines)


class DropConstraint(SchemaChange):
    """Drop a constraint from a table."""

    def __init__(
        self,
        model: str,
        column_name: str,
        constraint_name: Optional[str] = None,
    ):
        super().__init__(model)
        self.column_name = column_name
        self.constraint_name = (
            constraint_name or f"constraint_{self.model_name.lower()}_{column_name}"
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
        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Adding constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.get_table_name(state)} ADD CONSTRAINT {self.constraint_name} CHECK ({self.column_name} IS NOT NULL)"

    def to_migration(self) -> str:
        """Generate Python code to drop a constraint in a migration."""
        lines = []
        lines.append("DropConstraint(")
        lines.append(f'    model="{self.model}",')
        lines.append(f'    column_name="{self.column_name}",')

        # Instead of comparing with get_table_name(state), use default constraint name pattern
        default_constraint_name = f"constraint_{self.model_name.lower()}_{self.column_name}"
        if self.constraint_name != default_constraint_name:
            lines.append(f'    constraint_name="{self.constraint_name}",')

        lines.append(")")
        return "\n".join(lines)


def field_to_migration(field: Field) -> str:
    """
    Convert a Field object to its string representation for migrations.

    Args:
        field: The Field object to convert.

    Returns:
        A string representation of the Field that can be used in migrations.
    """
    field_type = field.__class__.__name__
    field_module = field.__class__.__module__

    # Start with importing the field if needed
    if "tortoise.fields" not in field_module:
        # For custom fields, include the full module path
        field_type = f"{field_module}.{field_type}"

    # Collect parameters
    params = []

    # Handle common field attributes
    if hasattr(field, "pk") and field.pk:
        params.append("primary_key=True")

    if hasattr(field, "null") and field.null:
        params.append("null=True")

    if hasattr(field, "unique") and field.unique:
        params.append("unique=True")

    if hasattr(field, "default") and field.default is not None and not callable(field.default):
        if isinstance(field.default, str):
            params.append(f"default='{field.default}'")
        elif isinstance(field.default, bool):
            params.append(f"default={str(field.default)}")
        else:
            params.append(f"default={field.default}")

    # Handle field-specific attributes
    if field_type == "CharField" and hasattr(field, "max_length"):
        params.append(f"max_length={field.max_length}")

    if field_type == "DecimalField":
        if hasattr(field, "max_digits"):
            params.append(f"max_digits={field.max_digits}")
        if hasattr(field, "decimal_places"):
            params.append(f"decimal_places={field.decimal_places}")

    if isinstance(field, RelationalField):
        if hasattr(field, "model_name"):
            # For ForeignKeyField, we need to include the related model
            related_model = field.model_name
            params.append(f"'{related_model}'")

        if hasattr(field, "related_name") and field.related_name:
            params.append(f"related_name='{field.related_name}'")

        if hasattr(field, "on_delete"):
            params.append(f"on_delete='{field.on_delete}'")

    # Generate the final string representation
    return f"{field_type}({', '.join(params)})"
