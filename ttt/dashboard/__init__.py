"""
TTT Dashboard — Unified HTML dashboard for migration runs.

Generates a standalone HTML landing page linking all migration artifacts:
conversion summary, review markers, doctor issues, analysis, benchmark, docs.
"""

from .generator import DashboardGenerator, generate_dashboard

__all__ = [
    "DashboardGenerator",
    "generate_dashboard",
]
