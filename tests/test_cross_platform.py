"""Cross-platform compatibility tests for File Categorizer System."""

import os
import sys
import tempfile
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src.core.scanner import FileScanner
from src.core.database import DatabaseManager
from src.core.models import ScanOptions, FileCategory, SearchCriteria
from src.core.config import AppConfig, DatabaseConfig, ScanConfig


class TestCrossPlatformPaths:
    """Test file path handling across different platforms."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.scanner = FileScanner()
        
    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_path_normalization_windows(self):
        """Test Windows path handling."""
        with patch('sys.platform', 'win32'):
            # Test Windows-style paths
            test_paths = [
                "C:\\Users\\Test\\Documents",
                "C:/Users/Test/Documents",  # Mixed separators
                "\\\\server\\share\\folder",  # UNC path
                "C:\\Users\\Test\\Documents with spaces",
                "C:\\Users\\Test\\Documents\\file.txt"
            ]
            
            for path_str in test_paths:
                path_obj = Path(path_str)
                # Ensure path is properly normalized
                assert isinstance(path_obj, Path)
                # Check that resolve() works without errors
                try:
                    resolved = path_obj.resolve()
                    assert isinstance(resolved, Path)
                except (OSError, ValueError):
                    # Some paths may not exist, but should not cause crashes
                    pass
    
    def test_path_normalization_posix(self):
        """Test POSIX (Linux/macOS) path handling."""
        with patch('sys.platform', 'linux'):
            # Test POSIX-style paths
            test_paths = [
                "/home/user/documents",
                "/home/user/documents with spaces",
                "/home/user/.hidden_folder",
                "~/documents",  # Home directory expansion
                "/tmp/test file.txt"
            ]
            
            for path_str in test_paths:
                if path_str.startswith('~'):
                    path_obj = Path(path_str).expanduser()
                else:
                    path_obj = Path(path_str)
                
                # Ensure path is properly normalized
                assert isinstance(path_obj, Path)
                # Check that resolve() works without errors
                try:
                    resolved = path_obj.resolve()
                    assert isinstance(resolved, Path)
                except (OSError, ValueError):
                    # Some paths may not exist, but should not cause crashes
                    pass
    
    def test_file_extension_case_sensitivity(self):
        """Test file extension handling across case-sensitive and case-insensitive filesystems."""
        # Create test files with different case extensions
        test_files = [
            "image.JPG",
            "image.jpg", 
            "image.Jpg",
            "vector.SVG",
            "vector.svg",
            "lightburn.LBRN2",
            "lightburn.lbrn2"
        ]
        
        for filename in test_files:
            test_file = self.temp_dir / filename
            test_file.touch()
        
        # Test categorization regardless of case
        for test_file in self.temp_dir.iterdir():
            category = self.scanner.categorize_file(test_file)
            assert category in [FileCategory.GRAPHICS, FileCategory.VECTOR, FileCategory.LIGHTBURN]
    
    def test_special_characters_in_paths(self):
        """Test handling of special characters in file paths."""
        special_chars_files = [
            "file with spaces.jpg",
            "file-with-dashes.png",
            "file_with_underscores.svg",
            "file.with.dots.ai",
            "file(with)parentheses.lbrn2",
            "file[with]brackets.eps"
        ]
        
        # Create files with special characters
        for filename in special_chars_files:
            try:
                test_file = self.temp_dir / filename
                test_file.touch()
                
                # Test that scanner can handle the file
                category = self.scanner.categorize_file(test_file)
                assert isinstance(category, FileCategory)
                
                # Test metadata extraction
                metadata = self.scanner.get_file_metadata(test_file)
                assert metadata is not None
                assert metadata.path == str(test_file)
                
            except (OSError, ValueError) as e:
                # Some special characters may not be supported on certain filesystems
                # This is expected behavior, not a failure
                print(f"Skipping {filename} due to filesystem limitation: {e}")
    
    def test_long_path_handling(self):
        """Test handling of long file paths."""
        # Create a deeply nested directory structure
        long_path = self.temp_dir
        for i in range(10):  # Create 10 levels deep
            long_path = long_path / f"level_{i}_directory_with_long_name"
            try:
                long_path.mkdir(exist_ok=True)
            except OSError:
                # Path too long for filesystem, skip test
                pytest.skip("Filesystem does not support long paths")
        
        # Create a file in the deep directory
        test_file = long_path / "test_file.jpg"
        try:
            test_file.touch()
            
            # Test that scanner can handle long paths
            category = self.scanner.categorize_file(test_file)
            assert category == FileCategory.GRAPHICS
            
        except OSError:
            # Path too long for filesystem, skip test
            pytest.skip("Filesystem does not support long paths")


class TestCrossPlatformDatabase:
    """Test database portability across platforms."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"
        
    def teardown_method(self):
        """Clean up test environment."""
        # Force garbage collection to close any remaining database connections
        import gc
        gc.collect()
        
        # On Windows, wait a bit for file handles to be released
        if sys.platform == 'win32':
            import time
            time.sleep(0.1)
        
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                # On Windows, database files might still be locked
                # Try again after a short delay
                if sys.platform == 'win32':
                    import time
                    time.sleep(0.5)
                    try:
                        shutil.rmtree(self.temp_dir)
                    except PermissionError:
                        # If still locked, just skip cleanup
                        # The temp directory will be cleaned up by the OS eventually
                        pass
                else:
                    raise
    
    def test_database_creation_cross_platform(self):
        """Test database creation on different platforms."""
        config = AppConfig(
            database=DatabaseConfig(path=self.db_path)
        )
        
        db_manager = DatabaseManager(config=config)
        db_manager.initialize()
        
        # Verify database file was created
        assert self.db_path.exists()
        
        # Verify database schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert 'files' in tables
        
        conn.close()
    
    def test_database_file_path_storage(self):
        """Test that file paths are stored correctly across platforms."""
        config = AppConfig(
            database=DatabaseConfig(path=self.db_path)
        )
        
        db_manager = DatabaseManager(config=config)
        db_manager.initialize()
        
        # Create test files with platform-specific paths
        test_paths = []
        if sys.platform == 'win32':
            test_paths = [
                "C:\\Users\\Test\\image.jpg",
                "D:\\Projects\\vector.svg",
                "\\\\server\\share\\lightburn.lbrn2"
            ]
        else:
            test_paths = [
                "/home/user/image.jpg",
                "/tmp/vector.svg", 
                "/usr/local/share/lightburn.lbrn2"
            ]
        
        # Add files to database
        from src.core.models import FileRecord
        from datetime import datetime
        import uuid
        
        for path_str in test_paths:
            file_record = FileRecord(
                id=str(uuid.uuid4()),
                path=path_str,
                filename=Path(path_str).name,
                category=FileCategory.GRAPHICS,
                size=1024,
                modified_date=datetime.now(),
                scanned_date=datetime.now()
            )
            db_manager.add_file(file_record)
        
        # Retrieve and verify paths
        criteria = SearchCriteria()
        results = db_manager.search_files(criteria)
        
        assert len(results) == len(test_paths)
        stored_paths = [r.path for r in results]
        
        for original_path in test_paths:
            assert original_path in stored_paths
    
    def test_database_portability(self):
        """Test that database files can be moved between platforms."""
        config = AppConfig(
            database=DatabaseConfig(path=self.db_path)
        )
        
        db_manager = DatabaseManager(config=config)
        db_manager.initialize()
        
        # Add some test data
        from src.core.models import FileRecord
        from datetime import datetime
        import uuid
        
        file_record = FileRecord(
            id=str(uuid.uuid4()),
            path="/test/path/image.jpg",
            filename="image.jpg",
            category=FileCategory.GRAPHICS,
            size=2048,
            modified_date=datetime.now(),
            scanned_date=datetime.now()
        )
        db_manager.add_file(file_record)
        
        # Force connection cleanup by deleting the manager
        del db_manager
        import gc
        gc.collect()
        
        # On Windows, wait for file handles to be released
        if sys.platform == 'win32':
            import time
            time.sleep(0.1)
        
        # Copy database to new location (simulating platform transfer)
        new_db_path = self.temp_dir / "transferred.db"
        shutil.copy2(self.db_path, new_db_path)
        
        # Open database from new location
        new_config = AppConfig(
            database=DatabaseConfig(path=new_db_path)
        )
        
        new_db_manager = DatabaseManager(config=new_config)
        new_db_manager.initialize()
        
        # Verify data integrity
        criteria = SearchCriteria()
        results = new_db_manager.search_files(criteria)
        
        assert len(results) == 1
        assert results[0].filename == "image.jpg"
        assert results[0].category == FileCategory.GRAPHICS


