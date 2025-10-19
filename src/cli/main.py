"""Main CLI interface for the File Categorizer System."""

import click
import json
import csv
import logging
import sys
from pathlib import Path
from typing import List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from ..core.scanner import FileScanner
from ..core.database import DatabaseManager
from ..core.models import ScanOptions, FileRecord
from ..core.exceptions import (
    FileCategorizeError, FileSystemError, DatabaseError, ScanError,
    PermissionError, PathNotFoundError, DatabaseConnectionError
)
from ..core.error_handler import ErrorHandler

# Initialize Rich console and error handler
console = Console()
error_handler = ErrorHandler()


@click.group()
@click.version_option(version="0.1.0")
@click.option('--config', '-c', type=click.Path(path_type=Path), 
              help='Configuration file path')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']), 
              help='Set logging level (overrides config)')
@click.option('--log-file', type=click.Path(path_type=Path), 
              help='Log file path (overrides config)')
@click.pass_context
def cli(ctx, config, log_level, log_file):
    """File Categorizer System - Scan and categorize design files."""
    # Set up configuration
    from ..core.config import setup_config
    from ..core.logging_config import setup_logging, LoggingConfig
    
    # Initialize configuration
    config_manager = setup_config(config)
    app_config = config_manager.get_config()
    
    # Override logging config if command line options provided
    if log_level or log_file:
        logging_config = LoggingConfig(
            level=log_level or app_config.logging.level,
            file_path=log_file or app_config.logging.file_path,
            file_enabled=app_config.logging.file_enabled,
            console_enabled=app_config.logging.console_enabled,
            format=app_config.logging.format,
            file_max_size_mb=app_config.logging.file_max_size_mb,
            file_backup_count=app_config.logging.file_backup_count
        )
    else:
        logging_config = app_config.logging
    
    # Set up logging
    setup_logging(logging_config)
    
    # Store config in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['config'] = app_config
    ctx.obj['config_manager'] = config_manager


