# AI Code Indexing & Token Optimization System

A local-first code intelligence system that helps AI coding agents reduce token usage by retrieving only the most relevant code context from repositories.

## Features

- Repository scanning and AST parsing
- Symbol and reference extraction
- SQLite-based indexing with FTS5 search
- FastAPI REST API
- Command-line interface
- Docker support
- Incremental reindexing

## Quick Start

### Prerequisites

- Python 3.9+
- pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd repo-context
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy environment configuration:
```bash
cp .env.example .env
# Edit .env as needed
```

### Usage

#### CLI

```bash
# Scan a repository
code-indexer scan

# Index the scanned data
code-indexer index

# Query the index
code-indexer query

# Start API server
code-indexer serve
```

#### API

Start the server:
```bash
code-indexer serve
```

API will be available at http://localhost:8000

Health check: http://localhost:8000/api/v1/health

#### Docker

```bash
# Build and run with docker-compose
cd docker
docker-compose up --build
```

## Development

### Setup

1. Install development dependencies:
```bash
pip install -e .[dev]
```

2. Install pre-commit hooks:
```bash
pre-commit install
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/code_indexer

# Run specific test types
pytest -m unit
pytest -m integration
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/
```

### Development Workflow

1. Create a feature branch
2. Make changes
3. Run tests and linting
4. Commit with conventional commits
5. Create pull request

## Project Structure

```
src/code_indexer/
├── app/              # Application core
├── parsers/          # Code parsers (tree-sitter)
├── scanner/          # Repository scanner
├── extractor/        # Symbol extraction
├── indexer/          # Database indexing
├── retrieval/        # Query and retrieval
├── api/              # FastAPI application
├── cli/              # Command-line interface
└── utils/            # Utilities (config, logging, exceptions)

tests/                # Test suite
docs/                 # Documentation
scripts/              # Build and deployment scripts
docker/               # Docker configuration
```

## Configuration

Configuration is managed through environment variables. See `.env.example` for available options.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Ensure all checks pass
6. Submit a pull request

## License

[MIT License](LICENSE)