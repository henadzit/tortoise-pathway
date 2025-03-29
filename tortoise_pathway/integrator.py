"""
Integrator for Tortoise ORM applications.

This module provides a simple way to integrate migrations with Tortoise ORM applications.
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from tortoise import Tortoise
from tortoise_pathway.migration import MigrationManager


class TortoisePathwayIntegrator:
    """Integrates migrations with Tortoise ORM applications."""

    def __init__(self, tortoise_config: Dict[str, Any], migrations_dir: Optional[str] = None):
        """
        Initialize the integrator.

        Args:
            tortoise_config: Tortoise ORM configuration dictionary.
            migrations_dir: Base directory for migrations (defaults to "migrations").
        """
        self.tortoise_config = tortoise_config
        self.migrations_dir = migrations_dir or "migrations"
        self.initialized = False
        self.managers: Dict[str, MigrationManager] = {}

    async def initialize(self) -> None:
        """Initialize Tortoise ORM and migration managers."""
        # Initialize Tortoise ORM if not already initialized
        if not Tortoise._inited:
            await Tortoise.init(config=self.tortoise_config)

        # Create migration managers for each app
        for app_name in self.tortoise_config.get("apps", {}).keys():
            app_migration_dir = os.path.join(self.migrations_dir, app_name)
            manager = MigrationManager(app_name, app_migration_dir)
            await manager.initialize()
            self.managers[app_name] = manager

        self.initialized = True

    async def close(self) -> None:
        """Close database connections."""
        if Tortoise._inited:
            await Tortoise.close_connections()

    async def migrate(self, app_name: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Apply pending migrations.

        Args:
            app_name: Optional app name to migrate. If None, all apps are migrated.

        Returns:
            Dictionary mapping app names to lists of applied migrations.
        """
        if not self.initialized:
            await self.initialize()

        results = {}

        if app_name:
            if app_name not in self.managers:
                raise ValueError(f"App '{app_name}' not found")

            manager = self.managers[app_name]
            applied = await manager.apply_migrations()
            results[app_name] = applied
        else:
            # Apply migrations for all apps
            for app_name, manager in self.managers.items():
                applied = await manager.apply_migrations()
                results[app_name] = applied

        return results

    async def get_migration_status(
        self, app_name: Optional[str] = None
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Get migration status for all apps or a specific app.

        Args:
            app_name: Optional app name to check. If None, all apps are checked.

        Returns:
            Dictionary with app names as keys and dictionaries with "applied" and "pending" lists as values.
        """
        if not self.initialized:
            await self.initialize()

        results = {}

        if app_name:
            if app_name not in self.managers:
                raise ValueError(f"App '{app_name}' not found")

            manager = self.managers[app_name]
            results[app_name] = {
                "applied": manager.get_applied_migrations(),
                "pending": manager.get_pending_migrations(),
            }
        else:
            # Get status for all apps
            for app_name, manager in self.managers.items():
                results[app_name] = {
                    "applied": manager.get_applied_migrations(),
                    "pending": manager.get_pending_migrations(),
                }

        return results


# Helper function for easy integration
async def setup_and_migrate(
    tortoise_config: Dict[str, Any], migrations_dir: Optional[str] = None
) -> None:
    """
    Setup Tortoise ORM with migrations and apply pending migrations.

    Args:
        tortoise_config: Tortoise ORM configuration dictionary.
        migrations_dir: Base directory for migrations (defaults to "migrations").
    """
    integrator = TortoisePathwayIntegrator(tortoise_config, migrations_dir)

    try:
        await integrator.initialize()
        results = await integrator.migrate()

        for app_name, applied in results.items():
            if applied:
                print(f"Applied {len(applied)} migration(s) for {app_name}:")
                for migration in applied:
                    print(f"  - {migration}")
            else:
                print(f"No migrations applied for {app_name}.")
    finally:
        await integrator.close()