@cli.command()
@click.argument("directory", type=click.Path(path_type=Path))
@click.option("--recursive/--no-recursive", default=None, help="Scan directories recursively (default from config)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--max-depth", type=int, help="Maximum directory depth to scan (default from config)")
@click.option("--include-hidden", is_flag=True, help="Include hidden files in scan (default from config)")
@click.pass_context
def scan(ctx, directory: Path, recursive: bool, verbose: bool, max_depth: int, include_hidden: bool):
    """Scan a directory for categorizable files."""
    try:
        # Get configuration
        app_config = ctx.obj['config']
        
        # Use config defaults if options not specified
        if recursive is None:
            recursive = app_config.scan.default_recursive
        if max_depth is None:
            max_depth = app_config.scan.default_max_depth
        if not include_hidden:
            include_hidden = app_config.scan.default_include_hidden
        
        # Validate directory path
        if not directory.exists():
            raise PathNotFoundError(f"Directory does not exist: {directory}")
        
        if not directory.is_dir():
            raise FileSystemError(f"Path is not a directory: {directory}")
        
        # Initialize database with error handling
        try:
            db_manager = DatabaseManager(config=app_config)
            
            # Perform health check
            if not db_manager.health_check():
                console.print("[yellow]Warning: Database health check failed, attempting to reinitialize...[/yellow]")
            
            db_manager.initialize()
            
        except DatabaseError as e:
            handle_cli_error(e, "database initialization")
            raise click.Abort()
        
        # Create scan options
        options = ScanOptions(
            recursive=recursive,
            verbose=verbose,
            max_depth=max_depth,
            include_hidden=include_hidden
        )
        
        # Initialize scanner
        scanner = FileScanner(config=app_config)
        
        if verbose:
            console.print(f"[bold blue]Starting scan of {directory}[/bold blue]")
            console.print(f"Options: recursive={recursive}, max_depth={max_depth}, include_hidden={include_hidden}")
        
        # Collect file records with progress bar and error handling
        file_records = []
        scan_errors = []
        
        try:
            if verbose:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
                ) as progress:
                    scan_task = progress.add_task("Scanning files...", total=None)
                    
                    try:
                        for file_record in scanner.scan_files(directory, options):
                            file_records.append(file_record)
                            progress.update(scan_task, description=f"Found {len(file_records)} categorizable files...")
                    except KeyboardInterrupt:
                        scanner.cancel_scan()
                        console.print("\n[yellow]Scan cancelled by user[/yellow]")
                        raise click.Abort()
                    
                    progress.update(scan_task, completed=True, description=f"Scan complete - found {len(file_records)} files")
            else:
                # Simple scan without progress bar
                try:
                    for file_record in scanner.scan_files(directory, options):
                        file_records.append(file_record)
                except KeyboardInterrupt:
                    scanner.cancel_scan()
                    console.print("\n[yellow]Scan cancelled by user[/yellow]")
                    raise click.Abort()
        
        except (FileSystemError, PermissionError) as e:
            handle_cli_error(e, "file scanning")
            raise click.Abort()
        
        # Perform the basic scan for statistics
        try:
            result = scanner.scan_directory(directory, options)
        except ScanError as e:
            handle_cli_error(e, "directory scan")
            raise click.Abort()
        
        # Add files to database in batch with progress and error handling
        if file_records:
            try:
                if verbose:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console
                    ) as progress:
                        db_task = progress.add_task("Adding files to database...", total=None)
                        db_manager.add_files_batch(file_records)
                        progress.update(db_task, completed=True, description="Database update complete")
                else:
                    db_manager.add_files_batch(file_records)
            except DatabaseError as e:
                handle_cli_error(e, "database update")
                console.print("[yellow]Files were scanned but could not be saved to database.[/yellow]")
                # Don't abort here, show scan results anyway
        
        # Display results with Rich formatting
        console.print(f"\n[bold green]✓ Scan completed[/bold green] in {result.duration:.2f} seconds")
        console.print(f"Total files processed: [bold]{result.total_files}[/bold]")
        console.print(f"Categorizable files found: [bold cyan]{len(file_records)}[/bold cyan]")
        console.print(f"Files added to database: [bold green]{len(file_records)}[/bold green]")
        
        if result.errors:
            console.print(f"[bold yellow]Warnings: {len(result.errors)}[/bold yellow]")
            if verbose:
                for error in result.errors[:10]:  # Show first 10 errors
                    console.print(f"  [yellow]- {error}[/yellow]")
                if len(result.errors) > 10:
                    console.print(f"  [dim]... and {len(result.errors) - 10} more warnings[/dim]")
        
        if len(file_records) > 0 and result.total_files > 0:
            success_rate = len(file_records) / result.total_files * 100
            console.print(f"Success rate: [bold]{success_rate:.1f}%[/bold]")
            
    except (PathNotFoundError, FileSystemError, PermissionError) as e:
        handle_cli_error(e, "scan")
        raise click.Abort()
    except click.Abort:
        raise
    except Exception as e:
        handle_cli_error(e, "scan")
        raise click.Abort()


@cli.command()
@click.argument("query", required=False)
@click.option("--category", "-c", type=click.Choice(["graphics", "lightburn", "vector"]), help="Filter by file category")
@click.option("--format", "-f", type=click.Choice(["table", "json", "csv"]), default="table", help="Output format")
@click.option("--min-size", type=int, help="Minimum file size in bytes")
@click.option("--max-size", type=int, help="Maximum file size in bytes")
@click.option("--limit", type=int, default=100, help="Maximum number of results to return")
def search(query: str, category: str, format: str, min_size: int, max_size: int, limit: int):
    """Search for files in the database."""
    try:
        # Initialize database
        db_manager = DatabaseManager()
        db_manager.initialize()
        
        # Create search criteria
        from ..core.models import SearchCriteria, FileCategory
        
        criteria = SearchCriteria(
            query=query,
            category=FileCategory(category) if category else None,
            min_size=min_size,
            max_size=max_size,
            limit=limit
        )
        
        # Perform search
        results = db_manager.search_files(criteria)
        
        # Display results
        _display_file_results(results, format)
        
        if not results:
            console.print("[yellow]No files found matching the search criteria.[/yellow]")
        else:
            console.print(f"\n[bold green]Found {len(results)} file(s)[/bold green]")
            
    except Exception as e:
        click.echo(f"Error during search: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--category", "-c", type=click.Choice(["graphics", "lightburn", "vector"]), help="Filter by file category")
