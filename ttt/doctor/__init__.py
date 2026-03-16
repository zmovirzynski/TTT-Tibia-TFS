"""
TTT Doctor — Server health-check module.

Diagnoses:
  - Lua syntax errors
  - Broken XML references
  - Conflicting item/action IDs
  - Duplicate event registrations
  - NPC keyword duplicates
  - Invalid callback signatures
  - XML validation (well-formed, required attrs, script paths)
  - Overall health score (HEALTHY / WARNING / CRITICAL)
"""

from .health_check import (
    run_health_checks,
    HealthIssue,
    HealthReport,
    HEALTH_CHECKS,
)
from .xml_validator import validate_xml_files, XmlIssue, XmlValidationReport
from .engine import (
    DoctorEngine,
    DoctorReport,
    DOCTOR_MODULES,
    format_doctor_text,
    format_doctor_json,
    format_doctor_html,
)

__all__ = [
    "run_health_checks",
    "HealthIssue",
    "HealthReport",
    "HEALTH_CHECKS",
    "validate_xml_files",
    "XmlIssue",
    "XmlValidationReport",
    "DoctorEngine",
    "DoctorReport",
    "DOCTOR_MODULES",
    "format_doctor_text",
    "format_doctor_json",
    "format_doctor_html",
]
