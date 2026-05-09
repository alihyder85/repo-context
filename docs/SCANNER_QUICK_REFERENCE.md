"""Quick reference for repository scanner usage."""

# ==============================================================================
# QUICK START
# ==============================================================================

from pathlib import Path
from code_indexer.scanner import RepositoryScanner

# Scan a repository
scanner = RepositoryScanner(Path("/path/to/repo"))
result = scanner.scan()

print(f"Found {result.total_files} files")
print(f"Total size: {result.total_size / 1024 / 1024:.2f}MB")

# ==============================================================================
# FILTERING
# ==============================================================================

# Get files by language
python_files = scanner.get_files_by_language(result, "python")
java_files = scanner.get_files_by_language(result, "java")

# Get files by extension
py_files = scanner.get_files_by_extension(result, ".py")

# ==============================================================================
# STATISTICS
# ==============================================================================

stats = scanner.get_statistics(result)
print(f"Language distribution: {stats['language_distribution']}")
print(f"Scan rate: {stats['files_per_second']:.1f} files/sec")

# ==============================================================================
# CUSTOM CONFIGURATION
# ==============================================================================

# Custom ignore patterns
scanner = RepositoryScanner(
    Path("/path/to/repo"),
    ignore_patterns=[".git/", "node_modules/", "*.log"],
    max_file_size_mb=50,
    use_threading=True,
    max_workers=8,
)

# Custom language mapping
scanner = RepositoryScanner(
    Path("/path/to/repo"),
    language_mapping={
        ".custom": "mylanguage",
    }
)

# ==============================================================================
# INCREMENTAL SCANNING
# ==============================================================================

from code_indexer.scanner import IncrementalScanner

incremental = IncrementalScanner(Path("/path/to/repo"))

# First scan
result1 = scanner.scan()
changes1 = incremental.update_index(result1)

# Second scan
result2 = scanner.scan()
changes2 = incremental.update_index(result2)

print(f"New: {len(changes2.new_files)}")
print(f"Modified: {len(changes2.modified_files)}")
print(f"Deleted: {len(changes2.deleted_files)}")

# ==============================================================================
# DETAILED CHANGE INFORMATION
# ==============================================================================

for new_file in changes2.new_files:
    print(f"NEW: {new_file.relative_path} ({new_file.size} bytes)")

for mod_file in changes2.modified_files:
    print(f"MODIFIED: {mod_file.relative_path}")

for del_file in changes2.deleted_files:
    print(f"DELETED: {del_file.relative_path}")

# ==============================================================================
# SCATTER OPERATIONS
# ==============================================================================

# Scan specific directory
result = scanner.scan_directory(Path("src"))

# Process files by language
for lang, files in result.files:
    lang_files = scanner.get_files_by_language(result, lang)
    print(f"{lang}: {len(lang_files)} files")

# ==============================================================================
# FILE METADATA ACCESS
# ==============================================================================

for file_meta in result.files:
    print(f"Path: {file_meta.relative_path}")
    print(f"Language: {file_meta.language}")
    print(f"Size: {file_meta.size} bytes")
    print(f"Modified: {file_meta.mtime}")
    print(f"Extension: {file_meta.extension}")

# ==============================================================================
# ERROR HANDLING
# ==============================================================================

result = scanner.scan()

if result.has_errors:
    for error in result.errors:
        print(f"Error: {error}")

# ==============================================================================
# PERFORMANCE TIPS
# ==============================================================================

# For large repositories:
scanner = RepositoryScanner(
    repo_path,
    use_threading=True,     # Enable threading
    max_workers=8,          # Increase workers
    max_file_size_mb=100,   # Skip large files
)

# For small/known patterns:
scanner = RepositoryScanner(
    repo_path,
    use_threading=False,    # Disable threading
)

# ==============================================================================
# SUPPORTED LANGUAGES
# ==============================================================================

# Python, Java, JavaScript/TypeScript, Go, Rust, C/C++, C#, Ruby, PHP, Swift,
# Kotlin, Scala, SQL, HTML, CSS, SCSS, LESS, JSON, YAML, XML, TOML

# ==============================================================================
# COMMON PATTERNS
# ==============================================================================

Common ignore patterns (already included by default):
- .git*                  # Git directories
- __pycache__/          # Python caches
- node_modules/         # NPM packages
- dist/ build/ target/  # Build artifacts
- .venv/ venv/          # Virtual environments
- .idea/ .vscode/       # IDE files
- .DS_Store             # OS files

# ==============================================================================
# API SUMMARY
# ==============================================================================

RepositoryScanner:
  - scan() -> ScanResult
  - scan_directory(path) -> ScanResult
  - get_files_by_language(result, lang) -> List[FileMetadata]
  - get_files_by_extension(result, ext) -> List[FileMetadata]
  - get_statistics(result) -> Dict

FileMetadata:
  - absolute_path: Path
  - relative_path: Path
  - extension: str
  - size: int
  - mtime: datetime
  - language: str
  - hash: Optional[str]

ScanResult:
  - files: List[FileMetadata]
  - total_files: int
  - total_size: int
  - scan_time: float
  - errors: List[str]
  - has_errors: bool

ChangedFiles:
  - new_files: List[FileMetadata]
  - modified_files: List[FileMetadata]
  - deleted_files: List[FileMetadata]
  - has_changes: bool
  - total_changed: int