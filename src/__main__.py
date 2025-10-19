"""Main entry point for the File Categorizer System.

This allows the package to be run as:
    python -m src
"""

from .cli.main import cli

if __name__ == "__main__":
    cli()