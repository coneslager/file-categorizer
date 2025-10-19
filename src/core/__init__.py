"""Core engine for file categorization and database operations."""

from .models import FileRecord, FileCategory, ScanOptions, SearchCriteria, ScanResult, CleanupResult
from .scanner import FileScanner
from .database import DatabaseManager

__all__ = [
    "FileRecord",
    "FileCategory", 
    "ScanOptions",
    "SearchCriteria",
    "ScanResult",
    "CleanupResult",
    "FileScanner",
    "DatabaseManager"
]