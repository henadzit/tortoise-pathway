from pathlib import Path
from typing import List

from tortoise_pathway.schema_change import SchemaChange


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

    async def apply(self) -> None:
        """Apply the migration forward."""
        if self.operations:
            for operation in self.operations:
                await operation.apply()
        else:
            raise NotImplementedError("Subclasses must implement this method or define operations")

    async def revert(self) -> None:
        """Revert the migration."""
        if self.operations:
            # Revert operations in reverse order
            for operation in reversed(self.operations):
                await operation.revert()
        else:
            raise NotImplementedError("Subclasses must implement this method or define operations")
