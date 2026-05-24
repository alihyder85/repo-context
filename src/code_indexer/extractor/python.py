"""Symbol and reference extractor for Python source files."""
from __future__ import annotations

import time
from typing import Any, Optional

from loguru import logger

from code_indexer.extractor.base import BaseExtractor, ExtractionContext
from code_indexer.extractor.models import (
    ExtractionResult,
    ExtractedSymbol,
    Reference,
)
from code_indexer.parsers.models import ParsedFile


def _node_text(node: Any, source_bytes: bytes) -> str:
    """Extract raw text for a tree-sitter node."""
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _first_line(text: str) -> str:
    """Return the first line of *text*, stripped."""
    return text.split("\n", 1)[0].strip()


def _extract_docstring(node: Any, source_bytes: bytes) -> Optional[str]:
    """Return the first string literal child as a docstring (max 500 chars)."""
    for child in node.children:
        if child.type == "expression_statement":
            for sub in child.children:
                if sub.type == "string":
                    raw = _node_text(sub, source_bytes).strip("\"'").strip()
                    # First paragraph only
                    para = raw.split("\n\n", 1)[0].strip()
                    return para[:500]
    return None


class PythonExtractor(BaseExtractor):
    """Stateless extractor for Python AST nodes."""

    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        """Extract symbols and references from a parsed Python file.

        Args:
            parsed_file: Parser output with tree-sitter tree.

        Returns:
            ExtractionResult with symbols and references.
        """
        start = time.perf_counter()
        file_path = str(parsed_file.file_meta.relative_path)
        ctx = ExtractionContext(file_path=file_path, language="python")

        if parsed_file.tree is None or parsed_file.source_bytes is None:
            elapsed = (time.perf_counter() - start) * 1000
            return ExtractionResult(
                file_meta=parsed_file.file_meta,
                has_errors=True,
                error=parsed_file.error or "no tree available",
                extract_time_ms=elapsed,
            )

        try:
            self._walk(parsed_file.tree.root_node, parsed_file.source_bytes, ctx)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PythonExtractor: error in {}: {}", file_path, exc)
            elapsed = (time.perf_counter() - start) * 1000
            return ExtractionResult(
                file_meta=parsed_file.file_meta,
                symbols=ctx.symbols,
                references=ctx.references,
                has_errors=True,
                error=str(exc),
                extract_time_ms=elapsed,
            )

        elapsed = (time.perf_counter() - start) * 1000
        return ExtractionResult(
            file_meta=parsed_file.file_meta,
            symbols=ctx.symbols,
            references=ctx.references,
            extract_time_ms=elapsed,
        )

    def _walk(self, node: Any, source_bytes: bytes, ctx: ExtractionContext) -> None:
        """Recursively walk AST nodes and accumulate symbols/references."""
        if node.type == "function_definition":
            self._extract_function(node, source_bytes, ctx)
        elif node.type == "class_definition":
            self._extract_class(node, source_bytes, ctx)
        elif node.type == "import_statement":
            self._extract_import(node, source_bytes, ctx)
        elif node.type == "import_from_statement":
            self._extract_import_from(node, source_bytes, ctx)
        elif node.type == "expression_statement":
            self._maybe_extract_assignment(node, source_bytes, ctx)
        elif node.type == "call":
            self._extract_call(node, source_bytes, ctx)
        else:
            for child in node.children:
                self._walk(child, source_bytes, ctx)

    def _extract_function(
        self, node: Any, source_bytes: bytes, ctx: ExtractionContext
    ) -> None:
        """Extract a function or method definition."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, source_bytes)
        qualified = ".".join(ctx.scope_stack + [name]) if ctx.scope_stack else name
        is_method = bool(ctx.scope_stack)
        sym_type = "method" if is_method else "function"
        sig = _first_line(_node_text(node, source_bytes))
        body = node.child_by_field_name("body")
        docstring = _extract_docstring(body, source_bytes) if body else None

        ctx.symbols.append(
            ExtractedSymbol(
                file_path=ctx.file_path,
                language=ctx.language,
                name=name,
                qualified_name=qualified,
                symbol_type=sym_type,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=sig,
                docstring=docstring,
            )
        )
        ctx.scope_stack.append(name)
        if body:
            for child in body.children:
                self._walk(child, source_bytes, ctx)
        ctx.scope_stack.pop()

    def _extract_class(
        self, node: Any, source_bytes: bytes, ctx: ExtractionContext
    ) -> None:
        """Extract a class definition and its members."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, source_bytes)
        qualified = ".".join(ctx.scope_stack + [name]) if ctx.scope_stack else name
        body = node.child_by_field_name("body")
        docstring = _extract_docstring(body, source_bytes) if body else None

        ctx.symbols.append(
            ExtractedSymbol(
                file_path=ctx.file_path,
                language=ctx.language,
                name=name,
                qualified_name=qualified,
                symbol_type="class",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=_first_line(_node_text(node, source_bytes)),
                docstring=docstring,
            )
        )

        # Inheritance references
        superclasses = node.child_by_field_name("superclasses")
        if superclasses:
            for arg in superclasses.children:
                if arg.type in ("identifier", "attribute"):
                    base_name = _node_text(arg, source_bytes)
                    ctx.references.append(
                        Reference(
                            file_path=ctx.file_path,
                            caller_qualified_name=qualified,
                            callee_name=base_name,
                            ref_type="inherit",
                            line=node.start_point[0] + 1,
                        )
                    )

        ctx.scope_stack.append(name)
        if body:
            for child in body.children:
                self._walk(child, source_bytes, ctx)
        ctx.scope_stack.pop()

    def _extract_import(
        self, node: Any, source_bytes: bytes, ctx: ExtractionContext
    ) -> None:
        """Extract a plain ``import x`` statement."""
        for child in node.children:
            if child.type == "dotted_name":
                callee = _node_text(child, source_bytes)
                ctx.references.append(
                    Reference(
                        file_path=ctx.file_path,
                        caller_qualified_name=ctx.current_scope,
                        callee_name=callee,
                        ref_type="import",
                        line=node.start_point[0] + 1,
                    )
                )
                ctx.symbols.append(
                    ExtractedSymbol(
                        file_path=ctx.file_path,
                        language=ctx.language,
                        name=callee.split(".")[-1],
                        qualified_name=callee,
                        symbol_type="import",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                    )
                )

    def _extract_import_from(
        self, node: Any, source_bytes: bytes, ctx: ExtractionContext
    ) -> None:
        """Extract a ``from x import y`` statement."""
        module_node = node.child_by_field_name("module_name")
        module = _node_text(module_node, source_bytes) if module_node else ""
        for child in node.children:
            if child.type in ("dotted_name", "aliased_import"):
                if child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    imported = _node_text(name_node, source_bytes) if name_node else ""
                else:
                    imported = _node_text(child, source_bytes)
                if imported == module:
                    continue
                callee = f"{module}.{imported}" if module else imported
                ctx.references.append(
                    Reference(
                        file_path=ctx.file_path,
                        caller_qualified_name=ctx.current_scope,
                        callee_name=callee,
                        ref_type="import",
                        line=node.start_point[0] + 1,
                    )
                )
                ctx.symbols.append(
                    ExtractedSymbol(
                        file_path=ctx.file_path,
                        language=ctx.language,
                        name=imported.split(".")[-1],
                        qualified_name=callee,
                        symbol_type="import",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                    )
                )

    def _maybe_extract_assignment(
        self, node: Any, source_bytes: bytes, ctx: ExtractionContext
    ) -> None:
        """Extract module-level variable assignments."""
        if ctx.scope_stack:
            return  # only module scope
        for child in node.children:
            if child.type == "assignment":
                lhs = child.child_by_field_name("left")
                rhs = child.child_by_field_name("right")
                if lhs and lhs.type == "identifier":
                    var_name = _node_text(lhs, source_bytes)
                    ctx.symbols.append(
                        ExtractedSymbol(
                            file_path=ctx.file_path,
                            language=ctx.language,
                            name=var_name,
                            qualified_name=var_name,
                            symbol_type="variable",
                            line_start=child.start_point[0] + 1,
                            line_end=child.end_point[0] + 1,
                        )
                    )
                    # assign reference if RHS is a call
                    if rhs and rhs.type == "call":
                        fn_node = rhs.child_by_field_name("function")
                        if fn_node:
                            ctx.references.append(
                                Reference(
                                    file_path=ctx.file_path,
                                    caller_qualified_name=ctx.current_scope,
                                    callee_name=_node_text(fn_node, source_bytes),
                                    ref_type="assign",
                                    line=child.start_point[0] + 1,
                                )
                            )

    def _extract_call(
        self, node: Any, source_bytes: bytes, ctx: ExtractionContext
    ) -> None:
        """Extract a function/method call reference."""
        fn_node = node.child_by_field_name("function")
        if fn_node:
            callee = _node_text(fn_node, source_bytes)
            ctx.references.append(
                Reference(
                    file_path=ctx.file_path,
                    caller_qualified_name=ctx.current_scope,
                    callee_name=callee,
                    ref_type="call",
                    line=node.start_point[0] + 1,
                )
            )
        for child in node.children:
            self._walk(child, source_bytes, ctx)
