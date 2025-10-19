"""Error handling utilities and retry logic for the File Categorizer System."""

import time
import logging
import sqlite3
from pathlib import Path
from typing import Callable, Any, Optional, Type, Union, List
from functools import wraps

from .exceptions import (
    FileCategorizeError, FileSystemError, DatabaseError, ScanError,
    RetryableError, RetryableDatabaseError, RetryableFileSystemError,
    DatabaseConnectionError, DatabaseCorruptionError, PermissionError,
    PathNotFoundError
)


logger = logging.getLogger(__name__)


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (RetryableError,)
):
    """
    Decorator to retry function calls on specific exceptions.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry
        exceptions: Tuple of exception types to retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise e
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    
                    if hasattr(e, 'increment_retry'):
                        e.increment_retry()
                    
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
                except Exception as e:
                    # Non-retryable exception, re-raise immediately
                    logger.error(f"Function {func.__name__} failed with non-retryable error: {e}")
                    raise e
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


class ErrorHandler:
    """Centralized error handling and recovery logic."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize error handler.
        
        Args:
            logger: Logger instance to use for error reporting
        """
        self.logger = logger or logging.getLogger(__name__)
        self.error_counts = {}
        self.recovery_strategies = {}
    
    def handle_file_system_error(self, error: Exception, file_path: Union[str, Path]) -> Optional[Any]:
        """
        Handle file system errors with appropriate recovery strategies.
        
        Args:
            error: The exception that occurred
            file_path: Path where the error occurred
            
        Returns:
            Recovery result if successful, None otherwise
        """
        file_path = Path(file_path) if isinstance(file_path, str) else file_path
        
        if isinstance(error, (OSError, IOError)):
            if error.errno == 13:  # Permission denied
                self.logger.warning(f"Permission denied accessing {file_path}: {error}")
                raise PermissionError(f"Permission denied: {file_path}")
            elif error.errno == 2:  # No such file or directory
                self.logger.warning(f"File not found: {file_path}")
                raise PathNotFoundError(f"Path not found: {file_path}")
            elif error.errno == 28:  # No space left on device
                self.logger.error(f"No space left on device: {error}")
                raise FileSystemError(f"No space left on device")
            else:
                self.logger.error(f"File system error accessing {file_path}: {error}")
                raise RetryableFileSystemError(f"File system error: {error}")
        
        elif isinstance(error, PermissionError):
            self.logger.warning(f"Permission error accessing {file_path}: {error}")
            raise PermissionError(f"Permission denied: {file_path}")
        
        else:
            self.logger.error(f"Unexpected file system error: {error}")
            raise FileSystemError(f"Unexpected file system error: {error}")
    
    def handle_database_error(self, error: Exception, operation: str = "unknown") -> Optional[Any]:
        """
        Handle database errors with appropriate recovery strategies.
        
        Args:
            error: The database exception that occurred
            operation: Description of the operation that failed
            
        Returns:
            Recovery result if successful, None otherwise
        """
        if isinstance(error, sqlite3.OperationalError):
            error_msg = str(error).lower()
            
            if "database is locked" in error_msg:
                self.logger.warning(f"Database locked during {operation}, will retry")
                raise RetryableDatabaseError(f"Database locked during {operation}")
            
            elif "no such table" in error_msg:
                self.logger.error(f"Database schema error during {operation}: {error}")
                raise DatabaseError(f"Database schema error: {error}")
            
            elif "disk i/o error" in error_msg:
                self.logger.error(f"Database I/O error during {operation}: {error}")
                raise RetryableDatabaseError(f"Database I/O error: {error}")
            
            elif "database disk image is malformed" in error_msg:
                self.logger.error(f"Database corruption detected during {operation}")
                raise DatabaseCorruptionError(f"Database corruption detected")
            
            else:
                self.logger.error(f"Database operational error during {operation}: {error}")
                raise RetryableDatabaseError(f"Database error: {error}")
        
        elif isinstance(error, sqlite3.IntegrityError):
            self.logger.warning(f"Database integrity error during {operation}: {error}")
            # Integrity errors are usually not retryable (constraint violations, etc.)
            raise DatabaseError(f"Database integrity error: {error}")
        
        elif isinstance(error, sqlite3.DatabaseError):
            self.logger.error(f"Database error during {operation}: {error}")
            raise DatabaseError(f"Database error: {error}")
        
        else:
            self.logger.error(f"Unexpected database error during {operation}: {error}")
            raise DatabaseError(f"Unexpected database error: {error}")
    
    def handle_scan_error(self, error: Exception, context: str = "") -> Optional[Any]:
        """
        Handle scan operation errors.
        
        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
            
        Returns:
            Recovery result if successful, None otherwise
        """
        context_msg = f" in {context}" if context else ""
        
        if isinstance(error, (FileSystemError, PermissionError)):
            # File system errors during scan - log and continue
            self.logger.warning(f"File system error during scan{context_msg}: {error}")
            return None  # Continue scanning other files
        
        elif isinstance(error, DatabaseError):
            # Database errors during scan - may need to retry or abort
            self.logger.error(f"Database error during scan{context_msg}: {error}")
            raise error  # Re-raise to handle at higher level
        
        elif isinstance(error, KeyboardInterrupt):
            self.logger.info(f"Scan cancelled by user{context_msg}")
            raise ScanError("Scan cancelled by user")
        
        else:
            self.logger.error(f"Unexpected error during scan{context_msg}: {error}")
            raise ScanError(f"Scan error: {error}")
    
    def safe_execute(self, func: Callable, *args, **kwargs) -> tuple[bool, Any, Optional[Exception]]:
        """
        Safely execute a function and return success status, result, and any exception.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Tuple of (success, result, exception)
        """
        try:
            result = func(*args, **kwargs)
            return True, result, None
        except Exception as e:
            self.logger.error(f"Error executing {func.__name__}: {e}")
            return False, None, e
    
    def log_error_summary(self, errors: List[Exception], operation: str = "operation"):
        """
        Log a summary of errors that occurred during an operation.
        
        Args:
            errors: List of exceptions that occurred
            operation: Description of the operation
        """
        if not errors:
            return
        
        error_counts = {}
        for error in errors:
            error_type = type(error).__name__
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        self.logger.warning(f"Error summary for {operation}:")
        for error_type, count in error_counts.items():
            self.logger.warning(f"  {error_type}: {count} occurrences")
        
        # Log first few unique error messages
        unique_messages = set()
        for error in errors[:10]:  # Limit to first 10 errors
            message = str(error)
            if message not in unique_messages:
                unique_messages.add(message)
                self.logger.warning(f"  Example: {message}")


def safe_path_operation(func: Callable) -> Callable:
    """
    Decorator to safely handle path operations with proper error handling.
    
    Args:
        func: Function that performs path operations
        
    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        error_handler = ErrorHandler()
        
        try:
            return func(*args, **kwargs)
        except (OSError, IOError, PermissionError) as e:
            # Extract file path from args if possible
            file_path = None
            for arg in args:
                if isinstance(arg, (str, Path)):
                    file_path = arg
                    break
            
            return error_handler.handle_file_system_error(e, file_path or "unknown")
        except Exception as e:
            logger.error(f"Unexpected error in path operation {func.__name__}: {e}")
            raise e
    
    return wrapper


def safe_database_operation(operation_name: str = "database operation"):
    """
    Decorator to safely handle database operations with proper error handling.
    
    Args:
        operation_name: Name of the database operation for logging
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = ErrorHandler()
            
            try:
                return func(*args, **kwargs)
            except (sqlite3.Error, DatabaseError) as e:
                return error_handler.handle_database_error(e, operation_name)
            except Exception as e:
                logger.error(f"Unexpected error in database operation {func.__name__}: {e}")
                raise DatabaseError(f"Unexpected database error: {e}")
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for handling repeated failures.
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise FileCategorizeError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful function call."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """Handle failed function call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"