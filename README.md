# Tortoise Pathway

Tortoise Pathway is a migration system for Tortoise ORM, inspired by Django's migration approach.

## Features

- Generate schema migrations from Tortoise models
- Apply and revert migrations


## Installation

You can install the package using pip:

```bash
pip install tortoise-pathway
```

Or if you prefer using uv:

```bash
uv add tortoise-pathway
```

## Development

Running tests
```bash
uv run pytest
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
```

### Working with Migrations

Generate migrations automatically based on your models:
```
python -m tortoise_pathway make --config myapp.config.TORTOISE_ORM
```

Apply migrations:
```
python -m tortoise_pathway migrate --config myapp.config.TORTOISE_ORM
```

Revert a migration:
```
python -m tortoise_pathway rollback --config myapp.config.TORTOISE_ORM --migration <migration_name>
```

## Known Limitations

- Limited support for databases
