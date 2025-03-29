"""
Schema difference detection for Tortoise ORM migrations.

This module provides functionality to detect differences between Tortoise models
and the actual database schema, generating migration operations.
"""

import typing
from typing import Dict, List, Any, Optional, Type, Union

from tortoise import Tortoise, connections
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
    """Base class for all schema changes."""

    def __init__(
        self,
        table_name: str,
        model: Optional[Type[Model]] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.table_name = table_name
        self.model = model
        self.params = params or {}

    def __str__(self) -> str:
        """String representation of the schema change."""
        return f"Schema change on {self.table_name}"

    def generate_sql_forward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for applying this change forward."""
        from tortoise_pathway.generators import generate_sql_for_schema_change

        return generate_sql_for_schema_change(self, "forward", dialect)

    def generate_sql_backward(self, dialect: str = "sqlite") -> str:
        """Generate SQL for reverting this change."""
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
            String with Python code that creates and applies this schema change.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """
        Generate Python code to reverse this schema change in a migration file.

        Args:
            var_name: Variable name to use in the generated code.

        Returns:
            String with Python code that reverses this schema change.
        """
        raise NotImplementedError("Subclasses must implement this method")


class CreateTable(SchemaChange):
    """Create a new table."""

    def __init__(
        self,
        table_name: str,
        model: Type[Model],
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(table_name, model, params)

    def __str__(self) -> str:
        return f"Create table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Create the table in the database."""
        connection = connections.get(connection_name)

        if self.model:
            sql = self.generate_sql_forward()
            await connection.execute_script(sql)
        else:
            # Fallback if no model is available
            await connection.execute_script(
                f"CREATE TABLE {self.table_name} (id INTEGER PRIMARY KEY);"
            )

    async def revert(self, connection_name: str = "default") -> None:
        """Drop the table from the database."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"DROP TABLE {self.table_name}")

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to create a table in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = CreateTable(")
        lines.append(f'    table_name="{self.table_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "reverse_change") -> str:
        """Generate Python code to reverse table creation in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"{var_name} = DropTable(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)


class DropTable(SchemaChange):
    """Drop an existing table."""

    def __str__(self) -> str:
        return f"Drop table {self.table_name}"

    async def apply(self, connection_name: str = "default") -> None:
        """Drop the table from the database."""
        connection = connections.get(connection_name)
        await connection.execute_script(f"DROP TABLE {self.table_name}")

    async def revert(self, connection_name: str = "default") -> None:
        """Recreate the table if model information is available."""
        if not self.model:
            raise ValueError(
                f"Cannot recreate table {self.table_name}: model information not available"
            )

        connection = connections.get(connection_name)
        sql = self.generate_sql_backward()
        await connection.execute_script(sql)

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop a table in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropTable(")
        lines.append(f'    table_name="{self.table_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "reverse_change") -> str:
        """Generate Python code to reverse table drop in a migration."""
        lines = [f"# Cannot automatically recreate dropped table {self.table_name}"]
        if self.model is not None:
            lines.append(f"try:")
            lines.append(f"    await {var_name}.revert()")
            lines.append(f"except Exception as e:")
            lines.append(f'    print(f"Warning: Cannot recreate table {self.table_name}: {{e}}")')
        return "\n".join(lines)


class RenameTable(SchemaChange):
    """Rename an existing table."""

    def __init__(
        self,
        table_name: str,
        new_name: str,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to rename a table in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = RenameTable(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    new_name="{self.new_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse table rename in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"{var_name} = RenameTable(")
        lines.append(f'    table_name="{self.new_name}",')
        lines.append(f'    new_name="{self.table_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)


class AddColumn(SchemaChange):
    """Add a new column to an existing table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        field_object: Field,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to add a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AddColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')

        # Only reference model fields if model is not None
        if self.model is not None:
            field_name = self.params.get("field_name", self.column_name)
            lines.append(
                f"    field_object={self.model.__name__}._meta.fields_map['{field_name}'],"
            )
            lines.append(f"    model={self.model.__name__},")
        else:
            # Handle case where field_object is needed but model is None
            lines.append(f"    # field_object not available - manual intervention required")

        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse column addition in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"try:")
        lines.append(f"    await {var_name}.revert()")
        lines.append(f"except NotImplementedError as e:")
        lines.append(f"    # SQLite may not support column dropping")
        lines.append(f'    print(f"Warning: {{e}}")')
        return "\n".join(lines)


class DropColumn(SchemaChange):
    """Drop a column from an existing table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: Optional[Type[Model]] = None,
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
        if not self.model:
            raise ValueError(
                f"Cannot recreate column {self.column_name} in {self.table_name}: model information not available"
            )

        # This would require getting field information from model
        # Simplified implementation:
        connection = connections.get(connection_name)
        field_name = self.column_name

        if self.model and field_name in self.model._meta.fields_map:
            field = self.model._meta.fields_map[field_name]
            field_type = field.__class__.__name__

            # Simplified column re-creation
            column_type = "TEXT"  # Default
            if field_type == "IntField":
                column_type = "INTEGER"
            elif field_type == "CharField":
                max_length = getattr(field, "max_length", 255)
                column_type = f"VARCHAR({max_length})"

            await connection.execute_script(
                f"ALTER TABLE {self.table_name} ADD COLUMN {self.column_name} {column_type}"
            )
        else:
            raise ValueError(f"Cannot recreate column {self.column_name}: field not found in model")

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"try:")
        lines.append(f"    await {var_name}.apply()")
        lines.append(f"except NotImplementedError as e:")
        lines.append(f"    # SQLite may not support dropping columns")
        lines.append(f'    print(f"Warning: {{e}}")')
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse column drop in a migration."""
        lines = [f"# Reverse: {self}"]
        if self.model is not None:
            lines.append(f"try:")
            lines.append(f"    await {var_name}.revert()")
            lines.append(f"except (NotImplementedError, ValueError) as e:")
            lines.append(f'    print(f"Warning: {{e}}")')
        else:
            lines.append(f"# Cannot recreate column without model information")
        return "\n".join(lines)


class AlterColumn(SchemaChange):
    """Alter the properties of an existing column."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        field_object: Field,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to alter a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AlterColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')

        # Only reference model fields if model is not None
        if self.model is not None:
            new_params = self.params.get("new", {})
            field_name = new_params.get("field_name", self.column_name)
            lines.append(
                f"    field_object={self.model.__name__}._meta.fields_map['{field_name}'],"
            )
            lines.append(f"    model={self.model.__name__},")
        else:
            # Handle case where field_object is needed but model is None
            lines.append(f"    # field_object not available - manual intervention required")

        lines.append(")")
        lines.append(f"try:")
        lines.append(f"    await {var_name}.apply()")
        lines.append(f"except NotImplementedError as e:")
        lines.append(f"    # SQLite may not support column alteration")
        lines.append(f'    print(f"Warning: {{e}}")')
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse column alteration in a migration."""
        lines = [f"# Reverse for AlterColumn requires manual intervention"]
        lines.append(f"try:")
        lines.append(f"    await {var_name}.revert()")
        lines.append(f"except (NotImplementedError, ValueError) as e:")
        lines.append(f'    print(f"Warning: {{e}}")')
        return "\n".join(lines)


class RenameColumn(SchemaChange):
    """Rename an existing column."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        new_name: str,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to rename a column in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = RenameColumn(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        lines.append(f'    new_name="{self.new_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"try:")
        lines.append(f"    await {var_name}.apply()")
        lines.append(f"except NotImplementedError as e:")
        lines.append(f"    # SQLite may not support column renaming")
        lines.append(f'    print(f"Warning: {{e}}")')
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse column rename in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"try:")
        lines.append(f"    await {var_name}.revert()")
        lines.append(f"except NotImplementedError as e:")
        lines.append(f"    # SQLite may not support column renaming")
        lines.append(f'    print(f"Warning: {{e}}")')
        return "\n".join(lines)


class AddIndex(SchemaChange):
    """Add an index to a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to add an index in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AddIndex(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse index addition in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"await {var_name}.revert()")
        return "\n".join(lines)


class DropIndex(SchemaChange):
    """Drop an index from a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop an index in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropIndex(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse index drop in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"await {var_name}.revert()")
        return "\n".join(lines)


class AddConstraint(SchemaChange):
    """Add a constraint to a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to add a constraint in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = AddConstraint(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse constraint addition in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"await {var_name}.revert()")
        return "\n".join(lines)


class DropConstraint(SchemaChange):
    """Drop a constraint from a table."""

    def __init__(
        self,
        table_name: str,
        column_name: str,
        model: Optional[Type[Model]] = None,
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

    def to_migration(self, var_name: str = "change") -> str:
        """Generate Python code to drop a constraint in a migration."""
        lines = [f"# {self}"]
        lines.append(f"{var_name} = DropConstraint(")
        lines.append(f'    table_name="{self.table_name}",')
        lines.append(f'    column_name="{self.column_name}",')
        if self.model is not None:
            lines.append(f"    model={self.model.__name__},")
        lines.append(")")
        lines.append(f"await {var_name}.apply()")
        return "\n".join(lines)

    def to_migration_reverse(self, var_name: str = "change") -> str:
        """Generate Python code to reverse constraint drop in a migration."""
        lines = [f"# Reverse: {self}"]
        lines.append(f"await {var_name}.revert()")
        return "\n".join(lines)


class SchemaDiffer:
    """Detects differences between Tortoise models and database schema."""

    def __init__(self, connection=None):
        self.connection = connection

    async def get_db_schema(self) -> Dict[str, Any]:
        """Get the current database schema."""
        conn = self.connection or Tortoise.get_connection("default")
        db_schema = {}

        # This is a simplified version. A real implementation would:
        # - Get all tables
        # - Get columns for each table
        # - Get indexes and constraints

        # Example for SQLite (would need different implementations for other DBs)
        tables = await conn.execute_query("SELECT name FROM sqlite_master WHERE type='table'")

        for table_record in tables[1]:
            table_name = table_record["name"]

            # Skip the migration tracking table and SQLite system tables
            if table_name == "tortoise_migrations" or table_name.startswith("sqlite_"):
                continue

            # Get column information
            columns_info = await conn.execute_query(f"PRAGMA table_info({table_name})")

            columns = {}
            for column in columns_info[1]:
                column_name = column["name"]
                column_type = column["type"]
                notnull = column["notnull"]
                default_value = column["dflt_value"]
                is_pk = column["pk"] == 1

                columns[column_name] = {
                    "type": column_type,
                    "nullable": not notnull,
                    "default": default_value,
                    "primary_key": is_pk,
                }

            # Get index information
            indexes_info = await conn.execute_query(f"PRAGMA index_list({table_name})")

            indexes = []
            for index in indexes_info[1]:
                index_name = index["name"]
                is_unique = index["unique"]

                # Get columns in this index
                index_columns_info = await conn.execute_query(f"PRAGMA index_info({index_name})")
                index_columns = [col["name"] for col in index_columns_info[1]]

                indexes.append({"name": index_name, "unique": is_unique, "columns": index_columns})

            db_schema[table_name] = {"columns": columns, "indexes": indexes}

        return db_schema

    def get_model_schema(self) -> Dict[str, Any]:
        """Get schema representation from Tortoise models."""
        model_schema = {}

        # For each registered model
        for app_name, app_models in Tortoise.apps.items():
            for model_name, model in app_models.items():
                if not issubclass(model, Model):
                    continue

                # Get model's DB table name
                table_name = model._meta.db_table

                # Get fields
                columns = {}
                for field_name, field_object in model._meta.fields_map.items():
                    # Skip reverse relations
                    if field_object.__class__.__name__ == "BackwardFKRelation":
                        continue

                    # Get field properties
                    field_type = field_object.__class__.__name__
                    nullable = getattr(field_object, "null", False)
                    default = getattr(field_object, "default", None)
                    pk = getattr(field_object, "pk", False)

                    # Get the actual DB column name
                    source_field = getattr(field_object, "source_field", None)
                    db_column = source_field if source_field is not None else field_name

                    columns[db_column] = {
                        "field_name": field_name,
                        "type": field_type,
                        "nullable": nullable,
                        "default": default,
                        "primary_key": pk,
                        "field_object": field_object,
                    }

                # Get indexes
                indexes = []
                if hasattr(model._meta, "indexes") and isinstance(
                    model._meta.indexes, (list, tuple)
                ):
                    for index_fields in model._meta.indexes:
                        if not isinstance(index_fields, (list, tuple)):
                            continue

                        index_columns = []
                        for field_name in index_fields:
                            if field_name in model._meta.fields_map:
                                source_field = getattr(
                                    model._meta.fields_map[field_name], "source_field", None
                                )
                                column_name = (
                                    source_field if source_field is not None else field_name
                                )
                                index_columns.append(column_name)

                        if index_columns:
                            indexes.append(
                                {
                                    "name": f"idx_{'_'.join(index_columns)}",
                                    "unique": False,
                                    "columns": index_columns,
                                }
                            )

                # Get unique constraints
                if hasattr(model._meta, "unique_together") and isinstance(
                    model._meta.unique_together, (list, tuple)
                ):
                    for unique_fields in model._meta.unique_together:
                        if not isinstance(unique_fields, (list, tuple)):
                            continue

                        unique_columns = []
                        for field_name in unique_fields:
                            if field_name in model._meta.fields_map:
                                source_field = getattr(
                                    model._meta.fields_map[field_name], "source_field", None
                                )
                                column_name = (
                                    source_field if source_field is not None else field_name
                                )
                                unique_columns.append(column_name)

                        if unique_columns:
                            indexes.append(
                                {
                                    "name": f"uniq_{'_'.join(unique_columns)}",
                                    "unique": True,
                                    "columns": unique_columns,
                                }
                            )

                model_schema[table_name] = {"columns": columns, "indexes": indexes, "model": model}

        return model_schema

    async def detect_changes(self) -> List[SchemaChange]:
        """Detect schema changes between models and database."""
        db_schema = await self.get_db_schema()
        model_schema = self.get_model_schema()

        changes = []

        # Detect table changes
        db_tables = set(db_schema.keys())
        model_tables = set(model_schema.keys())

        # Tables to create (in models but not in DB)
        for table_name in model_tables - db_tables:
            changes.append(
                CreateTable(
                    table_name=table_name,
                    model=model_schema[table_name]["model"],
                    params={"model": model_schema[table_name]["model"]},
                )
            )

        # Tables to drop (in DB but not in models)
        for table_name in db_tables - model_tables:
            changes.append(DropTable(table_name=table_name))

        # Check changes in existing tables
        for table_name in db_tables & model_tables:
            # Store model reference
            model = model_schema[table_name]["model"]

            # Columns in DB and model
            db_columns = set(db_schema[table_name]["columns"].keys())
            model_columns = set(model_schema[table_name]["columns"].keys())

            # Columns to add (in model but not in DB)
            for column_name in model_columns - db_columns:
                field_info = model_schema[table_name]["columns"][column_name]

                changes.append(
                    AddColumn(
                        table_name=table_name,
                        column_name=column_name,
                        field_object=field_info["field_object"],
                        model=model,
                        params=field_info,
                    )
                )

            # Columns to drop (in DB but not in model)
            for column_name in db_columns - model_columns:
                changes.append(
                    DropColumn(
                        table_name=table_name,
                        column_name=column_name,
                        model=model,
                    )
                )

            # Check for column changes
            for column_name in db_columns & model_columns:
                db_column = db_schema[table_name]["columns"][column_name]
                model_column = model_schema[table_name]["columns"][column_name]

                # This is simplified - a real implementation would compare types more carefully
                # Checking nullable changes, type changes, default value changes
                column_changed = False

                # For simplicity: if any property is different, mark as changed
                if db_column["nullable"] != model_column["nullable"]:
                    column_changed = True

                # Comparing types is tricky as DB types may not exactly match Python types
                # This would need more sophisticated comparison

                if column_changed:
                    changes.append(
                        AlterColumn(
                            table_name=table_name,
                            column_name=column_name,
                            field_object=model_column["field_object"],
                            model=model,
                            params={"old": db_column, "new": model_column},
                        )
                    )

            # Index changes would be implemented similarly

        return changes
