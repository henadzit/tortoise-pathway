# Tortoise Pathway

Tortoise Pathway is a migration system for Tortoise ORM, inspired by Django's migration approach.

## Features

- Generate schema migrations automatically
- Apply and revert migrations
- Class-based migration operations
- Direct database interaction without SQL generation
- Field dictionary-based table creation

## Key Concepts

### Schema Change Classes

Schema changes are represented by subclasses of the `SchemaChange` base class. Common operations include:

- `CreateTable`: Create new database tables
- `DropTable`: Remove existing tables
- `RenameTable`: Rename tables
- `AddColumn`: Add new columns
- `DropColumn`: Remove columns
- `AlterColumn`: Modify column properties
- `RenameColumn`: Rename columns
- `AddIndex`: Add indexes
- `DropIndex`: Remove indexes
- `AddConstraint`: Add constraints
- `DropConstraint`: Remove constraints

Each of these classes has methods to:
- Generate SQL for the operation
- Apply changes directly to the database
- Revert changes
- Generate migration code

### Creating Tables with Field Dictionaries

Tables are created using a dictionary of field definitions. This provides flexibility and explicit control over field definitions.

Example:

```python
from tortoise.fields import CharField, IntField, BooleanField
from tortoise_pathway.schema_diff import CreateTable

# Create a fields dictionary for a table
fields = {
    "id": IntField(pk=True),
    "name": CharField(max_length=100, null=False),
    "is_active": BooleanField(default=True),
}

# Create the table using the fields dictionary (required parameter)
change = CreateTable(
    table_name="my_table",
    fields=fields,
)

# Apply the change to create the table
await change.apply()
```

This approach provides:
- Explicit field definitions for better control
- More dynamic schema management
- No dependency on model classes

## Migration System

The migration system manages:

1. Detecting schema changes between models and database
2. Generating migration files with operations
3. Applying and reverting migrations
4. Tracking migration history

### Working with Migrations

Generate a migration:
```
python -m tortoise_pathway makemigrations --app myapp
```

Apply migrations:
```
python -m tortoise_pathway migrate --app myapp
```

Revert a migration:
```
python -m tortoise_pathway migrate --app myapp --reverse 20230101000000_migration_name
```

## Usage Examples

See the `examples/` directory for usage examples:
- `use_fields_dict.py`: Demonstrates creating tables with field dictionaries

## Installation

You can install the package using pip:

```bash
pip install tortoise-pathway
```

Or if you prefer using uv:

```bash
uv pip install tortoise-pathway
```

### Development Installation

For development, install the package in editable mode:

```bash
# Using pip
pip install -e .

# Or using uv
uv pip install -e .
```

To include development and test dependencies:

```bash
# Using pip
pip install -e ".[dev,test]"

# Or using uv
uv pip install -e ".[dev,test]"
```

## Project Structure

```
tortoise_pathway/
├── __init__.py                # Package initialization
├── __main__.py                # Entry point for CLI
├── migration.py               # Core migration classes and manager
├── schema_diff.py             # Schema difference detection
└── cli.py                     # Command-line interface
```

## Usage

### Configuration

Create a configuration module with a `TORTOISE_ORM` dictionary. For example, in `config.py`:

```python
TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.sqlite",
            "credentials": {
                "file_path": "db.sqlite3",
            },
        },
    },
    "apps": {
        "models": {
            "models": ["myapp.models"],
            "default_connection": "default",
        },
    },
    "use_tz": False,
}
```

### Defining Models

Define your Tortoise ORM models as usual:

```python
# myapp/models.py
from tortoise import fields, models

class User(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"
```

### Using the Command Line Interface

The CLI commands follow this structure:

```bash
python -m tortoise_pathway --config CONFIG_MODULE COMMAND [OPTIONS]
```

Where:
- `CONFIG_MODULE` is the Python import path to your configuration module
- `COMMAND` is one of `makemigrations`, `migrate`, `rollback`, or `showmigrations`

Make sure that your config module can be imported from where you run the command.

#### Creating Migrations

To create a migration based on model changes:

```bash
python -m tortoise_pathway --config myapp.config makemigrations --app models
```

This will create a migration file in the `migrations/models/` directory.

#### Applying Migrations

To apply pending migrations:

```bash
python -m tortoise_pathway --config myapp.config migrate --app models
```

#### Reverting Migrations

To revert the most recent migration:

```bash
python -m tortoise_pathway --config myapp.config rollback --app models
```

#### Viewing Migration Status

To see the status of migrations:

```bash
python -m tortoise_pathway --config myapp.config showmigrations --app models
```

### Helper Function

For simple cases, you can use the helper function:

```python
import asyncio
from tortoise_pathway.integrator import setup_and_migrate

from myapp.config import TORTOISE_ORM

if __name__ == "__main__":
    asyncio.run(setup_and_migrate(TORTOISE_ORM))
```

## Example Application

An example application is included in the `example/` directory:

```
example/
├── run_example.py             # Script to run the example
├── example.py                 # Example code demonstrating usage
└── myapp/                     # Example Tortoise app
    ├── __init__.py
    ├── config.py              # Tortoise ORM config
    └── models.py              # Example models
```

To run the example:

```bash
cd /path/to/tortoise-pathway
python example/run_example.py
```

The example script automatically adds the necessary paths to import the package.

## Troubleshooting

### Module Not Found

If you encounter "No module named tortoise_pathway", ensure that:

1. You've installed the package (`pip install -e .`)
2. You're running the command from a directory where Python can find your modules
3. If using a relative import path, make sure the directory structure is correct

### Import Errors

If you see "Cannot import tortoise", make sure you have Tortoise ORM installed:

```bash
pip install tortoise-orm>=0.24.2
```

## Example of an Auto-generated Migration

Here's an example of an auto-generated migration:

```python
"""
Auto-generated migration 20230501143025_create_user_table
"""

from tortoise_pathway.migration import Migration
from tortoise import connections


class CreateUserTableMigration(Migration):
    """
    Auto-generated migration based on model changes.
    """

    dependencies = []

    async def apply(self) -> None:
        """Apply the migration forward."""
        connection = connections.get("default")

        await connection.execute_script("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP NOT NULL
        );
        """)

    async def revert(self) -> None:
        """Revert the migration."""
        connection = connections.get("default")

        await connection.execute_script("DROP TABLE users")
```

## How It Works

1. **Schema Diff Detection**: Compares current Tortoise models with the database schema to detect changes
2. **Migration Generation**: Creates Python code to apply and revert schema changes
3. **Migration Tracking**: Stores applied migrations in a database table
4. **Migration Dependencies**: Allows migrations to depend on other migrations

## Known Limitations

- Limited support for SQLite schema alterations (due to SQLite's constraints)
- No support for data migrations yet
- Field type mapping may need adjustments for complex field types

## License

MIT
