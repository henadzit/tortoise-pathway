"""
Centralized code generators for Tortoise Pathway migrations.

This module contains all code generation functions for migrations to avoid duplication
across the codebase. It includes SQL generation and migration file templates.
"""

import datetime
from typing import List, Type

from tortoise import Tortoise, Model

from tortoise_pathway.schema_diff import SchemaChange, SchemaChangeType


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
    processed_column_names = set()  # Track column names to avoid duplicates

    # Process each field
    for field_name, field in model._meta.fields_map.items():
        # Skip reverse relations
        if field.__class__.__name__ == "BackwardFKRelation":
            continue

        field_type = field.__class__.__name__

        # Skip processing if this field maps to an already processed column
        # (like when a ForeignKeyField already added {field_name}_id)
        # ForeignKey fields in Tortoise ORM automatically create a column with "_id" suffix
        if field_type == "ForeignKeyField":
            # For ForeignKeyField, use the actual db column name (typically field_name + "_id")
            db_field_name = field.model_field_name
            source_field = getattr(field, "source_field", None)
            if source_field:
                db_column = source_field
            else:
                # Default to tortoise convention: field_name + "_id"
                db_column = f"{db_field_name}_id"
        else:
            # Get field properties for non-FK fields
            # Only use source_field if it's not None, otherwise fall back to field_name
            source_field = getattr(field, "source_field", None)
            db_column = source_field if source_field is not None else field_name

        # Skip if we've already processed this column name
        if db_column in processed_column_names:
            continue

        processed_column_names.add(db_column)

        nullable = getattr(field, "null", False)
        unique = getattr(field, "unique", False)
        pk = getattr(field, "pk", False)
        default = getattr(field, "default", None)

        # Determine SQL type from field type
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
            # Using getattr to handle potential missing attributes safely
            related_model_name = getattr(field, "model_name", None)
            related_table = None

            if related_model_name and model._meta.app:
                app_models = Tortoise.apps.get(model._meta.app, {})
                if related_model_name in app_models:
                    related_table = app_models[related_model_name]

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
        meta_indexes = getattr(model._meta, "indexes", [])
        if isinstance(meta_indexes, (list, tuple)):
            for index_fields in meta_indexes:
                if not isinstance(index_fields, (list, tuple)):
                    continue

                # Create a list to hold valid column names
                safe_index_columns: List[str] = []

                for field_name in index_fields:
                    if field_name in model._meta.fields_map:
                        source_field = getattr(
                            model._meta.fields_map[field_name], "source_field", None
                        )
                        column_name = source_field if source_field is not None else field_name
                        safe_index_columns.append(str(column_name))

                if safe_index_columns:
                    indexes.append(
                        f"CREATE INDEX idx_{table_name}_{'_'.join(safe_index_columns)} ON {table_name} ({', '.join(safe_index_columns)});"
                    )

    # Add unique constraints
    if hasattr(model._meta, "unique_together"):
        meta_unique = getattr(model._meta, "unique_together", [])
        if isinstance(meta_unique, (list, tuple)):
            for unique_fields in meta_unique:
                if not isinstance(unique_fields, (list, tuple)):
                    continue

                # Create a list to hold valid column names
                safe_unique_columns: List[str] = []

                for field_name in unique_fields:
                    if field_name in model._meta.fields_map:
                        source_field = getattr(
                            model._meta.fields_map[field_name], "source_field", None
                        )
                        column_name = source_field if source_field is not None else field_name
                        safe_unique_columns.append(str(column_name))

                if safe_unique_columns:
                    constraints.append(f"UNIQUE ({', '.join(safe_unique_columns)})")

    # Build the CREATE TABLE statement
    sql = f"CREATE TABLE {table_name} (\n"
    sql += ",\n".join(["    " + col for col in columns])

    if constraints:
        sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

    sql += "\n);"

    if indexes:
        sql += "\n\n" + "\n".join(indexes)

    return sql


def generate_sql_for_schema_change(
    change: SchemaChange, direction: str = "forward", dialect: str = "sqlite"
) -> str:
    """
    Generate SQL for a schema change.

    Args:
        change: The schema change to generate SQL for.
        direction: Either "forward" or "backward".
        dialect: SQL dialect (default: "sqlite").

    Returns:
        SQL string for applying the change.
    """
    if direction == "forward":
        if change.change_type == SchemaChangeType.CREATE_TABLE:
            model = change.params.get("model")
            if model:
                return generate_table_creation_sql(model, dialect)
            return f"CREATE TABLE {change.table_name} (id INTEGER PRIMARY KEY);"

        elif change.change_type == SchemaChangeType.ADD_COLUMN:
            # Ensure we have a valid column name
            if change.column_name is None:
                # Try to get the field name from the field object's params
                if "field_name" in change.params:
                    column_name = change.params["field_name"]
                else:
                    # Fallback to a safe default to avoid SQL errors
                    column_name = "new_column"
            else:
                column_name = change.column_name

            field_type = change.field_object.__class__.__name__
            nullable = getattr(change.field_object, "null", False)
            default = getattr(change.field_object, "default", None)

            sql = f"ALTER TABLE {change.table_name} ADD COLUMN {column_name}"

            # Map Tortoise field types to SQL types (simplified)
            if field_type == "CharField":
                max_length = getattr(change.field_object, "max_length", 255)
                sql += f" VARCHAR({max_length})"
            elif field_type == "IntField":
                sql += " INTEGER"
            elif field_type == "BooleanField":
                sql += " BOOLEAN"
            elif field_type == "DatetimeField":
                sql += " TIMESTAMP"
            else:
                sql += " TEXT"  # Default to TEXT for unknown types

            if not nullable:
                sql += " NOT NULL"

            if default is not None:
                if isinstance(default, str):
                    sql += f" DEFAULT '{default}'"
                else:
                    sql += f" DEFAULT {default}"

            return sql

        elif change.change_type == SchemaChangeType.DROP_TABLE:
            return f"DROP TABLE {change.table_name}"

        # Add other change types as needed

    elif direction == "backward":
        if change.change_type == SchemaChangeType.CREATE_TABLE:
            return f"DROP TABLE {change.table_name}"

        elif change.change_type == SchemaChangeType.ADD_COLUMN:
            # Ensure we have a valid column name
            column_name = change.column_name
            if column_name is None:
                if "field_name" in change.params:
                    column_name = change.params["field_name"]
                else:
                    column_name = "new_column"

            # SQLite has limited support for dropping columns
            if dialect == "sqlite":
                return f"-- SQLite doesn't support DROP COLUMN directly. Create a new table without this column."
            else:
                return f"ALTER TABLE {change.table_name} DROP COLUMN {column_name}"

        # Add other reverse operations as needed

    return f"-- SQL for {change.change_type} not implemented yet"


