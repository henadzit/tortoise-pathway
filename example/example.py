"""
Example script demonstrating Tortoise Pathway usage.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the parent directory to sys.path so we can import our package
sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise_pathway.integrator import TortoisePathwayIntegrator, setup_and_migrate
from myapp.config import TORTOISE_ORM


async def example_programmatic_usage():
    """Example of using Tortoise Pathway programmatically."""
    print("\n--- Example of programmatic usage ---")

    # Create an integrator instance
    integrator = TortoisePathwayIntegrator(TORTOISE_ORM, migrations_dir="migrations")

    try:
        # Initialize the integrator
        await integrator.initialize()

        # Get migration status
        status = await integrator.get_migration_status()

        print("\nMigration status:")
        for app_name, app_status in status.items():
            print(f"\nApp: {app_name}")
            print("Applied migrations:")
            if app_status["applied"]:
                for migration in app_status["applied"]:
                    print(f"  - {migration}")
            else:
                print("  (none)")

            print("Pending migrations:")
            if app_status["pending"]:
                for migration in app_status["pending"]:
                    print(f"  - {migration}")
            else:
                print("  (none)")

        # Apply migrations
        print("\nApplying migrations...")
        results = await integrator.migrate()

        for app_name, applied in results.items():
            if applied:
                print(f"Applied {len(applied)} migration(s) for {app_name}:")
                for migration in applied:
                    print(f"  - {migration}")
            else:
                print(f"No migrations applied for {app_name}.")

    finally:
        # Close the integrator
        await integrator.close()


async def example_helper_function():
    """Example of using the helper function."""
    print("\n--- Example of helper function usage ---")

    # Use the helper function to set up and apply migrations
    await setup_and_migrate(TORTOISE_ORM, migrations_dir="migrations")


async def main():
    """Main entry point."""
    # First, let's use the programmatic approach
    await example_programmatic_usage()

    # Then, let's use the helper function
    await example_helper_function()

    print("\nYou can also use the command-line interface:")
    print("python -m tortoise_pathway makemigrations --config=myapp.config --app=models")
    print("python -m tortoise_pathway migrate --config=myapp.config --app=models")
    print("python -m tortoise_pathway showmigrations --config=myapp.config --app=models")
    print("python -m tortoise_pathway rollback --config=myapp.config --app=models")


if __name__ == "__main__":
    # Make sure we're in the example directory
    os.chdir(Path(__file__).parent)

    # Run the example
    asyncio.run(main())
