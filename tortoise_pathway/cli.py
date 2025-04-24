"""
Command-line interface for Tortoise ORM migrations.

This module provides a command-line interface for managing migrations.
"""

import asyncio
import importlib
import functools
from typing import Dict, Any, Callable, TypeVar, Coroutine

import click
from tortoise import Tortoise

from tortoise_pathway.migration_manager import MigrationManager


T = TypeVar("T")


@click.group()
@click.option(
    "--config",
    required=True,
    help="Path to the Tortoise ORM configuration variable in dot notation (e.g., 'myapp.config.TORTOISE_ORM')",
    envvar="TORTOISE_ORM_CONFIG",
    type=str,
    metavar="CONFIG",
)
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """Command-line interface for Tortoise ORM migrations."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config

    click.secho(
        "Warning! This project is in VERY early development"
        " and not yet ready for production use."
        " Most things are broken and they will break again,"
        " and APIs will change.",
        fg="yellow",
    )


def asyncio_run(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """Decorator to run an async function in a synchronous context."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return func(*args, **kwargs)
        else:
            return loop.run_until_complete(func(*args, **kwargs))

    return wrapper


def close_connections_after(
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Decorator that ensures Tortoise connections are closed after the function completes."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await func(*args, **kwargs)
        finally:
            await Tortoise.close_connections()

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
            click.secho(
                f"Error: Invalid config path '{config_path}'. "
                "Format should be 'module.path.CONFIG_VAR'",
                fg="red",
            )
            raise click.Abort()

        module_path = ".".join(path_parts[:-1])
        config_var_name = path_parts[-1]

        # Import the module
        module = importlib.import_module(module_path)
        # Get the configuration variable
        tortoise_config = getattr(module, config_var_name, None)

        if not tortoise_config:
            click.secho(f"Error: Could not find {config_var_name} in {module_path}", fg="red")
            raise click.Abort()

        await Tortoise.init(config=tortoise_config)
        return tortoise_config

    except ImportError:
        click.secho(f"Error: Could not import {module_path}", fg="red")
        raise click.Abort()
    except Exception as e:
        click.secho(f"Error initializing Tortoise: {e}", fg="red")
        raise click.Abort()


def get_app_name(app: str | None, config: Dict[str, Any]) -> str:
    """Get the app name from args or automatically from config if there's only one app."""
    apps = config.get("apps", {})

    if app:
        # Check if specified app exists
        if app not in apps:
            click.secho(f"Error: App '{app}' not found in Tortoise ORM config", fg="red")
            raise click.Abort()
        return app

    # No app specified - check if there's just one app
    if len(apps) == 1:
        return next(iter(apps))

    # Multiple apps and none specified
    click.secho(
        "Error: You must specify an app name with --app when config has multiple apps", fg="red"
    )
    click.echo("Available apps:", ", ".join(apps.keys()))
    raise click.Abort()


@cli.command()
@click.option(
    "--app",
    help="App name (optional if config has only one app)",
    metavar="APP_NAME",
)
@click.option(
    "--name",
    help="Migration name (default: 'auto')",
    metavar="NAME",
)
@click.option(
    "--empty",
    is_flag=True,
    help="Create an empty migration",
)
@click.option(
    "--directory",
    help="Base migrations directory (default: 'migrations')",
    metavar="DIR",
)
@click.pass_context
@asyncio_run
@close_connections_after
async def make(
    ctx: click.Context,
    app: str,
    name: str,
    empty: bool,
    directory: str,
) -> None:
    """Create new migration(s) based on model changes."""
    config = await init_tortoise(ctx.obj["config"])
    app = get_app_name(app or None, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = directory or "migrations"

    manager = MigrationManager(app, migration_dir)
    await manager.initialize()

    if not name:
        name = "auto"

    if not empty:
        # Generate automatic migration based on model changes
        migration = await manager.create_migration(name, auto=True)
        if migration is None:
            click.secho("No changes detected.", fg="green")
            return
    else:
        # Create an empty migration
        migration = await manager.create_migration(name, auto=False)

    click.secho(f"Created migration {migration.name()} at {migration.path()}", fg="green")


@cli.command()
@click.option(
    "--app",
    help="App name (optional if config has only one app)",
    metavar="APP_NAME",
)
@click.option(
    "--directory",
    help="Base migrations directory (default: 'migrations')",
    metavar="DIR",
)
@click.pass_context
@asyncio_run
@close_connections_after
async def migrate(
    ctx: click.Context,
    app: str,
    directory: str,
) -> None:
    """Apply migrations to the database."""
    config = await init_tortoise(ctx.obj["config"])
    app = get_app_name(app or None, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = directory or "migrations"

    manager = MigrationManager(app, migration_dir)
    await manager.initialize()

    pending = manager.get_pending_migrations()

    if not pending:
        click.secho("No pending migrations.", fg="green")
        return

    click.echo(f"Applying {len(pending)} migration(s):")
    for migration in pending:
        click.echo(f"  - {migration.name()}")

    applied = await manager.apply_migrations()

    if applied:
        click.secho(f"Successfully applied {len(applied)} migration(s).", fg="green")
    else:
        click.secho("No migrations were applied.", fg="yellow")


@cli.command()
@click.option(
    "--app",
    help="App name (optional if config has only one app)",
    metavar="APP_NAME",
)
@click.option(
    "--migration",
    help="Specific migration to revert",
    metavar="MIGRATION_NAME",
)
@click.option(
    "--directory",
    help="Base migrations directory (default: 'migrations')",
    metavar="DIR",
)
@click.pass_context
@asyncio_run
@close_connections_after
async def rollback(
    ctx: click.Context,
    app: str,
    migration: str,
    directory: str,
) -> None:
    """Revert the most recent migration."""
    config = await init_tortoise(ctx.obj["config"])
    app = get_app_name(app or None, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = directory or "migrations"

    manager = MigrationManager(app, migration_dir)
    await manager.initialize()

    reverted = await manager.revert_migration(migration or None)

    if reverted:
        click.secho(f"Successfully reverted migration: {reverted.name()}", fg="green")
    else:
        click.secho("No migration was reverted.", fg="yellow")


@cli.command()
@click.option(
    "--app",
    help="App name (optional if config has only one app)",
    metavar="APP_NAME",
)
@click.option(
    "--directory",
    help="Base migrations directory (default: 'migrations')",
    metavar="DIR",
)
@click.pass_context
@asyncio_run
@close_connections_after
async def showmigrations(
    ctx: click.Context,
    app: str,
    directory: str,
) -> None:
    """Show migration status."""
    config = await init_tortoise(ctx.obj["config"])
    app = get_app_name(app or None, config)

    # The migrations directory is now the base directory, no need to join with app name
    migration_dir = directory or "migrations"

    manager = MigrationManager(app, migration_dir)
    await manager.initialize()

    applied = manager.get_applied_migrations()
    pending = manager.get_pending_migrations()

    click.echo(f"Migrations for {app}:")
    click.echo("\nApplied migrations:")
    if applied:
        for migration in applied:
            click.echo(f" \u2714 {click.style(migration.name(), fg='green')}")
    else:
        click.echo(" (none)")

    click.echo("\nPending migrations:")
    if pending:
        for migration in pending:
            click.echo(f" \u25cf {click.style(migration.name(), fg='yellow')}")
    else:
        click.echo(" (none)")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
