"""
Command-line interface for Tortoise ORM migrations.

This module provides a command-line interface for managing migrations.
"""

import argparse
import asyncio
import importlib
import contextlib
from typing import Dict, Any, Callable

from tortoise import Tortoise

from tortoise_pathway.migration_manager import MigrationManager
from tortoise_pathway.cliutil import Abort, Command, echo, env_default


@contextlib.asynccontextmanager
async def with_tortoise(ctx: dict):
    try:
        # Get the config path from the context
        config_path = ctx["config_path"]

        # Split the path to separate module path from variable name
        path_parts = config_path.split(".")
        if len(path_parts) < 2:
            raise Abort(
                f"Error: Invalid config path '{config_path}'. "
                "Format should be 'module.path.CONFIG_VAR'",
            )

        module_path = ".".join(path_parts[:-1])
        config_var_name = path_parts[-1]

        # Import the module
        module = importlib.import_module(module_path)
        # Get the configuration variable
        tortoise_config = getattr(module, config_var_name, None)

        if not tortoise_config:
            raise Abort(f"Error: Could not find {config_var_name} in {module_path}")

        await Tortoise.init(config=tortoise_config)
        ctx["tortoise_config"] = tortoise_config
        ctx["app"] = get_app_name(ctx["app_name"] or None, tortoise_config)
    except ImportError:
        raise Abort(f"Error: Could not import {module_path}")
    except Exception as e:
        raise Abort(f"Error initializing Tortoise: {e}")
    try:
        yield
    finally:
        await Tortoise.close_connections()


def get_app_name(app: str | None, config: Dict[str, Any]) -> str:
    """Get the app name from args or automatically from config if there's only one app."""
    apps = config.get("apps", {})

    if app:
        # Check if specified app exists
        if app not in apps:
            echo("Available apps: " + ", ".join(apps.keys()))
            raise Abort(f"Error: App '{app}' not found in Tortoise ORM config")
        return app

    # No app specified - check if there's just one app
    if len(apps) == 1:
        return next(iter(apps))

    # Multiple apps and none specified
    echo("Available apps: " + ", ".join(apps.keys()))
    raise Abort("Error: You must specify an app name with --app when config has multiple apps")


commands: Dict[str, tuple[Command, dict]] = {}
parser = argparse.ArgumentParser(description="Tortoise ORM migrations")
parser.add_argument(
    "--config",
    help="Path to the Tortoise ORM configuration variable in dot notation (e.g., 'myapp.config.TORTOISE_ORM')",
    type=str,
    required=True,
    action=env_default("TORTOISE_ORM_CONFIG"),
    metavar="TORTOISE_ORM",
)
parser.add_argument(
    "--app",
    help="App name (optional if config has only one app)",
    type=str,
    default=None,
    required=False,
    action=env_default("TORTOISE_APP_NAME"),
    metavar="APP_NAME",
)
parser.add_argument(
    "--directory",
    help="Base migrations directory (default: 'migrations')",
    type=str,
    default="migrations",
    action=env_default("MIGRATIONS_DIR"),
    metavar="DIRECTORY",
)
subparsers = parser.add_subparsers(dest="command", help="Command to execute", metavar="COMMAND")


def command(**params: dict) -> Callable[[Command], Command]:
    def decorator(func: Command) -> Command:
        subparser = subparsers.add_parser(func.__name__, help=func.__doc__)
        for param in params:
            subparser.add_argument(f"--{param}", **params[param])
        commands[func.__name__] = (func, params)
        return func

    return decorator


def main(argv=None) -> None:
    """Command-line interface for Tortoise ORM migrations."""
    echo(
        "=" * 80 + "\nWarning!\nThis project is in VERY early development"
        " and not yet ready for production use.\n"
        "Most things are broken and they will break again,"
        " and APIs will change.\n" + "=" * 80,
        "yellow",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    ctx = {
        "config_path": args.config,
        "app_name": args.app,
        "migrations_dir": args.directory,
    }

    cmd, params = commands[args.command]
    paramvalues = {}
    for param, cfg in params.items():
        value = getattr(args, param)
        paramvalues[param] = value
    try:

        async def run_cmd() -> None:
            async with with_tortoise(ctx):
                await cmd(ctx, **paramvalues)

        asyncio.run(run_cmd())
    except Abort as e:
        echo(str(e), "red")
        echo("Aborted!", "red")


@command(
    name={
        "help": "Name of the migration",
        "type": str,
        "default": "auto",
        "metavar": "NAME",
    },
    empty={
        "help": "Create an empty migration",
        "default": False,
        "action": "store_true",
    },
)
async def make(ctx: dict, name: str, empty: bool) -> None:
    """Create new migration(s) based on model changes."""

    app = ctx["app"]
    manager = MigrationManager(app, ctx["migrations_dir"])
    await manager.initialize()

    if not name:
        name = "auto"

    if not empty:
        # Generate automatic migration based on model changes
        migration = await manager.create_migration(name, auto=True)
        if migration is None:
            echo("No changes detected.", "green")
            return
    else:
        # Create an empty migration
        migration = await manager.create_migration(name, auto=False)

    echo(f"Created migration {migration.name()} at {migration.path()}", "green")


@command()
async def migrate(ctx: dict) -> None:
    """Apply migrations to the database."""
    app = ctx["app"]
    manager = MigrationManager(app, ctx["migrations_dir"])
    await manager.initialize()

    pending = manager.get_pending_migrations()

    if not pending:
        echo("No pending migrations.", "green")
        return

    echo(f"Applying {len(pending)} migration(s):")
    for migration in pending:
        echo(f"  - {migration.name()}")

    applied = await manager.apply_migrations()

    if applied:
        echo(f"Successfully applied {len(applied)} migration(s).", "green")
    else:
        echo("No migrations were applied.", "yellow")


@command(
    migration={
        "help": "Name of the migration to revert",
        "type": str,
        "default": None,
        "metavar": "MIGRATION",
    },
)
async def rollback(ctx: dict, migration: str) -> None:
    """Revert the most recent migration."""
    app = ctx["app"]
    manager = MigrationManager(app, ctx["migrations_dir"])
    await manager.initialize()

    reverted = await manager.revert_migration(migration or None)

    if reverted:
        echo(f"Successfully reverted migration: {reverted.name()}", "green")
    else:
        echo("No migration was reverted.", "yellow")


@command()
async def showmigrations(ctx: dict) -> None:
    """Show migration status."""
    app = ctx["app"]
    manager = MigrationManager(app, ctx["migrations_dir"])
    await manager.initialize()

    applied = manager.get_applied_migrations()
    pending = manager.get_pending_migrations()

    echo(f"Migrations for {app}:")
    echo("\nApplied migrations:")
    if applied:
        for migration in applied:
            echo(f" \u2714 {migration.name()}", "green")
    else:
        echo(" (none)")

    echo("\nPending migrations:")
    if pending:
        for migration in pending:
            echo(f" \u25cf {migration.name()}", "yellow")
    else:
        echo(" (none)")


if __name__ == "__main__":
    main()
