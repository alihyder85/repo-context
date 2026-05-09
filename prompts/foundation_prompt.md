Read PROJECT.md, ARCHITECTURE.md and TASKS.md.

Use the recommended architecture and package organization from the planning phase.

Implement Phase 1 Foundation setup.

Requirements:
- Create production-grade Python project structure
- Setup pyproject.toml
- Configure dependencies
- Add modular folders:
  - app
  - parsers
  - scanner
  - extractor
  - indexer
  - retrieval
  - api
  - cli
  - utils
  - tests
  - prompts
- Add logging setup
- Add .env configuration support
- Add linting/formatting:
  - black
  - mypy
  - flake8
- Add Docker support
- Add starter CLI entrypoint
- Add README
- Add typing throughout
- Add base configuration system
- Add custom exception structure

Generate:
- folder structure
- starter implementations
- dependency setup
- setup instructions
- development workflow

Constraints:
- Each generated file must have exactly one module docstring at the top — no duplicate import blocks
- Use pydantic-settings SettingsConfigDict (not the old class-based Config inner class)
- All typing imports must use the single canonical import block per file