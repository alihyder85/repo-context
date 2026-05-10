# PROJECT.md

# AI Code Indexing & Token Optimization System

## Goal

Build a local-first code intelligence system that helps AI coding agents reduce token usage by retrieving only the most relevant code context from repositories.

The system should:
- parse repositories into structured ASTs
- extract symbols and references
- build dependency relationships
- store searchable metadata in SQLite
- provide fast retrieval APIs
- minimize LLM context size

---

## Core Objectives

1. Reduce unnecessary LLM token usage
2. Avoid repeatedly sending entire files to LLMs
3. Build repository-aware retrieval
4. Support incremental indexing
5. Provide symbol-level code understanding
6. Enable fast local querying
7. Support future AI coding agents

---

## Core Features

- Repository scanning
- Tree-sitter parsing
- AST generation
- Symbol extraction
- Reference extraction
- Dependency graph generation
- SQLite storage
- FTS5 full-text search
- Incremental reindexing
- Minimal-context retrieval
- Semantic search (future)
- Agent APIs (future)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python |
| Parsing | tree-sitter |
| Database | SQLite |
| Search | SQLite FTS5 |
| API | FastAPI |
| ORM | SQLAlchemy |

---

## Design Principles

- Local-first architecture
- Minimal token usage
- Fast retrieval
- Extensible parser system
- Modular architecture
- Repository isolation
- Incremental updates
- AI-agent friendly

---

## Future Goals

- Embedding-based semantic search
- VSCode extension
- Multi-repo indexing
- Distributed indexing
- AI summarization cache
- Retrieval ranking engine
- Agent tool integrations

---
## Steps to run

### Step 1 — Install

```
cd /Users/alihyderlaskar/Developer/code/repo-context

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .venv\Scripts\activate           # Windows

# Install the package
pip install -e .

# Verify
code-indexer --version
```

### Step 2 — Configure

```
# Copy the example env file
cp .env.example .env
```

Edit .env to point at your repo:

```
DATABASE_URL=sqlite:///data/index.db     # where the index is stored
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=10
IGNORE_PATTERNS=[".git","__pycache__","node_modules",".venv"]
```

### Step 3 — Run the Scanner (works today ✅)

```
# Scan any repo from Python
python - <<'EOF'
from code_indexer.scanner import RepositoryScanner, IncrementalScanner
from pathlib import Path
import json

# Point at any repo on your machine
REPO = Path("/Users/alihyderlaskar/Developer/code/repo-context")

scanner = RepositoryScanner(REPO)
result  = scanner.scan()
stats   = scanner.get_statistics(result)

print(f"Files found  : {result.total_files}")
print(f"Size         : {stats['total_size_mb']:.2f} MB")
print(f"Scan time    : {result.scan_time:.3f}s")
print(f"Languages    : {stats['language_distribution']}")
print(f"Errors       : {len(result.errors)}")
print()

# Each file becomes this dict for the indexer
print("Sample record →", json.dumps(result.files[0].to_dict(), indent=2))
EOF
```

Output:

```
Files found  : 37
Size         : 0.12 MB
Languages    : {'python': 35, 'toml': 1, 'yaml': 1}

Sample record → {
  "relative_path": "src/code_indexer/scanner/scanner.py",
  "language": "python",
  "size": 9823,
  "mtime": "2026-05-09T23:20:14.243758",
  "hash": null
}
```

###Step 4 — Where Entries Are Stored

```
repo-context/
├── data/
│   └── index.db          ← SQLite database (created by Phase 6 Indexer)
├── logs/
│   └── code_indexer.log  ← structured log file
└── code_indexer.db       ← default fallback path from DATABASE_URL
```

SQLite schema (populated by Phases 3–8):

```
files         → one row per source file   (path, language, size, mtime)
symbols       → one row per function/class (name, type, line_start, signature)
symbol_refs   → one row per call/import    (caller_id → callee_id)
symbols_fts   → FTS5 virtual table         (full-text search over symbols)
```
Right now only the scanner output (FileMetadata.to_dict()) feeds into files. The symbols and symbol_refs tables need Phases 3–8.

### Step 5 — Run the API Server

```
# Start the FastAPI server
code-indexer serve --host 0.0.0.0 --port 8000

# Or with Docker
cd docker && docker-compose up
```

Check it's alive:

```
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/
```

### Step 6 — Use the Retrieval Engine with Coding Agents

This is the core use case. Here is exactly how to wire it into a Claude/Copilot prompt:

```
from code_indexer.retrieval import RetrievalEngine, RetrievalQuery
from pathlib import Path

engine = RetrievalEngine(Path("data/index.db"))

def build_agent_prompt(user_question: str, focal_symbol: str) -> str:
    """Build a minimal-token prompt for Claude/Copilot."""

    # 1. Ask the retrieval engine for relevant context
    context = engine.get_related_context(
        RetrievalQuery(
            query=focal_symbol,
            symbol_name=focal_symbol,
            token_budget=4_000,      # hard cap — never exceed this
            max_depth=2,             # 2-hop dependency traversal
            include_callers=True,
            include_imports=True,
        )
    )

    # 2. Build the code block from ranked snippets only
    code_section = ""
    for snippet in context.snippets:
        code_section += f"\n# {snippet.file_path}:{snippet.line_start}\n"
        code_section += snippet.content + "\n"

    # 3. Assemble final prompt
    prompt = f"""You are a coding assistant. Below is the relevant code context
(retrieved automatically — {context.total_tokens} tokens used, 
{context.dropped_count} irrelevant snippets excluded).

{code_section}

Question: {user_question}"""

    return prompt

# Usage
prompt = build_agent_prompt(
    user_question="Why does scan() return empty results?",
    focal_symbol="scan"
)
print(prompt)
```

### Step 7 — How to See Token Reduction

Run this comparison to measure the savings:

```
from code_indexer.scanner import RepositoryScanner
from code_indexer.retrieval import RetrievalEngine, RetrievalQuery
from code_indexer.retrieval.tokens import CharDivFourEstimator
from pathlib import Path

estimator = CharDivFourEstimator()

# ── NAIVE approach: send entire file ──────────────────────────────────
target_file = Path("src/code_indexer/scanner/scanner.py")
full_content = target_file.read_text()
naive_tokens = estimator.estimate(full_content)

# ── THIS SYSTEM: send only what's relevant ────────────────────────────
engine = RetrievalEngine(Path("data/index.db"))
result = engine.get_related_context(
    RetrievalQuery(query="scan", token_budget=4_000)
)
smart_tokens = result.total_tokens

# ── Compare ───────────────────────────────────────────────────────────
saving_pct = (1 - smart_tokens / naive_tokens) * 100
print(f"Naive (full file)   : {naive_tokens:,} tokens")
print(f"This system         : {smart_tokens:,} tokens")
print(f"Token reduction     : {saving_pct:.0f}%")
print(f"Dropped snippets    : {result.dropped_count}")
```

Typical result on a real codebase once fully indexed:

```
Naive (full file)   : 2,450 tokens
This system         :   180 tokens
Token reduction     :    93%
Dropped snippets    :    14

```