@click.option("--format", "-f", type=click.Choice(["table", "json", "csv"]), default="table", help="Output format")
@click.option("--limit", type=int, default=100, help="Maximum number of results to return")
@click.option("--exists-only", is_flag=True, help="Only show files that still exist on disk")
def list(category: str, format: str, limit: int, exists_only: bool):
    """List files in the database."""
    try:
        # Initialize database
        db_manager = DatabaseManager()
        db_manager.initialize()
        
        # Create search criteria for listing
        from ..core.models import SearchCriteria, FileCategory
        
        criteria = SearchCriteria(
            category=FileCategory(category) if category else None,
            limit=limit
        )
        
        # Get all files matching criteria
        results = db_manager.search_files(criteria)
        
        # Filter by existence if requested
        if exists_only:
            results = [f for f in results if f.exists]
        
        # Display results
        _display_file_results(results, format)
        
        if not results:
            console.print("[yellow]No files found in the database.[/yellow]")
        else:
            console.print(f"\n[bold green]Listed {len(results)} file(s)[/bold green]")
            
    except Exception as e:
        click.echo(f"Error listing files: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview cleanup without making changes")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--batch-size", type=int, default=1000, help="Number of files to process in each batch")
def cleanup(dry_run: bool, verbose: bool, batch_size: int):
    """Clean up database by removing non-existent files."""
    try:
        # Initialize database
        db_manager = DatabaseManager()
        db_manager.initialize()
        
        if verbose:
            console.print("[bold blue]Starting database cleanup...[/bold blue]")
            if dry_run:
                console.print("[bold yellow]DRY RUN MODE: No changes will be made to the database[/bold yellow]")
            console.print(f"Processing files in batches of {batch_size}")
        
        # Perform cleanup with progress bar
        if verbose:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                cleanup_task = progress.add_task("Checking file existence...", total=None)
                result = db_manager.cleanup_database(dry_run=dry_run, batch_size=batch_size)
                progress.update(cleanup_task, completed=True, description="Cleanup analysis complete")
        else:
            result = db_manager.cleanup_database(dry_run=dry_run, batch_size=batch_size)
        
        # Display results with Rich formatting
        status_text = "preview" if dry_run else "completed"
        status_color = "yellow" if dry_run else "green"
        console.print(f"\n[bold {status_color}]✓ Cleanup {status_text}[/bold {status_color}]")
        console.print(f"Files checked: [bold]{result.total_checked}[/bold]")
        
        removed_text = "would be removed" if dry_run else "removed"
        console.print(f"Files {removed_text}: [bold red]{result.removed_count}[/bold red]")
        
        if result.removed_count > 0:
            cleanup_rate = result.cleanup_rate * 100
            console.print(f"Cleanup rate: [bold]{cleanup_rate:.1f}%[/bold]")
            
            if verbose and result.removed_files:
                title = "Files that would be removed:" if dry_run else "Removed files:"
                console.print(f"\n[bold]{title}[/bold]")
                for i, file_path in enumerate(result.removed_files[:20]):  # Show first 20
                    console.print(f"  [red]- {file_path}[/red]")
                
                if len(result.removed_files) > 20:
                    remaining = len(result.removed_files) - 20
                    console.print(f"  [dim]... and {remaining} more files[/dim]")
        
        if result.errors:
            console.print(f"\n[bold red]Errors encountered: {len(result.errors)}[/bold red]")
            if verbose:
                for error in result.errors[:10]:  # Show first 10 errors
                    console.print(f"  [red]- {error}[/red]")
                if len(result.errors) > 10:
                    remaining = len(result.errors) - 10
                    console.print(f"  [dim]... and {remaining} more errors[/dim]")
        
        if dry_run and result.removed_count > 0:
            console.print(f"\n[bold yellow]To actually remove these files, run the command without --dry-run[/bold yellow]")
            
    except Exception as e:
        click.echo(f"Error during cleanup: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option("--port", "-p", default=5000, help="Port to run the web server on")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind the web server to")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def web(port: int, host: str, debug: bool):
    """Start the web interface."""
    try:
        from ..web.app import create_app
        
        console.print(f"[bold blue]Starting File Categorizer web interface...[/bold blue]")
        console.print(f"Server: http://{host}:{port}")
        console.print(f"Debug mode: {'enabled' if debug else 'disabled'}")
        console.print("\n[bold green]Press Ctrl+C to stop the server[/bold green]\n")
        
        # Initialize database
        db_manager = DatabaseManager()
        db_manager.initialize()
        
        # Create and run Flask app
        app = create_app({
            'DEBUG': debug,
            'HOST': host,
            'PORT': port
        })
        
        app.run(host=host, port=port, debug=debug)
        
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Server stopped by user[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]Error starting web server: {e}[/bold red]")
        raise click.Abort()


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command('show')
@click.pass_context
def show_config(ctx):
    """Show current configuration."""
    app_config = ctx.obj['config']
    
    console.print("[bold blue]Current Configuration:[/bold blue]\n")
    
    # Database configuration
    console.print("[bold]Database:[/bold]")
    console.print(f"  Path: {app_config.database.path}")
    console.print(f"  Timeout: {app_config.database.timeout}s")
    console.print(f"  Max connections: {app_config.database.max_connections}")
    console.print(f"  Backup enabled: {app_config.database.backup_enabled}")
    console.print(f"  Backup interval: {app_config.database.backup_interval_hours}h")
    
    # Scan configuration
    console.print("\n[bold]Scan:[/bold]")
    console.print(f"  Default recursive: {app_config.scan.default_recursive}")
    console.print(f"  Default include hidden: {app_config.scan.default_include_hidden}")
    console.print(f"  Default max depth: {app_config.scan.default_max_depth}")
    console.print(f"  Batch size: {app_config.scan.batch_size}")
    console.print(f"  Progress update interval: {app_config.scan.progress_update_interval}s")
    console.print(f"  Max file size: {app_config.scan.max_file_size_mb}MB")
    
    # Web configuration
    console.print("\n[bold]Web:[/bold]")
    console.print(f"  Host: {app_config.web.host}")
    console.print(f"  Port: {app_config.web.port}")
    console.print(f"  Debug: {app_config.web.debug}")
    console.print(f"  Max content length: {app_config.web.max_content_length} bytes")
    console.print(f"  Session timeout: {app_config.web.session_timeout_minutes} minutes")
    
    # Logging configuration
    console.print("\n[bold]Logging:[/bold]")
    console.print(f"  Level: {app_config.logging.level}")
    console.print(f"  File enabled: {app_config.logging.file_enabled}")
    console.print(f"  File path: {app_config.logging.file_path}")
    console.print(f"  File max size: {app_config.logging.file_max_size_mb}MB")
    console.print(f"  File backup count: {app_config.logging.file_backup_count}")
    console.print(f"  Console enabled: {app_config.logging.console_enabled}")


