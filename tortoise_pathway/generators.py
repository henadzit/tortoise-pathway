"""
Centralized code generators for Tortoise Pathway migrations.

This module contains all code generation functions for migrations to avoid duplication
across the codebase. It includes SQL generation and migration file templates.
"""

import datetime
from typing import List, Type, Dict, Any, Set
import re

from tortoise import Tortoise, Model
from tortoise.fields import Field, IntField

from tortoise_pathway.schema_change import (
    SchemaChange,
    CreateModel,
)
from tortoise_pathway.state import State


def generate_table_creation_sql(model: Type[Model], dialect: str = "sqlite") -> str:
    """
    Generate SQL to create a table for a model.

    Args:
        model: The Tortoise model class.
        dialect: SQL dialect to use.

    Returns:
        SQL string for table creation.
    """
    table_name = model._meta.db_table
    columns = []
    constraints = []

    # Process each field
    for field_name, field_obj in model._meta.fields_map.items():
        field_type = field_obj.__class__.__name__

        # Skip if this is a reverse relation
        if field_type == "BackwardFKRelation":
            continue

        db_column = field_obj.model_field_name
        nullable = field_obj.null
        unique = field_obj.unique
        pk = field_obj.pk
        default = field_obj.default

        # Get SQL type using the get_for_dialect method
        sql_type = field_obj.get_for_dialect(dialect, "SQL_TYPE")

        # Special handling for primary keys based on dialect and field type
        if pk and field_type == "IntField":
            if dialect == "sqlite":
                sql_type = "INTEGER"
                column_def = f"{db_column} {sql_type} PRIMARY KEY AUTOINCREMENT"
            elif dialect == "postgres":
                sql_type = "SERIAL"
                column_def = f"{db_column} {sql_type} PRIMARY KEY"
            else:
                column_def = f"{db_column} {sql_type} PRIMARY KEY"
        else:
            column_def = f"{db_column} {sql_type}"

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

        # Add foreign key constraints if needed
        if hasattr(field_obj, "reference") and field_obj.reference:
            related_table = field_obj.reference.db_table

            # For SQLite, in-place constraints are possible
            if related_table:
                constraints.append(f"FOREIGN KEY ({db_column}) REFERENCES {related_table} (id)")

    # Build the CREATE TABLE statement
    sql = f"CREATE TABLE {table_name} (\n"
    sql += ",\n".join(["    " + col for col in columns])

    if constraints:
        sql += ",\n" + ",\n".join(["    " + constraint for constraint in constraints])

    sql += "\n);"

    return sql


def generate_migration_class_name(migration_name: str) -> str:
    """
    Convert migration name to a suitable class name.

    Args:
        migration_name: Name of the migration, possibly with timestamp prefix.

    Returns:
        A CamelCase class name suitable for the migration.
    """
    # Remove timestamp prefix if present
    if re.match(r"^\d{8,14}_", migration_name):
        name_part = migration_name.split("_", 1)[1]
    else:
        name_part = migration_name

    # Convert to CamelCase
    words = re.split(r"[_\-\s]+", name_part)
    class_name = "".join(word.capitalize() for word in words) + "Migration"

    return class_name


def generate_timestamp() -> str:
    """Generate a timestamp string for migration filenames."""
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def generate_empty_migration(migration_name: str) -> str:
    """
    Generate content for an empty migration file.

    Args:
        migration_name: Name of the migration.

    Returns:
        String content for the migration file.
    """
    class_name = generate_migration_class_name(migration_name)

    return f'''"""
{migration_name} migration
"""

from tortoise_pathway.migration import Migration


class {class_name}(Migration):
    """
    Custom migration.
    """

    dependencies = []
    operations = [
        # Define your operations here
    ]
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

    # Create a State object to pass to to_migration
    state = State()

    # Prepare imports for schema change classes and models
    schema_changes_used = set()
    model_imports = set()
    field_imports = set()  # For field types when using fields dict

    for change in changes:
        # Add the change class name to imports
        schema_changes_used.add(change.__class__.__name__)

        # If we're generating a reverse operation as a different class type, add that too
        if isinstance(change, CreateModel):
            schema_changes_used.add("DropModel")

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
