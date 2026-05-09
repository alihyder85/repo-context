# Repository Scanner Module

## Overview

The Repository Scanner module provides efficient scanning of source code repositories, collecting comprehensive file metadata while respecting ignore patterns and applying flexible filtering.

## Features

### Core Scanning
- **Recursive scanning** of entire repositories
- **Automatic language detection** based on file extensions
- **Metadata collection** including size, modification time, and hash
- **Configurable ignore patterns** with glob pattern support
- **Performance optimization** with optional multi-threaded scanning

### Filtering System
- **Multiple filter types**: ignore patterns, hidden files, size limits, language support
- **Composable filters** using FilterChain builder pattern
- **Extensible design** for custom filters

### Change Detection
- **Incremental scanning** with change tracking
- **New file detection**
- **Modification detection** using size, mtime, and optional hashing
- **Deletion detection**

## Architecture

### Core Components

#### RepositoryScanner
Main scanning engine that discovers files and collects metadata.

```python
scanner = RepositoryScanner(repo_path)
result = scanner.scan()
```

#### Models
- `FileMetadata`: Represents a single file's metadata
- `ScanResult`: Contains scan results and statistics
- `RepositoryIndex`: Tracks repository state for incremental scans
- `ChangedFiles`: Represents detected changes

#### Filters
- `IgnorePatternFilter`: Glob pattern matching
- `HiddenFileFilter`: Exclude hidden/system files
- `SizeFilter`: File size limiting
- `LanguageFilter`: Support specific extensions
- `CompositeFilter`: Combine multiple filters
- `FilterChain`: Builder for filter chains

#### Change Detection
- `ChangeDetector`: Detects file changes between scans
- `IncrementalScanner`: Tracks state across scans

## Usage Examples

### Basic Scanning
```python
from code_indexer.scanner import RepositoryScanner

scanner = RepositoryScanner("/path/to/repo")
result = scanner.scan()

print(f"Found {result.total_files} files")
print(f"Total size: {result.total_size} bytes")
```

### Filter by Language
```python
python_files = scanner.get_files_by_language(result, "python")
java_files = scanner.get_files_by_language(result, "java")
```

### Custom Patterns
```python
scanner = RepositoryScanner(
    repo_path,
    ignore_patterns=[".git/", "node_modules/", "*.log"],
    max_file_size_mb=50,
)
```

### Threading
```python
scanner = RepositoryScanner(
    repo_path,
    use_threading=True,
    max_workers=8,
)
result = scanner.scan()
```

### Incremental Scanning
```python
from code_indexer.scanner import IncrementalScanner

incremental = IncrementalScanner(repo_path)

# First scan
result1 = scanner.scan()
changes1 = incremental.update_index(result1)

# Later scan
result2 = scanner.scan()
changes2 = incremental.update_index(result2)

print(f"New files: {len(changes2.new_files)}")
print(f"Modified: {len(changes2.modified_files)}")
print(f"Deleted: {len(changes2.deleted_files)}")
```

## Configuration

The scanner uses default patterns and settings but can be customized:

```python
RepositoryScanner(
    repo_root: Path,
    language_mapping: Optional[dict] = None,
    ignore_patterns: Optional[list] = None,
    max_file_size_mb: int = 10,
    use_threading: bool = True,
    max_workers: int = 4,
)
```

### Default Ignore Patterns
- `.git*`
- `__pycache__`, `*.pyc`, `*.pyo`
- `node_modules`, `package-lock.json`, `yarn.lock`
- `dist`, `build`, `target`
- Virtual environments (`.venv`, `venv`, `env`)
- IDE files (`.idea`, `.vscode`)
- OS files (`.DS_Store`, `Thumbs.db`)

### Supported Languages
Python, Java, JavaScript/TypeScript, Go, Rust, C/C#, Ruby, PHP, Swift, Kotlin, Scala, SQL, HTML/CSS, JSON, YAML, XML, TOML, and more.

## Performance Characteristics

### Time Complexity
- Sequential: O(n) where n = total files
- Threaded: O(n/m) where m = number of workers

### Space Complexity
- O(n) for storing metadata
- Streaming scan minimizes intermediate memory

### Optimization Tips
1. Use threading for repositories with 10k+ files
2. Increase `max_workers` for I/O bound systems
3. Use `max_file_size_mb` to skip large binaries
4. Set appropriate ignore patterns early

## Error Handling

The scanner gracefully handles:
- **Permission errors**: Logged and skipped
- **Broken symlinks**: Skipped
- **Encoding issues**: Logged and skipped
- **Large files**: Can be filtered by size limit

All errors are collected in `ScanResult.errors`.

## Testing

Comprehensive test coverage includes:
- Unit tests for each component
- Integration tests for complete workflows
- Many edge cases tested

Run tests:
```bash
pytest tests/test_scanner.py -v
```

## Future Improvements

### Phase 2+ Enhancements
1. **Symlink handling**
   - Configurable symlink following
   - Circular reference detection

2. **Binary file detection**
   - Magic number based detection
   - Avoid parsing binaries as source

3. **Encoding detection**
   - Auto-detect file encoding
   - Handle multi-encoding repositories

4. **Watch mode**
   - Real-time file system watching
   - Efficient incremental updates

5. **Performance metrics**
   - Detailed timing per phase
   - Memory profiling
   - Bottleneck identification

6. **Custom metadata**
   - Plugin system for extracting custom metadata
   - Language-specific metadata (e.g., imports)

7. **Caching**
   - Cache scan results to disk
   - Resume interrupted scans
   - Persistent index

8. **Distribution**
   - Map/reduce for massive repositories
   - Parallel processing across machines
   - Cloud storage support

9. **Advanced filtering**
   - Regular expression patterns
   - Complexity-based filtering
   - Duplicate file detection

10. **Reporting**
    - Detailed scan reports
    - HTML/JSON export
    - Statistics over time

## Troubleshooting

### Scanner is slow
- Check repository size (very large repos need threading)
- Reduce ignore patterns (fewer patterns = faster)
- Profile with `max_workers` parameter

### Missing files
- Check ignore patterns are correct
- Ensure file extensions are in language mapping
- Verify file permissions

### High memory usage
- Reduce `max_workers` to lower thread count
- Process results in batches
- Clear result objects when done

## See Also
- [Architecture](../../../docs/ARCHITECTURE.md)
- [Project Documentation](../../../PROJECT.md)