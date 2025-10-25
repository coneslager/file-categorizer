"""Flask web application for the File Categorizer System."""

import logging
import traceback
from flask import Flask, render_template, request, jsonify
from .blueprints.api import api_bp
from .blueprints.main import main_bp
from ..core.exceptions import DatabaseError, FileSystemError, FileCategorizeError


def create_app(config=None):
    """
    Create and configure the Flask application.
    
    Args:
        config: Configuration object or dictionary
        
    Returns:
        Configured Flask application
    """
    app = Flask(__name__, 
                static_folder='static',
                template_folder='templates')
    
    # Default configuration
    app.config.update({
        'SECRET_KEY': 'dev-key-change-in-production',
        'JSON_SORT_KEYS': False,
        'TEMPLATES_AUTO_RELOAD': True,  # Disable template caching
        'SEND_FILE_MAX_AGE_DEFAULT': 0,  # Disable static file caching
    })
    
    if config:
        app.config.update(config)
    
    # Disable template caching in debug mode
    if app.config.get('DEBUG', False):
        app.jinja_env.auto_reload = True
        app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Configure logging
    if not app.debug:
        # Set up file logging for production
        import os
        from logging.handlers import RotatingFileHandler
        
        log_dir = os.path.join(os.path.expanduser('~'), '.file_categorizer', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'web_app.log'),
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('File Categorizer web application startup')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'API endpoint not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}', exc_info=True)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }), 500
        
        error_details = None
        if app.debug:
            error_details = traceback.format_exc()
        
        return render_template('errors/500.html', error_details=error_details), 500
    
    @app.errorhandler(DatabaseError)
    def database_error(error):
        app.logger.error(f'Database Error: {error}', exc_info=True)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Database error',
                'message': str(error)
            }), 503
        
        error_details = None
        if app.debug:
            error_details = traceback.format_exc()
        
        return render_template('errors/database_error.html', 
                             error_message=str(error),
                             error_details=error_details), 503
    
    @app.errorhandler(FileSystemError)
    def filesystem_error(error):
        app.logger.error(f'File System Error: {error}', exc_info=True)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'File system error',
                'message': str(error)
            }), 400
        
        return render_template('errors/500.html', 
                             error_details=str(error) if app.debug else None), 500
    
    @app.errorhandler(FileCategorizeError)
    def categorize_error(error):
        app.logger.error(f'Categorization Error: {error}', exc_info=True)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Application error',
                'message': str(error)
            }), 400
        
        return render_template('errors/500.html',
                             error_details=str(error) if app.debug else None), 500
    
    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.error(f'Unexpected Error: {error}', exc_info=True)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Unexpected error',
                'message': 'An unexpected error occurred'
            }), 500
        
        error_details = None
        if app.debug:
            error_details = traceback.format_exc()
        
        return render_template('errors/500.html', error_details=error_details), 500
    
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host='127.0.0.1', port=5000)