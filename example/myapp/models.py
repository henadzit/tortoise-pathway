"""
Example Tortoise ORM models.
"""

from tortoise import fields, models


class User(models.Model):
    """User model example."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self):
        return f"{self.name} <{self.email}>"


class Task(models.Model):
    """Task model example."""

    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    description = fields.TextField()
    completed = fields.BooleanField(default=False)
    due_date = fields.DatetimeField(null=True)
    user = fields.ForeignKeyField("models.User", related_name="tasks")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "tasks"

    def __str__(self):
        return self.title