def generate_migration_class_name(migration_name: str) -> str:
    """
    Generate a valid Python class name from a migration name.

    Args:
        migration_name: The migration name (usually with timestamp prefix).

    Returns:
        A valid Python class name.
    """
    # Strip timestamp if present (assuming format like YYYYMMDDHHMMSS_name)
    if "_" in migration_name and migration_name.split("_")[0].isdigit():
        class_base = migration_name.split("_", 1)[1]
    else:
        class_base = migration_name

    return f"{class_base.title().replace('_', '')}Migration"


def generate_timestamp() -> str:
    """Generate a timestamp string for migration names."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def generate_empty_migration(migration_name: str) -> str:
    """
    Generate empty migration file content.

    Args:
        migration_name: Name of the migration.

    Returns:
        String content for the migration file.
    """
    class_name = generate_migration_class_name(migration_name)

    return f'''"""
Migration {migration_name}
"""

from tortoise_pathway.migration import Migration


class {class_name}(Migration):
    """
    Custom migration class.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        # Write your forward migration logic here
        pass

    async def revert(self) -> None:
        """Revert the migration."""
        # Write your backward migration logic here
        pass
'''


def generate_auto_migration(migration_name: str, changes: List[SchemaChange]) -> str:
    """
    Generate migration file content based on detected changes.

    Args:
        migration_name: Name of the migration.
        changes: List of schema changes to include in the migration.

    Returns:
        String content for the migration file.
    """
    class_name = generate_migration_class_name(migration_name)

    # If no changes detected, return placeholder template
    if not changes:
        return f'''"""
Auto-generated migration {migration_name}
"""

from tortoise_pathway.migration import Migration
from tortoise import connections


class {class_name}(Migration):
    """
    Auto-generated migration based on model changes.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        connection = connections.get("default")

        # Auto-generated migration operations would go here
        # For example:
        # await connection.execute_script(
        #     """
        #     ALTER TABLE my_table ADD COLUMN new_column VARCHAR(255) NOT NULL DEFAULT '';
        #     """
        # )

    async def revert(self) -> None:
        """Revert the migration."""
        connection = connections.get("default")

        # Auto-generated rollback operations would go here
        # For example:
        # await connection.execute_script(
        #     """
        #     ALTER TABLE my_table DROP COLUMN new_column;
        #     """
        # )
'''

    # Generate operations for each change
    operations = []
    reverse_operations = []

    for change in changes:
        operations.append(f"# {change}")
        reverse_operations.append(f"# Reverse for: {change}")

        if change.change_type == SchemaChangeType.CREATE_TABLE:
            model = change.params.get("model")
            if model:
                sql = generate_table_creation_sql(model)
                operations.append(f'await connection.execute_script("""')
                operations.append(f"{sql}")
                operations.append(f'""")')
            else:
                operations.append(
                    f'await connection.execute_script("CREATE TABLE {change.table_name} (id INTEGER PRIMARY KEY)")'
                )

            reverse_operations.append(
                f'await connection.execute_script("DROP TABLE {change.table_name}")'
            )

        elif change.change_type == SchemaChangeType.ADD_COLUMN:
            sql = generate_sql_for_schema_change(change, "forward")
            operations.append(f'await connection.execute_script("{sql}")')

            reverse_sql = generate_sql_for_schema_change(change, "backward")
            reverse_operations.append(f'await connection.execute_script("{reverse_sql}")')

        elif change.change_type == SchemaChangeType.DROP_TABLE:
            operations.append(f'await connection.execute_script("DROP TABLE {change.table_name}")')
            reverse_operations.append(
                f"# Cannot automatically recreate dropped table {change.table_name}"
            )

        # Add other change types as needed

    # Filter out any None values
    operations = [op for op in operations if op is not None]
    reverse_operations = [op for op in reverse_operations if op is not None]

    # Generate the final migration code
    indent = "        "
    operations_str = "\n".join(indent + op for op in operations)
    reverse_operations_str = "\n".join(indent + op for op in reverse_operations)

    return f'''"""
Auto-generated migration {migration_name}
"""

from tortoise_pathway.migration import Migration
from tortoise import connections


class {class_name}(Migration):
    """
    Auto-generated migration based on model changes.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        connection = connections.get("default")

{operations_str}

    async def revert(self) -> None:
        """Revert the migration."""
        connection = connections.get("default")

{reverse_operations_str}
'''
