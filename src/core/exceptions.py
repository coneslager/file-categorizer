"""Custom exceptions for the File Categorizer System."""


class FileCategorizeError(Exception):
    """Base exception for file categorization errors."""
    pass


class FileSystemError(FileCategorizeError):
    """Exception for file system related errors."""
    pass


class DatabaseError(FileCategorizeError):
    """Exception for database related errors."""
    pass


class ScanError(FileCategorizeError):
    """Exception for scanning operation errors."""
    pass


class ValidationError(FileCategorizeError):
    """Exception for data validation errors."""
    pass


class ConfigurationError(FileCategorizeError):
    """Exception for configuration related errors."""
    pass


class PermissionError(FileSystemError):
    """Exception for file permission errors."""
    pass


class PathNotFoundError(FileSystemError):
    """Exception for path not found errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Exception for database connection errors."""
    pass


class DatabaseCorruptionError(DatabaseError):
    """Exception for database corruption errors."""
    pass


class ScanCancelledError(ScanError):
    """Exception for cancelled scan operations."""
    pass


class RetryableError(FileCategorizeError):
    """Base class for errors that can be retried."""
    
    def __init__(self, message, retry_count=0, max_retries=3):
        super().__init__(message)
        self.retry_count = retry_count
        self.max_retries = max_retries
    
    @property
    def can_retry(self):
        """Check if this error can be retried."""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """Increment retry count."""
        self.retry_count += 1
        return self


class RetryableDatabaseError(DatabaseError, RetryableError):
    """Database error that can be retried."""
    pass


class RetryableFileSystemError(FileSystemError, RetryableError):
    """File system error that can be retried."""
    pass