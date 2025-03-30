"""
Core migration module for Tortoise ORM.

This module contains the Migration class and functions for managing migrations.
"""

import importlib
import inspect
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Type, cast

from tortoise import Tortoise
from tortoise.exceptions import OperationalError

from tortoise_pathway.schema_differ import SchemaDiffer
from tortoise_pathway.generators import generate_empty_migration, generate_auto_migration


class Migration:
    """Base class for all migrations."""

    dependencies: List[str] = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        raise NotImplementedError("Subclasses must implement this method")

    async def revert(self) -> None:
        """Revert the migration."""
        raise NotImplementedError("Subclasses must implement this method")


class MigrationManager:
    """Manages migrations for Tortoise ORM models."""

    def __init__(self, app_name: str, migrations_dir: str = "migrations"):
        self.app_name = app_name
        self.migrations_dir = migrations_dir
        self.migration_dir_path = Path(migrations_dir)
        self.migrations: Dict[str, Type[Migration]] = {}
        self.applied_migrations: Set[str] = set()

    async def initialize(self, connection=None) -> None:
        """Initialize the migration system."""
        # Create migrations table if it doesn't exist
        await self._ensure_migration_table_exists(connection)

        # Load applied migrations from database
        await self._load_applied_migrations(connection)

        # Discover available migrations
        self._discover_migrations()

    async def _ensure_migration_table_exists(self, connection=None) -> None:
        """Create migration history table if it doesn't exist."""
        conn = connection or Tortoise.get_connection("default")

        try:
            await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS tortoise_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app VARCHAR(100) NOT NULL,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP NOT NULL
            )
            """)
        except OperationalError:
            # Different syntax for PostgreSQL
            await conn.execute_script("""
            CREATE TABLE IF NOT EXISTS tortoise_migrations (
                id SERIAL PRIMARY KEY,
                app VARCHAR(100) NOT NULL,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP NOT NULL
            )
            """)

    async def _load_applied_migrations(self, connection=None) -> None:
        """Load list of applied migrations from the database."""
        conn = connection or Tortoise.get_connection("default")

        records = await conn.execute_query(
            f"SELECT name FROM tortoise_migrations WHERE app = '{self.app_name}'"
        )

        self.applied_migrations = {record["name"] for record in records[1]}

    def _discover_migrations(self) -> None:
        """Discover available migrations in the migrations directory."""
        if not self.migration_dir_path.exists():
            self.migration_dir_path.mkdir(parents=True, exist_ok=True)
            return

        for file_path in self.migration_dir_path.glob("*.py"):
            if file_path.name.startswith("__"):
                continue

            migration_name = file_path.stem

            # Determine if migrations_dir is absolute or relative
            migrations_path = Path(self.migrations_dir)

            if migrations_path.is_absolute():
                # For absolute paths, we need to determine the module path
                # based on the Python package structure
                # Try to find the relative path from the current working directory
                rel_path = migrations_path.relative_to(Path.cwd())
                module_path = str(rel_path).replace("/", ".").replace("\\", ".")
                module_path = f"{module_path}.{migration_name}"
            else:
                # For relative paths, use the existing logic
                module_path = (
                    f"{self.migrations_dir.replace('/', '.').replace('\\', '.')}.{migration_name}"
                )

            try:
                module = importlib.import_module(module_path)

                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Migration) and obj is not Migration:
                        self.migrations[migration_name] = obj
                        break
            except (ImportError, AttributeError) as e:
                print(f"Error loading migration {migration_name}: {e}")

    async def create_migration(self, name: str, auto: bool = True) -> Path:
        """Create a new migration file."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        migration_name = f"{timestamp}_{name}"

        # Make sure migrations directory exists
        self.migration_dir_path.mkdir(parents=True, exist_ok=True)

        # Create migration file path
        migration_file = self.migration_dir_path / f"{migration_name}.py"

        if auto:
            # Generate migration content based on model changes
            differ = SchemaDiffer()
            changes = await differ.detect_changes()
            content = generate_auto_migration(migration_name, changes)
        else:
            # Create an empty migration template
            content = generate_empty_migration(migration_name)

        with open(migration_file, "w") as f:
            f.write(content)

        return migration_file

    async def apply_migrations(self, connection=None) -> List[str]:
        """Apply pending migrations."""
        conn = connection or Tortoise.get_connection("default")
        applied = []

        # Get pending migrations
        pending = self.get_pending_migrations()

        # Apply each migration
        for name in pending:
            migration_class = self.migrations[name]
            migration = migration_class()

            try:
                # Apply migration
                await migration.apply()

                # Record that migration was applied
                now = datetime.datetime.now().isoformat()
                await conn.execute_query(
                    "INSERT INTO tortoise_migrations (app, name, applied_at) VALUES (?, ?, ?)",
                    [self.app_name, name, now],
                )

                self.applied_migrations.add(name)
                applied.append(name)
                print(f"Applied migration: {name}")

            except Exception as e:
                print(f"Error applying migration {name}: {e}")
                # Rollback transaction if supported
                raise

        return applied

    async def revert_migration(
        self, migration_name: Optional[str] = None, connection=None
    ) -> Optional[str]:
        """Revert the last applied migration or a specific migration."""
        conn = connection or Tortoise.get_connection("default")

        if not migration_name:
            # Get the last applied migration
            records = await conn.execute_query(
                "SELECT name FROM tortoise_migrations WHERE app = ? ORDER BY id DESC LIMIT 1",
                [self.app_name],
            )

            if not records[1]:
                print("No migrations to revert")
                return None

            migration_name = cast(str, records[1][0]["name"])

        if migration_name not in self.migrations:
            raise ValueError(f"Migration {migration_name} not found")

        if migration_name not in self.applied_migrations:
            raise ValueError(f"Migration {migration_name} is not applied")

        # Revert the migration
        migration_class = self.migrations[migration_name]
        migration = migration_class()

        try:
            # Revert migration
            await migration.revert()

            # Remove migration record
            await conn.execute_query(
                "DELETE FROM tortoise_migrations WHERE app = ? AND name = ?",
                [self.app_name, migration_name],
            )

            self.applied_migrations.remove(migration_name)
            print(f"Reverted migration: {migration_name}")
            return migration_name

        except Exception as e:
            print(f"Error reverting migration {migration_name}: {e}")
            # Rollback transaction if supported
            raise

    def get_pending_migrations(self) -> List[str]:
        """Get list of pending migrations."""
        pending = [name for name in self.migrations if name not in self.applied_migrations]

        # Sort by timestamp (assuming migration names start with timestamp)
        return sorted(pending)

    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migrations."""
        return sorted(self.applied_migrations)
