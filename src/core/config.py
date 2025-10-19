"""Configuration management for the File Categorizer System."""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import configparser
import json


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    path: Optional[Path] = None
    timeout: float = 30.0
    max_connections: int = 5
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    
    def __post_init__(self):
        if self.path is None:
            self.path = Path.home() / ".file_categorizer" / "files.db"


@dataclass
class ScanConfig:
    """Scanning configuration settings."""
    default_recursive: bool = True
    default_include_hidden: bool = False
    default_max_depth: Optional[int] = None
    batch_size: int = 100
    progress_update_interval: float = 0.5
    max_file_size_mb: int = 1000  # Skip files larger than this
    
    
@dataclass
class WebConfig:
    """Web interface configuration settings."""
    host: str = "127.0.0.1"
    port: int = 5000
    debug: bool = False
    secret_key: str = "dev-key-change-in-production"
    max_content_length: int = 16 * 1024 * 1024  # 16MB
    session_timeout_minutes: int = 60
    

@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    file_path: Optional[Path] = None
    file_max_size_mb: int = 10
    file_backup_count: int = 5
    console_enabled: bool = True
    
    def __post_init__(self):
        if self.file_path is None:
            self.file_path = Path.home() / ".file_categorizer" / "logs" / "app.log"


@dataclass
class AppConfig:
    """Main application configuration."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    web: WebConfig = field(default_factory=WebConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Application metadata
    app_name: str = "File Categorizer"
    version: str = "0.1.0"
    data_dir: Path = field(default_factory=lambda: Path.home() / ".file_categorizer")
    
    def __post_init__(self):
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure logs directory exists
        if self.logging.file_enabled and self.logging.file_path:
            self.logging.file_path.parent.mkdir(parents=True, exist_ok=True)


class ConfigManager:
    """Manages application configuration from multiple sources."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file. If None, uses default location.
        """
        if config_file is None:
            config_file = Path.home() / ".file_categorizer" / "config.ini"
        
        self.config_file = config_file
        self.config = AppConfig()
        self.logger = logging.getLogger(__name__)
        
        # Load configuration from file if it exists
        if self.config_file.exists():
            self.load_from_file()
        else:
            # Create default configuration file
            self.save_to_file()
    
    def load_from_file(self) -> None:
        """Load configuration from INI file."""
        try:
            parser = configparser.ConfigParser(interpolation=None)  # Disable interpolation
            parser.read(self.config_file)
            
            # Load database configuration
            if 'database' in parser:
                db_section = parser['database']
                if 'path' in db_section:
                    self.config.database.path = Path(db_section['path'])
                if 'timeout' in db_section:
                    self.config.database.timeout = db_section.getfloat('timeout')
                if 'max_connections' in db_section:
                    self.config.database.max_connections = db_section.getint('max_connections')
                if 'backup_enabled' in db_section:
                    self.config.database.backup_enabled = db_section.getboolean('backup_enabled')
                if 'backup_interval_hours' in db_section:
                    self.config.database.backup_interval_hours = db_section.getint('backup_interval_hours')
            
            # Load scan configuration
            if 'scan' in parser:
                scan_section = parser['scan']
                if 'default_recursive' in scan_section:
                    self.config.scan.default_recursive = scan_section.getboolean('default_recursive')
                if 'default_include_hidden' in scan_section:
                    self.config.scan.default_include_hidden = scan_section.getboolean('default_include_hidden')
                if 'default_max_depth' in scan_section:
                    depth_str = scan_section.get('default_max_depth')
                    self.config.scan.default_max_depth = int(depth_str) if depth_str and depth_str != 'None' else None
                if 'batch_size' in scan_section:
                    self.config.scan.batch_size = scan_section.getint('batch_size')
                if 'progress_update_interval' in scan_section:
                    self.config.scan.progress_update_interval = scan_section.getfloat('progress_update_interval')
                if 'max_file_size_mb' in scan_section:
                    self.config.scan.max_file_size_mb = scan_section.getint('max_file_size_mb')
            
            # Load web configuration
            if 'web' in parser:
                web_section = parser['web']
                if 'host' in web_section:
                    self.config.web.host = web_section.get('host')
                if 'port' in web_section:
                    self.config.web.port = web_section.getint('port')
                if 'debug' in web_section:
                    self.config.web.debug = web_section.getboolean('debug')
                if 'secret_key' in web_section:
                    self.config.web.secret_key = web_section.get('secret_key')
                if 'max_content_length' in web_section:
                    self.config.web.max_content_length = web_section.getint('max_content_length')
                if 'session_timeout_minutes' in web_section:
                    self.config.web.session_timeout_minutes = web_section.getint('session_timeout_minutes')
            
            # Load logging configuration
            if 'logging' in parser:
                log_section = parser['logging']
                if 'level' in log_section:
                    self.config.logging.level = log_section.get('level')
                if 'format' in log_section:
                    self.config.logging.format = log_section.get('format')
                if 'file_enabled' in log_section:
                    self.config.logging.file_enabled = log_section.getboolean('file_enabled')
                if 'file_path' in log_section:
                    self.config.logging.file_path = Path(log_section.get('file_path'))
                if 'file_max_size_mb' in log_section:
                    self.config.logging.file_max_size_mb = log_section.getint('file_max_size_mb')
                if 'file_backup_count' in log_section:
                    self.config.logging.file_backup_count = log_section.getint('file_backup_count')
                if 'console_enabled' in log_section:
                    self.config.logging.console_enabled = log_section.getboolean('console_enabled')
            
            self.logger.info(f"Configuration loaded from {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Error loading configuration from {self.config_file}: {e}")
            # Use default configuration on error
    
    def save_to_file(self) -> None:
        """Save current configuration to INI file."""
        try:
            # Ensure config directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            parser = configparser.ConfigParser(interpolation=None)  # Disable interpolation
            
            # Database section
            parser['database'] = {
                'path': str(self.config.database.path),
                'timeout': str(self.config.database.timeout),
                'max_connections': str(self.config.database.max_connections),
                'backup_enabled': str(self.config.database.backup_enabled),
                'backup_interval_hours': str(self.config.database.backup_interval_hours)
            }
            
            # Scan section
            parser['scan'] = {
                'default_recursive': str(self.config.scan.default_recursive),
                'default_include_hidden': str(self.config.scan.default_include_hidden),
                'default_max_depth': str(self.config.scan.default_max_depth),
                'batch_size': str(self.config.scan.batch_size),
                'progress_update_interval': str(self.config.scan.progress_update_interval),
                'max_file_size_mb': str(self.config.scan.max_file_size_mb)
            }
            
            # Web section
            parser['web'] = {
                'host': self.config.web.host,
                'port': str(self.config.web.port),
                'debug': str(self.config.web.debug),
                'secret_key': self.config.web.secret_key,
                'max_content_length': str(self.config.web.max_content_length),
                'session_timeout_minutes': str(self.config.web.session_timeout_minutes)
            }
            
            # Logging section
            parser['logging'] = {
                'level': self.config.logging.level,
                'format': self.config.logging.format,  # No need to escape with interpolation=None
                'file_enabled': str(self.config.logging.file_enabled),
                'file_path': str(self.config.logging.file_path),
                'file_max_size_mb': str(self.config.logging.file_max_size_mb),
                'file_backup_count': str(self.config.logging.file_backup_count),
                'console_enabled': str(self.config.logging.console_enabled)
            }
            
            with open(self.config_file, 'w') as f:
                parser.write(f)
            
            self.logger.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving configuration to {self.config_file}: {e}")
    
    def get_config(self) -> AppConfig:
        """Get the current configuration."""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """
        Update configuration values.
        
        Args:
            **kwargs: Configuration values to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                self.logger.warning(f"Unknown configuration key: {key}")
        
        # Save updated configuration
        self.save_to_file()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = AppConfig()
        self.save_to_file()
        self.logger.info("Configuration reset to defaults")
    
    def export_to_json(self, file_path: Path) -> None:
        """
        Export configuration to JSON format.
        
        Args:
            file_path: Path to save JSON file
        """
        try:
            config_dict = {
                'database': {
                    'path': str(self.config.database.path),
                    'timeout': self.config.database.timeout,
                    'max_connections': self.config.database.max_connections,
                    'backup_enabled': self.config.database.backup_enabled,
                    'backup_interval_hours': self.config.database.backup_interval_hours
                },
                'scan': {
                    'default_recursive': self.config.scan.default_recursive,
                    'default_include_hidden': self.config.scan.default_include_hidden,
                    'default_max_depth': self.config.scan.default_max_depth,
                    'batch_size': self.config.scan.batch_size,
                    'progress_update_interval': self.config.scan.progress_update_interval,
                    'max_file_size_mb': self.config.scan.max_file_size_mb
                },
                'web': {
                    'host': self.config.web.host,
                    'port': self.config.web.port,
                    'debug': self.config.web.debug,
                    'secret_key': self.config.web.secret_key,
                    'max_content_length': self.config.web.max_content_length,
                    'session_timeout_minutes': self.config.web.session_timeout_minutes
                },
                'logging': {
                    'level': self.config.logging.level,
                    'format': self.config.logging.format,
                    'file_enabled': self.config.logging.file_enabled,
                    'file_path': str(self.config.logging.file_path),
                    'file_max_size_mb': self.config.logging.file_max_size_mb,
                    'file_backup_count': self.config.logging.file_backup_count,
                    'console_enabled': self.config.logging.console_enabled
                }
            }
            
            with open(file_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            self.logger.info(f"Configuration exported to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error exporting configuration to {file_path}: {e}")


# Global configuration instance
_config_manager = None


def get_config() -> AppConfig:
    """Get the global application configuration."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.get_config()


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def setup_config(config_file: Optional[Path] = None) -> ConfigManager:
    """
    Set up global configuration.
    
    Args:
        config_file: Optional path to configuration file
        
    Returns:
        ConfigManager instance
    """
    global _config_manager
    _config_manager = ConfigManager(config_file)
    return _config_manager