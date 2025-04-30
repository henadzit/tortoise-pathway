from tortoise.models import Model
from tortoise import fields


class MigrationDBModel(Model):
    """
    Migration database model for Tortoise ORM.
    This model is used to track applied migrations in the database.
    """

    name = fields.CharField(max_length=255, primary_key=True)
    app = fields.CharField(max_length=255)
    applied_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "tortoise_migrations"
        default_connection = "default"


__models__ = [MigrationDBModel]
