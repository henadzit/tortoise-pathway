"""
Auto-generation of migrations for Tortoise ORM models.

This module provides functionality to automatically generate migrations
from existing models without tracking changes.
"""

import os
import importlib
import inspect
from datetime import datetime
from typing import List, Dict, Any, Optional, Type, Tuple

from tortoise import Tortoise, Model, fields
from tortoise.exceptions import OperationalError

from tortoise_pathway.migration import Migration, MigrationManager
from tortoise_pathway.schema_diff import SchemaDiffer, SchemaChange, SchemaChangeType


async def generate_initial_migration(
    app_name: str,
    config_module: str,
    migration_name: str = "initial",
    migrations_dir: Optional[str] = None,
) -> str:
    """
    Generate an initial migration for all models in an app.

    Args:
        app_name: The app name as defined in Tortoise ORM config.
        config_module: The module containing Tortoise ORM config.
        migration_name: Name for the migration (default: "initial").
        migrations_dir: Directory to store migrations (default: "migrations/<app_name>").

    Returns:
        Path to the generated migration file.
    """
    # Import the config module
    try:
        config = importlib.import_module(config_module)
        tortoise_config = getattr(config, "TORTOISE_ORM", None)

        if not tortoise_config:
            raise ValueError(f"Could not find TORTOISE_ORM in {config_module}")

        # Initialize Tortoise ORM
        await Tortoise.init(config=tortoise_config)

        # Create migration manager
        if not migrations_dir:
            migrations_dir = os.path.join("migrations", app_name)

        manager = MigrationManager(app_name, migrations_dir)
        await manager.initialize()

        # Create an initial migration
        migration_file = await manager.create_migration(migration_name, auto=True)

        return str(migration_file)

    except ImportError:
        raise ImportError(f"Could not import {config_module}")
    finally:
        # Close Tortoise connections
        if Tortoise._inited:
            await Tortoise.close_connections()


async def generate_model_creation_operations(models: List[Type[Model]]) -> List[SchemaChange]:
    """
    Generate schema changes for creating models.

    Args:
        models: List of Tortoise model classes.

    Returns:
        List of SchemaChange objects representing model creation.
    """
    changes = []

    for model in models:
        table_name = model._meta.db_table

        changes.append(
            SchemaChange(
                change_type=SchemaChangeType.CREATE_TABLE,
                table_name=table_name,
                params={"model": model},
            )
        )

    return changes


def generate_table_creation_sql(model: Type[Model], dialect: str = "sqlite") -> str:
    """
    Generate SQL for creating a table from a Tortoise model.

    Args:
        model: Tortoise model class.
        dialect: SQL dialect (default: "sqlite").

    Returns:
        SQL string for table creation.
    """
    table_name = model._meta.db_table
    columns = []
    constraints = []

    # Process each field
    for field_name, field in model._meta.fields_map.items():
        # Skip reverse relations
        if field.__class__.__name__ == "BackwardFKRelation":
            continue

        # Get field properties
        db_column = getattr(field, "source_field", field_name)
        nullable = getattr(field, "null", False)
        unique = getattr(field, "unique", False)
        pk = getattr(field, "pk", False)
        default = getattr(field, "default", None)

        # Determine SQL type from field type
        field_type = field.__class__.__name__

        if field_type == "IntField":
            sql_type = "INTEGER"
        elif field_type == "CharField":
            max_length = getattr(field, "max_length", 255)
            sql_type = f"VARCHAR({max_length})"
        elif field_type == "TextField":
            sql_type = "TEXT"
        elif field_type == "BooleanField":
            sql_type = "BOOLEAN"
        elif field_type == "FloatField":
            sql_type = "REAL"
        elif field_type == "DecimalField":
            sql_type = "DECIMAL"
        elif field_type == "DatetimeField":
            sql_type = "TIMESTAMP"
        elif field_type == "DateField":
            sql_type = "DATE"
        elif field_type == "ForeignKeyField":
            related_model = field.model_name
            related_table = Tortoise.apps.get(model._meta.app, {}).get(related_model, None)

            if related_table:
                related_table_name = related_table._meta.db_table
                sql_type = "INTEGER"  # Assuming integer foreign keys

                # Add foreign key constraint
                constraints.append(
                    f"FOREIGN KEY ({db_column}) REFERENCES {related_table_name} (id)"
                )
            else:
                sql_type = "INTEGER"  # Fallback if related table not found
        else:
            sql_type = "TEXT"  # Default to TEXT for unknown types

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
                    sql_type = "SERIAL"
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

    # Add index creation for any defined indexes
    indexes = []
    if hasattr(model._meta, "indexes"):
        for index_fields in model._meta.indexes:
            index_columns = [
                model._meta.fields_map[field_name].source_field
                if hasattr(model._meta.fields_map[field_name], "source_field")
                else field_name
                for field_name in index_fields
            ]
            indexes.append(
                f"CREATE INDEX idx_{table_name}_{'_'.join(index_columns)} ON {table_name} ({', '.join(index_columns)});"
            )

    # Add unique constraints
    if hasattr(model._meta, "unique_together"):
        for unique_fields in model._meta.unique_together:
            unique_columns = [
                model._meta.fields_map[field_name].source_field
                if hasattr(model._meta.fields_map[field_name], "source_field")
                else field_name
                for field_name in unique_fields
            ]
            constraints.append(f"UNIQUE ({', '.join(unique_columns)})")

    # Build the CREATE TABLE statement
    sql = f"CREATE TABLE {table_name} (\n"
    sql += ",\n".join(["    " + col for col in columns])

    if constraints:
        sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

    sql += "\n);"

    if indexes:
        sql += "\n\n" + "\n".join(indexes)

    return sql


def generate_model_creation_migration(
    models: List[Type[Model]], migration_name: str, app_name: str
) -> Tuple[str, str]:
    """
    Generate a migration file for creating models.

    Args:
        models: List of Tortoise model classes.
        migration_name: Name for the migration.
        app_name: The app name.

    Returns:
        Tuple of (migration_code, full_migration_name).
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    full_migration_name = f"{timestamp}_{migration_name}"

    # Forward operations (table creation)
    forward_operations = []
    backward_operations = []

    for model in models:
        table_name = model._meta.db_table

        # Add forward operation
        sql = generate_table_creation_sql(model)
        forward_operations.append(f"# Create table {table_name}")
        forward_operations.append(f'await connection.execute_script("""{sql}""")')

        # Add backward operation
        backward_operations.append(f"# Drop table {table_name}")
        backward_operations.append(f'await connection.execute_script("DROP TABLE {table_name}")')

    # Generate the migration code
    code = f'''"""
Migration {full_migration_name} for {app_name}
"""

from tortoise_pathway.migration import Migration
from tortoise import connections


class {migration_name.title().replace("_", "")}Migration(Migration):
    """
    Migration to create initial models.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply migration to create tables."""
        connection = connections.get("default")

{chr(10).join(["        " + op for op in forward_operations])}

    async def revert(self) -> None:
        """Revert migration by dropping tables."""
        connection = connections.get("default")

{chr(10).join(["        " + op for op in backward_operations])}
'''

    return code, full_migration_name
