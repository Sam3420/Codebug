"""Compatibility shim exposing grader utilities inside the server package."""

from .grader import GradeResult, grade_submission, run_hidden_tests

__all__ = ["GradeResult", "grade_submission", "run_hidden_tests"]
