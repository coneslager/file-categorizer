# File Categorizer System

A tool for scanning and categorizing design files including graphics, LightBurn, and vector design files.

## Features

- Scan directories for design files
- Categorize files by type (graphics, lightburn, vector)
- Persistent SQLite database storage
- Command-line interface with rich formatting
- Web interface for browser-based management
- File cleanup and maintenance tools

## Installation

### From Source

1. Clone the repository:
```bash
git clone <repository-url>
cd file-categorizer
```

2. Install the package:
```bash
pip install -e .
```

### For Development

Install with development dependencies:
```bash
pip install -e ".[dev]"
```

### System Requirements

- Python 3.8 or higher
- SQLite3 (included with Python)
- Supported platforms: Windows, macOS, Linux

For detailed cross-platform compatibility information, see [CROSS_PLATFORM_COMPATIBILITY.md](CROSS_PLATFORM_COMPATIBILITY.md).

### Verify Installation

After installation, verify that the package is working correctly:

```bash
# Check if the command is available
file-categorizer --version

# Test basic functionality
file-categorizer --help

# Alternative command
file-cat --help

# Run as Python module
python -m src --help
```

## Usage

### CLI Interface

The File Categorizer provides a comprehensive command-line interface with the following commands:

#### Scanning Directories

```bash
# Basic directory scan
file-categorizer scan /path/to/directory

# Recursive scan with verbose output
file-categorizer scan /path/to/directory --recursive --verbose

# Scan with custom depth limit
file-categorizer scan /path/to/directory --max-depth 3

# Include hidden files
file-categorizer scan /path/to/directory --include-hidden
```

#### Searching and Listing Files

```bash
# Search for files by name
file-categorizer search "project"

# Search by category
file-categorizer search --category graphics

# Search with size filters
file-categorizer search --min-size 1000000 --max-size 10000000

# List all files
file-categorizer list

# List files by category with different output formats
file-categorizer list --category vector --format json
file-categorizer list --category lightburn --format csv

# Show only existing files
file-categorizer list --exists-only
```

#### Database Maintenance

```bash
# Preview cleanup (dry run)
file-categorizer cleanup --dry-run

# Perform actual cleanup
file-categorizer cleanup --verbose

# Cleanup with custom batch size
file-categorizer cleanup --batch-size 500
```

#### Web Interface

```bash
# Start web server on default port (5000)
file-categorizer web

# Start on custom port and host
file-categorizer web --port 8080 --host 0.0.0.0

# Start in debug mode
file-categorizer web --debug
```

#### Configuration Management

```bash
# Show current configuration
file-categorizer config show

# Set configuration values
file-categorizer config set database.timeout 30
file-categorizer config set scan.default_recursive true

# Reset to defaults
file-categorizer config reset

# Export configuration
file-categorizer config export config-backup.json
```

#### Alternative Command

You can also use the shorter alias:
```bash
file-cat scan /path/to/directory
file-cat search "filename"
file-cat web
```

### Web Interface

1. Start the web server:
```bash
file-categorizer web
```

2. Open your browser and navigate to `http://localhost:5000`

The web interface provides:
- Interactive file browsing and filtering
- Real-time scan progress with Server-Sent Events
- Search functionality with category filters
- Database cleanup tools with dry-run preview
- Responsive design for desktop and mobile devices

#### Web API Endpoints

The web interface also exposes REST API endpoints:

- `GET /api/files` - List files with optional filters
- `POST /api/scan` - Initiate directory scan
- `GET /api/search` - Search files
- `POST /api/cleanup` - Clean up database
- `DELETE /api/files/<id>` - Remove specific file
- `GET /api/progress` - Server-Sent Events for scan progress

### Programmatic Usage

You can also use the File Categorizer as a Python library:

```python
from src import FileScanner, DatabaseManager, FileCategory, ScanOptions

# Initialize components
scanner = FileScanner()
db_manager = DatabaseManager()
db_manager.initialize()

# Scan a directory
from pathlib import Path
options = ScanOptions(recursive=True, verbose=False)
result = scanner.scan_directory(Path("/path/to/directory"), options)

# Search the database
from src import SearchCriteria
criteria = SearchCriteria(category=FileCategory.GRAPHICS, limit=50)
files = db_manager.search_files(criteria)

# Process results
for file_record in files:
    print(f"{file_record.filename} - {file_record.category.value}")
```

## Development

### Setup Development Environment

1. Clone the repository:
```bash
git clone <repository-url>
cd file-categorizer
```

2. Install development dependencies:
```bash
pip install -e ".[dev]"
```

3. Run tests:
```bash
pytest
```

4. Run code formatting:
```bash
black src/
```

5. Run linting:
```bash
flake8 src/
```

### Project Structure

```
src/
├── __init__.py          # Package initialization and exports
├── __main__.py          # Main entry point for python -m src
├── cli/                 # Command-line interface
│   └── main.py         # CLI commands and options
├── core/               # Core business logic
│   ├── models.py       # Data models and enums
│   ├── scanner.py      # File scanning logic
│   ├── database.py     # Database operations
│   ├── config.py       # Configuration management
│   └── exceptions.py   # Custom exceptions
└── web/                # Web interface
    ├── app.py          # Flask application
    ├── blueprints/     # API endpoints
    ├── templates/      # HTML templates
    └── static/         # CSS, JS, images
```

## File Categories

- **Graphics**: JPG, PNG, GIF, BMP, TIFF, WebP, ICO
- **LightBurn**: .lbrn, .lbrn2 files
- **Vector**: AI, SVG, EPS files

## License

MIT License