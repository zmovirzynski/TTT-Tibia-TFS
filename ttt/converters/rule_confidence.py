"""Per-rule confidence scoring for transformation mappings."""

from typing import Dict


def rule_confidence(mapping: Dict) -> float:
    """Compute a confidence score for a single mapping rule.

    Returns a float 0.0–1.0 indicating how "safe" the transformation is.

    Scoring:
    - 1.0: Simple method rename with no ambiguity
    - 0.9: Has a chained call (auto-appended :getId() etc.)
    - 0.8: Static method or wrapper-based transformation
    - 0.7: Custom transformation handler
    - 0.5: Has a stub marker (needs manual review)
    - 0.6: Has a TTT note (may need manual review)
    """
    if mapping.get("stub"):
        return 0.5

    if mapping.get("custom"):
        custom = mapping["custom"]
        # Some custom types are very safe
        safe_customs = {
            "type_check",
            "vocation_check",
            "item_type_getter",
            "item_type_by_name",
            "house_lookup",
            "npc_get_self",
            "npc_method_self",
        }
        if custom in safe_customs:
            return 0.85
        # Passthrough customs are lower confidence
        if "passthrough" in custom:
            return 0.6
        return 0.7

    if mapping.get("note") and "TTT:" in str(mapping.get("note", "")):
        # Has a note suggesting manual review
        base = 0.7
        if mapping.get("chain"):
            base = 0.65  # chained + note = less certain
        return base

    if mapping.get("chain"):
        return 0.9

    if mapping.get("static"):
        return 0.85

    if mapping.get("wrapper"):
        return 0.85

    method = mapping.get("method")
    if method:
        # Simple method rename — highest confidence
        return 1.0

    # No method defined — fallback/passthrough
    return 0.6


def aggregate_confidence(confidences: list) -> float:
    """Compute aggregate confidence from per-rule scores.

    Uses a weighted approach: low-confidence rules drag down the
    overall score more than high-confidence rules raise it.
    """
    if not confidences:
        return 1.0
    # Geometric-ish mean biased toward low values
    product = 1.0
    for c in confidences:
        product *= c
    geo_mean = product ** (1.0 / len(confidences))
    # Blend with arithmetic mean for stability
    arith_mean = sum(confidences) / len(confidences)
    return 0.4 * geo_mean + 0.6 * arith_mean
