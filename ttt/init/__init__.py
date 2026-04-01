"""
Project initialization — ``ttt init`` scaffolds a ttt.project.toml file.
"""

from .scaffold import init_project, InitResult

__all__ = ["init_project", "InitResult"]