@config.command('set')
@click.argument('key')
@click.argument('value')
@click.pass_context
def set_config(ctx, key, value):
    """Set a configuration value. Use dot notation for nested keys (e.g., database.timeout)."""
    config_manager = ctx.obj['config_manager']
    app_config = ctx.obj['config']
    
    try:
        # Parse nested key
        keys = key.split('.')
        if len(keys) != 2:
            raise ValueError("Key must be in format 'section.key' (e.g., 'database.timeout')")
        
        section, setting = keys
        
        # Get the section object
        if not hasattr(app_config, section):
            raise ValueError(f"Unknown configuration section: {section}")
        
        section_obj = getattr(app_config, section)
        
        if not hasattr(section_obj, setting):
            raise ValueError(f"Unknown setting '{setting}' in section '{section}'")
        
        # Get current value to determine type
        current_value = getattr(section_obj, setting)
        
        # Convert value to appropriate type
        if isinstance(current_value, bool):
            converted_value = value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(current_value, int):
            converted_value = int(value)
        elif isinstance(current_value, float):
            converted_value = float(value)
        elif isinstance(current_value, Path):
            converted_value = Path(value)
        else:
            converted_value = value
        
        # Set the value
        setattr(section_obj, setting, converted_value)
        
        # Save configuration
        config_manager.save_to_file()
        
        console.print(f"[green]✓[/green] Set {key} = {converted_value}")
        
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error setting configuration:[/red] {e}")
        raise click.Abort()


@config.command('reset')
@click.confirmation_option(prompt='Are you sure you want to reset all configuration to defaults?')
@click.pass_context
def reset_config(ctx):
    """Reset configuration to default values."""
    config_manager = ctx.obj['config_manager']
    
    try:
        config_manager.reset_to_defaults()
        console.print("[green]✓ Configuration reset to defaults[/green]")
    except Exception as e:
        console.print(f"[red]Error resetting configuration:[/red] {e}")
        raise click.Abort()


@config.command('export')
@click.argument('file_path', type=click.Path(path_type=Path))
@click.pass_context
def export_config(ctx, file_path):
    """Export configuration to JSON file."""
    config_manager = ctx.obj['config_manager']
    
    try:
        config_manager.export_to_json(file_path)
        console.print(f"[green]✓ Configuration exported to {file_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error exporting configuration:[/red] {e}")
        raise click.Abort()


