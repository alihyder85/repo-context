Read PROJECT.md, ARCHITECTURE.md and TASKS.md before making changes.

Implement the Repository Scanner module for this AI code indexing system.

Goal:
Build a production-grade repository scanning system that efficiently discovers source files, collects metadata, and supports incremental indexing for future AST parsing and retrieval.

Requirements:

Core Features:
- Recursively scan repositories
- Detect programming languages by extension
- Support configurable include/exclude patterns
- Ignore:
  - .git
  - node_modules
  - dist
  - build
  - target
  - __pycache__
  - binaries
  - virtual environments
- Skip hidden/system files where appropriate

Metadata Collection:
For each file collect:
- absolute path
- relative path
- extension
- file size
- modified timestamp (mtime)
- optional SHA256 hash (computed on-demand by ChangeDetector, not at scan time — field is None until explicitly requested)
- detected language

Incremental Detection:
- Detect changed files using:
  - mtime
  - size
- Optional hash validation
- Detect:
  - new files
  - modified files
  - deleted files

Architecture:
- Use pathlib
- Strong typing throughout
- Modular/extensible design
- Add scanner interfaces/protocols
- Separate scanning logic from filtering logic
- Add configuration-driven ignore patterns

Performance:
- Efficient traversal for large repositories
- Add optional concurrent scanning
- Add file size limits
- Avoid loading full file contents unnecessarily

Error Handling:
- Gracefully handle:
  - permission issues
  - broken symlinks
  - invalid paths
  - encoding issues
- Add structured logging

Testing:
- Add unit tests
- Add integration tests
- Mock filesystem operations where appropriate
- Include edge cases

Generate:
1. Scanner module implementation
2. File metadata models
3. Ignore/filter system
4. Incremental change detector
5. Configuration support
6. Tests
7. Example usage
8. Suggested future improvements

Constraints:
- Follow PROJECT.md and ARCHITECTURE.md
- Keep modules small and maintainable
- Prefer composition over tight coupling
- Add docstrings and type hints everywhere
- Keep future parser/indexer integration in mind

Do not implement AST parsing yet.
Focus only on repository scanning and metadata collection.