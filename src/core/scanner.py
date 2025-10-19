"""File system scanner for the File Categorizer System."""

import time
import logging
from pathlib import Path
from typing import Iterator, Optional, Callable, List
from .models import FileRecord, FileCategory, ScanOptions, ScanResult
from .exceptions import (
    FileSystemError, ScanError, PermissionError, PathNotFoundError,
    ScanCancelledError
)
from .error_handler import ErrorHandler, safe_path_operation, retry_on_error


class FileScanner:
    """Handles file system scanning and categorization."""

    def __init__(self, progress_callback: Optional[Callable[[int, int], None]] = None, config=None):
        """
        Initialize the file scanner.
        
        Args:
            progress_callback: Optional callback function for progress reporting.
                               Called with (current_count, total_count) parameters.
            config: Optional configuration object
        """
        # Import here to avoid circular imports
        from .config import get_config
        
        self.progress_callback = progress_callback
        self.config = config or get_config()
        self.error_handler = ErrorHandler()
        self.logger = logging.getLogger(__name__)
        self._cancelled = False

    def scan_directory(self, path: Path, options: ScanOptions) -> ScanResult:
        """
        Scan a directory for categorizable files.
        
        Args:
            path: Directory path to scan
            options: Scanning options
            
        Returns:
            ScanResult with operation details
        """
        start_time = time.time()
        total_files = 0
        categorized_files = 0
        new_files = 0
        updated_files = 0
        errors = []
        
        try:
            # Validate input path with proper error handling
            self._validate_scan_path(path)
            
            # Reset cancellation flag
            self._cancelled = False
            
            # Scan files and collect results
            for file_record in self.scan_files(path, options):
                if self._cancelled:
                    raise ScanCancelledError("Scan was cancelled by user")
                
                if file_record:
                    categorized_files += 1
                    new_files += 1  # For now, treat all as new (database integration in later tasks)
                total_files += 1
                
                # Report progress if callback is provided
                if self.progress_callback:
                    try:
                        self.progress_callback(total_files, total_files)
                    except Exception as e:
                        self.logger.warning(f"Progress callback error: {e}")
                        
        except ScanCancelledError:
            errors.append("Scan was cancelled by user")
            self.logger.info("Scan cancelled by user")
        except (FileSystemError, PermissionError, PathNotFoundError) as e:
            errors.append(str(e))
            self.logger.error(f"File system error during scan: {e}")
        except Exception as e:
            error_msg = f"Unexpected scan error: {str(e)}"
            errors.append(error_msg)
            self.logger.error(error_msg)
            self.error_handler.handle_scan_error(e, f"scanning {path}")
        
        duration = time.time() - start_time
        
        # Log error summary if there were errors
        if errors:
            self.error_handler.log_error_summary([Exception(err) for err in errors], "directory scan")
        
        return ScanResult(total_files, categorized_files, new_files, updated_files, errors, duration)

    def categorize_file(self, file_path: Path) -> Optional[FileCategory]:
        """
        Categorize a file based on its extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileCategory if file can be categorized, None otherwise
        """
        # Implementation will be added in task 2.1
        return FileCategory.categorize_file(file_path)

    @safe_path_operation
    def get_file_metadata(self, file_path: Path) -> Optional[FileRecord]:
        """
        Extract metadata from a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileRecord if file exists and can be categorized, None otherwise
        """
        try:
            # Check if file exists
            if not file_path.exists() or not file_path.is_file():
                return None
            
            # Categorize the file
            category = self.categorize_file(file_path)
            if category is None:
                return None
            
            # Create and return FileRecord with metadata
            return FileRecord.create(file_path, category)
            
        except (OSError, IOError, PermissionError) as e:
            # Handle file system errors gracefully
            self.error_handler.handle_file_system_error(e, file_path)
            return None
        except Exception as e:
            self.logger.warning(f"Unexpected error getting metadata for {file_path}: {e}")
            return None

    def scan_files(self, path: Path, options: ScanOptions) -> Iterator[FileRecord]:
        """
        Generator that yields FileRecord objects for categorizable files.
        
        Args:
            path: Directory path to scan
            options: Scanning options
            
        Yields:
            FileRecord objects for each categorizable file found
        """
        scan_errors = []
        
        try:
            # Determine scanning pattern based on options
            if options.recursive:
                pattern = "**/*"
            else:
                pattern = "*"
            
            # Scan directory using pathlib with error handling
            try:
                items = list(path.glob(pattern))
            except (OSError, PermissionError) as e:
                self.logger.error(f"Error accessing directory {path}: {e}")
                self.error_handler.handle_file_system_error(e, path)
                return
            
            for item in items:
                # Check for cancellation
                if self._cancelled:
                    self.logger.info("Scan cancelled, stopping file iteration")
                    return
                
                try:
                    # Skip if not a file
                    if not item.is_file():
                        continue
                    
                    # Skip hidden files unless explicitly included
                    if not options.include_hidden and item.name.startswith('.'):
                        continue
                    
                    # Check depth limit if specified
                    if options.max_depth is not None:
                        try:
                            relative_path = item.relative_to(path)
                            depth = len(relative_path.parts) - 1
                            if depth > options.max_depth:
                                continue
                        except ValueError:
                            # Item is not relative to path, skip it
                            continue
                    
                    # Get file metadata and categorization
                    file_record = self.get_file_metadata(item)
                    if file_record:
                        yield file_record
                        
                except (OSError, PermissionError) as e:
                    # Handle file access errors gracefully
                    error_msg = f"Could not access {item}: {e}"
                    scan_errors.append(error_msg)
                    
                    if options.verbose:
                        self.logger.warning(error_msg)
                    
                    # Don't let individual file errors stop the entire scan
                    continue
                    
                except Exception as e:
                    # Handle unexpected errors for individual files
                    error_msg = f"Unexpected error processing {item}: {e}"
                    scan_errors.append(error_msg)
                    self.logger.warning(error_msg)
                    continue
                    
        except KeyboardInterrupt:
            self.logger.info("Scan interrupted by user")
            self._cancelled = True
            raise ScanCancelledError("Scan cancelled by user")
        except Exception as e:
            # Handle any unexpected errors during scanning
            error_msg = f"Error during directory scan: {e}"
            self.logger.error(error_msg)
            self.error_handler.handle_scan_error(e, f"scanning {path}")
            return
        
        # Log summary of scan errors if any occurred
        if scan_errors:
            self.logger.warning(f"Scan completed with {len(scan_errors)} file access errors")
            if options.verbose:
                for error in scan_errors[:10]:  # Log first 10 errors
                    self.logger.warning(f"  {error}")
                if len(scan_errors) > 10:
                    self.logger.warning(f"  ... and {len(scan_errors) - 10} more errors")
    
    def cancel_scan(self):
        """Cancel the current scan operation."""
        self._cancelled = True
        self.logger.info("Scan cancellation requested")
    
    def _validate_scan_path(self, path: Path):
        """
        Validate that the scan path is accessible and is a directory.
        
        Args:
            path: Path to validate
            
        Raises:
            PathNotFoundError: If path doesn't exist
            FileSystemError: If path is not a directory or not accessible
        """
        try:
            if not path.exists():
                raise PathNotFoundError(f"Path does not exist: {path}")
            
            if not path.is_dir():
                raise FileSystemError(f"Path is not a directory: {path}")
            
            # Test if we can read the directory
            try:
                next(path.iterdir(), None)
            except PermissionError:
                raise PermissionError(f"Permission denied accessing directory: {path}")
            except OSError as e:
                raise FileSystemError(f"Cannot access directory {path}: {e}")
                
        except (OSError, IOError) as e:
            self.error_handler.handle_file_system_error(e, path)