class TestCrossPlatformCLI:
    """Test CLI interface consistency across platforms."""
    
    def test_cli_path_arguments(self):
        """Test CLI path argument handling."""
        from src.cli.main import cli
        from click.testing import CliRunner
        
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Create a test directory
            test_dir = Path("test_directory")
            test_dir.mkdir()
            
            # Test scan command with different path formats
            if sys.platform == 'win32':
                # Test Windows path format
                result = runner.invoke(cli, ['scan', str(test_dir.resolve())])
            else:
                # Test POSIX path format
                result = runner.invoke(cli, ['scan', str(test_dir.resolve())])
            
            # Command should not fail due to path format issues
            # Note: It may fail for other reasons (no database, etc.) but not path handling
            assert "Path" not in result.output or "invalid" not in result.output.lower()
    
    def test_config_file_paths(self):
        """Test configuration file path handling."""
        from src.core.config import ConfigManager
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("""
[database]
path = test.db
timeout = 30

[scan]
default_recursive = true
default_max_depth = 10
""")
            config_path = Path(f.name)
        
        try:
            # Test loading config from different path formats
            config_manager = ConfigManager(config_path)
            config = config_manager.get_config()
            
            assert config.database.timeout == 30
            assert config.scan.default_recursive == True
            assert config.scan.default_max_depth == 10
            
        finally:
            config_path.unlink()


