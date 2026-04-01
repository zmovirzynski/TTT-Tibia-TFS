"""
XML validator for OTServ server data files.

Validates:
  - XML is well-formed (parseable)
  - Required attributes are present
  - Script paths referenced in XML exist on disk
"""

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List

from ..utils import read_file_safe, find_xml_files


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class XmlIssue:
    """A single XML validation issue."""
    severity: str   # "error", "warning"
    check_name: str  # "xml-malformed", "xml-missing-attr", "xml-missing-script"
    filepath: str
    line: int = 0
    message: str = ""

    def as_dict(self) -> Dict:
        return {
            "severity": self.severity,
            "check_name": self.check_name,
            "filepath": self.filepath,
            "line": self.line,
            "message": self.message,
        }


@dataclass
class XmlValidationReport:
    """Aggregated XML validation results."""
    issues: List[XmlIssue] = field(default_factory=list)
    total_files_scanned: int = 0
    total_files_valid: int = 0

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def errors(self) -> List[XmlIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[XmlIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def as_dict(self) -> Dict:
        return {
            "issues": [i.as_dict() for i in self.issues],
            "total_files_scanned": self.total_files_scanned,
            "total_files_valid": self.total_files_valid,
            "total_issues": self.total_issues,
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
        }


# ---------------------------------------------------------------------------
# Required attributes per element type
# ---------------------------------------------------------------------------

# Maps tag name -> list of (required_attr_set, description)
# At least one of the required_attr_sets must be fully present
REQUIRED_ATTRS = {
    "action": [
        ({"script"}, "action must have a 'script' attribute"),
        # Must also have one of itemid/fromid/actionid/uniqueid
    ],
    "movevent": [
        ({"script"}, "movevent must have a 'script' attribute"),
    ],
    "talkaction": [
        ({"words"}, "talkaction must have a 'words' attribute"),
        ({"script"}, "talkaction must have a 'script' attribute"),
    ],
    "event": [
        ({"name"}, "event must have a 'name' attribute"),
        ({"type"}, "event must have a 'type' attribute"),
    ],
    "globalevent": [
        ({"name"}, "globalevent must have a 'name' attribute"),
    ],
}

# IDs required for certain tags (at least one must be present)
ID_ATTRS = {
    "action": ["itemid", "fromid", "actionid", "uniqueid"],
    "movevent": ["itemid", "fromid", "actionid", "uniqueid", "tileitem", "event"],
}


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _check_wellformed(xml_path: str) -> List[XmlIssue]:
    """Check if an XML file is well-formed."""
    issues = []
    content = read_file_safe(xml_path)
    if content is None:
        issues.append(XmlIssue(
            severity="error",
            check_name="xml-malformed",
            filepath=xml_path,
            message="File could not be read",
        ))
        return issues

    try:
        ET.fromstring(content)
    except ET.ParseError as e:
        line = 0
        msg = str(e)
        # Extract line number from error: "syntax error: line X, column Y"
        m = re.search(r'line (\d+)', msg)
        if m:
            line = int(m.group(1))
        issues.append(XmlIssue(
            severity="error",
            check_name="xml-malformed",
            filepath=xml_path,
            line=line,
            message=f"XML parse error: {msg}",
        ))

    return issues


def _check_required_attrs(xml_path: str) -> List[XmlIssue]:
    """Check that required attributes are present on XML elements."""
    issues = []
    content = read_file_safe(xml_path)
    if content is None:
        return issues

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return issues  # already caught by wellformed check

    # Build line map: find line numbers for elements
    lines = content.split("\n")

    def _find_element_line(tag_name: str, attribs: dict, start_from: int = 0) -> int:
        """Best-effort line number finder for an element."""
        for i in range(start_from, len(lines)):
            line_lower = lines[i].lower()
            if f"<{tag_name.lower()}" in line_lower:
                # Check if attribs match
                match = True
                for k, v in list(attribs.items())[:1]:
                    if f'{k}=' in line_lower:
                        match = True
                        break
                if match:
                    return i + 1  # 1-based
        return 0

    line_counter = 0
    for elem in root.iter():
        tag = elem.tag.lower()
        attribs_lower = {k.lower(): v for k, v in elem.attrib.items()}

        line_counter = _find_element_line(tag, elem.attrib, max(0, line_counter - 1))

        # Check required attrs
        if tag in REQUIRED_ATTRS:
            for required_set, desc in REQUIRED_ATTRS[tag]:
                for attr in required_set:
                    if attr not in attribs_lower:
                        issues.append(XmlIssue(
                            severity="warning",
                            check_name="xml-missing-attr",
                            filepath=xml_path,
                            line=line_counter,
                            message=f"Missing attribute '{attr}' — {desc}",
                        ))

        # Check that actions/movements have at least one ID attribute
        if tag in ID_ATTRS:
            id_list = ID_ATTRS[tag]
            has_id = any(a in attribs_lower for a in id_list)
            if not has_id:
                # Check if it's the root element (e.g. <actions>)
                if tag not in ("actions", "movements", "talkactions",
                               "creaturescripts", "globalevents"):
                    issues.append(XmlIssue(
                        severity="warning",
                        check_name="xml-missing-attr",
                        filepath=xml_path,
                        line=line_counter,
                        message=f"<{tag}> has no ID attribute (expected one of: {', '.join(id_list)})",
                    ))

    return issues


def _check_script_paths(xml_path: str) -> List[XmlIssue]:
    """Check that all script paths referenced in XML exist on disk."""
    issues = []
    content = read_file_safe(xml_path)
    if content is None:
        return issues

    xml_dir = os.path.dirname(xml_path)
    scripts_dir = os.path.join(xml_dir, "scripts")

    for i, line in enumerate(content.split("\n"), start=1):
        m = re.search(r'script\s*=\s*"([^"]+)"', line, re.IGNORECASE)
        if m:
            script_ref = m.group(1)
            candidates = [
                os.path.join(xml_dir, script_ref),
                os.path.join(scripts_dir, script_ref),
            ]
            if not any(os.path.isfile(c) for c in candidates):
                issues.append(XmlIssue(
                    severity="error",
                    check_name="xml-missing-script",
                    filepath=xml_path,
                    line=i,
                    message=f"Script file not found: '{script_ref}'",
                ))

    return issues


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_xml_files(directory: str) -> XmlValidationReport:
    """Validate all XML files in a server directory."""
    report = XmlValidationReport()

    xml_files = find_xml_files(directory)
    report.total_files_scanned = len(xml_files)

    valid_count = 0
    for xml_path in xml_files:
        file_issues: List[XmlIssue] = []

        file_issues.extend(_check_wellformed(xml_path))

        # Only run further checks if XML is well-formed
        if not any(i.check_name == "xml-malformed" for i in file_issues):
            file_issues.extend(_check_required_attrs(xml_path))
            file_issues.extend(_check_script_paths(xml_path))

        if not file_issues:
            valid_count += 1

        report.issues.extend(file_issues)

    report.total_files_valid = valid_count

    report.issues.sort(key=lambda i: (
        0 if i.severity == "error" else 1,
        i.filepath,
        i.line,
    ))

    return report
