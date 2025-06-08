"""
Centralized code generators for Tortoise Pathway migrations.

This module contains all code generation functions for migrations to avoid duplication
across the codebase. It includes SQL generation and migration file templates.
"""

import datetime
from typing import List
import re

from tortoise.fields import Field
from tortoise.indexes import Index

from tortoise_pathway.operations import (
    AddField,
    Operation,
    CreateModel,
    AddIndex,
    DropIndex,
)
from tortoise_pathway.operations.alter_field import AlterField


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


def generate_empty_migration(migration_name: str, dependencies: list[tuple[str, str]] = []) -> str:
    """
    Generate content for an empty migration file.

    Args:
        migration_name: Name of the migration.

    Returns:
        String content for the migration file.
    """
    class_name = generate_migration_class_name(migration_name)

    dependencies_str = ""
    if dependencies:
        dependencies_str = ", ".join(
            f'("{app_name}", "{migration_name}")' for app_name, migration_name in dependencies
        )

    return f'''"""
{migration_name} migration
"""

from tortoise_pathway.migration import Migration


class {class_name}(Migration):
    """
    Custom migration.
    """

    dependencies = [{dependencies_str}]
    operations = [
        # Define your operations here
    ]
'''


def generate_auto_migration(
    migration_name: str, changes: list[Operation], dependencies: list[tuple[str, str]] = []
) -> str:
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
    field_imports = set()
    index_imports = set()

    for change in changes:
        # Add the change class name to imports
        schema_changes_used.add(change.__class__.__name__)

        if isinstance(change, CreateModel):
            # Add field type imports if using fields dictionary
            if change.fields:
                for field_obj in change.fields.values():
                    field_imports.update(field_to_imports(field_obj))

        elif isinstance(change, AddField) or isinstance(change, AlterField):
            field_imports.update(field_to_imports(change.field_object))
        elif isinstance(change, AddIndex) or isinstance(change, DropIndex):
            index_imports.update(index_to_imports(change.index))

    schema_imports = ", ".join(sorted(schema_changes_used))
    model_imports_str = "\n".join(sorted(model_imports))
    field_imports_str = "\n".join(sorted(field_imports))
    index_imports_str = "\n".join(sorted(index_imports))

    # Complete import section
    imports = []
    imports.append("from tortoise_pathway.migration import Migration")
    imports.append(f"from tortoise_pathway.operations import {schema_imports}")

    if model_imports_str:
        imports.append(model_imports_str)

    if field_imports_str:
        imports.append(field_imports_str)

    if index_imports_str:
        imports.append(index_imports_str)

    all_imports = "\n".join(imports)

    dependencies_str = ""
    if dependencies:
        dependencies_str = ", ".join(
            f'("{app_name}", "{migration_name}")' for app_name, migration_name in dependencies
        )

    # Generate operations code by utilizing the to_migration method
    operations = []
    for i, change in enumerate(changes):
        # Get the to_migration code which represents the operation
        migration_code = change.to_migration()

        # Split by lines and remove comment lines
        lines = migration_code.split("\n")
        operation_lines = [line for line in lines if not line.startswith("#")]

        if operation_lines:
            # Join back and ensure trailing comma
            operation_def = "\n        ".join(operation_lines)
            if not operation_def.endswith(","):
                operation_def += ","

            operations.append(f"        {operation_def}")

    operations_str = "\n".join(operations)

    return f'''"""
Auto-generated migration {migration_name}
"""

{all_imports}


class {class_name}(Migration):
    """
    Auto-generated migration based on model changes.
    """

    dependencies = [{dependencies_str}]
    operations = [
{operations_str}
    ]
'''


def field_to_imports(field: Field) -> List[str]:
    """
    Convert a field object to an import string.
    """
    imports = [f"from {field.__class__.__module__} import {field.__class__.__name__}"]
    if hasattr(field, "enum_type"):
        imports.append(f"from {field.enum_type.__module__} import {field.enum_type.__name__}")
    return imports


def index_to_imports(index: Index) -> List[str]:
    """
    Convert an index object to an import string.
    """
    return [f"from {index.__class__.__module__} import {index.__class__.__name__}"]