def _display_file_results(results: List[FileRecord], format: str):
    """Display file results in the specified format."""
    if not results:
        return
    
    if format == "json":
        # Convert to JSON-serializable format
        json_data = []
        for file_record in results:
            json_data.append({
                "id": file_record.id,
                "path": file_record.path,
                "filename": file_record.filename,
                "category": file_record.category.value,
                "size": file_record.size,
                "modified_date": file_record.modified_date.isoformat(),
                "scanned_date": file_record.scanned_date.isoformat(),
                "exists": file_record.exists
            })
        click.echo(json.dumps(json_data, indent=2))
        
    elif format == "csv":
        # Output CSV format
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["ID", "Path", "Filename", "Category", "Size", "Modified Date", "Scanned Date", "Exists"])
        
        # Write data rows
        for file_record in results:
            writer.writerow([
                file_record.id,
                file_record.path,
                file_record.filename,
                file_record.category.value,
                file_record.size,
                file_record.modified_date.isoformat(),
                file_record.scanned_date.isoformat(),
                file_record.exists
            ])
        
        click.echo(output.getvalue().strip())
        
    else:  # table format (default) - use Rich table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Filename", style="cyan", no_wrap=False, max_width=30)
        table.add_column("Category", style="green", justify="center")
        table.add_column("Size", justify="right")
        table.add_column("Modified", style="blue")
        table.add_column("Path", style="dim", no_wrap=False, max_width=50)
        
        for file_record in results:
            # Format file size
            size_str = _format_file_size(file_record.size)
            
            # Format modified date
            modified_str = file_record.modified_date.strftime("%Y-%m-%d %H:%M")
            
            # Get category color
            category_color = _get_category_color(file_record.category.value)
            
            # Format filename with status indicator
            filename = file_record.filename
            if not file_record.exists:
                filename = f"[red][MISSING][/red] {filename}"
            
            # Add row to table
            table.add_row(
                filename,
                f"[{category_color}]{file_record.category.value}[/{category_color}]",
                size_str,
                modified_str,
                file_record.path
            )
        
        console.print(table)


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def _get_category_color(category: str) -> str:
    """Get color for file category."""
    colors = {
        "graphics": "cyan",
        "lightburn": "yellow",
        "vector": "magenta"
    }
    return colors.get(category, "white")


def setup_logging(log_level: str, log_file: str = None):
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Set up handlers
    handlers = []
    
    if log_file:
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    else:
        # Console handler (stderr to avoid interfering with CLI output)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        format=log_format
    )
    
    # Set specific logger levels
    logging.getLogger('src.core').setLevel(getattr(logging, log_level.upper()))


def handle_cli_error(error: Exception, operation: str = "operation") -> None:
    """
    Handle CLI errors with appropriate user feedback.
    
    Args:
        error: The exception that occurred
        operation: Description of the operation that failed
    """
    if isinstance(error, PathNotFoundError):
        console.print(f"[bold red]Error:[/bold red] {error}")
        console.print("[yellow]Please check that the path exists and is accessible.[/yellow]")
    elif isinstance(error, PermissionError):
        console.print(f"[bold red]Permission Error:[/bold red] {error}")
        console.print("[yellow]Please check file/directory permissions or run with appropriate privileges.[/yellow]")
    elif isinstance(error, DatabaseConnectionError):
        console.print(f"[bold red]Database Error:[/bold red] {error}")
        console.print("[yellow]Please check that the database directory is writable.[/yellow]")
    elif isinstance(error, DatabaseError):
        console.print(f"[bold red]Database Error:[/bold red] {error}")
        console.print("[yellow]Try running the command again. If the problem persists, the database may be corrupted.[/yellow]")
    elif isinstance(error, ScanError):
        console.print(f"[bold red]Scan Error:[/bold red] {error}")
        console.print("[yellow]The scan operation encountered an error. Some files may not have been processed.[/yellow]")
    elif isinstance(error, FileSystemError):
        console.print(f"[bold red]File System Error:[/bold red] {error}")
        console.print("[yellow]Please check file system permissions and available space.[/yellow]")
    elif isinstance(error, FileCategorizeError):
        console.print(f"[bold red]Error:[/bold red] {error}")
    else:
        console.print(f"[bold red]Unexpected Error:[/bold red] {error}")
        console.print("[yellow]An unexpected error occurred. Please check the logs for more details.[/yellow]")
    
    # Log the full error for debugging
    logging.getLogger(__name__).error(f"CLI error in {operation}: {error}", exc_info=True)


if __name__ == "__main__":
    cli()