"""
TTT Script Generator — Generates script skeletons for OTServ (scaffolding).

Exports:
  - generate_script(...): main entry point
  - ScriptTemplate: template registry
"""

from .templates import (
    generate_script,
    ScriptTemplate,
    TEMPLATE_TYPES,
)

__all__ = [
    "generate_script",
    "ScriptTemplate",
    "TEMPLATE_TYPES",
]
