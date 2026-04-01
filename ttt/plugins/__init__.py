"""
Plugin system — Load custom mapping packs and lint/fix rule packs.
"""

from .loader import (
    PluginLoader,
    PluginManifest,
    PluginError,
    load_mapping_pack,
    load_rule_pack,
    discover_plugins,
)

__all__ = [
    "PluginLoader",
    "PluginManifest",
    "PluginError",
    "load_mapping_pack",
    "load_rule_pack",
    "discover_plugins",
]
