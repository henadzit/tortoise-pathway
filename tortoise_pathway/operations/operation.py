"""
Base operation for Tortoise ORM migrations.
"""

import re
from typing import TYPE_CHECKING

from tortoise import connections

from tortoise_pathway.schema import get_schema_manager
from tortoise_pathway.schema.base import BaseSchemaManager

if TYPE_CHECKING:
    from tortoise_pathway.state import State


def get_dialect(connection) -> str:
    """
    Determine the database dialect from a connection.

    Args:
        connection: The database connection.

    Returns:
        A string representing the dialect ('sqlite', 'postgres', etc.)
    """
    return connection.capabilities.dialect


class Operation:
    """Base class for all schema change operations.

    Args:
        model: Model reference in the format "{app_name}.{model_name}".
    """

    app_name: str
    model_name: str | None

    def __init__(
        self,
        model: str,
    ):
        self.model = model
        self.app_name, self.model_name = self._split_model_reference(model)

    @staticmethod
    def _split_model_reference(model_ref: str) -> tuple:
        """Split model reference into app and model name.

        Args:
            model_ref: Model reference in the format "{app_name}.{model_name}" or "{app_name}".

        Returns:
            Tuple of (app_name, model_name).
        """

        # "app.model"
        if "." in model_ref:
            app_name, _, model_name = model_ref.rpartition(".")

        # "app"
        else:
            app_name, model_name = model_ref, None

        if not app_name:
            raise ValueError(
                f"Invalid model reference: {model_ref}. Expected format: 'app' or 'app.Model'"
            )

        return app_name, model_name

    def get_table_name(self, state: "State") -> str:
        """
        Get the table name for this schema change, if applicable.

        Args:
            state: State object that contains schema information.

        Returns:
            The table name for the model.
        """

        if not self.model_name:
            raise ValueError("Operation does not have an applicable table")

        # Use the state's get_table_name method
        table_name = state.get_table_name(self.app_name, self.model_name)
        if table_name:
            return table_name

        # Fall back to Tortoise.apps if available
        try:
            from tortoise import Tortoise

            if (
                Tortoise.apps
                and self.app_name in Tortoise.apps
                and self.model_name in Tortoise.apps[self.app_name]
            ):
                model_class = Tortoise.apps[self.app_name][self.model_name]
                if hasattr(model_class, "_meta") and hasattr(
                    model_class._meta, "db_table"
                ):
                    return model_class._meta.db_table
        except (ImportError, AttributeError):
            pass

        # Last resort: Convert from model name to table name using convention
        # (typically CamelCase to snake_case)

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", self.model_name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    async def apply(self, state: "State", connection_name: str = "default") -> None:
        """
        Apply this schema change to the database.

        Args:
            state: State object that contains schema information.
            connection_name: The database connection name to use.
        """
        connection = connections.get(connection_name)
        schema_manager = get_schema_manager(get_dialect(connection))
        sql = self.forward_sql(state=state, schema_manager=schema_manager)
        await connection.execute_script(sql)

    async def revert(self, state: "State", connection_name: str = "default") -> None:
        """
        Revert this schema change from the database.

        Args:
            state: State object that contains schema information.
            connection_name: The database connection name to use.
        """
        connection = connections.get(connection_name)
        schema_manager = get_schema_manager(get_dialect(connection))
        sql = self.backward_sql(state=state, schema_manager=schema_manager)
        await connection.execute_script(sql)

    def forward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """
        Generate SQL for applying this change forward.

        Args:
            state: State object that contains schema information.
            schema_manager: Schema manager object that contains schema information.

        Returns:
            SQL string for applying the change.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def backward_sql(self, state: "State", schema_manager: BaseSchemaManager) -> str:
        """
        Generate SQL for reverting this change.

        Args:
            state: State object that contains schema information.
            dialect: SQL dialect (default: "sqlite").

        Returns:
            SQL string for reverting the change.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def to_migration(self) -> str:
        """
        Generate Python code for this schema change to be included in a migration file.

        Returns:
            String with Python code that represents this schema change operation,
            suitable for inclusion in Migration.operations list.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def __str__(self) -> str:
        return self.to_migration().replace("\n", "")
