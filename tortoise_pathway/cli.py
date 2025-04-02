"""
Command-line interface for Tortoise ORM migrations.

This module provides a command-line interface for managing migrations.
"""

import os
import sys
import asyncio
import argparse
import importlib
from typing import Dict, Any

from tortoise import Tortoise

from tortoise_pathway.migration_manager import MigrationManager
from tortoise_pathway.schema_differ import SchemaDiffer


async def init_tortoise(config_module: str) -> Dict[str, Any]:
    """Initialize Tortoise ORM with configuration from a module."""
    try:
        config = importlib.import_module(config_module)
        tortoise_config = getattr(config, "TORTOISE_ORM", None)

        if not tortoise_config:
            print(f"Error: Could not find TORTOISE_ORM in {config_module}")
            sys.exit(1)

        await Tortoise.init(config=tortoise_config)
        return tortoise_config

    except ImportError:
        print(f"Error: Could not import {config_module}")
        raise
        # sys.exit(1)
    except Exception as e:
        print(f"Error initializing Tortoise: {e}")
        sys.exit(1)


async def makemigrations(args: argparse.Namespace) -> None:
    """Create new migration(s) based on model changes."""
    config = await init_tortoise(args.config)

    if not args.app:
        print("Error: You must specify an app name with --app")
        sys.exit(1)

    if args.app not in config.get("apps", {}):
        print(f"Error: App '{args.app}' not found in Tortoise ORM config")
        sys.exit(1)

    migration_dir = args.directory or os.path.join(args.app, "migrations")

    manager = MigrationManager(args.app, migration_dir)
    await manager.initialize()

    if args.name:
        name = args.name
    else:
        name = "auto"

    if not args.empty:
        # Generate automatic migration based on model changes
        differ = SchemaDiffer(args.app)
        changes = await differ.detect_changes()

        if not changes:
            print("No changes detected.")
            return

        print(f"Detected {len(changes)} changes:")
        for change in changes:
            print(f"  - {change}")

        migration = await manager.create_migration(name, auto=True)
    else:
        # Create an empty migration
        migration = await manager.create_migration(name, auto=False)

    print(f"Created migration {migration.name()} at {migration.path()}")


async def migrate(args: argparse.Namespace) -> None:
    """Apply migrations to the database."""
    await init_tortoise(args.config)

    if not args.app:
        print("Error: You must specify an app name with --app")
        sys.exit(1)

    migration_dir = args.directory or os.path.join(args.app, "migrations")

    manager = MigrationManager(args.app, migration_dir)
    await manager.initialize()

    pending = manager.get_pending_migrations()

    if not pending:
        print("No pending migrations.")
        return

    print(f"Applying {len(pending)} migration(s):")
    for migration in pending:
        print(f"  - {migration.name()}")

    applied = await manager.apply_migrations()

    if applied:
        print(f"Successfully applied {len(applied)} migration(s).")
    else:
        print("No migrations were applied.")


async def rollback(args: argparse.Namespace) -> None:
    """Revert the most recent migration."""
    await init_tortoise(args.config)

    if not args.app:
        print("Error: You must specify an app name with --app")
        sys.exit(1)

    migration_dir = args.directory or os.path.join(args.app, "migrations")

    manager = MigrationManager(args.app, migration_dir)
    await manager.initialize()

    if args.migration:
        reverted = await manager.revert_migration(args.migration)
    else:
        reverted = await manager.revert_migration()

    if reverted:
        print(f"Successfully reverted migration: {reverted.name()}")
    else:
        print("No migration was reverted.")


async def showmigrations(args: argparse.Namespace) -> None:
    """Show migration status."""
    await init_tortoise(args.config)

    if not args.app:
        print("Error: You must specify an app name with --app")
        sys.exit(1)

    migration_dir = args.directory or os.path.join(args.app, "migrations")

    manager = MigrationManager(args.app, migration_dir)
    await manager.initialize()

    applied = manager.get_applied_migrations()
    pending = manager.get_pending_migrations()

    print(f"Migrations for {args.app}:")
    print("\nApplied migrations:")
    if applied:
        for migration in applied:
            print(f"  [X] {migration.name()}")
    else:
        print("  (none)")

    print("\nPending migrations:")
    if pending:
        for migration in pending:
            print(f"  [ ] {migration.name()}")
    else:
        print("  (none)")


def main() -> None:
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description="Tortoise ORM migrations")

    # Common arguments
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the Tortoise ORM configuration module (e.g., 'myapp.settings')",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # makemigrations command
    make_parser = subparsers.add_parser("makemigrations", help="Create new migration(s)")
    make_parser.add_argument("--app", help="App name")
    make_parser.add_argument("--name", help="Migration name (default: 'auto')")
    make_parser.add_argument("--empty", action="store_true", help="Create an empty migration")
    make_parser.add_argument("--directory", help="Migrations directory")

    # migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Apply migrations")
    migrate_parser.add_argument("--app", help="App name")
    migrate_parser.add_argument("--directory", help="Migrations directory")

    # rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Revert migrations")
    rollback_parser.add_argument("--app", help="App name")
    rollback_parser.add_argument("--migration", help="Specific migration to revert")
    rollback_parser.add_argument("--directory", help="Migrations directory")

    # showmigrations command
    show_parser = subparsers.add_parser("showmigrations", help="List migrations and their status")
    show_parser.add_argument("--app", help="App name")
    show_parser.add_argument("--directory", help="Migrations directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "makemigrations":
        asyncio.run(makemigrations(args))
    elif args.command == "migrate":
        asyncio.run(migrate(args))
    elif args.command == "rollback":
        asyncio.run(rollback(args))
    elif args.command == "showmigrations":
        asyncio.run(showmigrations(args))


if __name__ == "__main__":
    main()
