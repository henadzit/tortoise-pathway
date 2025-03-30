"""
Schema difference detection for Tortoise ORM migrations.

This module provides functionality to detect differences between Tortoise models
and the actual database schema, generating migration operations.
"""

from typing import Dict, Any, Optional, Type

from tortoise import connections
from tortoise.fields import Field
from tortoise.models import Model


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
        table_name: The name of the table this change applies to.
        model: Model reference in the format "{app_name}.{model_name}".
        params: Optional additional parameters for the schema change.
    """

    def __init__(
        self,
        table_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.table_name = table_name
        self.model = model
        self.params = params or {}

    def __str__(self) -> str:
        """String representation of the schema change."""
        return f"Schema change on {self.table_name}"

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """
        Generate SQL for applying this change forward.

        Args:
            dialect: SQL dialect (default: "sqlite").

        Returns:
            SQL string for applying the change.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """
        Generate SQL for reverting this change.

        Args:
            dialect: SQL dialect (default: "sqlite").

        Returns:
            SQL string for reverting the change.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def generate_sql_forward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for applying this change forward."""
        # For backward compatibility, we first try the new method
        try:
            return self.forward_sql(dialect)
        except NotImplementedError:
            # Fall back to the old way
            from tortoise_pathway.generators import generate_sql_for_schema_change

            return generate_sql_for_schema_change(self, "forward", dialect)

    def generate_sql_backward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for reverting this change."""
        # For backward compatibility, we first try the new method
        try:
            return self.backward_sql(dialect)
        except NotImplementedError:
            # Fall back to the old way
            from tortoise_pathway.generators import generate_sql_for_schema_change

            return generate_sql_for_schema_change(self, "backward", dialect)

    async def apply(self, connection_name: str = "default") -> None:
        """Apply this schema change to the database."""
        connection = connections.get(connection_name)
        sql = self.generate_sql_forward()
        await connection.execute_script(sql)

    async def revert(self, connection_name: str = "default") -> None:
        """Revert this schema change from the database."""
        connection = connections.get(connection_name)
        sql = self.generate_sql_backward()
        await connection.execute_script(sql)

    def to_migration(self, var_name: str = "change") -> str:
        """
        Generate Python code for this schema change to be included in a migration file.

        Args:
            var_name: Variable name to use in the generated code.

        Returns:
            String with Python code that represents this schema change operation,
            suitable for inclusion in Migration.operations list.
        """
        raise NotImplementedError("Subclasses must implement this method")


class CreateTable(SchemaChange):
    """Create a new table."""

    def __init__(
        self,
        table_name: str,
        fields: Dict[str, Field],
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.fields = fields

    def __str__(self) -> str:
        return f"Create table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Create the table in the database."""
        connection = connections.get(connection_name)

        # Generate SQL from fields dictionary
        sql = self._generate_sql_from_fields()
        await connection.execute_script(sql)

    async def revert(self, connection_name: str = "default") -> None:
        """Drop the table from the database."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"DROP TABLE {self.table_name}")

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for creating the table."""
        return self._generate_sql_from_fields(dialect)

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping the table."""
        return f"DROP TABLE {self.table_name}"

    # Preserve existing methods to not break the API
    def generate_sql_forward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for applying this change forward."""
        return self.forward_sql(dialect)

    def generate_sql_backward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for reverting this change."""
        return self.backward_sql(dialect)

    def _generate_sql_from_fields(self, dialect: str = "sqlite") -> str:
        """
        Generate SQL to create a table from the fields dictionary.

        Args:
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
        sql = f"CREATE TABLE {self.table_name} (\n"
        sql += ",\n".join(["    " + col for col in columns])

        if constraints:
            sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

        sql += "\n);"

        return sql

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to create a table in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = CreateTable(")
        lines.append(f'    table_name="{self.table_name}",')
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
        table_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)

    def __str__(self) -> str:
        return f"Drop table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Drop the table from the database."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"DROP TABLE {self.table_name}")

    async def revert(self, connection_name: str = "default") -> None:
        """Recreate the table if model information is available."""
        connection = connections.get(connection_name)
        sql = self.generate_sql_backward()
        await connection.execute_script(sql)

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping the table."""
        return f"DROP TABLE {self.table_name}"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for recreating the table."""
        from tortoise_pathway.generators import generate_table_creation_sql

        # Since model is now a string instead of a Model class,
        # we need to provide guidance for handling this in migrations
        return f"-- To recreate table {self.table_name}, import the model class from '{self.model}' first"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop a table in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropTable(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class RenameTable(SchemaChange):
    """Rename an existing table."""

    def __init__(
        self,
        table_name: str,
        new_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.new_name = new_name

    def __str__(self) -> str:
        return f"Rename table {self.table_name} to {self.new_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Rename the table in the database."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"ALTER TABLE {self.table_name} RENAME TO {self.new_name}")

    async def revert(self, connection_name: str = "default") -> None:
        """Rename the table back to its original name."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"ALTER TABLE {self.new_name} RENAME TO {self.table_name}")

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for renaming the table."""
        if dialect == "sqlite" or dialect == "postgres":
            return f"ALTER TABLE {self.table_name} RENAME TO {self.new_name}"
        else:
            return f"-- Rename table not implemented for dialect: {dialect}"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for reverting the table rename."""
        if dialect == "sqlite" or dialect == "postgres":
            return f"ALTER TABLE {self.new_name} RENAME TO {self.table_name}"
        else:
            return f"-- Rename table not implemented for dialect: {dialect}"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to rename a table in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = RenameTable(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class AddColumn(SchemaChange):
    """Add a new column to an existing table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        field_object: Field,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name
        self.field_object = field_object

    def __str__(self) -> str:
        return f"Add column {self.column_name} to table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Add the column to the database table."""
        connection = connections.get(connection_name)
        sql = self.generate_sql_forward()
        await connection.execute_script(sql)

    async def revert(self, connection_name: str = "default") -> None:
        """Drop the column from the database table."""
        connection = connections.get(connection_name)
        dialect = get_dialect(connection)

        if dialect == "sqlite":
            # SQLite doesn't support DROP COLUMN directly
            # This would require creating a new table, copying data, and replacing
            raise NotImplementedError(
                f"Cannot automatically drop column {self.column_name} from {self.table_name} in SQLite"
            )
        else:
            # For PostgreSQL and other databases that support DROP COLUMN
            await connection.execute_script(
                f"ALTER TABLE {self.table_name} DROP COLUMN {self.column_name}"
            )

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for adding a column."""
        field_type = self.field_object.__class__.__name__
        nullable = getattr(self.field_object, "null", False)
        default = getattr(self.field_object, "default", None)
        is_pk = getattr(self.field_object, "pk", False)

        sql = f"ALTER TABLE {self.table_name} ADD COLUMN {self.column_name}"

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

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a column."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support DROP COLUMN directly. Create a new table without this column."
        else:
            return f"ALTER TABLE {self.table_name} DROP COLUMN {self.column_name}"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to add a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AddColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')

        # Include field_object using field_to_migration
        lines.append(f"    field_object={field_to_migration(self.field_object)},")

        # Include model parameter
        lines.append(f'    model="{self.model}",')

        lines.append(")")
        return "\n".join(lines)


class DropColumn(SchemaChange):
    """Drop a column from an existing table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name

    def __str__(self) -> str:
        return f"Drop column {self.column_name} from table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Drop the column from the database table."""
        connection = connections.get(connection_name)
        dialect = get_dialect(connection)

        if dialect == "sqlite":
            # SQLite doesn't support DROP COLUMN directly
            raise NotImplementedError(
                f"Cannot automatically drop column {self.column_name} from {self.table_name} in SQLite"
            )
        else:
            # For PostgreSQL and other databases that support DROP COLUMN
            await connection.execute_script(
                f"ALTER TABLE {self.table_name} DROP COLUMN {self.column_name}"
            )

    async def revert(self, connection_name: str = "default") -> None:
        """Recreate the column if model information is available."""
        # To recreate the column, you would need to import the model dynamically
        # This would require significant changes to the implementation
        raise NotImplementedError(
            f"Recreating column {self.column_name} with string model reference requires implementation"
        )

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a column."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support DROP COLUMN directly. Create a new table without this column."
        else:
            return f"ALTER TABLE {self.table_name} DROP COLUMN {self.column_name}"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for recreating a column."""
        # With the model as a string, we can't directly access fields_map
        # An implementation would need to import the model dynamically
        return f"-- Recreating column {self.column_name} with string model reference requires implementation"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class AlterColumn(SchemaChange):
    """Alter the properties of an existing column."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        field_object: Field,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name
        self.field_object = field_object

    def __str__(self) -> str:
        return f"Alter column {self.column_name} on table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Alter the column in the database table."""
        connection = connections.get(connection_name)
        dialect = get_dialect(connection)

        if dialect == "sqlite":
            # SQLite doesn't support ALTER COLUMN directly
            # This would require complex table recreation
            raise NotImplementedError(
                f"Cannot automatically alter column {self.column_name} in {self.table_name} for SQLite"
            )
        else:
            sql = self.generate_sql_forward()
            await connection.execute_script(sql)

    async def revert(self, connection_name: str = "default") -> None:
        """Revert the column alteration if old values are available."""
        # This operation needs detailed old column information
        # If params contains old column info, we could use it here
        old_info = self.params.get("old", {})
        if not old_info:
            raise ValueError(
                f"Cannot revert column alteration for {self.column_name}: old column information not available"
            )

        # Complex implementation required; simplified version:
        raise NotImplementedError(
            f"Reverting column alteration for {self.column_name} requires manual intervention"
        )

    def forward_sql(self, dialect: str = "sqlite") -> str:
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

            return (
                f"ALTER TABLE {self.table_name} ALTER COLUMN {self.column_name} TYPE {column_type}"
            )
        else:
            return f"-- Alter column not implemented for dialect: {dialect}"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for reverting a column alteration."""
        # This requires old column information from params
        old_info = self.params.get("old", {})
        if not old_info:
            return "-- Cannot revert column alteration: old column information not available"

        # Even with old info, SQLite doesn't support this directly
        if dialect == "sqlite":
            return "-- SQLite doesn't support ALTER COLUMN directly. Create a new table with the original schema."

        # For postgres and other databases that support ALTER COLUMN
        # This is a simplified version, would need more detailed logic for a real implementation
        return f"-- Reverting column alteration for {self.column_name} requires manual intervention"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to alter a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AlterColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')

        # Include field_object using field_to_migration
        lines.append(f"    field_object={field_to_migration(self.field_object)},")

        # Include model parameter
        lines.append(f'    model="{self.model}",')

        lines.append(")")
        return "\n".join(lines)


class RenameColumn(SchemaChange):
    """Rename an existing column."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        new_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name
        self.new_name = new_name

    def __str__(self) -> str:
        return f"Rename column {self.column_name} to {self.new_name} on table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Rename the column in the database table."""
        connection = connections.get(connection_name)
        dialect = get_dialect(connection)

        if dialect == "sqlite":
            # SQLite support for RENAME COLUMN depends on version
            # This would likely require table recreation
            raise NotImplementedError(
                f"Cannot automatically rename column {self.column_name} to {self.new_name} in SQLite"
            )
        else:
            await connection.execute_script(
                f"ALTER TABLE {self.table_name} RENAME COLUMN {self.column_name} TO {self.new_name}"
            )

    async def revert(self, connection_name: str = "default") -> None:
        """Rename the column back to its original name."""
        connection = connections.get(connection_name)
        dialect = get_dialect(connection)

        if dialect == "sqlite":
            raise NotImplementedError(
                f"Cannot automatically rename column {self.new_name} back to {self.column_name} in SQLite"
            )
        else:
            await connection.execute_script(
                f"ALTER TABLE {self.table_name} RENAME COLUMN {self.new_name} TO {self.column_name}"
            )

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for renaming a column."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support RENAME COLUMN directly. Create a new table with the new schema."
        elif dialect == "postgres":
            return (
                f"ALTER TABLE {self.table_name} RENAME COLUMN {self.column_name} TO {self.new_name}"
            )
        else:
            return f"-- Rename column not implemented for dialect: {dialect}"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for reverting a column rename."""
        if dialect == "sqlite":
            return "-- SQLite doesn't support RENAME COLUMN directly. Create a new table with the original schema."
        elif dialect == "postgres":
            return (
                f"ALTER TABLE {self.table_name} RENAME COLUMN {self.new_name} TO {self.column_name}"
            )
        else:
            return f"-- Rename column not implemented for dialect: {dialect}"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to rename a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = RenameColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    new_name="{self.new_name}",')
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class AddIndex(SchemaChange):
    """Add an index to a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name

    def __str__(self) -> str:
        return f"Add index on {self.column_name} in table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Add the index to the database table."""
        connection = connections.get(connection_name)
        await connection.execute_script(
            f"CREATE INDEX idx_{self.table_name}_{self.column_name} ON {self.table_name} ({self.column_name})"
        )

    async def revert(self, connection_name: str = "default") -> None:
        """Drop the index from the database table."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"DROP INDEX idx_{self.table_name}_{self.column_name}")

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for adding an index."""
        return f"CREATE INDEX idx_{self.table_name}_{self.column_name} ON {self.table_name} ({self.column_name})"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX idx_{self.table_name}_{self.column_name}"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to add an index in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AddIndex(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class DropIndex(SchemaChange):
    """Drop an index from a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name

    def __str__(self) -> str:
        return f"Drop index on {self.column_name} in table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Drop the index from the database table."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"DROP INDEX idx_{self.table_name}_{self.column_name}")

    async def revert(self, connection_name: str = "default") -> None:
        """Recreate the index on the database table."""
        connection = connections.get(connection_name)
        await connection.execute_script(
            f"CREATE INDEX idx_{self.table_name}_{self.column_name} ON {self.table_name} ({self.column_name})"
        )

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX idx_{self.table_name}_{self.column_name}"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for adding an index."""
        return f"CREATE INDEX idx_{self.table_name}_{self.column_name} ON {self.table_name} ({self.column_name})"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop an index in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropIndex(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class AddConstraint(SchemaChange):
    """Add a constraint to a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name

    def __str__(self) -> str:
        return f"Add constraint on {self.column_name} in table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Add the constraint to the database table."""
        # This would need more specific information about the constraint type
        # Placeholder implementation:
        connection = connections.get(connection_name)
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"

        # This is a simplification - real constraints need more specific SQL
        await connection.execute_script(
            f"ALTER TABLE {self.table_name} ADD CONSTRAINT {constraint_name} CHECK ({self.column_name} IS NOT NULL)"
        )

    async def revert(self, connection_name: str = "default") -> None:
        """Remove the constraint from the database table."""
        connection = connections.get(connection_name)
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"
        await connection.execute_script(
            f"ALTER TABLE {self.table_name} DROP CONSTRAINT {constraint_name}"
        )

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for adding a constraint."""
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"

        # This is a simplification - real constraints need more specific SQL based on constraint type
        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Adding constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.table_name} ADD CONSTRAINT {constraint_name} CHECK ({self.column_name} IS NOT NULL)"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a constraint."""
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"

        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Dropping constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.table_name} DROP CONSTRAINT {constraint_name}"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to add a constraint in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AddConstraint(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    model="{self.model}",')
        lines.append(")")
        return "\n".join(lines)


class DropConstraint(SchemaChange):
    """Drop a constraint from a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)
        self.column_name = column_name

    def __str__(self) -> str:
        return f"Drop constraint on {self.column_name} in table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Drop the constraint from the database table."""
        connection = connections.get(connection_name)
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"
        await connection.execute_script(
            f"ALTER TABLE {self.table_name} DROP CONSTRAINT {constraint_name}"
        )

    async def revert(self, connection_name: str = "default") -> None:
        """Recreate the constraint on the database table."""
        # This would need more specific information about the constraint type
        # Placeholder implementation:
        connection = connections.get(connection_name)
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"

        # This is a simplification - real constraints need more specific SQL
        await connection.execute_script(
            f"ALTER TABLE {self.table_name} ADD CONSTRAINT {constraint_name} CHECK ({self.column_name} IS NOT NULL)"
        )

    def forward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for dropping a constraint."""
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"

        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Dropping constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.table_name} DROP CONSTRAINT {constraint_name}"

    def backward_sql(self, dialect: str = "sqlite") -> str:
        """Generate SQL for adding a constraint."""
        constraint_name = f"constraint_{self.table_name}_{self.column_name}"

        # This is a simplification - real constraints need more specific SQL based on constraint type
        if dialect == "sqlite":
            # SQLite has limited support for constraints via ALTER TABLE
            return "-- Adding constraints in SQLite may require table recreation"
        else:
            return f"ALTER TABLE {self.table_name} ADD CONSTRAINT {constraint_name} CHECK ({self.column_name} IS NOT NULL)"

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop a constraint in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropConstraint(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    model="{self.model}",')
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

    if field_type == "ForeignKeyField":
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
