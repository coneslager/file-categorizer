"""API blueprint for REST endpoints."""

import os
import threading
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from ...core.database import DatabaseManager
from ...core.scanner import FileScanner
from ...core.models import SearchCriteria, ScanOptions, FileCategory
from ...core.exceptions import (
    DatabaseError, FileSystemError, ScanError, ValidationError,
    PermissionError, PathNotFoundError
)
from ...core.error_handler import ErrorHandler

api_bp = Blueprint('api', __name__)

# Initialize error handler
error_handler = ErrorHandler()

# Global state for long-running operations
_scan_state = {
    'active': False,
    'progress': {},
    'thread': None,
    'error': None
}

_cleanup_state = {
    'active': False,
    'progress': {},
    'thread': None,
    'error': None
}


def get_db_manager():
    """Get database manager instance with error handling."""
    try:
        db = DatabaseManager()
        
        # Try to initialize the database if it doesn't exist
        try:
            # Perform health check
            if not db.health_check():
                current_app.logger.info("Database not found or unhealthy, initializing...")
                db.initialize()
        except Exception as init_error:
            current_app.logger.warning(f"Database initialization issue: {init_error}")
            # Try to initialize anyway
            db.initialize()
            
        return db
    except DatabaseError as e:
        current_app.logger.error(f"Database initialization failed: {e}")
        raise e
    except Exception as e:
        current_app.logger.error(f"Unexpected error initializing database: {e}")
        raise DatabaseError(f"Database initialization failed: {e}")


def validate_request_data(data, required_fields):
    """
    Validate request data contains required fields.
    
    Args:
        data: Request data dictionary
        required_fields: List of required field names
        
    Raises:
        ValidationError: If validation fails
    """
    if not data:
        raise ValidationError("Request body is required")
    
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")


