"""
Configuration loader for TTT — reads config.toml using Python 3.11+ tomllib.
Falls back silently on older Python versions. Config is always optional;
CLI arguments always take precedence over config values.
"""

from pathlib import Path
from typing import Any, Dict, Optional


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load config.toml and return its contents as a dict.

    Returns an empty dict if:
    - Python < 3.11 (no tomllib available)
    - No config.toml found
    - File cannot be parsed

    Args:
        config_path: Explicit path to config.toml. If None, searches upward from cwd.
    """
    try:
        import tomllib
    except ImportError:
        return {}

    path = Path(config_path) if config_path else _find_config()
    if path is None or not path.exists():
        return {}

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _find_config() -> Optional[Path]:
    """Search for config.toml upward from the current working directory."""
    for directory in [Path.cwd(), *Path.cwd().parents]:
        candidate = directory / "config.toml"
        if candidate.exists():
            return candidate
        if directory == directory.parent:
            break
    return None
