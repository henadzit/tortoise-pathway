from collections import defaultdict
import inspect
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Type, cast

from tortoise import Tortoise

from tortoise_pathway.migration import Migration
from tortoise_pathway.operations.operation import Operation
from tortoise_pathway.schema_differ import SchemaDiffer
from tortoise_pathway.state import State
from tortoise_pathway.generators import (
    generate_empty_migration,
    generate_auto_migration,
)


class MigrationManager:
    """Manages migrations for Tortoise ORM models."""

    app_names: list[str]
    base_migrations_dir: Path
    migrations: list[Type[Migration]]
    applied_migrations: set[tuple[str, str]]
    migration_state: State
    applied_state: State

    def __init__(self, app_names: list[str], migrations_dir: str = "migrations"):
        self.app_names = app_names
        if Path(migrations_dir).is_absolute():
            self.base_migrations_dir = Path(migrations_dir).relative_to(Path.cwd())
        else:
            self.base_migrations_dir = Path(migrations_dir)

        # Set the app-specific migrations directory
        self.migrations = []
        self.applied_migrations = set()
        self.migration_state = State()
        self.applied_state = State()

    def get_migrations_dir(self, app_name: str) -> Path:
        return self.base_migrations_dir / app_name

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

        await conn.execute_script(
            """
        CREATE TABLE IF NOT EXISTS tortoise_migrations (
            app VARCHAR(100) NOT NULL,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP NOT NULL
        )
        """
        )

    async def _load_applied_migrations(self, app: str = None, connection=None) -> None:
        """Load list of applied migrations from the database."""
        conn = connection or Tortoise.get_connection("default")

        where = f"WHERE app = '{app}'" if app else ""
        records = await conn.execute_query(
            f"SELECT app, name FROM tortoise_migrations {where}"
        )

        self.applied_migrations = {
            (record["app"], record["name"]) for record in records[1]
        }

    def _discover_migrations(self) -> None:
        """Discover available migrations in the migrations directory and sort them based on dependencies."""
        migrations = []
        for app_name in self.app_names:
            app_migrations = load_migrations_from_disk(
                app_name, self.get_migrations_dir(app_name)
            )
            migrations.extend(app_migrations)
        self.migrations = sort_migrations(migrations)

    async def create_migrations(
        self, name: str = None, app: str = None, auto: bool = True
    ) -> list[Type[Migration]]:
        """
        Create new migration files and return the Migration instances.  If app is specified, the migration will be created for that app only (and all its dependencies).

        Args:
            name: The descriptive name for the migration. If None, a name will be generated based on detected changes.
            app: The app to create the migration for. If None, the migration will be created for all apps.
            auto: Whether to auto-generate migration operations based on model changes

        Returns:
            A Migration instance representing the newly created migration.
            None if no changes were detected.

        Raises:
            ImportError: If the migration file couldn't be loaded or no Migration class was found
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        if auto:
            # Generate migration content based on model changes compared to existing migrations state
            differ = SchemaDiffer(self.migration_state)
            all_changes = await differ.detect_changes()

            # Calculate changes by app
            changes_by_app = defaultdict(list)
            for change in all_changes:
                changes_by_app[change.app_name].append(change)

            # No changes to selected app? (or any)
            if not (changes_by_app.get(app) if app else changes_by_app):
                return []

            if app:
                # Check dependencies for the selected app (foreign key references)
                app_dependencies = await differ.get_change_app_dependencies()

                # Update apps in order of dependencies
                apps_updated = flatten_app_dependencies(app_dependencies, app)
                if app not in apps_updated:
                    apps_updated.append(app)
            else:
                # Update all apps
                apps_updated = changes_by_app.keys()
        else:
            if not app:
                raise ValueError("No app specified for empty migration")

            changes_by_app = {app: []}
            apps_updated = [app]

        # Generate migrations for all effected apps
        new_migrations = []
        for app_name in apps_updated:
            migrations_dir = self.get_migrations_dir(app_name)

            # Make sure app migrations directory exists
            migrations_dir.mkdir(parents=True, exist_ok=True)

            changes = changes_by_app.get(app_name)
            file_name = name or (
                gen_name_from_changes(changes) if changes else "migration"
            )
            migration_name = f"{timestamp}_{file_name}"

            # Create migration file path
            migration_file = migrations_dir / f"{migration_name}.py"

            dependencies = []
            if self.migrations:
                last_migration = self.migrations[-1]
                dependencies = [(last_migration.app_name, last_migration.name())]

            if changes:
                content = generate_auto_migration(migration_name, changes, dependencies)
            else:
                content = generate_empty_migration(migration_name, dependencies)

            with open(migration_file, "w") as f:
                f.write(content)

            # Load the migration module and instantiate the migration
            try:
                migration = load_migration_file(migrations_dir / f"{migration_name}.py")
                self.migrations.append(migration)

                for operation in migration.operations:
                    self.migration_state.apply_operation(operation)
                self.migration_state.snapshot(migration_name)

                # Inject app name
                migration.app_name = app_name

                new_migrations.append(migration)

            except (ImportError, AttributeError) as e:
                print(f"Error loading migration {migration_name}: {e}")
                raise ImportError(f"Failed to load newly created migration: {e}")

        return new_migrations

    async def apply_migrations(
        self, app: str = None, connection=None
    ) -> List[Type[Migration]]:
        """
        Apply pending migrations.

        Returns:
            List of Migration instances that were applied
        """
        conn = connection or Tortoise.get_connection("default")
        applied_migrations = []

        # Get pending migrations
        pending_migrations = self.get_pending_migrations(app=app)

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
                    f"INSERT INTO tortoise_migrations (app, name, applied_at) VALUES ('{migration.app_name}', '{migration_name}', '{now}')",
                )

                self.applied_migrations.add((migration.app_name, migration_name))
                applied_migrations.append(migration)
                self.applied_state.snapshot(migration_name)
                print(f"Applied migration: {migration.display_name()}")
            except Exception as e:
                print(f"Error applying migration {migration.display_name()}: {e}")
                # Rollback transaction if supported
                raise

        return applied_migrations

    async def revert_migration(
        self,
        app: str | None = None,
        migration_name: Optional[str] = None,
        connection=None,
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
                f"SELECT app, name FROM tortoise_migrations {f'WHERE app = \'{app}\'' if app else ''} ORDER BY applied_at DESC LIMIT 1",
            )

            if not records[1]:
                print("No migrations to revert")
                return None

            record = records[1][0]
            migration_name = cast(str, record["name"])
            app = cast(str, record["app"])

        if (app, migration_name) not in set(
            [(m.app_name, m.name()) for m in self.migrations]
        ):
            raise ValueError(f"Migration {app} -> {migration_name} not found")

        if (app, migration_name) not in self.applied_migrations:
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
                [app, migration_name],
            )

            self.applied_migrations.remove((app, migration_name))

            # Rebuild state from remaining applied migrations
            self.applied_state = self.applied_state.prev()

            print(f"Reverted migration: {migration_name}")
            return migration

        except Exception as e:
            print(f"Error reverting migration {migration_name}: {e}")
            # Rollback transaction if supported
            raise

    def get_pending_migrations(self, app: str = None) -> list[Type[Migration]]:
        """
        Get list of pending migrations.

        Returns:
            List of Migration instances
        """
        return [
            m
            for m in self.migrations
            if (m.app_name, m.name()) not in self.applied_migrations
            if app is None or m.app_name == app
        ]

    def get_applied_migrations(self, app: str = None) -> list[Type[Migration]]:
        """
        Get list of applied migrations.

        Returns:
            List of Migration instances
        """
        return [
            m
            for m in self.migrations
            if (m.app_name, m.name()) in self.applied_migrations
            if app is None or m.app_name == app
        ]

    def _rebuild_state(self) -> None:
        """Build the state from applied migrations."""
        self.migration_state = State()

        for migration in self.migrations:
            for operation in migration.operations:
                self.migration_state.apply_operation(operation)
            self.migration_state.snapshot(migration.name())

        self.applied_state = State()
        for migration in self.get_applied_migrations():
            for operation in migration.operations:
                self.applied_state.apply_operation(operation)
            self.applied_state.snapshot(migration.name())


def gen_name_from_changes(changes: List[Operation]) -> str:
    models_changed = set()
    fields_changed = defaultdict(set)
    field_ops_only = True

    for change in changes:
        model_name = getattr(change, "model_name", None)
        if model_name:
            models_changed.add(model_name)

            field_name = getattr(change, "field_name", None)
            if field_name:
                fields_changed[model_name].add(field_name)
            else:
                field_ops_only = False

    name = "auto"
    if len(models_changed) > 1:
        name = "auto"
    elif len(models_changed) == 1:
        model_name = next(iter(models_changed))
        if len(fields_changed[model_name]) > 1:
            name = model_name.lower()
        elif len(fields_changed[model_name]) == 1 and field_ops_only:
            field_name = next(iter(fields_changed[model_name]))
            name = f"{model_name.lower()}_{field_name}"
        else:
            name = model_name.lower()
    return name


def load_migrations_from_disk(
    app_name: str, migrations_dir: Path
) -> List[Type[Migration]]:
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

        try:
            migration = load_migration_file(file_path)

            # Set app_name for operations where the app_name is hard to determine,
            # for instance, RunSQL operations.
            for operation in migration.operations:
                if not operation.app_name:
                    operation.app_name = app_name

            # Inject app_name for the migration class
            migration.app_name = app_name

            loaded_migrations.append(migration)

        except (ImportError, AttributeError) as e:
            print(f"Error loading migration {migration_name}: {e}")

    return loaded_migrations


def sort_migrations(migrations: list[Type[Migration]]) -> list[Type[Migration]]:
    """Sort migrations based on dependencies."""
    root = None
    # for traversing the dependency graph from the root to the leaves
    reverse_dependency_graph: dict[tuple[str, str], list[Type[Migration]]] = (
        defaultdict(list)
    )

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
        migration_key = (migration.app_name, migration.name())
        visited[migration_key] += 1

        if visited[migration_key] < len(migration.dependencies):
            # wait for other branches before proceeding further
            continue

        if migration != root and visited[migration_key] > len(migration.dependencies):
            raise ValueError(f"Circular dependency detected to {migration_key}")

        sorted_migrations.append(migration)

        for next_node in reverse_dependency_graph[migration_key]:
            stack.append(next_node)

    if len(sorted_migrations) != len(migrations):
        raise ValueError(
            f"Circular dependency detected to {migration.app_name} {migration.name()}"
        )

    return sorted_migrations


def load_migration_file(migration_path: Path) -> Type[Migration]:
    """Load a migration file."""
    path_without_ext = migration_path.with_suffix("")
    module_path = f"{str(path_without_ext).replace('/', '.').replace('\\', '.')}"
    module = __import__(module_path, globals(), locals(), [], 0)

    # Dig into the module to find the Migration class
    for path in module_path.split(".")[1:]:
        module = getattr(module, path)

    for _name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and issubclass(obj, Migration) and obj is not Migration:
            return obj
    raise ImportError(f"No Migration class found in the module {module_path}")


def flatten_app_dependencies(
    app_dependencies: dict[str, list[str]],
    app_name: str,
    already_checked: set[str] | None = None,
) -> list[str]:
    """Builds a list of all app dependencies for a given app"""
    if already_checked is None:
        already_checked = set()

    dependencies = []
    for _app_name in app_dependencies[app_name]:
        if _app_name not in already_checked:
            already_checked.add(_app_name)
            additional_dependencies = flatten_app_dependencies(
                app_dependencies, _app_name, already_checked
            )
            dependencies.extend(additional_dependencies)
            if _app_name not in dependencies:
                dependencies.append(_app_name)

    return dependencies
