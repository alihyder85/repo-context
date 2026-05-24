"""Symbol and reference extractor for Java source files."""
from __future__ import annotations

import time
from typing import Any, Optional

from loguru import logger

from code_indexer.extractor.base import BaseExtractor, ExtractionContext
from code_indexer.extractor.models import ExtractionResult, ExtractedSymbol, Reference
from code_indexer.parsers.models import ParsedFile


def _node_text(node: Any, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _first_line(text: str) -> str:
    return text.split("\n", 1)[0].strip()


def _javadoc(node: Any, src: bytes) -> Optional[str]:
    prev = node.prev_sibling
    while prev and prev.type in ("line_comment", "block_comment"):
        text = _node_text(prev, src).strip()
        if text.startswith("/**"):
            cleaned = "\n".join(
                line.strip().lstrip("*").strip()
                for line in text.strip("/**").strip("*/").splitlines()
            )
            return cleaned.strip()[:500]
        prev = prev.prev_sibling
    return None


class JavaExtractor(BaseExtractor):
    """Stateless extractor for Java AST nodes."""

    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        """Extract symbols and references from a parsed Java file.

        Args:
            parsed_file: Parser output with tree-sitter tree.

        Returns:
            ExtractionResult with symbols and references.
        """
        start = time.perf_counter()
        file_path = str(parsed_file.file_meta.relative_path)
        ctx = ExtractionContext(file_path=file_path, language="java")

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
        except Exception as exc:
            logger.warning("JavaExtractor: error in {}: {}", file_path, exc)
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

    def _walk(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        t = node.type
        if t == "class_declaration":
            self._extract_class(node, src, ctx)
        elif t == "interface_declaration":
            self._extract_interface(node, src, ctx)
        elif t == "method_declaration":
            self._extract_method(node, src, ctx)
        elif t == "import_declaration":
            self._extract_import(node, src, ctx)
        elif t == "field_declaration":
            self._extract_field(node, src, ctx)
        elif t == "method_invocation":
            self._extract_call(node, src, ctx)
        else:
            for child in node.children:
                self._walk(child, src, ctx)

    def _extract_class(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, src)
        qualified = ".".join(ctx.scope_stack + [name]) if ctx.scope_stack else name

        # Superclass reference
        superclass = node.child_by_field_name("superclass")
        if superclass:
            ctx.references.append(Reference(
                file_path=ctx.file_path,
                caller_qualified_name=qualified,
                callee_name=_node_text(superclass, src),
                ref_type="inherit",
                line=node.start_point[0] + 1,
            ))

        ctx.symbols.append(ExtractedSymbol(
            file_path=ctx.file_path,
            language=ctx.language,
            name=name,
            qualified_name=qualified,
            symbol_type="class",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=_first_line(_node_text(node, src)),
            docstring=_javadoc(node, src),
        ))
        ctx.scope_stack.append(name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._walk(child, src, ctx)
        ctx.scope_stack.pop()

    def _extract_interface(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, src)
        ctx.symbols.append(ExtractedSymbol(
            file_path=ctx.file_path,
            language=ctx.language,
            name=name,
            qualified_name=name,
            symbol_type="class",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=_first_line(_node_text(node, src)),
            docstring=_javadoc(node, src),
        ))

    def _extract_method(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, src)
        qualified = ".".join(ctx.scope_stack + [name]) if ctx.scope_stack else name
        ctx.symbols.append(ExtractedSymbol(
            file_path=ctx.file_path,
            language=ctx.language,
            name=name,
            qualified_name=qualified,
            symbol_type="method",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=_first_line(_node_text(node, src)),
            docstring=_javadoc(node, src),
        ))
        ctx.scope_stack.append(name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._walk(child, src, ctx)
        ctx.scope_stack.pop()

    def _extract_import(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        for child in node.children:
            if child.type == "scoped_identifier":
                callee = _node_text(child, src)
                ctx.references.append(Reference(
                    file_path=ctx.file_path,
                    caller_qualified_name=ctx.current_scope,
                    callee_name=callee,
                    ref_type="import",
                    line=node.start_point[0] + 1,
                ))
                ctx.symbols.append(ExtractedSymbol(
                    file_path=ctx.file_path,
                    language=ctx.language,
                    name=callee.split(".")[-1],
                    qualified_name=callee,
                    symbol_type="import",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                ))

    def _extract_field(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        if not ctx.scope_stack:
            return  # only within class scope
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = _node_text(name_node, src)
                    ctx.symbols.append(ExtractedSymbol(
                        file_path=ctx.file_path,
                        language=ctx.language,
                        name=name,
                        qualified_name=".".join(ctx.scope_stack + [name]),
                        symbol_type="variable",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                    ))

    def _extract_call(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        name_node = node.child_by_field_name("name")
        if name_node:
            ctx.references.append(Reference(
                file_path=ctx.file_path,
                caller_qualified_name=ctx.current_scope,
                callee_name=_node_text(name_node, src),
                ref_type="call",
                line=node.start_point[0] + 1,
            ))
        for child in node.children:
            self._walk(child, src, ctx)
