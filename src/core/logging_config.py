"""Logging configuration and utilities for the File Categorizer System."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from .config import LoggingConfig, get_config


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        """Format log record with colors."""
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class ContextFilter(logging.Filter):
    """Filter that adds context information to log records."""
    
    def __init__(self, context: Dict[str, Any] = None):
        """
        Initialize context filter.
        
        Args:
            context: Dictionary of context information to add to records
        """
        super().__init__()
        self.context = context or {}
    
    def filter(self, record):
        """Add context information to log record."""
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


class LoggingManager:
    """Manages logging configuration and setup."""
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Initialize logging manager.
        
        Args:
            config: Logging configuration. If None, uses global config.
        """
        self.config = config or get_config().logging
        self.loggers = {}
        self.handlers = {}
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """Set up the root logger with configured handlers."""
        root_logger = logging.getLogger()
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Set log level
        try:
            log_level = getattr(logging, self.config.level.upper())
            root_logger.setLevel(log_level)
        except AttributeError:
            root_logger.setLevel(logging.INFO)
            root_logger.warning(f"Invalid log level '{self.config.level}', using INFO")
        
        # Add console handler if enabled
        if self.config.console_enabled:
            console_handler = self._create_console_handler()
            root_logger.addHandler(console_handler)
            self.handlers['console'] = console_handler
        
        # Add file handler if enabled
        if self.config.file_enabled and self.config.file_path:
            file_handler = self._create_file_handler()
            if file_handler:
                root_logger.addHandler(file_handler)
                self.handlers['file'] = file_handler
    
    def _create_console_handler(self) -> logging.Handler:
        """Create and configure console handler."""
        handler = logging.StreamHandler(sys.stderr)
        
        # Use colored formatter for console
        formatter = ColoredFormatter(self.config.format)
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_file_handler(self) -> Optional[logging.Handler]:
        """Create and configure rotating file handler."""
        try:
            # Ensure log directory exists
            self.config.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create rotating file handler
            max_bytes = self.config.file_max_size_mb * 1024 * 1024
            handler = logging.handlers.RotatingFileHandler(
                self.config.file_path,
                maxBytes=max_bytes,
                backupCount=self.config.file_backup_count
            )
            
            # Use standard formatter for file
            formatter = logging.Formatter(self.config.format)
            handler.setFormatter(formatter)
            
            return handler
            
        except Exception as e:
            # If file handler creation fails, log to console
            logging.getLogger(__name__).error(f"Failed to create file handler: {e}")
            return None
    
    def get_logger(self, name: str, context: Dict[str, Any] = None) -> logging.Logger:
        """
        Get a logger with optional context.
        
        Args:
            name: Logger name
            context: Optional context information to add to log records
            
        Returns:
            Configured logger instance
        """
        if name in self.loggers:
            return self.loggers[name]
        
        logger = logging.getLogger(name)
        
        # Add context filter if provided
        if context:
            context_filter = ContextFilter(context)
            logger.addFilter(context_filter)
        
        self.loggers[name] = logger
        return logger
    
    def add_handler(self, name: str, handler: logging.Handler):
        """
        Add a custom handler to the root logger.
        
        Args:
            name: Handler name for reference
            handler: Handler instance to add
        """
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        self.handlers[name] = handler
    
    def remove_handler(self, name: str):
        """
        Remove a handler from the root logger.
        
        Args:
            name: Handler name to remove
        """
        if name in self.handlers:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.handlers[name])
            del self.handlers[name]
    
    def set_level(self, level: str):
        """
        Set the logging level for all loggers.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        try:
            log_level = getattr(logging, level.upper())
            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)
            
            # Update config
            self.config.level = level.upper()
            
        except AttributeError:
            logging.getLogger(__name__).error(f"Invalid log level: {level}")
    
    def enable_debug_logging(self):
        """Enable debug logging for development."""
        self.set_level('DEBUG')
        
        # Add more detailed formatter for debug mode
        debug_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        
        for handler in self.handlers.values():
            if isinstance(handler, logging.StreamHandler):
                handler.setFormatter(ColoredFormatter(debug_format))
            else:
                handler.setFormatter(logging.Formatter(debug_format))
    
    def create_audit_logger(self, name: str = 'audit') -> logging.Logger:
        """
        Create a separate audit logger for tracking important operations.
        
        Args:
            name: Audit logger name
            
        Returns:
            Audit logger instance
        """
        audit_logger = logging.getLogger(name)
        audit_logger.setLevel(logging.INFO)
        
        # Create separate audit log file
        audit_file = self.config.file_path.parent / 'audit.log'
        
        try:
            audit_handler = logging.handlers.RotatingFileHandler(
                audit_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            
            # Use specific format for audit logs
            audit_format = '%(asctime)s - AUDIT - %(message)s'
            audit_handler.setFormatter(logging.Formatter(audit_format))
            
            audit_logger.addHandler(audit_handler)
            audit_logger.propagate = False  # Don't propagate to root logger
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to create audit logger: {e}")
        
        return audit_logger
    
    def log_system_info(self):
        """Log system information for debugging."""
        import platform
        import sys
        
        logger = self.get_logger(__name__)
        logger.info("=== System Information ===")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Working directory: {Path.cwd()}")
        logger.info(f"Log file: {self.config.file_path}")
        logger.info("=== End System Information ===")


# Global logging manager instance
_logging_manager = None


def setup_logging(config: Optional[LoggingConfig] = None) -> LoggingManager:
    """
    Set up global logging configuration.
    
    Args:
        config: Optional logging configuration
        
    Returns:
        LoggingManager instance
    """
    global _logging_manager
    _logging_manager = LoggingManager(config)
    return _logging_manager


def get_logger(name: str, context: Dict[str, Any] = None) -> logging.Logger:
    """
    Get a logger instance with optional context.
    
    Args:
        name: Logger name
        context: Optional context information
        
    Returns:
        Logger instance
    """
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    
    return _logging_manager.get_logger(name, context)


def get_audit_logger() -> logging.Logger:
    """
    Get the audit logger for tracking important operations.
    
    Returns:
        Audit logger instance
    """
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    
    return _logging_manager.create_audit_logger()


class LogContext:
    """Context manager for adding context to log messages."""
    
    def __init__(self, logger: logging.Logger, **context):
        """
        Initialize log context.
        
        Args:
            logger: Logger to add context to
            **context: Context key-value pairs
        """
        self.logger = logger
        self.context = context
        self.filter = None
    
    def __enter__(self):
        """Enter context and add filter."""
        self.filter = ContextFilter(self.context)
        self.logger.addFilter(self.filter)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and remove filter."""
        if self.filter:
            self.logger.removeFilter(self.filter)


def log_function_call(logger: logging.Logger = None):
    """
    Decorator to log function calls with arguments and return values.
    
    Args:
        logger: Logger to use. If None, creates one based on function module.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_logger = logger or get_logger(func.__module__)
            
            # Log function entry
            func_logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                func_logger.debug(f"{func.__name__} returned: {result}")
                return result
            except Exception as e:
                func_logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
                raise
        
        return wrapper
    return decorator