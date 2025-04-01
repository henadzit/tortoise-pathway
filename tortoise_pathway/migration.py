from pathlib import Path
from typing import List

from tortoise_pathway.schema_change import SchemaChange
from tortoise_pathway.state import State


class Migration:
    """Base class for all migrations."""

    dependencies: List[str] = []
    operations: List[SchemaChange] = []

    def name(self) -> str:
        """
        Return the name of the migration based on its module location.

        The name is extracted from the module name where this migration class is defined.
        """
        module = self.__class__.__module__
        # Get the filename which is the last part of the module path
        return module.split(".")[-1]

    def path(self) -> Path:
        """
        Return the path to the migration file relative to the current working directory.

        Uses the module information to determine the file location.
        """
        module = self.__class__.__module__
        module_path = module.replace(".", "/")
        return Path(f"{module_path}.py")

    async def apply(self, state: State) -> None:
        """
        Apply the migration forward.

        Args:
            state: State object that contains schema information.
        """
        if self.operations:
            for operation in self.operations:
                await operation.apply(state=state)
        else:
            raise NotImplementedError("Subclasses must implement this method or define operations")

    async def revert(self, state: State) -> None:
        """
        Revert the migration.

        Args:
            state: State object that contains schema information.
        """
        if self.operations:
            # Revert operations in reverse order
            for operation in reversed(self.operations):
                await operation.revert(state=state)
        else:
            raise NotImplementedError("Subclasses must implement this method or define operations")
