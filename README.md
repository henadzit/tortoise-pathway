# Tortoise Pathway

⚠️ **This project is in VERY early development and not yet ready for production use. Most things are broken and they will break again, APIs will change.**

⚠️ **Most of the code is written with Claude, there are issues with code style that are common for AI generated code.**

🤓 Code contributions ans assistance with testing is welcome and appreciated!

Tortoise Pathway is a migration system for [Tortoise ORM](https://github.com/tortoise/tortoise-orm/), inspired by Django's migration approach.

## Features

- Generate schema migrations from Tortoise models
- Apply and revert migrations
- No need for a database connection to generate migrations
- If you have used Django migrations, you will feel at home

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
python -m tortoise_pathway --config myapp.config.TORTOISE_ORM make
```

Apply migrations:
```
python -m tortoise_pathway --config myapp.config.TORTOISE_ORM migrate
```

Revert a migration:
```
python -m tortoise_pathway --config myapp.config.TORTOISE_ORM rollback --migration <migration_name>
```