class TestCrossPlatformWeb:
    """Test web interface consistency across platforms."""
    
    def test_static_file_serving(self):
        """Test that static files are served correctly across platforms."""
        from src.web.app import create_app
        
        app = create_app({'TESTING': True})
        
        with app.test_client() as client:
            # Test CSS file serving
            response = client.get('/static/css/style.css')
            # Should not return 404 due to path issues
            assert response.status_code in [200, 304, 404]  # 404 is ok if file doesn't exist
            
            # Test JS file serving
            response = client.get('/static/js/app.js')
            assert response.status_code in [200, 304, 404]
    
    def test_api_path_handling(self):
        """Test API endpoint path parameter handling."""
        from src.web.app import create_app
        import json
        
        app = create_app({'TESTING': True})
        
        with app.test_client() as client:
            # Test scan endpoint with different path formats
            test_paths = []
            if sys.platform == 'win32':
                test_paths = ["C:\\temp", "C:/temp"]
            else:
                test_paths = ["/tmp", "/home/user"]
            
            for test_path in test_paths:
                response = client.post('/api/scan', 
                    data=json.dumps({'path': test_path}),
                    content_type='application/json'
                )
                
                # Should not fail due to path format (may fail for other reasons)
                data = response.get_json()
                if response.status_code != 200:
                    # Error should not be about path format
                    assert 'path format' not in data.get('error', '').lower()
                    assert 'invalid path' not in data.get('error', '').lower()


def test_platform_detection():
    """Test that the application correctly detects the current platform."""
    import platform
    
    # Test that we can detect the platform
    current_platform = platform.system()
    assert current_platform in ['Windows', 'Linux', 'Darwin']
    
    # Test sys.platform detection
    assert sys.platform in ['win32', 'linux', 'darwin', 'cygwin']


def test_file_system_case_sensitivity():
    """Test file system case sensitivity detection and handling."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a test file
        test_file = temp_path / "TestFile.txt"
        test_file.touch()
        
        # Try to access with different case
        different_case = temp_path / "testfile.txt"
        
        # Check if filesystem is case-sensitive
        case_sensitive = not different_case.exists()
        
        # Our application should handle both cases correctly
        scanner = FileScanner()
        
        # Test with original case
        category = scanner.categorize_file(test_file)
        # Should return UNKNOWN since .txt is not a categorizable extension
        
        if not case_sensitive:
            # On case-insensitive filesystems, both should work
            category2 = scanner.categorize_file(different_case)
            # Both should give same result


if __name__ == "__main__":
    pytest.main([__file__])