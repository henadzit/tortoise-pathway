"""
Command-line interface for Tortoise ORM migrations.

This module provides a command-line interface for managing migrations.
"""

import sys
import asyncio
import argparse
import importlib
import functools
from typing import Dict, Any, Callable, TypeVar, Coroutine

from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from tortoise_pathway.migration_manager import MigrationManager


T = TypeVar("T")


def close_connections_after(
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Decorator that ensures Tortoise connections are closed after the function completes."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await func(*args, **kwargs)
        finally:
            try:
                await Tortoise.close_connections()
            except ConfigurationError:
                # If Tortoise is not initialized, we can ignore this error
                pass

    return wrapper


async def init_tortoise(config_path: str) -> Dict[str, Any]:
    """Initialize Tortoise ORM with configuration from a module variable.

    Args:
        config_path: Path to the config variable in dot notation (e.g., 'myapp.config.TORTOISE_ORM')
    """
    try:
        # Split the path to separate module path from variable name
        path_parts = config_path.split(".")
        if len(path_parts) < 2:
            print(
                f"Error: Invalid config path '{config_path}'. Format should be 'module.path.CONFIG_VAR'"
            )
            sys.exit(1)

        module_path = ".".join(path_parts[:-1])
        config_var_name = path_parts[-1]

        # Import the module
        module = importlib.import_module(module_path)
        # Get the configuration variable
        tortoise_config = getattr(module, config_var_name, None)

        if not tortoise_config:
            print(f"Error: Could not find {config_var_name} in {module_path}")
            sys.exit(1)

        await Tortoise.init(config=tortoise_config)
        return tortoise_config

    except ImportError:
        print(f"Error: Could not import {module_path}")
        raise
    except Exception as e:
        print(f"Error initializing Tortoise: {e}")
        sys.exit(1)


def get_app_name(args: argparse.Namespace, config: Dict[str, Any]) -> str:
    """Get the app name from args or automatically from config if there's only one app."""
    apps = config.get("apps", {})

    if args.app:
        # Check if specified app exists
        if args.app not in apps:
            print(f"Error: App '{args.app}' not found in Tortoise ORM config")
            sys.exit(1)
        return args.app

    # No app specified - check if there's just one app
    if len(apps) == 1:
        return next(iter(apps))

    # Multiple apps and none specified
    print("Error: You must specify an app name with --app when config has multiple apps")
    print("Available apps:", ", ".join(apps.keys()))
    sys.exit(1)


@close_connections_after
async def make(args: argparse.Namespace) -> None:
    """Create new migration(s) based on model changes."""
    config = await init_tortoise(args.config)
    app = get_app_name(args, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = args.directory or "migrations"

    manager = MigrationManager(app, migration_dir)
    await manager.initialize()

    if args.name:
        name = args.name
    else:
        name = "auto"

    if not args.empty:
        # Generate automatic migration based on model changes
        migration = await manager.create_migration(name, auto=True)
        if migration is None:
            print("No changes detected.")
            return
    else:
        # Create an empty migration
        migration = await manager.create_migration(name, auto=False)

    print(f"Created migration {migration.name()} at {migration.path()}")


@close_connections_after
async def migrate(args: argparse.Namespace) -> None:
    """Apply migrations to the database."""
    config = await init_tortoise(args.config)
    app = get_app_name(args, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = args.directory or "migrations"

    manager = MigrationManager(app, migration_dir)
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


@close_connections_after
async def rollback(args: argparse.Namespace) -> None:
    """Revert the most recent migration."""
    config = await init_tortoise(args.config)
    app = get_app_name(args, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = args.directory or "migrations"

    manager = MigrationManager(app, migration_dir)
    await manager.initialize()

    if args.migration:
        reverted = await manager.revert_migration(args.migration)
    else:
        reverted = await manager.revert_migration()

    if reverted:
        print(f"Successfully reverted migration: {reverted.name()}")
    else:
        print("No migration was reverted.")


@close_connections_after
async def showmigrations(args: argparse.Namespace) -> None:
    """Show migration status."""
    config = await init_tortoise(args.config)
    app = get_app_name(args, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = args.directory or "migrations"

    manager = MigrationManager(app, migration_dir)
    await manager.initialize()

    applied = manager.get_applied_migrations()
    pending = manager.get_pending_migrations()

    print(f"Migrations for {app}:")
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


def print_warning():
    RED = "\033[91m"
    RESET = "\033[0m"
    print(
        f"{RED}Wargning! This project is in VERY early development and not yet ready for production use."
        f" Most things are broken and they will break again, APIs will change.{RESET}"
    )


def main() -> None:
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description="Tortoise ORM migrations")

    # Common arguments
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the Tortoise ORM configuration variable in dot notation (e.g., 'myapp.config.TORTOISE_ORM')",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # make command
    make_parser = subparsers.add_parser("make", help="Create new migration(s)")
    make_parser.add_argument("--app", help="App name (optional if config has only one app)")
    make_parser.add_argument("--name", help="Migration name (default: 'auto')")
    make_parser.add_argument("--empty", action="store_true", help="Create an empty migration")
    make_parser.add_argument(
        "--directory", help="Base migrations directory (default: 'migrations')"
    )

    # migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Apply migrations")
    migrate_parser.add_argument("--app", help="App name (optional if config has only one app)")
    migrate_parser.add_argument(
        "--directory", help="Base migrations directory (default: 'migrations')"
    )

    # rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Revert migrations")
    rollback_parser.add_argument("--app", help="App name (optional if config has only one app)")
    rollback_parser.add_argument("--migration", help="Specific migration to revert")
    rollback_parser.add_argument(
        "--directory", help="Base migrations directory (default: 'migrations')"
    )

    # showmigrations command
    show_parser = subparsers.add_parser("showmigrations", help="List migrations and their status")
    show_parser.add_argument("--app", help="App name (optional if config has only one app)")
    show_parser.add_argument(
        "--directory", help="Base migrations directory (default: 'migrations')"
    )

    args = parser.parse_args()

    print_warning()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "make":
        asyncio.run(make(args))
    elif args.command == "migrate":
        asyncio.run(migrate(args))
    elif args.command == "rollback":
        asyncio.run(rollback(args))
    elif args.command == "showmigrations":
        asyncio.run(showmigrations(args))


if __name__ == "__main__":
    main()
