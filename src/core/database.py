"""Database manager for the File Categorizer System."""

import sqlite3
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .models import FileRecord, SearchCriteria, CleanupResult
from .exceptions import (
    DatabaseError, DatabaseConnectionError, DatabaseCorruptionError,
    RetryableDatabaseError
)
from .error_handler import (
    ErrorHandler, safe_database_operation, retry_on_error, CircuitBreaker
)


class DatabaseManager:
    """Manages SQLite database operations for file records."""

    def __init__(self, db_path: Optional[Path] = None, config=None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to SQLite database file. If None, uses config or default location.
            config: Optional configuration object
        """
        # Import here to avoid circular imports
        from .config import get_config
        
        app_config = config or get_config()
        
        if db_path is None:
            db_path = app_config.database.path
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = app_config.database
        self.error_handler = ErrorHandler()
        self.logger = logging.getLogger(__name__)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        self._connection_pool = []
        self._max_pool_size = self.config.max_connections

    @retry_on_error(max_retries=3, exceptions=(RetryableDatabaseError,))
    @safe_database_operation("database initialization")
    def initialize(self) -> None:
        """
        Initialize the database schema.
        
        Creates tables and indexes if they don't exist.
        """
        def _initialize():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if database is accessible
                try:
                    cursor.execute("SELECT 1")
                except sqlite3.DatabaseError as e:
                    if "database disk image is malformed" in str(e).lower():
                        self.logger.error("Database corruption detected, attempting recovery")
                        self._attempt_database_recovery()
                        # Retry with new connection
                        conn = self.get_connection()
                        cursor = conn.cursor()
                
                # Create files table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        id TEXT PRIMARY KEY,
                        path TEXT UNIQUE NOT NULL,
                        filename TEXT NOT NULL,
                        category TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        modified_date INTEGER NOT NULL,
                        scanned_date INTEGER NOT NULL,
                        file_exists INTEGER DEFAULT 1
                    )
                """)
                
                # Create indexes for better query performance
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_category ON files(category)",
                    "CREATE INDEX IF NOT EXISTS idx_filename ON files(filename)",
                    "CREATE INDEX IF NOT EXISTS idx_path ON files(path)",
                    "CREATE INDEX IF NOT EXISTS idx_exists ON files(file_exists)",
                    "CREATE INDEX IF NOT EXISTS idx_modified_date ON files(modified_date)"
                ]
                
                for index_sql in indexes:
                    try:
                        cursor.execute(index_sql)
                    except sqlite3.Error as e:
                        self.logger.warning(f"Failed to create index: {e}")
                        # Continue with other indexes
                
                conn.commit()
                self.logger.info("Database initialized successfully")
        
        return self.circuit_breaker.call(_initialize)

    @retry_on_error(max_retries=3, exceptions=(RetryableDatabaseError,))
    @safe_database_operation("add file record")
    def add_file(self, file_record: FileRecord) -> None:
        """
        Add a file record to the database.
        
        Args:
            file_record: FileRecord to add
        """
        def _add_file():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Convert datetime objects to timestamps for storage
                modified_timestamp = int(file_record.modified_date.timestamp())
                scanned_timestamp = int(file_record.scanned_date.timestamp())
                
                # Use INSERT OR REPLACE to handle duplicates by path
                cursor.execute("""
                    INSERT OR REPLACE INTO files 
                    (id, path, filename, category, size, modified_date, scanned_date, file_exists)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_record.id,
                    file_record.path,
                    file_record.filename,
                    file_record.category.value,
                    file_record.size,
                    modified_timestamp,
                    scanned_timestamp,
                    1 if file_record.exists else 0
                ))
                
                conn.commit()
        
        return self.circuit_breaker.call(_add_file)
    
    @retry_on_error(max_retries=3, exceptions=(RetryableDatabaseError,))
    @safe_database_operation("batch add file records")
    def add_files_batch(self, file_records: List[FileRecord]) -> None:
        """
        Add multiple file records to the database in a batch operation.
        
        Args:
            file_records: List of FileRecord objects to add
        """
        if not file_records:
            return
        
        def _add_files_batch():
            # Process in smaller chunks to avoid memory issues and lock timeouts
            chunk_size = 100
            total_chunks = (len(file_records) + chunk_size - 1) // chunk_size
            
            for i in range(0, len(file_records), chunk_size):
                chunk = file_records[i:i + chunk_size]
                chunk_num = (i // chunk_size) + 1
                
                self.logger.debug(f"Processing batch chunk {chunk_num}/{total_chunks} ({len(chunk)} records)")
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Prepare batch data for this chunk
                    batch_data = []
                    for record in chunk:
                        try:
                            modified_timestamp = int(record.modified_date.timestamp())
                            scanned_timestamp = int(record.scanned_date.timestamp())
                            
                            batch_data.append((
                                record.id,
                                record.path,
                                record.filename,
                                record.category.value,
                                record.size,
                                modified_timestamp,
                                scanned_timestamp,
                                1 if record.exists else 0
                            ))
                        except Exception as e:
                            self.logger.warning(f"Skipping invalid record {record.path}: {e}")
                            continue
                    
                    if batch_data:
                        # Execute batch insert for this chunk
                        cursor.executemany("""
                            INSERT OR REPLACE INTO files 
                            (id, path, filename, category, size, modified_date, scanned_date, file_exists)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch_data)
                        
                        conn.commit()
            
            self.logger.info(f"Successfully added {len(file_records)} file records in batch")
        
        return self.circuit_breaker.call(_add_files_batch)

    def search_files(self, criteria: SearchCriteria) -> List[FileRecord]:
        """
        Search for files based on criteria.
        
        Args:
            criteria: Search criteria
            
        Returns:
            List of matching FileRecord objects
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Build dynamic query based on criteria
                query_parts = ["SELECT * FROM files WHERE 1=1"]
                params = []
                
                # Add query filters
                if criteria.query:
                    query_parts.append("AND (filename LIKE ? OR path LIKE ?)")
                    search_term = f"%{criteria.query}%"
                    params.extend([search_term, search_term])
                
                if criteria.category:
                    query_parts.append("AND category = ?")
                    params.append(criteria.category.value)
                
                if criteria.min_size is not None:
                    query_parts.append("AND size >= ?")
                    params.append(criteria.min_size)
                
                if criteria.max_size is not None:
                    query_parts.append("AND size <= ?")
                    params.append(criteria.max_size)
                
                if criteria.modified_after:
                    query_parts.append("AND modified_date >= ?")
                    params.append(int(criteria.modified_after.timestamp()))
                
                if criteria.modified_before:
                    query_parts.append("AND modified_date <= ?")
                    params.append(int(criteria.modified_before.timestamp()))
                
                # Add ordering and pagination
                query_parts.append("ORDER BY modified_date DESC")
                
                if criteria.limit:
                    query_parts.append("LIMIT ?")
                    params.append(criteria.limit)
                    
                    if criteria.offset > 0:
                        query_parts.append("OFFSET ?")
                        params.append(criteria.offset)
                
                query = " ".join(query_parts)
                cursor.execute(query, params)
                
                # Convert rows to FileRecord objects
                results = []
                for row in cursor.fetchall():
                    file_record = self._row_to_file_record(row)
                    results.append(file_record)
                
                return results
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to search files: {e}") from e

    def remove_file(self, file_id: str) -> bool:
        """
        Remove a file record from the database.
        
        Args:
            file_id: ID of the file record to remove
            
        Returns:
            True if file was removed, False if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
                conn.commit()
                
                return cursor.rowcount > 0
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to remove file record: {e}") from e

    def mark_files_nonexistent(self, file_ids: List[str]) -> int:
        """
        Mark multiple files as non-existent without removing them from database.
        
        This is useful for soft deletion or when you want to keep records
        but mark them as missing.
        
        Args:
            file_ids: List of file IDs to mark as non-existent
            
        Returns:
            Number of files marked as non-existent
        """
        if not file_ids:
            return 0
            
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Use executemany for batch update
                cursor.executemany(
                    "UPDATE files SET file_exists = 0 WHERE id = ?",
                    [(file_id,) for file_id in file_ids]
                )
                
                conn.commit()
                return cursor.rowcount
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to mark files as non-existent: {e}") from e

    def verify_and_update_existence(self, dry_run: bool = False, batch_size: int = 1000) -> CleanupResult:
        """
        Verify file existence and update the file_exists flag without removing records.
        
        This method updates the file_exists column to reflect current file system state
        without actually deleting database records.
        
        Args:
            dry_run: If True, don't actually update records, just preview changes
            batch_size: Number of records to process in each batch
            
        Returns:
            CleanupResult with operation details
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get total count for progress tracking
                cursor.execute("SELECT COUNT(*) FROM files")
                total_count = cursor.fetchone()[0]
                
                updated_files = []
                errors = []
                processed_count = 0
                
                # Process files in batches
                offset = 0
                while offset < total_count:
                    # Get batch of file records
                    cursor.execute("""
                        SELECT id, path, file_exists FROM files 
                        ORDER BY id 
                        LIMIT ? OFFSET ?
                    """, (batch_size, offset))
                    
                    batch_files = cursor.fetchall()
                    if not batch_files:
                        break
                    
                    # Check existence and prepare updates
                    batch_updates = []
                    
                    for file_id, file_path, current_exists in batch_files:
                        try:
                            path_obj = Path(file_path)
                            actual_exists = path_obj.exists()
                            
                            # Only update if status changed
                            if bool(current_exists) != actual_exists:
                                updated_files.append(file_path)
                                batch_updates.append((1 if actual_exists else 0, file_id))
                        
                        except (OSError, PermissionError, ValueError) as e:
                            errors.append(f"Error checking {file_path}: {str(e)}")
                            continue
                    
                    # Batch update existence status
                    if batch_updates and not dry_run:
                        cursor.executemany(
                            "UPDATE files SET file_exists = ? WHERE id = ?",
                            batch_updates
                        )
                    
                    processed_count += len(batch_files)
                    offset += batch_size
                
                if not dry_run:
                    conn.commit()
                
                return CleanupResult(
                    total_checked=processed_count,
                    removed_count=len(updated_files),  # In this case, "removed" means "updated"
                    removed_files=updated_files,
                    errors=errors,
                    dry_run=dry_run
                )
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to verify and update file existence: {e}") from e

    def cleanup_database(self, dry_run: bool = False, batch_size: int = 1000) -> CleanupResult:
        """
        Clean up database by removing records for non-existent files.
        
        Uses batch operations for improved performance with large datasets.
        
        Args:
            dry_run: If True, don't actually remove records, just preview changes
            batch_size: Number of records to process in each batch for performance
            
        Returns:
            CleanupResult with operation details
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get total count for progress tracking
                cursor.execute("SELECT COUNT(*) FROM files WHERE file_exists = 1")
                total_count = cursor.fetchone()[0]
                
                removed_files = []
                errors = []
                processed_count = 0
                
                # Process files in batches for better performance
                offset = 0
                while offset < total_count:
                    # Get batch of file records
                    cursor.execute("""
                        SELECT id, path FROM files 
                        WHERE file_exists = 1 
                        ORDER BY id 
                        LIMIT ? OFFSET ?
                    """, (batch_size, offset))
                    
                    batch_files = cursor.fetchall()
                    if not batch_files:
                        break
                    
                    # Check existence for current batch
                    batch_to_remove = []
                    
                    for file_id, file_path in batch_files:
                        try:
                            path_obj = Path(file_path)
                            if not path_obj.exists():
                                removed_files.append(file_path)
                                batch_to_remove.append(file_id)
                        
                        except (OSError, PermissionError, ValueError) as e:
                            # Handle file system errors (permissions, network drives, invalid paths, etc.)
                            errors.append(f"Error checking {file_path}: {str(e)}")
                            continue
                    
                    # Batch remove non-existent files from database
                    if batch_to_remove and not dry_run:
                        # Use executemany for batch deletion
                        cursor.executemany("DELETE FROM files WHERE id = ?", 
                                         [(file_id,) for file_id in batch_to_remove])
                    
                    processed_count += len(batch_files)
                    offset += batch_size
                
                if not dry_run:
                    conn.commit()
                
                return CleanupResult(
                    total_checked=processed_count,
                    removed_count=len(removed_files),
                    removed_files=removed_files,
                    errors=errors,
                    dry_run=dry_run
                )
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to cleanup database: {e}") from e

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection with proper error handling and configuration.
        
        Returns:
            SQLite connection object
            
        Raises:
            DatabaseConnectionError: If connection cannot be established
        """
        try:
            # Create connection with optimized settings
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.config.timeout,
                check_same_thread=False
            )
            
            # Configure connection for better performance and reliability
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and performance
            conn.execute("PRAGMA cache_size=10000")  # Increase cache size
            conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
            conn.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
            
            return conn
            
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "database is locked" in error_msg:
                raise RetryableDatabaseError(f"Database is locked: {e}")
            elif "no such file or directory" in error_msg:
                # Try to create the directory and retry
                try:
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    return sqlite3.connect(self.db_path, timeout=self.config.timeout)
                except Exception as create_error:
                    raise DatabaseConnectionError(f"Cannot create database directory: {create_error}")
            else:
                raise DatabaseConnectionError(f"Cannot connect to database: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"Unexpected database connection error: {e}")
    
    def _attempt_database_recovery(self):
        """
        Attempt to recover a corrupted database by creating a backup and rebuilding.
        """
        try:
            backup_path = self.db_path.with_suffix('.db.backup')
            
            # Create backup of corrupted database
            if self.db_path.exists():
                import shutil
                shutil.copy2(self.db_path, backup_path)
                self.logger.info(f"Created backup of corrupted database: {backup_path}")
            
            # Remove corrupted database
            if self.db_path.exists():
                self.db_path.unlink()
                self.logger.info("Removed corrupted database file")
            
            # The database will be recreated on next initialization
            self.logger.info("Database recovery completed - will be recreated on next access")
            
        except Exception as e:
            self.logger.error(f"Database recovery failed: {e}")
            raise DatabaseCorruptionError(f"Cannot recover corrupted database: {e}")
    
    def health_check(self) -> bool:
        """
        Perform a health check on the database.
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Test basic operations
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # Test integrity
                cursor.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()[0]
                
                if integrity_result != "ok":
                    self.logger.error(f"Database integrity check failed: {integrity_result}")
                    return False
                
                self.logger.debug(f"Database health check passed ({table_count} tables)")
                return True
                
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
    
    def _row_to_file_record(self, row: tuple) -> FileRecord:
        """
        Convert a database row to a FileRecord object.
        
        Args:
            row: Database row tuple
            
        Returns:
            FileRecord object
        """
        from .models import FileCategory
        
        return FileRecord(
            id=row[0],
            path=row[1],
            filename=row[2],
            category=FileCategory(row[3]),
            size=row[4],
            modified_date=datetime.fromtimestamp(row[5]),
            scanned_date=datetime.fromtimestamp(row[6]),
            exists=bool(row[7])
        )