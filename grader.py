"""Compatibility shim exposing public grader registry at the repo root."""

from .graders import GRADERS, GRADER_SPECS, grade_task

__all__ = ["GRADERS", "GRADER_SPECS", "grade_task"]
