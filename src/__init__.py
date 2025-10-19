"""File Categorizer System - A tool for scanning and categorizing design files."""

__version__ = "0.1.0"
__author__ = "File Categorizer Team"
__description__ = "A tool for scanning and categorizing design files"

# Import main components for programmatic access
from .core.models import FileCategory, FileRecord, ScanOptions, SearchCriteria
from .core.scanner import FileScanner
from .core.database import DatabaseManager
from .cli.main import cli

__all__ = [
    "FileCategory",
    "FileRecord", 
    "ScanOptions",
    "SearchCriteria",
    "FileScanner",
    "DatabaseManager",
    "cli"
]