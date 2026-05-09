"""Example usage of the repository scanner."""

from pathlib import Path

from code_indexer.scanner import (
    IncrementalScanner,
    RepositoryScanner,
)


def example_basic_scanning() -> None:
    """Example: Basic repository scanning."""
    # Create scanner
    repo_path = Path("/path/to/repository")
    scanner = RepositoryScanner(repo_path)

    # Scan the repository
    result = scanner.scan()

    # Print results
    print(f"Scanned {result.total_files} files")
    print(f"Total size: {result.total_size / 1024 / 1024:.2f} MB")
    print(f"Scan time: {result.scan_time:.2f} seconds")

    # Get statistics
    stats = scanner.get_statistics(result)
    print(f"Language distribution: {stats['language_distribution']}")


def example_filter_files() -> None:
    """Example: Filter scanned files by language."""
    repo_path = Path("/path/to/repository")
    scanner = RepositoryScanner(repo_path)
    result = scanner.scan()

    # Get Python files
    python_files = scanner.get_files_by_language(result, "python")
    print(f"Found {len(python_files)} Python files")

    # Get JavaScript files
    js_files = scanner.get_files_by_language(result, "javascript")
    print(f"Found {len(js_files)} JavaScript files")

    # Get files by extension
    py_files = scanner.get_files_by_extension(result, ".py")
    print(f"Found {len(py_files)} .py files")


def example_custom_patterns() -> None:
    """Example: Scan with custom ignore patterns."""
    repo_path = Path("/path/to/repository")

    # Custom patterns
    ignore_patterns = [
        ".git/",
        "node_modules/",
        "*.log",
        "build/",
        "dist/",
        "custom_ignore_dir/",
    ]

    scanner = RepositoryScanner(
        repo_path,
        ignore_patterns=ignore_patterns,
        max_file_size_mb=50,  # Skip files larger than 50MB
    )

    result = scanner.scan()
    print(f"Scanned {result.total_files} files with custom patterns")


def example_threading() -> None:
    """Example: Use threading for faster scanning of large repositories."""
    repo_path = Path("/path/to/large/repository")

    scanner = RepositoryScanner(
        repo_path,
        use_threading=True,
        max_workers=8,  # Use 8 threads
    )

    result = scanner.scan()
    print(f"Scanned {result.total_files} files in {result.scan_time:.2f}s")


def example_incremental_scanning() -> None:
    """Example: Incremental scanning with change detection."""
    repo_path = Path("/path/to/repository")

    # Create incremental scanner
    incremental = IncrementalScanner(repo_path, use_hash=False)

    # First scan
    scanner = RepositoryScanner(repo_path)
    result1 = scanner.scan()
    incremental.update_index(result1)

    print(f"First scan: Found {result1.total_files} files")

    # Simulate changes in repository
    # (In reality, files would be added/modified/deleted)

    # Second scan
    result2 = scanner.scan()
    changes2 = incremental.update_index(result2)

    print("Changes detected:")
    print(f"  New files: {len(changes2.new_files)}")
    print(f"  Modified files: {len(changes2.modified_files)}")
    print(f"  Deleted files: {len(changes2.deleted_files)}")


def example_change_detection() -> None:
    """Example: Detailed change detection."""
    repo_path = Path("/path/to/repository")

    scanner = RepositoryScanner(repo_path)
    incremental = IncrementalScanner(repo_path)

    # First scan (establish baseline)
    result1 = scanner.scan()
    changes = incremental.update_index(result1)

    # Simulate time passing and files changing
    # In reality, you would wait and let the user modify files

    # Second scan
    result2 = scanner.scan()
    changes = incremental.update_index(result2)

    if changes.has_changes:
        print("Repository has changes!")
        for new_file in changes.new_files:
            print(f"  NEW: {new_file.relative_path}")
        for mod_file in changes.modified_files:
            print(f"  MODIFIED: {mod_file.relative_path}")
        for del_file in changes.deleted_files:
            print(f"  DELETED: {del_file.relative_path}")


def example_directory_scanning() -> None:
    """Example: Scan specific directory within repository."""
    repo_path = Path("/path/to/repository")
    scanner = RepositoryScanner(repo_path)

    # Scan specific directory
    result = scanner.scan_directory(Path("src"))

    print(f"Scanned 'src' directory: {result.total_files} files")
    for file_meta in result.files:
        print(f"  {file_meta.relative_path}")


def example_statistics() -> None:
    """Example: Generate and analyze scan statistics."""
    repo_path = Path("/path/to/repository")
    scanner = RepositoryScanner(repo_path)
    result = scanner.scan()

    stats = scanner.get_statistics(result)

    print("Repository Statistics:")
    print(f"  Total files: {stats['total_files']}")
    print(f"  Total size: {stats['total_size_mb']:.2f} MB")
    print(f"  Scan time: {stats['scan_time_seconds']:.2f}s")
    print(f"  Files/second: {stats['files_per_second']:.1f}")
    print(f"  Errors: {stats['error_count']}")
    print("\n  Language Distribution:")
    for language, count in stats["language_distribution"].items():
        percentage = (count / stats["total_files"]) * 100
        print(f"    {language}: {count} files ({percentage:.1f}%)")


if __name__ == "__main__":
    # Uncomment to run examples
    # example_basic_scanning()
    # example_filter_files()
    # example_custom_patterns()
    # example_threading()
    # example_incremental_scanning()
    # example_change_detection()
    # example_directory_scanning()
    # example_statistics()

    print("Scanner examples - uncomment in __main__ to run")
