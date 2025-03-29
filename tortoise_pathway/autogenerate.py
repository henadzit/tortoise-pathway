"""
Auto-generation of migrations for Tortoise ORM models.

This module provides functionality to automatically generate migrations
from existing models without tracking changes.
"""

import os
import importlib
from typing import List, Optional, Type

from tortoise import Tortoise, Model

from tortoise_pathway.migration import MigrationManager
from tortoise_pathway.schema_diff import SchemaChange, SchemaChangeType


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
