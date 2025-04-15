import importlib
import inspect
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Type, cast

from tortoise import Tortoise

from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_differ import SchemaDiffer
from tortoise_pathway.state import State
from tortoise_pathway.generators import generate_empty_migration, generate_auto_migration


class MigrationManager:
    """Manages migrations for Tortoise ORM models."""

    def __init__(self, app_name: str, migrations_dir: str = "migrations"):
        self.app_name = app_name
        # Create the base migrations directory path
        if Path(migrations_dir).is_absolute():
            self.base_migrations_dir = Path(migrations_dir).relative_to(Path.cwd())
        else:
            self.base_migrations_dir = Path(migrations_dir)

        # Set the app-specific migrations directory
        self.migrations_dir = self.base_migrations_dir / app_name
        self.migrations: Dict[str, Type[Migration]] = {}
        self.applied_migrations: Set[str] = set()
        self.state = State(app_name)

    async def initialize(self, connection=None) -> None:
        """Initialize the migration system."""
        # Create migrations table if it doesn't exist
        await self._ensure_migration_table_exists(connection)

        # Load applied migrations from database
        await self._load_applied_migrations(connection)

        # Discover available migrations
        self._discover_migrations()

        # Rebuild state from applied migrations
        self._rebuild_state()

    async def _ensure_migration_table_exists(self, connection=None) -> None:
        """Create migration history table if it doesn't exist."""
        conn = connection or Tortoise.get_connection("default")

        await conn.execute_script("""
        CREATE TABLE IF NOT EXISTS tortoise_migrations (
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
        # Ensure the app-specific migrations directory exists
        if not self.migrations_dir.exists():
            self.migrations_dir.mkdir(parents=True, exist_ok=True)
            return

        for file_path in self.migrations_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue

            migration_name = file_path.stem

            # Create module path with app name included
            module_path = (
                f"{str(self.base_migrations_dir).replace('/', '.').replace('\\', '.')}."
                f"{self.app_name}.{migration_name}"
            )

            try:
                module = importlib.import_module(module_path)

                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Migration) and obj is not Migration:
                        self.migrations[migration_name] = obj
                        break
            except (ImportError, AttributeError) as e:
                print(f"Error loading migration {migration_name}: {e}")

    async def create_migration(self, name: str, auto: bool = True) -> Migration:
        """
        Create a new migration file and return the Migration instance.

        Args:
            name: The descriptive name for the migration
            auto: Whether to auto-generate migration operations based on model changes

        Returns:
            A Migration instance representing the newly created migration

        Raises:
            ImportError: If the migration file couldn't be loaded or no Migration class was found
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        migration_name = f"{timestamp}_{name}"

        # Make sure app migrations directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        # Create migration file path
        migration_file = self.migrations_dir / f"{migration_name}.py"

        if auto:
            # Generate migration content based on model changes compared to existing migrations state
            differ = SchemaDiffer(self.app_name, self.state)
            changes = await differ.detect_changes()
            content = generate_auto_migration(migration_name, changes)
        else:
            # Create an empty migration template
            content = generate_empty_migration(migration_name)

        with open(migration_file, "w") as f:
            f.write(content)

        # Load the migration module and instantiate the migration
        module_path = (
            f"{str(self.base_migrations_dir).replace('/', '.').replace('\\', '.')}."
            f"{self.app_name}.{migration_name}"
        )
        try:
            module = importlib.import_module(module_path)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, Migration) and obj is not Migration:
                    self.migrations[migration_name] = obj
                    return obj()

            # If we reach here, no Migration class was found in the module
            raise ImportError(f"No Migration class found in the generated module {module_path}")
        except (ImportError, AttributeError) as e:
            print(f"Error loading migration {migration_name}: {e}")
            raise ImportError(f"Failed to load newly created migration: {e}")

    async def apply_migrations(self, connection=None) -> List[Migration]:
        """
        Apply pending migrations.

        Returns:
            List of Migration instances that were applied
        """
        conn = connection or Tortoise.get_connection("default")
        applied_migrations = []

        # Get pending migrations
        pending_migrations = self.get_pending_migrations()

        # Apply each migration
        for migration in pending_migrations:
            migration_name = migration.name()

            try:
                # Apply migration
                for operation in migration.operations:
                    await operation.apply(self.state)
                    self.state.apply_operation(operation)

                # Record that migration was applied
                now = datetime.datetime.now().isoformat()
                # inlining the values helps to avoid the complexity of choosing the correct placeholders
                # for the backend. The probability of SQL injection here is close to 0.
                await conn.execute_query(
                    f"INSERT INTO tortoise_migrations (app, name, applied_at) VALUES ('{self.app_name}', '{migration_name}', '{now}')",
                )

                self.applied_migrations.add(migration_name)
                applied_migrations.append(migration)
                self.state.snapshot(migration_name)
                print(f"Applied migration: {migration_name}")
            except Exception as e:
                print(f"Error applying migration {migration_name}: {e}")
                # Rollback transaction if supported
                raise

        return applied_migrations

    async def revert_migration(
        self, migration_name: Optional[str] = None, connection=None
    ) -> Optional[Migration]:
        """
        Revert the last applied migration or a specific migration.

        Args:
            migration_name: Name of specific migration to revert, or None for the last applied
            connection: Database connection to use

        Returns:
            Migration instance that was reverted, or None if no migration was reverted
        """
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
            for operation in reversed(migration.operations):
                await operation.revert(self.state)
                self.state.apply_operation(operation)
            # Remove migration record
            await conn.execute_query(
                "DELETE FROM tortoise_migrations WHERE app = ? AND name = ?",
                [self.app_name, migration_name],
            )

            self.applied_migrations.remove(migration_name)

            # Rebuild state from remaining applied migrations
            self.state = self.state.prev()

            print(f"Reverted migration: {migration_name}")
            return migration

        except Exception as e:
            print(f"Error reverting migration {migration_name}: {e}")
            # Rollback transaction if supported
            raise

    def get_pending_migrations(self) -> List[Migration]:
        """
        Get list of pending migrations.

        Returns:
            List of Migration instances
        """
        # Get pending migration names
        pending_names = [name for name in self.migrations if name not in self.applied_migrations]

        # Sort by timestamp (assuming migration names start with timestamp)
        pending_names = sorted(pending_names)

        # Convert to Migration objects
        return [self.migrations[name]() for name in pending_names]

    def get_applied_migrations(self) -> List[Migration]:
        """
        Get list of applied migrations.

        Returns:
            List of Migration instances
        """
        # Get applied migration names that we have loaded
        applied_names = [name for name in self.applied_migrations if name in self.migrations]

        # Sort them
        applied_names = sorted(applied_names)

        # Convert to Migration objects
        return [self.migrations[name]() for name in applied_names]

    def _rebuild_state(self) -> None:
        """Build the state from applied migrations."""
        self.state = State(self.app_name)

        for migration in self.get_applied_migrations():
            for operation in migration.operations:
                self.state.apply_operation(operation)
            self.state.snapshot(migration.name())
