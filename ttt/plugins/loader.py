"""
Plugin loader — Discovers and loads mapping packs and rule packs.

Mapping packs are TOML files with a ``[manifest]`` header and ``[mappings]`` table.
Rule packs are Python modules that expose a ``RULES`` dict (rule_id → LintRule class).
"""

import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ttt")

# ── Manifest ──────────────────────────────────────────────────────────────


@dataclass
class PluginManifest:
    """Metadata for a plugin pack."""

    name: str = ""
    version: str = "0.0.0"
    type: str = ""  # "mappings" or "rules"
    description: str = ""
    path: str = ""


class PluginError(Exception):
    """Raised when a plugin fails validation or loading."""


# ── Mapping packs ─────────────────────────────────────────────────────────


def load_mapping_pack(path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load a TOML mapping pack file. Returns the function-mapping dict.

    Expected format::

        [manifest]
        name = "my-custom-mappings"
        version = "1.0.0"
        type = "mappings"

        [mappings]
        myLegacyFunc = { method = "newMethod", obj_type = "player", obj_param = 0, drop_params = [0] }
    """
    try:
        import tomllib
    except ImportError:
        raise PluginError("Python 3.11+ required for TOML plugin loading (tomllib)")

    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise PluginError(f"Mapping pack not found: {path}")

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        raise PluginError(f"Failed to parse mapping pack {path}: {exc}")

    manifest = data.get("manifest", {})
    _validate_manifest(manifest, path, expected_type="mappings")

    mappings = data.get("mappings", {})
    if not isinstance(mappings, dict):
        raise PluginError(f"Mapping pack {path}: [mappings] must be a table")

    # Validate each entry has at least a 'method' key
    for func_name, entry in mappings.items():
        if not isinstance(entry, dict):
            raise PluginError(
                f"Mapping pack {path}: entry '{func_name}' must be a table"
            )
        if "method" not in entry:
            raise PluginError(
                f"Mapping pack {path}: entry '{func_name}' missing required 'method' key"
            )

    logger.info(
        f"  Loaded mapping pack '{manifest.get('name', path)}' "
        f"({len(mappings)} entries)"
    )
    return mappings


# ── Rule packs ────────────────────────────────────────────────────────────


def load_rule_pack(path: str) -> Dict[str, type]:
    """
    Load a Python rule pack module. Returns a dict of rule_id → LintRule subclass.

    The module must define a ``RULES`` dict at the top level, e.g.::

        from ttt.linter.rules import LintRule, LintIssue, LintSeverity

        class MyCustomRule(LintRule):
            rule_id = "custom-check"
            description = "My custom lint check"
            severity = LintSeverity.WARNING

            def check(self, code, lines, filename=""):
                # ...
                return []

        RULES = {"custom-check": MyCustomRule}
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise PluginError(f"Rule pack not found: {path}")

    module_name = f"ttt_plugin_{os.path.basename(path).replace('.py', '')}"

    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise PluginError(f"Cannot create module spec for {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
    except PluginError:
        raise
    except Exception as exc:
        raise PluginError(f"Failed to load rule pack {path}: {exc}")

    rules = getattr(mod, "RULES", None)
    if rules is None:
        raise PluginError(f"Rule pack {path}: module must define a RULES dict")
    if not isinstance(rules, dict):
        raise PluginError(f"Rule pack {path}: RULES must be a dict")

    # Validate each rule
    from ..linter.rules import LintRule

    for rule_id, cls in rules.items():
        if not isinstance(cls, type) or not issubclass(cls, LintRule):
            raise PluginError(
                f"Rule pack {path}: '{rule_id}' must be a LintRule subclass"
            )
        if not hasattr(cls, "rule_id") or cls.rule_id != rule_id:
            raise PluginError(
                f"Rule pack {path}: class rule_id '{getattr(cls, 'rule_id', '')}' "
                f"does not match dict key '{rule_id}'"
            )

    logger.info(
        f"  Loaded rule pack '{module_name}' ({len(rules)} rules)"
    )
    return rules


# ── Discovery ─────────────────────────────────────────────────────────────


def discover_plugins(project_config: dict) -> List[PluginManifest]:
    """
    Discover plugin paths from a loaded ``ttt.project.toml`` config.

    Returns a list of :class:`PluginManifest` objects (not yet loaded).
    """
    plugins_section = project_config.get("plugins", {})
    result: List[PluginManifest] = []

    for path in plugins_section.get("mappings", []):
        result.append(
            PluginManifest(
                name=os.path.basename(path),
                type="mappings",
                path=path,
            )
        )

    for path in plugins_section.get("rules", []):
        result.append(
            PluginManifest(
                name=os.path.basename(path),
                type="rules",
                path=path,
            )
        )

    return result


# ── Full loader ───────────────────────────────────────────────────────────


class PluginLoader:
    """
    High-level loader: discovers and loads all plugins from a project config.
    """

    def __init__(self, project_config: Optional[dict] = None):
        self.project_config = project_config or {}
        self.extra_mappings: Dict[str, Dict[str, Any]] = {}
        self.extra_rules: Dict[str, type] = {}
        self.errors: List[str] = []
        self.manifests: List[PluginManifest] = []

    def load_all(self) -> None:
        """Discover and load all plugins. Errors are collected, not raised."""
        self.manifests = discover_plugins(self.project_config)

        for manifest in self.manifests:
            try:
                if manifest.type == "mappings":
                    mappings = load_mapping_pack(manifest.path)
                    # Check for conflicts
                    for key in mappings:
                        if key in self.extra_mappings:
                            self.errors.append(
                                f"Mapping conflict: '{key}' defined in multiple packs"
                            )
                    self.extra_mappings.update(mappings)
                elif manifest.type == "rules":
                    rules = load_rule_pack(manifest.path)
                    for key in rules:
                        if key in self.extra_rules:
                            self.errors.append(
                                f"Rule conflict: '{key}' defined in multiple packs"
                            )
                    self.extra_rules.update(rules)
            except PluginError as exc:
                self.errors.append(str(exc))
            except Exception as exc:
                self.errors.append(f"Unexpected error loading {manifest.path}: {exc}")

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


# ── Helpers ───────────────────────────────────────────────────────────────


def _validate_manifest(
    manifest: dict, path: str, expected_type: Optional[str] = None
) -> None:
    """Validate a [manifest] section from a TOML pack."""
    if not manifest.get("name"):
        raise PluginError(f"Pack {path}: [manifest] must include 'name'")

    pack_type = manifest.get("type", "")
    if expected_type and pack_type != expected_type:
        raise PluginError(
            f"Pack {path}: expected type '{expected_type}', got '{pack_type}'"
        )
