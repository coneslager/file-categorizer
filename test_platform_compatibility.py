#!/usr/bin/env python3
"""
Cross-platform compatibility test runner for File Categorizer System.

This script runs comprehensive tests to verify that the application works
correctly across different operating systems and file systems.
"""

import sys
import platform
import subprocess
import tempfile
import shutil
from pathlib import Path


def print_platform_info():
    """Print current platform information."""
    print("=" * 60)
    print("PLATFORM COMPATIBILITY TEST")
    print("=" * 60)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Python: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"sys.platform: {sys.platform}")
    print("=" * 60)


def test_basic_imports():
    """Test that all modules can be imported."""
    print("\n1. Testing basic imports...")
    
    try:
        import src
        print(f"✓ Package version: {src.__version__}")
        
        from src.core.scanner import FileScanner
        print("✓ FileScanner import successful")
        
        from src.core.database import DatabaseManager
        print("✓ DatabaseManager import successful")
        
        from src.cli.main import cli
        print("✓ CLI import successful")
        
        from src.web.app import create_app
        print("✓ Web app import successful")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_cli_functionality():
    """Test basic CLI functionality."""
    print("\n2. Testing CLI functionality...")
    
    try:
        # Test CLI help
        result = subprocess.run([
            sys.executable, "-m", "src", "--help"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ CLI help command works")
        else:
            print(f"✗ CLI help failed: {result.stderr}")
            return False
        
        # Test version command
        result = subprocess.run([
            sys.executable, "-m", "src", "--version"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "0.1.0" in result.stdout:
            print("✓ CLI version command works")
        else:
            print(f"✗ CLI version failed: {result.stderr}")
            return False
        
        return True
        
    except subprocess.TimeoutExpired:
        print("✗ CLI test timed out")
        return False
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        return False


def test_file_operations():
    """Test file system operations."""
    print("\n3. Testing file system operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            # Test file creation with various names
            test_files = [
                "normal_file.jpg",
                "file with spaces.png",
                "file-with-dashes.svg",
                "file_with_underscores.ai"
            ]
            
            if sys.platform != 'win32':
                # Add Unix-specific test files
                test_files.extend([
                    ".hidden_file.lbrn2",
                    "file:with:colons.eps"  # May not work on Windows
                ])
            
            created_files = []
            for filename in test_files:
                try:
                    test_file = temp_path / filename
                    test_file.touch()
                    created_files.append(test_file)
                except OSError as e:
                    print(f"  Warning: Could not create {filename}: {e}")
            
            print(f"✓ Created {len(created_files)} test files")
            
            # Test file scanning
            from src.core.scanner import FileScanner
            from src.core.models import ScanOptions
            
            scanner = FileScanner()
            options = ScanOptions(recursive=False, verbose=False)
            
            result = scanner.scan_directory(temp_path, options)
            print(f"✓ Scanned directory, found {result.total_files} files")
            
            # Test file categorization
            categorized_count = 0
            for test_file in created_files:
                try:
                    category = scanner.categorize_file(test_file)
                    if category:
                        categorized_count += 1
                except Exception as e:
                    print(f"  Warning: Could not categorize {test_file.name}: {e}")
            
            print(f"✓ Categorized {categorized_count} files")
            
            return True
            
        except Exception as e:
            print(f"✗ File operations failed: {e}")
            return False


def test_database_operations():
    """Test database operations."""
    print("\n4. Testing database operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = temp_path / "test.db"
        
        try:
            from src.core.database import DatabaseManager
            from src.core.config import AppConfig, DatabaseConfig
            from src.core.models import FileRecord, FileCategory, SearchCriteria
            from datetime import datetime
            import uuid
            
            # Create database
            config = AppConfig(database=DatabaseConfig(path=db_path))
            db_manager = DatabaseManager(config=config)
            db_manager.initialize()
            
            print("✓ Database created successfully")
            
            # Test adding files
            test_record = FileRecord(
                id=str(uuid.uuid4()),
                path=str(temp_path / "test.jpg"),
                filename="test.jpg",
                category=FileCategory.GRAPHICS,
                size=1024,
                modified_date=datetime.now(),
                scanned_date=datetime.now()
            )
            
            db_manager.add_file(test_record)
            print("✓ File record added to database")
            
            # Test searching
            criteria = SearchCriteria(limit=10)
            results = db_manager.search_files(criteria)
            
            if len(results) == 1 and results[0].filename == "test.jpg":
                print("✓ Database search works correctly")
            else:
                print(f"✗ Database search failed: expected 1 result, got {len(results)}")
                return False
            
            # Test cleanup
            cleanup_result = db_manager.cleanup_database(dry_run=True)
            print(f"✓ Database cleanup test completed ({cleanup_result.total_checked} files checked)")
            
            # Force connection cleanup
            del db_manager
            import gc
            gc.collect()
            
            return True
            
        except Exception as e:
            print(f"✗ Database operations failed: {e}")
            return False


def test_web_interface():
    """Test web interface basic functionality."""
    print("\n5. Testing web interface...")
    
    try:
        from src.web.app import create_app
        
        app = create_app({'TESTING': True})
        
        with app.test_client() as client:
            # Test main page
            response = client.get('/')
            if response.status_code == 200:
                print("✓ Main page loads successfully")
            else:
                print(f"✗ Main page failed: {response.status_code}")
                return False
            
            # Test API endpoint
            response = client.get('/api/files')
            if response.status_code in [200, 404]:  # 404 is ok if no database
                print("✓ API endpoint accessible")
            else:
                print(f"✗ API endpoint failed: {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Web interface test failed: {e}")
        return False


def test_console_scripts():
    """Test installed console scripts."""
    print("\n6. Testing console scripts...")
    
    try:
        # Test file-categorizer command
        result = subprocess.run([
            "file-categorizer", "--version"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ file-categorizer command works")
        else:
            print(f"✗ file-categorizer command failed: {result.stderr}")
            return False
        
        # Test file-cat alias
        result = subprocess.run([
            "file-cat", "--version"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ file-cat alias works")
        else:
            print(f"✗ file-cat alias failed: {result.stderr}")
            return False
        
        return True
        
    except FileNotFoundError:
        print("✗ Console scripts not found (package may not be installed)")
        return False
    except subprocess.TimeoutExpired:
        print("✗ Console script test timed out")
        return False
    except Exception as e:
        print(f"✗ Console script test failed: {e}")
        return False


def run_pytest_tests():
    """Run pytest cross-platform tests."""
    print("\n7. Running pytest cross-platform tests...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", "tests/test_cross_platform.py", "-v"
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✓ All pytest cross-platform tests passed")
            return True
        else:
            print(f"✗ Some pytest tests failed:")
            print(result.stdout)
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("✗ pytest not found, skipping detailed tests")
        return False
    except subprocess.TimeoutExpired:
        print("✗ pytest tests timed out")
        return False
    except Exception as e:
        print(f"✗ pytest execution failed: {e}")
        return False


def main():
    """Run all platform compatibility tests."""
    print_platform_info()
    
    tests = [
        ("Basic Imports", test_basic_imports),
        ("CLI Functionality", test_cli_functionality),
        ("File Operations", test_file_operations),
        ("Database Operations", test_database_operations),
        ("Web Interface", test_web_interface),
        ("Console Scripts", test_console_scripts),
        ("Pytest Tests", run_pytest_tests)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {test_name} crashed: {e}")
    
    print("\n" + "=" * 60)
    print("PLATFORM COMPATIBILITY TEST RESULTS")
    print("=" * 60)
    print(f"Passed: {passed}/{total} tests")
    
    if passed == total:
        print("✓ ALL TESTS PASSED - Platform compatibility verified!")
        return 0
    else:
        print(f"✗ {total - passed} tests failed - Platform compatibility issues detected")
        return 1


if __name__ == "__main__":
    sys.exit(main())