"""
Centralized code generators for Tortoise Pathway migrations.

This module contains all code generation functions for migrations to avoid duplication
across the codebase. It includes SQL generation and migration file templates.
"""

import datetime
from typing import List, Type

from tortoise import Tortoise, Model

from tortoise_pathway.schema_change import (
    SchemaChange,
    CreateTable,
)


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

        # Get SQL type using the get_for_dialect method
        sql_type = field.get_for_dialect(dialect, "SQL_TYPE")

        # Handle special cases for primary keys
        if pk:
            if dialect == "sqlite" and field_type == "IntField":
                # For SQLite, INTEGER PRIMARY KEY AUTOINCREMENT must use exactly "INTEGER" type
                sql_type = "INTEGER"
            elif field_type == "IntField" and dialect == "postgres":
                sql_type = "SERIAL"

        # Add foreign key constraints separately if needed
        if field_type == "ForeignKeyField":
            # Using getattr to handle potential missing attributes safely
            related_model_name = getattr(field, "model_name", None)
            related_table = None

            if related_model_name and model._meta.app:
                app_models = Tortoise.apps.get(model._meta.app, {})
                if related_model_name in app_models:
                    related_table = app_models[related_model_name]

            if related_table:
                related_table_name = related_table._meta.db_table
                # Add foreign key constraint
                constraints.append(
                    f"FOREIGN KEY ({db_column}) REFERENCES {related_table_name} (id)"
                )

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
        return change.forward_sql(dialect)
    elif direction == "backward":
        return change.backward_sql(dialect)
    else:
        return f"-- Invalid direction: {direction}"


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
    operations = []  # Add your SchemaChange operations here
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
        raise ValueError("No changes")

    # Prepare imports for schema change classes and models
    schema_changes_used = set()
    model_imports = set()
    field_imports = set()  # For field types when using fields dict

    for change in changes:
        # Add the change class name to imports
        schema_changes_used.add(change.__class__.__name__)

        # If we're generating a reverse operation as a different class type, add that too
        if isinstance(change, CreateTable):
            schema_changes_used.add("DropTable")

            # Add field type imports if using fields dictionary
            if hasattr(change, "fields") and change.fields:
                for field_name, field_obj in change.fields.items():
                    field_class = field_obj.__class__.__name__
                    field_module = field_obj.__class__.__module__
                    field_imports.add(f"from {field_module} import {field_class}")

    schema_imports = ", ".join(sorted(schema_changes_used))
    model_imports_str = "\n".join(sorted(model_imports))
    field_imports_str = "\n".join(sorted(field_imports))

    # Complete import section
    imports = []
    imports.append("from tortoise_pathway.migration import Migration")
    imports.append(f"from tortoise_pathway.schema_change import {schema_imports}")

    if model_imports_str:
        imports.append(model_imports_str)

    if field_imports_str:
        imports.append(field_imports_str)

    all_imports = "\n".join(imports)

    # Generate operations code by utilizing the to_migration method
    operations = []
    for i, change in enumerate(changes):
        operations.append(f"    # {change}")

        # Get the to_migration code which represents the operation
        migration_code = change.to_migration()

        # Split by lines and remove comment lines
        lines = migration_code.split("\n")
        operation_lines = [line for line in lines if not line.startswith("#")]

        if operation_lines:
            # Join back and ensure trailing comma
            operation_def = "\n    ".join(operation_lines)
            if not operation_def.endswith(","):
                operation_def += ","

            operations.append(f"    {operation_def}")

    operations_str = "\n".join(operations)

    return f'''"""
Auto-generated migration {migration_name}
"""

{all_imports}


class {class_name}(Migration):
    """
    Auto-generated migration based on model changes.
    """

    dependencies = []
    operations = [
{operations_str}
    ]
'''
