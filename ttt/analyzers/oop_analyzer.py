"""AST-based OOP structural analyzer for TTT source files."""

import ast
import os
from dataclasses import dataclass, field
from typing import List


MAX_METHOD_LINES = 50
MAX_PARAMS = 5
MIN_DICT_KEYS = 3


@dataclass
class OopIssue:
    file_path: str
    entity_name: str
    issue_type: str
    line_start: int
    line_end: int
    description: str
    guideline: str


@dataclass
class FileAnalysis:
    file_path: str
    issues: List[OopIssue] = field(default_factory=list)
    total_lines: int = 0


_GUIDELINES = {
    "METHOD_TOO_LONG": (
        "Break this method into smaller private helper methods, each with a single "
        "responsibility. Aim for methods under 20 lines. Use descriptive names that "
        "reveal intent without requiring comments."
    ),
    "TOO_MANY_PARAMS": (
        "Introduce a parameter object (dataclass or namedtuple) to group related "
        "parameters. Consider whether some parameters indicate a missing abstraction "
        "or that the method is doing too much."
    ),
    "DICT_AS_OBJECT": (
        "Replace the dict with a dataclass or class that encodes the structure "
        "explicitly. This makes fields discoverable, type-checkable, and gives you "
        "a natural place for validation and methods."
    ),
    "STANDALONE_FUNCTION": (
        "Move this function inside the relevant class as a static method, class "
        "method, or instance method. If it belongs to none, consider creating a "
        "dedicated helper class or moving it to a utils module."
    ),
}


class OopAnalyzer:
    TARGET_FILES = [
        "engine.py",
        "report.py",
        "scanner.py",
        "diff_html.py",
        "main.py",
        os.path.join("converters", "lua_transformer.py"),
        os.path.join("converters", "xml_to_revscript.py"),
        os.path.join("converters", "npc_converter.py"),
        os.path.join("converters", "ast_lua_transformer.py"),
        os.path.join("converters", "ast_utils.py"),
        os.path.join("converters", "scope_analyzer.py"),
        os.path.join("converters", "ast_transform_visitor.py"),
        os.path.join("mappings", "tfs03_functions.py"),
        os.path.join("mappings", "tfs04_functions.py"),
        os.path.join("mappings", "signatures.py"),
        os.path.join("mappings", "constants.py"),
        os.path.join("mappings", "xml_events.py"),
    ]

    def analyze_project(self, ttt_root: str) -> List[FileAnalysis]:
        results = []
        for rel_path in self.TARGET_FILES:
            full_path = os.path.join(ttt_root, rel_path)
            if os.path.isfile(full_path):
                results.append(self._analyze_file(full_path, rel_path))
        return results

    def _analyze_file(self, path: str, rel_path: str) -> FileAnalysis:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        lines = source.splitlines()
        total_lines = len(lines)

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            return FileAnalysis(file_path=rel_path, total_lines=total_lines)

        issues: List[OopIssue] = []
        issues.extend(self._detect_long_methods(tree, lines, rel_path))
        issues.extend(self._detect_many_params(tree, rel_path))
        issues.extend(self._detect_dict_patterns(tree, rel_path))
        issues.extend(self._detect_module_functions(tree, rel_path))

        return FileAnalysis(file_path=rel_path, issues=issues, total_lines=total_lines)

    def _detect_long_methods(
        self, tree: ast.AST, lines: list, file_path: str
    ) -> List[OopIssue]:
        issues = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            start = node.lineno
            end = node.end_lineno or start
            length = end - start + 1
            if length > MAX_METHOD_LINES:
                issues.append(
                    OopIssue(
                        file_path=file_path,
                        entity_name=node.name,
                        issue_type="METHOD_TOO_LONG",
                        line_start=start,
                        line_end=end,
                        description=(
                            f"`{node.name}` spans {length} lines ({start}–{end}), "
                            f"exceeding the {MAX_METHOD_LINES}-line limit."
                        ),
                        guideline=_GUIDELINES["METHOD_TOO_LONG"],
                    )
                )
        return issues

    def _detect_many_params(self, tree: ast.AST, file_path: str) -> List[OopIssue]:
        issues = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            param_names = [a.arg for a in args.args if a.arg != "self"]
            param_names += [a.arg for a in args.posonlyargs if a.arg != "self"]
            if len(param_names) > MAX_PARAMS:
                issues.append(
                    OopIssue(
                        file_path=file_path,
                        entity_name=node.name,
                        issue_type="TOO_MANY_PARAMS",
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        description=(
                            f"`{node.name}` has {len(param_names)} parameters "
                            f"({', '.join(param_names)}), exceeding the limit of {MAX_PARAMS}."
                        ),
                        guideline=_GUIDELINES["TOO_MANY_PARAMS"],
                    )
                )
        return issues

    def _detect_dict_patterns(self, tree: ast.AST, file_path: str) -> List[OopIssue]:
        issues = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            keys: set = set()
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Subscript)
                    and isinstance(child.slice, ast.Constant)
                    and isinstance(child.slice.value, str)
                ):
                    keys.add(child.slice.value)
            if len(keys) >= MIN_DICT_KEYS:
                sorted_keys = sorted(keys)
                issues.append(
                    OopIssue(
                        file_path=file_path,
                        entity_name=node.name,
                        issue_type="DICT_AS_OBJECT",
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        description=(
                            f"`{node.name}` accesses {len(keys)} distinct string keys "
                            f"({', '.join(repr(k) for k in sorted_keys[:6])}{'…' if len(sorted_keys) > 6 else ''}), "
                            f"suggesting dict-as-object usage."
                        ),
                        guideline=_GUIDELINES["DICT_AS_OBJECT"],
                    )
                )
        return issues

    def _detect_module_functions(self, tree: ast.AST, file_path: str) -> List[OopIssue]:
        has_class = any(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
        if not has_class:
            return []
        issues = []
        for node in tree.body:  # type: ignore[attr-defined]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                issues.append(
                    OopIssue(
                        file_path=file_path,
                        entity_name=node.name,
                        issue_type="STANDALONE_FUNCTION",
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        description=(
                            f"`{node.name}` is a module-level function in a file "
                            f"that also defines classes."
                        ),
                        guideline=_GUIDELINES["STANDALONE_FUNCTION"],
                    )
                )
        return issues
