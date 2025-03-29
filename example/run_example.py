#!/usr/bin/env python3
"""
Simple script to run the Tortoise Pathway example.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from example.example import main


if __name__ == "__main__":
    # Change to the example directory
    os.chdir(Path(__file__).parent)

    # Run the example
    asyncio.run(main())

    print("\nExample completed successfully!")
    print("You can now explore the generated migrations in the 'migrations' directory.")
    print("\nYou can also try changing the models.py file and running the example again")
    print("to see how schema changes are detected and new migrations are generated.")
