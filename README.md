# Tortoise Pathway

Tortoise Pathway is a migration system for Tortoise ORM, inspired by Django's migration approach.

## Features

- Generate schema migrations from Tortoise models
- Apply and revert migrations
- Class-based migration operations

## Key Concepts

### Schema Change Classes

Schema changes are represented by subclasses of the `SchemaChange` base class. Common operations include:

- `CreateModel`: Create new database tables
- `DropModel`: Remove existing tables
- `RenameModel`: Rename tables
- `AddField`: Add new columns
- `DropField`: Remove columns
- `AlterField`: Modify column properties
- `RenameField`: Rename columns
- `AddIndex`: Add indexes
- `DropIndex`: Remove indexes
- `AddConstraint`: Add constraints
- `DropConstraint`: Remove constraints

Each of these classes has methods to:
- Generate SQL for the operation
- Apply changes directly to the database
- Revert changes
- Generate migration code

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
python -m tortoise_pathway rollback --app myapp --migration 20230101000000_migration_name
```

## Installation

You can install the package using pip:

```bash
pip install tortoise-pathway
```

Or if you prefer using uv:

```bash
uv add tortoise-pathway
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
├── migration.py               # Core migration classes
├── migration_manager.py       # Migration management and tracking
├── schema_change.py           # Schema change operation classes
├── schema_differ.py           # Schema difference detection
├── generators.py              # Code generation utilities
├── state.py                   # Database state management
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
    id = fields.IntField(primary_key=True)
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

## Example of an Auto-generated Migration

Here's an example of an auto-generated migration:

```python
"""
Auto-generated migration 20230501143025_create_user_table
"""

from tortoise_pathway.migration import Migration
from tortoise_pathway.schema_change import CreateModel
from tortoise.fields.data import CharField
from tortoise.fields.data import DatetimeField
from tortoise.fields.data import IntField


class CreateUserTableMigration(Migration):
    """
    Auto-generated migration based on model changes.
    """

    dependencies = []
    operations = [
        CreateModel(
            model="myapp.User",
            fields={
                "id": IntField(primary_key=True),
                "name": CharField(max_length=255),
                "email": CharField(max_length=255, unique=True),
                "created_at": DatetimeField(auto_now_add=True),
            },
        ),
    ]
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
