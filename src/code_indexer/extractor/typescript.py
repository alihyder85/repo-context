"""Symbol and reference extractor for TypeScript source files."""
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


def _jsdoc(node: Any, src: bytes) -> Optional[str]:
    prev = node.prev_sibling
    while prev and prev.type == "comment":
        text = _node_text(prev, src).strip()
        if text.startswith("/**"):
            cleaned = "\n".join(
                line.strip().lstrip("*").strip()
                for line in text.strip("/**").strip("*/").splitlines()
            )
            return cleaned.strip()[:500]
        prev = prev.prev_sibling
    return None


class TypeScriptExtractor(BaseExtractor):
    """Stateless extractor for TypeScript AST nodes."""

    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        """Extract symbols and references from a parsed TypeScript file.

        Args:
            parsed_file: Parser output with tree-sitter tree.

        Returns:
            ExtractionResult with symbols and references.
        """
        start = time.perf_counter()
        file_path = str(parsed_file.file_meta.relative_path)
        ctx = ExtractionContext(file_path=file_path, language="typescript")

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
            logger.warning("TypeScriptExtractor: error in {}: {}", file_path, exc)
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
        if t in ("function_declaration", "method_definition"):
            self._extract_function(node, src, ctx)
        elif t in ("class_declaration", "abstract_class_declaration"):
            self._extract_class(node, src, ctx)
        elif t == "interface_declaration":
            self._extract_interface(node, src, ctx)
        elif t == "type_alias_declaration":
            self._extract_type_alias(node, src, ctx)
        elif t in ("lexical_declaration", "variable_declaration"):
            self._extract_var_decl(node, src, ctx)
        elif t == "import_statement":
            self._extract_import(node, src, ctx)
        elif t == "call_expression":
            self._extract_call(node, src, ctx)
        else:
            for child in node.children:
                self._walk(child, src, ctx)

    def _extract_function(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, src)
        qualified = ".".join(ctx.scope_stack + [name]) if ctx.scope_stack else name
        sym_type = "method" if ctx.scope_stack else "function"
        ctx.symbols.append(ExtractedSymbol(
            file_path=ctx.file_path,
            language=ctx.language,
            name=name,
            qualified_name=qualified,
            symbol_type=sym_type,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=_first_line(_node_text(node, src)),
            docstring=_jsdoc(node, src),
        ))
        ctx.scope_stack.append(name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._walk(child, src, ctx)
        ctx.scope_stack.pop()

    def _extract_class(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, src)
        qualified = ".".join(ctx.scope_stack + [name]) if ctx.scope_stack else name

        for child in node.children:
            if child.type == "class_heritage":
                for sub in child.children:
                    if sub.type == "extends_clause":
                        for grandchild in sub.children:
                            if grandchild.type in ("identifier", "member_expression"):
                                ctx.references.append(Reference(
                                    file_path=ctx.file_path,
                                    caller_qualified_name=qualified,
                                    callee_name=_node_text(grandchild, src),
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
            docstring=_jsdoc(node, src),
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
            symbol_type="class",  # treat interfaces as class for retrieval
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=_first_line(_node_text(node, src)),
            docstring=_jsdoc(node, src),
        ))

    def _extract_type_alias(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        ctx.symbols.append(ExtractedSymbol(
            file_path=ctx.file_path,
            language=ctx.language,
            name=_node_text(name_node, src),
            qualified_name=_node_text(name_node, src),
            symbol_type="variable",
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=_first_line(_node_text(node, src)),
        ))

    def _extract_var_decl(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        if ctx.scope_stack:
            return
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                if name_node and name_node.type == "identifier":
                    ctx.symbols.append(ExtractedSymbol(
                        file_path=ctx.file_path,
                        language=ctx.language,
                        name=_node_text(name_node, src),
                        qualified_name=_node_text(name_node, src),
                        symbol_type="variable",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                    ))

    def _extract_import(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        source_node = node.child_by_field_name("source")
        module = _node_text(source_node, src).strip("'\"") if source_node else ""
        for child in node.children:
            if child.type == "import_clause":
                for sub in child.children:
                    if sub.type == "identifier":
                        ctx.references.append(Reference(
                            file_path=ctx.file_path,
                            caller_qualified_name=ctx.current_scope,
                            callee_name=f"{module}.{_node_text(sub, src)}",
                            ref_type="import",
                            line=node.start_point[0] + 1,
                        ))

    def _extract_call(self, node: Any, src: bytes, ctx: ExtractionContext) -> None:
        fn_node = node.child_by_field_name("function")
        if fn_node:
            ctx.references.append(Reference(
                file_path=ctx.file_path,
                caller_qualified_name=ctx.current_scope,
                callee_name=_node_text(fn_node, src),
                ref_type="call",
                line=node.start_point[0] + 1,
            ))
        for child in node.children:
            self._walk(child, src, ctx)
