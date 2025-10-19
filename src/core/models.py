"""Core data models and enums for the File Categorizer System."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid


class FileCategory(Enum):
    """File categories supported by the system."""
    GRAPHICS = "graphics"
    LIGHTBURN = "lightburn"
    VECTOR = "vector"

    @classmethod
    def get_extensions(cls) -> Dict[str, "FileCategory"]:
        """Get mapping of file extensions to categories."""
        return {
            # Graphics files
            ".jpg": cls.GRAPHICS,
            ".jpeg": cls.GRAPHICS,
            ".png": cls.GRAPHICS,
            ".gif": cls.GRAPHICS,
            ".bmp": cls.GRAPHICS,
            ".tiff": cls.GRAPHICS,
            ".tif": cls.GRAPHICS,
            ".webp": cls.GRAPHICS,
            ".ico": cls.GRAPHICS,
            
            # LightBurn files
            ".lbrn": cls.LIGHTBURN,
            ".lbrn2": cls.LIGHTBURN,
            
            # Vector design files
            ".ai": cls.VECTOR,
            ".svg": cls.VECTOR,
            ".eps": cls.VECTOR,
        }

    @classmethod
    def categorize_file(cls, file_path: Path) -> Optional["FileCategory"]:
        """Categorize a file based on its extension."""
        extension = file_path.suffix.lower()
        extensions_map = cls.get_extensions()
        return extensions_map.get(extension)


@dataclass
class FileRecord:
    """Represents a file record in the database."""
    id: str
    path: str
    filename: str
    category: FileCategory
    size: int
    modified_date: datetime
    scanned_date: datetime
    exists: bool = True

    @classmethod
    def create(cls, file_path: Path, category: FileCategory) -> "FileRecord":
        """Create a FileRecord from a file path."""
        stat = file_path.stat()
        return cls(
            id=str(uuid.uuid4()),
            path=str(file_path.resolve()),
            filename=file_path.name,
            category=category,
            size=stat.st_size,
            modified_date=datetime.fromtimestamp(stat.st_mtime),
            scanned_date=datetime.now(),
            exists=True
        )


@dataclass
class ScanOptions:
    """Options for directory scanning operations."""
    recursive: bool = True
    verbose: bool = False
    max_depth: Optional[int] = None
    include_hidden: bool = False


@dataclass
class SearchCriteria:
    """Criteria for searching files in the database."""
    query: Optional[str] = None
    category: Optional[FileCategory] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    modified_after: Optional[datetime] = None
    modified_before: Optional[datetime] = None
    limit: Optional[int] = None
    offset: int = 0


@dataclass
class ScanResult:
    """Result of a directory scan operation."""
    total_files: int
    categorized_files: int
    new_files: int
    updated_files: int
    errors: List[str]
    duration: float

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of the scan."""
        if self.total_files == 0:
            return 1.0
        return self.categorized_files / self.total_files


@dataclass
class CleanupResult:
    """Result of a database cleanup operation."""
    total_checked: int
    removed_count: int
    removed_files: List[str]
    errors: List[str]
    dry_run: bool = False

    @property
    def cleanup_rate(self) -> float:
        """Calculate the cleanup rate."""
        if self.total_checked == 0:
            return 0.0
        return self.removed_count / self.total_checked