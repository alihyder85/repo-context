"""Tests for the parser layer (Phase 3)."""
from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

import pytest

from code_indexer.parsers.models import ParsedFile
from code_indexer.parsers.protocols import ParserProtocol
from code_indexer.parsers.python import PythonParser
from code_indexer.parsers.javascript import JavaScriptParser
from code_indexer.parsers.typescript import TypeScriptParser
from code_indexer.parsers.java import JavaParser
from code_indexer.parsers.registry import ParserRegistry
from code_indexer.scanner.models import FileMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meta(path: Path, language: str = "python") -> FileMetadata:
    return FileMetadata(
        absolute_path=path,
        relative_path=path.name,
        extension=path.suffix,
        size=path.stat().st_size if path.exists() else 0,
        mtime=datetime.now(),
        language=language,
    )


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# PythonParser
# ---------------------------------------------------------------------------

class TestPythonParser:
    def test_valid_python(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "hello.py", "def hello():\n    pass\n")
        result = PythonParser().parse(_make_meta(p, "python"))
        assert isinstance(result, ParsedFile)
        assert result.tree is not None
        assert result.source_bytes is not None
        assert result.error is None
        assert result.parse_time_ms >= 0

    def test_syntax_error_returns_partial_tree(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "bad.py", "def bad(:\n    pass\n")
        result = PythonParser().parse(_make_meta(p, "python"))
        assert result.tree is not None
        assert result.has_errors is True

    def test_empty_file(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "empty.py", "")
        result = PythonParser().parse(_make_meta(p, "python"))
        assert result.tree is not None
        assert result.error is None

    def test_unreadable_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.py"
        meta = FileMetadata(
            absolute_path=missing,
            relative_path=Path("missing.py"),
            extension=".py",
            size=0,
            mtime=datetime.now(),
            language="python",
        )
        result = PythonParser().parse(meta)
        assert result.tree is None
        assert result.error is not None
        assert result.has_errors is True

    def test_comments_only(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "comments.py", "# just a comment\n# another\n")
        result = PythonParser().parse(_make_meta(p, "python"))
        assert result.tree is not None
        assert result.error is None

    def test_large_file(self, tmp_path: Path) -> None:
        content = "x = 1\n" * 200_000
        p = _write(tmp_path, "large.py", content)
        result = PythonParser().parse(_make_meta(p, "python"))
        assert result.tree is not None

    def test_protocol_compliance(self) -> None:
        assert isinstance(PythonParser(), ParserProtocol)


# ---------------------------------------------------------------------------
# JavaScriptParser
# ---------------------------------------------------------------------------

class TestJavaScriptParser:
    def test_valid_js(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "app.js", "function hello() { return 42; }\n")
        result = JavaScriptParser().parse(_make_meta(p, "javascript"))
        assert result.tree is not None
        assert result.error is None

    def test_broken_syntax(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "bad.js", "function bad( { }\n")
        result = JavaScriptParser().parse(_make_meta(p, "javascript"))
        assert result.tree is not None
        assert result.has_errors is True

    def test_empty_file(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "empty.js", "")
        result = JavaScriptParser().parse(_make_meta(p, "javascript"))
        assert result.tree is not None


# ---------------------------------------------------------------------------
# TypeScriptParser
# ---------------------------------------------------------------------------

class TestTypeScriptParser:
    def test_valid_ts(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "app.ts", "interface Foo { bar: string; }\n")
        result = TypeScriptParser().parse(_make_meta(p, "typescript"))
        assert result.tree is not None
        assert result.error is None

    def test_broken_syntax(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "bad.ts", "interface Foo { bar: }\n")
        result = TypeScriptParser().parse(_make_meta(p, "typescript"))
        assert result.tree is not None  # partial tree returned


# ---------------------------------------------------------------------------
# JavaParser
# ---------------------------------------------------------------------------

class TestJavaParser:
    def test_valid_java(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "Hello.java", textwrap.dedent("""\
            public class Hello {
                public static void main(String[] args) {}
            }
        """))
        result = JavaParser().parse(_make_meta(p, "java"))
        assert result.tree is not None
        assert result.error is None

    def test_broken_syntax(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "Bad.java", "public class Bad { void foo( { } }")
        result = JavaParser().parse(_make_meta(p, "java"))
        assert result.tree is not None
        assert result.has_errors is True


# ---------------------------------------------------------------------------
# ParserRegistry
# ---------------------------------------------------------------------------

class TestParserRegistry:
    def test_supported_languages(self) -> None:
        reg = ParserRegistry()
        langs = reg.supported_languages()
        assert "python" in langs
        assert "javascript" in langs
        assert "typescript" in langs
        assert "java" in langs

    def test_get_returns_none_for_unknown(self) -> None:
        assert ParserRegistry().get("cobol") is None

    def test_parse_unsupported_language(self) -> None:
        reg = ParserRegistry()
        meta = FileMetadata(
            absolute_path=Path("/fake/file.rb"),
            relative_path=Path("file.rb"),
            extension=".rb",
            size=0,
            mtime=datetime.now(),
            language="ruby",
        )
        result = reg.parse(meta)
        assert result.tree is None
        assert result.error is not None
        assert "unsupported" in result.error

    def test_parse_dispatches_correctly(self, tmp_path: Path) -> None:
        reg = ParserRegistry()
        p = _write(tmp_path, "test.py", "x = 1\n")
        meta = _make_meta(p, "python")
        result = reg.parse(meta)
        assert result.tree is not None
        assert result.language == "python"

    def test_parse_never_raises_on_missing_file(self) -> None:
        reg = ParserRegistry()
        meta = FileMetadata(
            absolute_path=Path("/nonexistent/file.py"),
            relative_path=Path("file.py"),
            extension=".py",
            size=0,
            mtime=datetime.now(),
            language="python",
        )
        result = reg.parse(meta)
        assert result.error is not None


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestParserIntegration:
    def test_full_pipeline_on_real_file(self, tmp_path: Path) -> None:
        """Feed a real .py file through registry and assert ParsedFile."""
        code = textwrap.dedent("""\
            \"\"\"Module docstring.\"\"\"

            class Greeter:
                def greet(self, name: str) -> str:
                    return f"Hello, {name}"
        """)
        p = _write(tmp_path, "greeter.py", code)
        reg = ParserRegistry()
        result = reg.parse(_make_meta(p, "python"))
        assert result.tree is not None
        assert result.source_bytes is not None
        assert result.has_errors is False
        assert result.parse_time_ms > 0
