"""Utilitários gerais (I/O, parser de argumentos Lua, etc.)."""

import os
import re
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger("ttt")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[%(levelname)s] %(message)s"
    ))
    root = logging.getLogger("ttt")
    root.setLevel(level)
    root.addHandler(handler)
    return root


def find_lua_files(directory: str) -> List[str]:
    lua_files = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith(".lua"):
                lua_files.append(os.path.join(root, f))
    return sorted(lua_files)


def find_xml_files(directory: str) -> List[str]:
    xml_files = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith(".xml"):
                xml_files.append(os.path.join(root, f))
    return sorted(xml_files)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def relative_path(filepath: str, base: str) -> str:
    return os.path.relpath(filepath, base)


def read_file_safe(filepath: str) -> Optional[str]:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return None
    logger.error(f"Could not read file: {filepath}")
    return None


def write_file_safe(filepath: str, content: str):
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def split_lua_args(args_str: str) -> List[str]:
    args = []
    current = []
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    in_string = None  # None, '"', "'"
    i = 0

    while i < len(args_str):
        ch = args_str[i]

        if in_string and ch == "\\" and i + 1 < len(args_str):
            current.append(ch)
            current.append(args_str[i + 1])
            i += 2
            continue

        if not in_string and ch == "[" and i + 1 < len(args_str) and args_str[i + 1] == "[":
            # Find closing ]]
            end = args_str.find("]]", i + 2)
            if end != -1:
                current.append(args_str[i:end + 2])
                i = end + 2
                continue

        if ch in ('"', "'"):
            if in_string is None:
                in_string = ch
            elif in_string == ch:
                in_string = None
            current.append(ch)
            i += 1
            continue

        if in_string:
            current.append(ch)
            i += 1
            continue

        if ch == "(":
            depth_paren += 1
            current.append(ch)
        elif ch == ")":
            depth_paren -= 1
            current.append(ch)
        elif ch == "[":
            depth_bracket += 1
            current.append(ch)
        elif ch == "]":
            depth_bracket -= 1
            current.append(ch)
        elif ch == "{":
            depth_brace += 1
            current.append(ch)
        elif ch == "}":
            depth_brace -= 1
            current.append(ch)
        elif ch == "," and depth_paren == 0 and depth_bracket == 0 and depth_brace == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)

        i += 1

    last = "".join(current).strip()
    if last:
        args.append(last)

    return args


def extract_function_call(code: str, start: int) -> Optional[Tuple[int, int, str, List[str]]]:
    paren_start = code.find("(", start)
    if paren_start == -1:
        return None

    func_name = code[start:paren_start].strip()

    depth = 1
    i = paren_start + 1
    in_string = None

    while i < len(code) and depth > 0:
        ch = code[i]

        if in_string and ch == "\\" and i + 1 < len(code):
            i += 2
            continue

        if ch in ('"', "'"):
            if in_string is None:
                in_string = ch
            elif in_string == ch:
                in_string = None
            i += 1
            continue

        if not in_string:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

        i += 1

    if depth != 0:
        return None

    paren_end = i  # position after closing paren
    args_str = code[paren_start + 1:paren_end - 1]
    args = split_lua_args(args_str)

    return (start, paren_end, func_name, args)


def camel_to_variable(name: str) -> str:
    for prefix in ("do", "get", "set", "is", "has", "can"):
        if name.startswith(prefix) and len(name) > len(prefix):
            name = name[len(prefix):]
            break
    if name:
        name = name[0].lower() + name[1:]
    return name
