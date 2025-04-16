from collections import defaultdict
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
        if Path(migrations_dir).is_absolute():
            self.base_migrations_dir = Path(migrations_dir).relative_to(Path.cwd())
        else:
            self.base_migrations_dir = Path(migrations_dir)

        # Set the app-specific migrations directory
        self.migrations_dir = self.base_migrations_dir / app_name
        self.migrations: list[Type[Migration]] = []
        self.applied_migrations: Set[str] = set()
        self.migration_state = State(app_name)
        self.applied_state = State(app_name)

    async def initialize(self, connection=None) -> None:
        """Initialize the migration system."""
        # Create migrations table if it doesn't exist
        await self._ensure_migration_table_exists(connection)

        # Load applied migrations from database
        await self._load_applied_migrations(connection)

        # Discover available migrations
        self._discover_migrations()

        # Rebuild state from migrations
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
        """Discover available migrations in the migrations directory and sort them based on dependencies."""
        migrations = load_migrations_from_disk(self.migrations_dir)
        self.migrations = sort_migrations(migrations)

    async def create_migration(self, name: str, auto: bool = True) -> Optional[Type[Migration]]:
        """
        Create a new migration file and return the Migration instance.

        Args:
            name: The descriptive name for the migration
            auto: Whether to auto-generate migration operations based on model changes

        Returns:
            A Migration instance representing the newly created migration.
            None if no changes were detected.

        Raises:
            ImportError: If the migration file couldn't be loaded or no Migration class was found
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        migration_name = f"{timestamp}_{name}"

        # Make sure app migrations directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        # Create migration file path
        migration_file = self.migrations_dir / f"{migration_name}.py"

        dependencies = []
        if self.migrations:
            dependencies = [self.migrations[-1].name()]

        if auto:
            # Generate migration content based on model changes compared to existing migrations state
            differ = SchemaDiffer(self.app_name, self.migration_state)
            changes = await differ.detect_changes()
            if not changes:
                return None

            content = generate_auto_migration(migration_name, changes, dependencies)
        else:
            content = generate_empty_migration(migration_name, dependencies)

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
                    self.migrations.append(obj)

                    for operation in obj.operations:
                        self.migration_state.apply_operation(operation)
                    self.migration_state.snapshot(migration_name)

                    return obj

            # If we reach here, no Migration class was found in the module
            raise ImportError(f"No Migration class found in the generated module {module_path}")
        except (ImportError, AttributeError) as e:
            print(f"Error loading migration {migration_name}: {e}")
            raise ImportError(f"Failed to load newly created migration: {e}")

    async def apply_migrations(self, connection=None) -> List[Type[Migration]]:
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
                    await operation.apply(self.applied_state)
                    self.applied_state.apply_operation(operation)

                # Record that migration was applied
                now = datetime.datetime.now().isoformat()
                # inlining the values helps to avoid the complexity of choosing the correct placeholders
                # for the backend. The probability of SQL injection here is close to 0.
                await conn.execute_query(
                    f"INSERT INTO tortoise_migrations (app, name, applied_at) VALUES ('{self.app_name}', '{migration_name}', '{now}')",
                )

                self.applied_migrations.add(migration_name)
                applied_migrations.append(migration)
                self.applied_state.snapshot(migration_name)
                print(f"Applied migration: {migration_name}")
            except Exception as e:
                print(f"Error applying migration {migration_name}: {e}")
                # Rollback transaction if supported
                raise

        return applied_migrations

    async def revert_migration(
        self, migration_name: Optional[str] = None, connection=None
    ) -> Optional[Type[Migration]]:
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

        if migration_name not in [m.name() for m in self.migrations]:
            raise ValueError(f"Migration {migration_name} not found")

        if migration_name not in self.applied_migrations:
            raise ValueError(f"Migration {migration_name} is not applied")

        # Revert the migration
        migration = next(m for m in self.migrations if m.name() == migration_name)

        try:
            for operation in reversed(migration.operations):
                await operation.revert(self.applied_state)
                # TODO: should be reverting, not applying
                self.applied_state.apply_operation(operation)
            # Remove migration record
            await conn.execute_query(
                "DELETE FROM tortoise_migrations WHERE app = ? AND name = ?",
                [self.app_name, migration_name],
            )

            self.applied_migrations.remove(migration_name)

            # Rebuild state from remaining applied migrations
            self.applied_state = self.applied_state.prev()

            print(f"Reverted migration: {migration_name}")
            return migration

        except Exception as e:
            print(f"Error reverting migration {migration_name}: {e}")
            # Rollback transaction if supported
            raise

    def get_pending_migrations(self) -> List[Type[Migration]]:
        """
        Get list of pending migrations.

        Returns:
            List of Migration instances
        """
        return [m for m in self.migrations if m.name() not in self.applied_migrations]

    def get_applied_migrations(self) -> List[Type[Migration]]:
        """
        Get list of applied migrations.

        Returns:
            List of Migration instances
        """
        return [m for m in self.migrations if m.name() in self.applied_migrations]

    def _rebuild_state(self) -> None:
        """Build the state from applied migrations."""
        self.migration_state = State(self.app_name)

        for migration in self.migrations:
            for operation in migration.operations:
                self.migration_state.apply_operation(operation)
            self.migration_state.snapshot(migration.name())

        self.applied_state = State(self.app_name)
        for migration in self.get_applied_migrations():
            for operation in migration.operations:
                self.applied_state.apply_operation(operation)
            self.applied_state.snapshot(migration.name())


def load_migrations_from_disk(migrations_dir: Path) -> List[Type[Migration]]:
    """Load migrations from the migrations directory."""
    # Ensure the app-specific migrations directory exists
    if not migrations_dir.exists():
        migrations_dir.mkdir(parents=True, exist_ok=True)
        return []

    # Get all Python files and sort them by name for idempotency
    migration_files = sorted(migrations_dir.glob("*.py"))

    loaded_migrations = []
    for file_path in migration_files:
        if file_path.name.startswith("__"):
            continue

        migration_name = file_path.stem

        # Create module path with app name included
        module_path = f"{str(migrations_dir).replace('/', '.').replace('\\', '.')}.{migration_name}"

        try:
            module = importlib.import_module(module_path)

            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, Migration) and obj is not Migration:
                    loaded_migrations.append(obj)
                    break
        except (ImportError, AttributeError) as e:
            print(f"Error loading migration {migration_name}: {e}")

    return loaded_migrations


def sort_migrations(migrations: List[Type[Migration]]) -> List[Type[Migration]]:
    """Sort migrations based on dependencies."""
    root = None
    # for traversing the dependency graph from the root to the leaves
    reverse_dependency_graph: Dict[str, List[Type[Migration]]] = defaultdict(list)

    for migration in migrations:
        for dependency in migration.dependencies:
            reverse_dependency_graph[dependency].append(migration)

        if not migration.dependencies:
            if root:
                raise ValueError(
                    f"Multiple root migrations found: {root.name()} and {migration.name()}"
                )
            root = migration

    if migrations and root is None:
        raise ValueError("No root migration found")

    sorted_migrations = []
    if root is None:
        return sorted_migrations

    visited: Dict[str, int] = defaultdict(int)
    stack: List[Type[Migration]] = [root]

    while stack:
        migration = stack.pop()
        visited[migration.name()] += 1

        if visited[migration.name()] < len(migration.dependencies):
            # wait for other branches before proceeding further
            continue

        if migration != root and visited[migration.name()] > len(migration.dependencies):
            raise ValueError(f"Circular dependency detected to {migration.name()}")

        sorted_migrations.append(migration)

        for next_node in reverse_dependency_graph[migration.name()]:
            stack.append(next_node)

    if len(sorted_migrations) != len(migrations):
        raise ValueError(f"Circular dependency detected to {migration.name()}")

    return sorted_migrations
