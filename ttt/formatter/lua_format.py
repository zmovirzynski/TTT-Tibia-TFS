"""TTT Lua formatter engine and report helpers."""

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..utils import find_lua_files, read_file_safe, write_file_safe


@dataclass
class LuaFormatConfig:
    """Configuration loaded from .tttformat.json."""

    indent_style: str = "spaces"  # spaces | tabs
    indent_size: int = 4
    space_around_operators: bool = True
    blank_lines_between_functions: int = 1
    align_table_fields: bool = True
    trailing_commas: bool = True
    trim_trailing_whitespace: bool = True
    ignore_patterns: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, config_path: str) -> "LuaFormatConfig":
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return cls()

        return cls(
            indent_style=data.get("indentStyle", "spaces"),
            indent_size=int(data.get("indentSize", 4)),
            space_around_operators=bool(data.get("spaceAroundOperators", True)),
            blank_lines_between_functions=int(
                data.get("blankLinesBetweenFunctions", 1)
            ),
            align_table_fields=bool(data.get("alignTableFields", True)),
            trailing_commas=bool(data.get("trailingCommas", True)),
            trim_trailing_whitespace=bool(data.get("trimTrailingWhitespace", True)),
            ignore_patterns=list(data.get("ignore", [])),
        )

    @classmethod
    def find_config(cls, start_dir: str) -> Optional[str]:
        current = os.path.abspath(start_dir)
        while True:
            candidate = os.path.join(current, ".tttformat.json")
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        return None

    @property
    def indent_unit(self) -> str:
        if self.indent_style == "tabs":
            return "\t"
        size = max(1, self.indent_size)
        return " " * size


@dataclass
class FormatResult:
    """Formatting result for a single file."""

    filepath: str
    original_code: str = ""
    formatted_code: str = ""
    changed: bool = False
    error: str = ""


@dataclass
class FormatReport:
    """Aggregated formatter report."""

    files: List[FormatResult] = field(default_factory=list)
    target_path: str = ""
    check_mode: bool = False

    @property
    def files_scanned(self) -> int:
        return len(self.files)

    @property
    def files_changed(self) -> int:
        return sum(1 for f in self.files if f.changed)

    @property
    def files_unchanged(self) -> int:
        return sum(1 for f in self.files if not f.changed and not f.error)

    @property
    def files_errored(self) -> int:
        return sum(1 for f in self.files if f.error)


