"""
TTT Fixer — Auto-fix engine for OTServ/TFS Lua scripts.

Automatically corrects issues detected by the TTT Linter:
  - deprecated-api: replaces old procedural calls with OOP equivalents
  - missing-return: adds 'return true' to callbacks
  - global-variable-leak: adds 'local' keyword
  - deprecated-constant: replaces obsolete constants
  - invalid-callback-signature: updates callback signatures

Usage:
    from ttt.fixer import FixEngine
    engine = FixEngine()
    result = engine.fix_file("path/to/script.lua")
"""

from .auto_fix import FixEngine, FileFixResult, FixReport

__all__ = ["FixEngine", "FileFixResult", "FixReport"]