def handle_api_error(error, operation="operation"):
    """
    Handle API errors and return appropriate JSON response.
    
    Args:
        error: The exception that occurred
        operation: Description of the operation that failed
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    current_app.logger.error(f"API error in {operation}: {error}", exc_info=True)
    
    if isinstance(error, ValidationError):
        return {'error': 'Validation error', 'message': str(error)}, 400
    elif isinstance(error, PathNotFoundError):
        return {'error': 'Path not found', 'message': str(error)}, 404
    elif isinstance(error, PermissionError):
        return {'error': 'Permission denied', 'message': str(error)}, 403
    elif isinstance(error, FileSystemError):
        return {'error': 'File system error', 'message': str(error)}, 400
    elif isinstance(error, DatabaseError):
        return {'error': 'Database error', 'message': str(error)}, 503
    elif isinstance(error, ScanError):
        return {'error': 'Scan error', 'message': str(error)}, 400
    else:
        return {'error': 'Internal server error', 'message': 'An unexpected error occurred'}, 500


@api_bp.route('/files', methods=['GET'])
def get_files():
    """
    Get files with optional filtering and pagination.
    
    Query parameters:
    - query: Search query for filename/path
    - category: Filter by category (graphics, lightburn, vector)
    - min_size: Minimum file size in bytes
    - max_size: Maximum file size in bytes
    - limit: Number of results to return (default: 50)
    - offset: Number of results to skip (default: 0)
    """
    try:
        # Parse and validate query parameters
        query = request.args.get('query', '').strip()
        category_str = request.args.get('category', '').strip()
        
        # Validate numeric parameters
        try:
            min_size = request.args.get('min_size', type=int)
            max_size = request.args.get('max_size', type=int)
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid numeric parameter: {e}")
        
        # Validate limit and offset ranges
        if limit < 1 or limit > 1000:
            raise ValidationError("Limit must be between 1 and 1000")
        if offset < 0:
            raise ValidationError("Offset must be non-negative")
        
        # Validate size parameters
        if min_size is not None and min_size < 0:
            raise ValidationError("Minimum size must be non-negative")
        if max_size is not None and max_size < 0:
            raise ValidationError("Maximum size must be non-negative")
        if min_size is not None and max_size is not None and min_size > max_size:
            raise ValidationError("Minimum size cannot be greater than maximum size")
        
        # Validate and convert category
        category = None
        if category_str:
            try:
                category = FileCategory(category_str)
            except ValueError:
                raise ValidationError(f'Invalid category: {category_str}. Valid categories: {[c.value for c in FileCategory]}')
        
        # Create search criteria
        criteria = SearchCriteria(
            query=query if query else None,
            category=category,
            min_size=min_size,
            max_size=max_size,
            limit=limit,
            offset=offset
        )
        
        # Search files with error handling
        try:
            db = get_db_manager()
            files = db.search_files(criteria)
        except DatabaseError as e:
            current_app.logger.warning(f"Database not available for file search: {e}")
            # Return empty results if database is not available
            return jsonify({
                'files': [],
                'count': 0,
                'offset': offset,
                'limit': limit,
                'total_requested': 0
            })
        
        # Convert to JSON-serializable format
        files_data = []
        for file_record in files:
            try:
                files_data.append({
                    'id': file_record.id,
                    'path': file_record.path,
                    'filename': file_record.filename,
                    'category': file_record.category.value,
                    'size': file_record.size,
                    'modified_date': file_record.modified_date.isoformat(),
                    'scanned_date': file_record.scanned_date.isoformat(),
                    'exists': file_record.exists
                })
            except Exception as e:
                current_app.logger.warning(f"Error serializing file record {file_record.id}: {e}")
                continue
        
        return jsonify({
            'files': files_data,
            'count': len(files_data),
            'offset': offset,
            'limit': limit,
            'total_requested': len(files)
        })
        
    except (ValidationError, DatabaseError, FileSystemError) as e:
        response_data, status_code = handle_api_error(e, "get files")
        return jsonify(response_data), status_code
    except Exception as e:
        response_data, status_code = handle_api_error(e, "get files")
        return jsonify(response_data), status_code


@api_bp.route('/files/stats', methods=['GET'])
def get_file_stats():
    """Get file statistics by category."""
    try:
        db = get_db_manager()
        
        # Get counts for each category
        stats = {}
        total_count = 0
        
        for category in FileCategory:
            criteria = SearchCriteria(category=category)
            files = db.search_files(criteria)
            count = len(files)
            stats[category.value] = count
            total_count += count
        
        stats['total'] = total_count
        
        return jsonify(stats)
        
    except DatabaseError as e:
        current_app.logger.warning(f"Database not initialized for stats: {e}")
        # Return zero stats if database is not initialized
        return jsonify({
            'total': 0,
            'graphics': 0,
            'lightburn': 0,
            'vector': 0
        })
    except Exception as e:
        current_app.logger.error(f"Error getting file stats: {e}")
        return jsonify({
            'total': 0,
            'graphics': 0,
            'lightburn': 0,
            'vector': 0
        })


@api_bp.route('/files/recent', methods=['GET'])
def get_recent_files():
    """Get recently scanned files."""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        db = get_db_manager()
        criteria = SearchCriteria(limit=limit)
        files = db.search_files(criteria)
        
        # Convert to JSON-serializable format
        files_data = []
        for file_record in files:
            files_data.append({
                'id': file_record.id,
                'path': file_record.path,
                'filename': file_record.filename,
                'category': file_record.category.value,
                'size': file_record.size,
                'modified_date': file_record.modified_date.isoformat(),
                'scanned_date': file_record.scanned_date.isoformat(),
                'exists': file_record.exists
            })
        
        return jsonify({'files': files_data})
        
    except DatabaseError as e:
        current_app.logger.warning(f"Database not initialized for recent files: {e}")
        # Return empty list if database is not initialized
        return jsonify({'files': []})
    except Exception as e:
        current_app.logger.error(f"Error getting recent files: {e}")
        return jsonify({'files': []})


@api_bp.route('/files/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Delete a specific file record."""
    try:
        db = get_db_manager()
        success = db.remove_file(file_id)
        
        if success:
            return jsonify({'message': 'File record deleted successfully'})
        else:
            return jsonify({'error': 'File record not found'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Error deleting file {file_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/scan', methods=['POST'])
def start_scan():
    """
    Start a directory scan operation.
    
    JSON body:
    - path: Directory path to scan
    - recursive: Whether to scan recursively (default: true)
    - include_hidden: Whether to include hidden files (default: false)
    """
    try:
        if _scan_state['active']:
            return jsonify({'error': 'Scan already in progress'}), 409
        
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'Directory path is required'}), 400
        
        scan_path = Path(data['path'])
        if not scan_path.exists():
            return jsonify({'error': 'Directory does not exist'}), 400
        
        if not scan_path.is_dir():
            return jsonify({'error': 'Path is not a directory'}), 400
        
        # Parse options
        recursive = data.get('recursive', True)
        include_hidden = data.get('include_hidden', False)
        
        options = ScanOptions(
            recursive=recursive,
            include_hidden=include_hidden,
            verbose=True
        )
        
        # Start scan in background thread
        def run_scan():
            try:
                _scan_state['active'] = True
                _scan_state['progress'] = {
                    'status': 'running',
                    'total_files': 0,
                    'categorized_files': 0,
                    'new_files': 0,
                    'errors': [],
                    'current_file': '',
                    'start_time': datetime.now().isoformat()
                }
                
                # Initialize database
                db = get_db_manager()
                db.initialize()
                
                # Create enhanced progress callback
                def progress_callback(current_file_path, categorized_count, total_count):
                    _scan_state['progress'].update({
                        'current_file': str(current_file_path) if current_file_path else '',
                        'categorized_files': categorized_count,
                        'total_files': total_count
                    })
                
                # Collect files with progress reporting
                file_records = []
                categorized_count = 0
                total_count = 0
                
                try:
                    # First pass: count total files for better progress reporting
                    _scan_state['progress']['status'] = 'counting'
                    
                    if options.recursive:
                        pattern = "**/*"
                    else:
                        pattern = "*"
                    
                    all_files = list(scan_path.glob(pattern))
                    all_files = [f for f in all_files if f.is_file()]
                    
                    if not options.include_hidden:
                        all_files = [f for f in all_files if not f.name.startswith('.')]
                    
                    total_count = len(all_files)
                    _scan_state['progress']['total_files'] = total_count
                    _scan_state['progress']['status'] = 'scanning'
                    
                    # Second pass: process files
                    scanner = FileScanner()
                    
                    for i, file_path in enumerate(all_files):
                        if not _scan_state['active']:  # Check for cancellation
                            break
                            
                        try:
                            # Update current file
                            progress_callback(file_path, categorized_count, total_count)
                            
                            # Get file metadata and categorization
                            file_record = scanner.get_file_metadata(file_path)
                            if file_record:
                                file_records.append(file_record)
                                categorized_count += 1
                                
                                # Update progress
                                _scan_state['progress']['categorized_files'] = categorized_count
                                
                        except Exception as e:
                            error_msg = f"Error processing {file_path}: {str(e)}"
                            _scan_state['progress']['errors'].append(error_msg)
                            current_app.logger.warning(error_msg)
                    
                    # Store results in database
                    if file_records and _scan_state['active']:
                        _scan_state['progress']['status'] = 'saving'
                        db.add_files_batch(file_records)
                        _scan_state['progress']['new_files'] = len(file_records)
                    
                    # Update final progress
                    if _scan_state['active']:
                        _scan_state['progress'].update({
                            'status': 'completed',
                            'total_files': total_count,
                            'categorized_files': categorized_count,
                            'new_files': len(file_records),
                            'current_file': '',
                            'end_time': datetime.now().isoformat()
                        })
                    else:
                        _scan_state['progress'].update({
                            'status': 'cancelled',
                            'end_time': datetime.now().isoformat()
                        })
                        
                except Exception as scan_error:
                    raise scan_error
                
            except Exception as e:
                current_app.logger.error(f"Scan error: {e}")
                _scan_state['progress'].update({
                    'status': 'error',
                    'error': str(e),
                    'end_time': datetime.now().isoformat()
                })
            finally:
                _scan_state['active'] = False
        
        # Start background thread
        thread = threading.Thread(target=run_scan)
        thread.daemon = True
        thread.start()
        _scan_state['thread'] = thread
        
        return jsonify({
            'message': 'Scan started successfully',
            'scan_id': 'current'  # For future enhancement with multiple scans
        })
        
    except Exception as e:
        current_app.logger.error(f"Error starting scan: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/scan/status', methods=['GET'])
def get_scan_status():
    """Get current scan status and progress."""
    try:
        return jsonify({
            'active': _scan_state['active'],
            'progress': _scan_state['progress'] or {}
        })
    except Exception as e:
        current_app.logger.error(f"Error getting scan status: {e}")
        # Return safe default status
        return jsonify({
            'active': False,
            'progress': {}
        })


@api_bp.route('/scan', methods=['DELETE'])
def stop_scan():
    """Stop the current scan operation."""
    try:
        if not _scan_state['active']:
            return jsonify({'error': 'No scan in progress'}), 400
        
        # Note: This is a simple implementation. In a production system,
        # you'd want more sophisticated cancellation handling
        _scan_state['progress']['status'] = 'cancelled'
        _scan_state['active'] = False
        
        return jsonify({'message': 'Scan stop requested'})
        
    except Exception as e:
        current_app.logger.error(f"Error stopping scan: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/init', methods=['POST'])
def initialize_system():
    """Initialize the database and system components."""
    try:
        db = get_db_manager()
        db.initialize()
        
        return jsonify({
            'message': 'System initialized successfully',
            'database_ready': True
        })
        
    except Exception as e:
        current_app.logger.error(f"Error initializing system: {e}")
        return jsonify({
            'error': 'Failed to initialize system',
            'message': str(e),
            'database_ready': False
        }), 500


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Check system health and database status."""
    try:
        db = get_db_manager()
        db_healthy = db.health_check()
        
        return jsonify({
            'status': 'healthy' if db_healthy else 'degraded',
            'database_ready': db_healthy,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'database_ready': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503


@api_bp.route('/search', methods=['GET'])
def search_files():
    """
    Search files with advanced criteria.
    Same as /files endpoint but with different naming for clarity.
    """
    return get_files()


@api_bp.route('/cleanup', methods=['POST'])
def start_cleanup():
    """
    Start database cleanup operation.
    
    JSON body:
    - dry_run: Whether to perform dry run (default: true)
    - batch_size: Number of files to process per batch (default: 1000)
    """
    try:
        if _cleanup_state['active']:
            return jsonify({'error': 'Cleanup already in progress'}), 409
        
        data = request.get_json() or {}
        dry_run = data.get('dry_run', True)
        batch_size = data.get('batch_size', 1000)
        
        # Start cleanup in background thread
        def run_cleanup():
            try:
                _cleanup_state['active'] = True
                _cleanup_state['progress'] = {
                    'status': 'running',
                    'total_checked': 0,
                    'removed_count': 0,
                    'errors': [],
                    'dry_run': dry_run,
                    'current_batch': 0,
                    'start_time': datetime.now().isoformat()
                }
                
                # Initialize database
                db = get_db_manager()
                
                # Enhanced cleanup with progress reporting
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        
                        # Get total count for progress tracking
                        cursor.execute("SELECT COUNT(*) FROM files WHERE file_exists = 1")
                        total_count = cursor.fetchone()[0]
                        
                        removed_files = []
                        errors = []
                        processed_count = 0
                        
                        # Process files in batches
                        offset = 0
                        batch_num = 0
                        
                        while offset < total_count and _cleanup_state['active']:
                            batch_num += 1
                            _cleanup_state['progress']['current_batch'] = batch_num
                            
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
                                if not _cleanup_state['active']:  # Check for cancellation
                                    break
                                    
                                try:
                                    path_obj = Path(file_path)
                                    if not path_obj.exists():
                                        removed_files.append(file_path)
                                        batch_to_remove.append(file_id)
                                
                                except (OSError, PermissionError, ValueError) as e:
                                    error_msg = f"Error checking {file_path}: {str(e)}"
                                    errors.append(error_msg)
                                    continue
                            
                            # Batch remove non-existent files from database
                            if batch_to_remove and not dry_run and _cleanup_state['active']:
                                cursor.executemany("DELETE FROM files WHERE id = ?", 
                                                 [(file_id,) for file_id in batch_to_remove])
                            
                            processed_count += len(batch_files)
                            offset += batch_size
                            
                            # Update progress
                            _cleanup_state['progress'].update({
                                'total_checked': processed_count,
                                'removed_count': len(removed_files),
                                'errors': errors
                            })
                        
                        if not dry_run and _cleanup_state['active']:
                            conn.commit()
                        
                        # Update final progress
                        if _cleanup_state['active']:
                            _cleanup_state['progress'].update({
                                'status': 'completed',
                                'total_checked': processed_count,
                                'removed_count': len(removed_files),
                                'removed_files': removed_files,
                                'errors': errors,
                                'dry_run': dry_run,
                                'end_time': datetime.now().isoformat()
                            })
                        else:
                            _cleanup_state['progress'].update({
                                'status': 'cancelled',
                                'end_time': datetime.now().isoformat()
                            })
                            
                except Exception as cleanup_error:
                    raise cleanup_error
                
            except Exception as e:
                current_app.logger.error(f"Cleanup error: {e}")
                _cleanup_state['progress'].update({
                    'status': 'error',
                    'error': str(e),
                    'end_time': datetime.now().isoformat()
                })
            finally:
                _cleanup_state['active'] = False
        
        # Start background thread
        thread = threading.Thread(target=run_cleanup)
        thread.daemon = True
        thread.start()
        _cleanup_state['thread'] = thread
        
        return jsonify({
            'message': 'Cleanup started successfully',
            'dry_run': dry_run
        })
        
    except Exception as e:
        current_app.logger.error(f"Error starting cleanup: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/cleanup/status', methods=['GET'])
def get_cleanup_status():
    """Get current cleanup status and progress."""
    try:
        return jsonify({
            'active': _cleanup_state['active'],
            'progress': _cleanup_state['progress'] or {}
        })
    except Exception as e:
        current_app.logger.error(f"Error getting cleanup status: {e}")
        # Return safe default status
        return jsonify({
            'active': False,
            'progress': {}
        })


@api_bp.route('/cleanup', methods=['DELETE'])
def stop_cleanup():
    """Stop the current cleanup operation."""
    try:
        if not _cleanup_state['active']:
            return jsonify({'error': 'No cleanup in progress'}), 400
        
        _cleanup_state['progress']['status'] = 'cancelled'
        _cleanup_state['active'] = False
        
        return jsonify({'message': 'Cleanup stop requested'})
        
    except Exception as e:
        current_app.logger.error(f"Error stopping cleanup: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/progress/scan')
def scan_progress_stream():
    """
    Server-Sent Events endpoint for real-time scan progress.
    """
    import json
    import time
    
    def generate():
        """Generate SSE data for scan progress."""
        try:
            # Send initial connection message
            initial_msg = json.dumps({'type': 'connected', 'message': 'Connected to scan progress stream'})
            yield f"data: {initial_msg}\n\n"
            
            last_progress = {}
            iterations = 0
            
            while iterations < 120:  # Max 60 seconds (120 * 0.5s)
                iterations += 1
                
                try:
                    current_progress = _scan_state['progress'].copy() if _scan_state['progress'] else {}
                    
                    # Only send updates when progress changes
                    if current_progress != last_progress:
                        progress_data = {
                            'type': 'progress',
                            'active': _scan_state['active'],
                            'progress': current_progress
                        }
                        
                        progress_msg = json.dumps(progress_data)
                        yield f"data: {progress_msg}\n\n"
                        last_progress = current_progress.copy()
                    
                    # Stop streaming if scan is not active and completed
                    if not _scan_state['active'] and current_progress.get('status') in ['completed', 'error', 'cancelled']:
                        finished_msg = json.dumps({'type': 'finished', 'message': 'Scan completed'})
                        yield f"data: {finished_msg}\n\n"
                        break
                    
                    # Send heartbeat every 10 iterations
                    if iterations % 10 == 0:
                        heartbeat_msg = json.dumps({'type': 'heartbeat', 'iteration': iterations})
                        yield f"data: {heartbeat_msg}\n\n"
                    
                except Exception as inner_e:
                    current_app.logger.error(f"SSE inner loop error: {inner_e}")
                    error_msg = json.dumps({'type': 'error', 'message': f'Inner error: {str(inner_e)}'})
                    yield f"data: {error_msg}\n\n"
                
                # Wait before next update
                time.sleep(0.5)
                
        except GeneratorExit:
            # Client disconnected
            current_app.logger.info("SSE client disconnected")
        except Exception as e:
            current_app.logger.error(f"SSE scan progress error: {e}")
            try:
                error_msg = json.dumps({'type': 'error', 'message': str(e)})
                yield f"data: {error_msg}\n\n"
            except:
                yield f"data: {{'type': 'error', 'message': 'Unknown error'}}\n\n"
    
    try:
        return current_app.response_class(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
    except Exception as e:
        current_app.logger.error(f"SSE endpoint error: {e}")
        return jsonify({'error': 'SSE endpoint failed', 'message': str(e)}), 500


@api_bp.route('/progress/cleanup')
def cleanup_progress_stream():
    """
    Server-Sent Events endpoint for real-time cleanup progress.
    """
    def generate():
        """Generate SSE data for cleanup progress."""
        try:
            import json
            import time
            
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to cleanup progress stream'})}\n\n"
            
            last_progress = {}
            
            while True:
                current_progress = _cleanup_state['progress'].copy() if _cleanup_state['progress'] else {}
                
                # Only send updates when progress changes
                if current_progress != last_progress:
                    progress_data = {
                        'type': 'progress',
                        'active': _cleanup_state['active'],
                        'progress': current_progress
                    }
                    
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    last_progress = current_progress.copy()
                
                # Stop streaming if cleanup is not active
                if not _cleanup_state['active'] and current_progress.get('status') in ['completed', 'error', 'cancelled']:
                    yield f"data: {json.dumps({'type': 'finished', 'message': 'Cleanup completed'})}\n\n"
                    break
                
                # Wait before next update
                time.sleep(0.5)  # Update every 500ms
                
        except GeneratorExit:
            # Client disconnected
            pass
        except Exception as e:
            current_app.logger.error(f"SSE cleanup progress error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return current_app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )