# Cross-Platform Compatibility Guide

This document outlines the cross-platform compatibility features and testing procedures for the File Categorizer System.

## Supported Platforms

The File Categorizer System has been tested and verified to work on:

- **Windows** (Windows 10, Windows 11)
- **macOS** (macOS 10.15+)
- **Linux** (Ubuntu 18.04+, CentOS 7+, other major distributions)

## Platform-Specific Considerations

### File Path Handling

The application uses Python's `pathlib.Path` for cross-platform path handling:

- **Windows**: Supports both forward slashes (`/`) and backslashes (`\`) as path separators
- **POSIX (Linux/macOS)**: Uses forward slashes (`/`) as path separators
- **UNC Paths**: Windows UNC paths (`\\server\share`) are supported
- **Home Directory**: Tilde expansion (`~`) works on all platforms

### File System Case Sensitivity

- **Windows**: Case-insensitive file system (default NTFS)
- **macOS**: Case-insensitive by default (HFS+/APFS), but can be case-sensitive
- **Linux**: Case-sensitive file system (ext4, etc.)

The application handles file extensions case-insensitively across all platforms:
- `.JPG`, `.jpg`, `.Jpg` are all recognized as graphics files
- `.SVG`, `.svg` are both recognized as vector files
- `.LBRN2`, `.lbrn2` are both recognized as LightBurn files

### Database Portability

The SQLite database files are fully portable across platforms:

- Database files created on Windows can be used on Linux/macOS and vice versa
- File paths stored in the database maintain their original format
- No platform-specific database schema differences

### Special Characters in File Names

The application handles special characters in file names across platforms:

- **Spaces**: Supported on all platforms
- **Unicode**: Full Unicode support for international characters
- **Special symbols**: `()[]{}` supported on all platforms
- **Platform restrictions**: Respects OS-specific filename limitations

### Long Path Support

- **Windows**: Supports paths up to 260 characters (standard limit) or 32,767 characters (with long path support enabled)
- **Linux/macOS**: Supports paths up to 4,096 characters (typical filesystem limit)

## Testing Cross-Platform Compatibility

### Automated Testing

Run the comprehensive cross-platform test suite:

```bash
# Run the platform compatibility test script
python test_platform_compatibility.py

# Run pytest cross-platform tests
pytest tests/test_cross_platform.py -v
```

### Manual Testing Checklist

#### Installation Testing
- [ ] Package installs correctly with `pip install -e .`
- [ ] Console scripts (`file-categorizer`, `file-cat`) are available
- [ ] Python module execution works (`python -m src`)

#### CLI Testing
- [ ] All CLI commands work with platform-specific paths
- [ ] Configuration file loading works with platform paths
- [ ] Log file creation works in platform-appropriate locations

#### File Operations Testing
- [ ] Directory scanning works with platform-specific path formats
- [ ] File categorization works with case variations
- [ ] Special characters in filenames are handled correctly
- [ ] Long paths are supported (within OS limits)

#### Database Testing
- [ ] Database creation works in platform-appropriate locations
- [ ] File paths are stored and retrieved correctly
- [ ] Database files can be copied between platforms
- [ ] Cleanup operations work correctly

#### Web Interface Testing
- [ ] Web server starts on all platforms
- [ ] Static files are served correctly
- [ ] API endpoints handle platform-specific paths
- [ ] File upload/scan operations work

## Platform-Specific Installation Notes

### Windows

```bash
# Install Python 3.8+ from python.org or Microsoft Store
# Install the package
pip install -e .

# Verify installation
file-categorizer --version
```

**Windows-specific features:**
- Supports Windows-style paths (`C:\Users\...`)
- Works with UNC network paths (`\\server\share`)
- Handles Windows file permissions correctly

### macOS

```bash
# Install Python 3.8+ (via Homebrew recommended)
brew install python

# Install the package
pip3 install -e .

# Verify installation
file-categorizer --version
```

**macOS-specific features:**
- Handles case-insensitive HFS+/APFS filesystems
- Supports macOS file attributes and permissions
- Works with macOS-specific path conventions

### Linux

```bash
# Install Python 3.8+ (distribution-specific)
# Ubuntu/Debian:
sudo apt update && sudo apt install python3 python3-pip

# CentOS/RHEL:
sudo yum install python3 python3-pip

# Install the package
pip3 install -e .

# Verify installation
file-categorizer --version
```

**Linux-specific features:**
- Handles case-sensitive filesystems correctly
- Supports Linux file permissions and ownership
- Works with various filesystem types (ext4, xfs, btrfs, etc.)

## Configuration Considerations

### Default Paths

The application uses platform-appropriate default paths:

- **Windows**: `%USERPROFILE%\.file_categorizer\`
- **macOS**: `~/.file_categorizer/`
- **Linux**: `~/.file_categorizer/`

### Configuration Files

Configuration files use platform-appropriate formats:
- INI format for cross-platform compatibility
- UTF-8 encoding for international character support
- Platform-specific path separators handled automatically

### Log Files

Log files are created in platform-appropriate locations:
- **Windows**: `%USERPROFILE%\.file_categorizer\logs\`
- **macOS/Linux**: `~/.file_categorizer/logs/`

## Troubleshooting Platform Issues

### Windows Issues

**Long Path Support:**
If you encounter path length issues on Windows, enable long path support:
1. Open Group Policy Editor (`gpedit.msc`)
2. Navigate to: Computer Configuration > Administrative Templates > System > Filesystem
3. Enable "Enable Win32 long paths"

**Permission Issues:**
Run Command Prompt as Administrator if you encounter permission errors.

### macOS Issues

**Case Sensitivity:**
If you have a case-sensitive APFS volume, ensure file references match exact case.

**Permission Issues:**
Grant Terminal/Python access to folders in System Preferences > Security & Privacy.

### Linux Issues

**Permission Issues:**
Ensure your user has read/write access to the directories you want to scan:
```bash
chmod +r /path/to/scan
```

**SELinux:**
On SELinux-enabled systems, you may need to adjust security contexts for database files.

## Performance Considerations

### File System Performance

- **Windows NTFS**: Good performance with large directories
- **macOS APFS**: Excellent performance with metadata operations
- **Linux ext4**: Good general performance, excellent with large files

### Database Performance

- **Windows**: SQLite WAL mode provides good concurrent access
- **macOS**: Benefits from APFS copy-on-write features
- **Linux**: Excellent performance on modern filesystems

## Continuous Integration

The project includes CI/CD configurations for testing across platforms:

- **GitHub Actions**: Tests on Windows, macOS, and Ubuntu
- **Platform Matrix**: Python 3.8, 3.9, 3.10, 3.11 on each platform
- **Automated Testing**: Full test suite runs on each platform

## Contributing Platform Support

When contributing code that may affect cross-platform compatibility:

1. Test on at least two different platforms
2. Use `pathlib.Path` for all file operations
3. Avoid platform-specific system calls
4. Add appropriate tests to `tests/test_cross_platform.py`
5. Update this documentation if adding platform-specific features

## Known Limitations

- **Windows**: UNC paths may have performance implications
- **macOS**: Case-insensitive filesystems may cause confusion with similarly named files
- **Linux**: Some distributions may have restrictive default permissions
- **All Platforms**: Very long paths (>4000 characters) may cause issues on some filesystems