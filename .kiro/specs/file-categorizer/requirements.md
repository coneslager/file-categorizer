# Requirements Document

## Introduction

A file categorization and management system that scans hard drives to identify, categorize, and manage graphics files, LightBurn files, and vector design files. The system provides both an interactive CLI and a lightweight web interface for file management operations with persistent database storage.

## Glossary

- **File_Categorizer_System**: The complete application including CLI and web components
- **Graphics_Files**: Image files including JPG, PNG, GIF, BMP, TIFF, and other common image formats
- **LightBurn_Files**: Files with .lbrn and .lbrn2 extensions used by LightBurn laser cutting software
- **Vector_Design_Files**: Files including .ai (Illustrator), .svg (SVG), and Inkscape files (.svg, .eps)
- **File_Database**: SQLite database storing file metadata and categorization information
- **Scan_Operation**: Process of traversing directory structures to identify and categorize files
- **CLI_Interface**: Command-line interface for system operations
- **Web_Interface**: Browser-based interface for system operations

## Requirements

### Requirement 1

**User Story:** As a designer, I want to scan my hard drive for design files, so that I can organize and manage my scattered file collection.

#### Acceptance Criteria

1. WHEN the user initiates a scan operation, THE File_Categorizer_System SHALL traverse specified directory paths recursively
2. WHILE scanning directories, THE File_Categorizer_System SHALL identify files by extension matching Graphics_Files, LightBurn_Files, and Vector_Design_Files
3. THE File_Categorizer_System SHALL store file metadata including path, size, modification date, and category in the File_Database
4. WHEN a file is encountered during scanning, THE File_Categorizer_System SHALL categorize it into one of three categories: graphics, lightburn, or vector
5. THE File_Categorizer_System SHALL provide progress feedback during scan operations

### Requirement 2

**User Story:** As a user, I want to search and filter my categorized files, so that I can quickly find specific files or file types.

#### Acceptance Criteria

1. THE File_Categorizer_System SHALL provide search functionality by filename, file path, and category
2. WHEN the user performs a search, THE File_Categorizer_System SHALL return matching results from the File_Database
3. THE File_Categorizer_System SHALL support filtering by file category (graphics, lightburn, vector)
4. THE File_Categorizer_System SHALL support filtering by file size ranges and date ranges
5. WHEN displaying search results, THE File_Categorizer_System SHALL show file path, size, modification date, and category

### Requirement 3

**User Story:** As a user, I want to interact with the system through both CLI and web interface, so that I can choose the most convenient method for different tasks.

#### Acceptance Criteria

1. THE File_Categorizer_System SHALL provide a CLI_Interface with commands for scan, search, list, and cleanup operations
2. THE File_Categorizer_System SHALL provide a Web_Interface accessible through a local web server
3. WHEN using the CLI_Interface, THE File_Categorizer_System SHALL accept command-line arguments and display results in terminal format
4. WHEN using the Web_Interface, THE File_Categorizer_System SHALL display results in HTML tables with sorting and filtering capabilities
5. THE File_Categorizer_System SHALL maintain consistent functionality between CLI_Interface and Web_Interface

### Requirement 4

**User Story:** As a user, I want to clean up my file database, so that I can remove references to deleted or moved files.

#### Acceptance Criteria

1. THE File_Categorizer_System SHALL verify file existence when performing cleanup operations
2. WHEN a file no longer exists at its recorded path, THE File_Categorizer_System SHALL remove the entry from the File_Database
3. THE File_Categorizer_System SHALL provide a dry-run option that shows what would be cleaned without making changes
4. WHEN cleanup is completed, THE File_Categorizer_System SHALL report the number of entries removed
5. THE File_Categorizer_System SHALL allow users to manually remove specific entries from the File_Database

### Requirement 5

**User Story:** As a user, I want the system to persist my file information, so that I don't need to rescan everything each time I use the application.

#### Acceptance Criteria

1. THE File_Categorizer_System SHALL use SQLite as the File_Database for persistent storage
2. WHEN the application starts, THE File_Categorizer_System SHALL create the File_Database if it does not exist
3. THE File_Categorizer_System SHALL store file records with unique identifiers to prevent duplicates
4. WHEN rescanning directories, THE File_Categorizer_System SHALL update existing records and add new ones
5. THE File_Categorizer_System SHALL maintain database integrity and handle concurrent access safely