class LuaFormatter:
    """Lua code formatter with opinionated but safe defaults."""

    def __init__(self, config: Optional[LuaFormatConfig] = None):
        self.config = config or LuaFormatConfig()

    def format_code(self, code: str) -> str:
        text = code.replace("\r\n", "\n").replace("\r", "\n")

        if self.config.trim_trailing_whitespace:
            text = "\n".join(line.rstrip() for line in text.split("\n"))

        if self.config.space_around_operators:
            text = "\n".join(
                self._format_operators_line(line) for line in text.split("\n")
            )

        text = self._format_indentation(text)
        text = self._format_table_blocks(text)
        text = self._apply_function_spacing(text)

        # Compact >2 blank lines down to 2.
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.rstrip("\n") + "\n"

    def format_file(self, filepath: str, check: bool = False) -> FormatResult:
        result = FormatResult(filepath=filepath)

        code = read_file_safe(filepath)
        if code is None:
            result.error = "Could not read file"
            return result

        result.original_code = code
        result.formatted_code = self.format_code(code)
        result.changed = result.original_code != result.formatted_code

        if result.changed and not check:
            write_file_safe(filepath, result.formatted_code)

        return result

    def format_directory(self, directory: str, check: bool = False) -> FormatReport:
        files = find_lua_files(directory)
        report = FormatReport(target_path=directory, check_mode=check)

        for path in files:
            rel = os.path.relpath(path, directory).replace("\\", "/")
            if self._is_ignored(rel):
                continue
            report.files.append(self.format_file(path, check=check))

        return report

    def _is_ignored(self, relpath: str) -> bool:
        if not self.config.ignore_patterns:
            return False
        norm = relpath.replace("\\", "/")
        return any(
            fnmatch.fnmatch(norm, pattern) for pattern in self.config.ignore_patterns
        )

    def _format_indentation(self, text: str) -> str:
        lines = text.split("\n")
        formatted: List[str] = []
        indent_level = 0

        for raw_line in lines:
            stripped = raw_line.strip()

            if not stripped:
                formatted.append("")
                continue

            dedent_before = (
                1 if re.match(r"^(end|until|else\b|elseif\b)", stripped) else 0
            )
            indent_level = max(0, indent_level - dedent_before)

            formatted.append(f"{self.config.indent_unit * indent_level}{stripped}")

            delta = self._block_delta(stripped)
            indent_level = max(0, indent_level + delta)

            if re.match(r"^(else\b|elseif\b)", stripped):
                indent_level += 1

        return "\n".join(formatted)

    def _block_delta(self, stripped_line: str) -> int:
        if stripped_line.startswith("--"):
            return 0

        clean = _strip_strings_and_comments(stripped_line)
        opens = len(re.findall(r"\b(function|then|do|repeat)\b", clean))
        closes = len(re.findall(r"\b(end|until)\b", clean))

        if stripped_line.startswith("elseif") and re.search(r"\bthen\b", clean):
            opens = max(0, opens - 1)

        return opens - closes

    def _format_operators_line(self, line: str) -> str:
        code_part, comment_part = _split_comment_part(line)

        code_part = re.sub(r"\s*(==|~=|<=|>=|\.\.|=|<|>)\s*", r" \1 ", code_part)
        code_part = re.sub(r"\s+", " ", code_part)

        # Keep leading indentation untouched; it will be normalized later.
        code_part = code_part.strip()

        if comment_part:
            if code_part:
                return f"{code_part} {comment_part}"
            return comment_part
        return code_part

    def _apply_function_spacing(self, text: str) -> str:
        needed = max(0, self.config.blank_lines_between_functions)
        if needed == 0:
            return text

        replacement = "\nend" + ("\n" * (needed + 1)) + "function"
        return re.sub(r"\nend\n+function", replacement, text)

    def _format_table_blocks(self, text: str) -> str:
        lines = text.split("\n")
        out = list(lines)

        i = 0
        while i < len(out):
            line = out[i]
            if "{" not in line:
                i += 1
                continue

            depth = line.count("{") - line.count("}")
            if depth <= 0:
                i += 1
                continue

            start = i
            j = i + 1
            while j < len(out) and depth > 0:
                depth += out[j].count("{") - out[j].count("}")
                j += 1

            end = j - 1
            if end - start < 2:
                i = j
                continue

            block = out[start : end + 1]
            formatted_block = self._format_single_table_block(block)
            out[start : end + 1] = formatted_block
            i = start + len(formatted_block)

        return "\n".join(out)

    def _format_single_table_block(self, block_lines: List[str]) -> List[str]:
        if len(block_lines) < 3:
            return block_lines

        field_indexes: List[int] = []
        key_width = 0

        for idx in range(1, len(block_lines) - 1):
            stripped = block_lines[idx].strip()
            if not stripped or stripped.startswith("--") or "=" not in stripped:
                continue
            match = re.match(
                r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", block_lines[idx]
            )
            if not match:
                continue
            key = match.group(2)
            key_width = max(key_width, len(key))
            field_indexes.append(idx)

        for idx in field_indexes:
            indent, key, value = _parse_table_field(block_lines[idx])
            if indent is None:
                continue

            value_code, value_comment = _split_comment_part(value)
            value_code = value_code.strip()

            if (
                self.config.trailing_commas
                and value_code
                and not value_code.endswith(",")
            ):
                value_code = f"{value_code},"

            if self.config.align_table_fields:
                line = f"{indent}{key.ljust(key_width)} = {value_code}"
            else:
                line = f"{indent}{key} = {value_code}"

            if value_comment:
                line = f"{line} {value_comment}"
            block_lines[idx] = line.rstrip()

        return block_lines


def _strip_strings_and_comments(text: str) -> str:
    out = []
    i = 0
    in_string = ""

    while i < len(text):
        ch = text[i]

        if in_string:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == in_string:
                in_string = ""
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = ch
            i += 1
            continue

        if ch == "-" and i + 1 < len(text) and text[i + 1] == "-":
            break

        out.append(ch)
        i += 1

    return "".join(out)


def _split_comment_part(line: str) -> Tuple[str, str]:
    i = 0
    in_string = ""

    while i < len(line):
        ch = line[i]
        if in_string:
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == in_string:
                in_string = ""
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = ch
            i += 1
            continue

        if ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
            return line[:i], line[i:]

        i += 1

    return line, ""


def _parse_table_field(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    match = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
    if not match:
        return None, None, None
    return match.group(1), match.group(2), match.group(3)


def format_report_text(report: FormatReport, base_dir: str = "") -> str:
    lines: List[str] = []
    mode = "check" if report.check_mode else "format"
    lines.append(f"TTT Formatter Report ({mode})")
    lines.append("=" * 48)
    lines.append("")

    for item in report.files:
        rel = os.path.relpath(item.filepath, base_dir) if base_dir else item.filepath
        if item.error:
            lines.append(f"[ERROR] {rel}: {item.error}")
        elif item.changed:
            status = "needs formatting" if report.check_mode else "formatted"
            lines.append(f"[CHANGED] {rel} ({status})")
        else:
            lines.append(f"[OK] {rel}")

    if report.files:
        lines.append("")

    lines.append(
        f"Summary: {report.files_scanned} files, "
        f"{report.files_changed} changed, "
        f"{report.files_unchanged} unchanged, "
        f"{report.files_errored} errors"
    )

    return "\n".join(lines)
