"""
Models for testing application with no migrations.
"""

from tortoise import fields, models


class User(models.Model):
    """User model for testing."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self):
        return f"{self.name} <{self.email}>"


class Note(models.Model):
    """Note model for testing."""

    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=100)
    content = fields.TextField()
    is_active = fields.BooleanField(default=True)
    user = fields.ForeignKeyField("test_no_migrations.User", related_name="notes")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notes"

        unique_together = ("user", "title")

    def __str__(self):
        return self.title
