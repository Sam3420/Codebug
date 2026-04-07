"""Patch parsing and application utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class LineReplacement:
    """Single line replacement patch operation."""

    line_no: int
    content: str


class PatchError(ValueError):
    """Raised when a patch payload is invalid."""


def parse_patch(patch: str) -> List[LineReplacement] | None:
    """
    Parse a patch payload.

    Supported formats:
    - Full replacement source: any non-JSON string. Returns ``None``.
    - JSON array of objects: [{"line_no": 3, "content": "fixed line"}]
    """

    try:
        data = json.loads(patch)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, list):
        raise PatchError("Patch JSON must be an array of line replacement objects.")

    replacements: List[LineReplacement] = []
    for item in data:
        if not isinstance(item, dict):
            raise PatchError("Each patch entry must be an object.")
        line_no = item.get("line_no")
        content = item.get("content")
        if not isinstance(line_no, int) or line_no < 1:
            raise PatchError("Patch line_no must be a positive integer.")
        if not isinstance(content, str):
            raise PatchError("Patch content must be a string.")
        replacements.append(LineReplacement(line_no=line_no, content=content))
    return replacements


def apply_patch(source: str, patch: str) -> tuple[str, int]:
    """Apply a patch and return the patched source plus changed-line count."""

    replacements = parse_patch(patch)
    if replacements is None:
        normalized = patch.replace("\r\n", "\n")
        changed = _count_changed_lines(source, normalized)
        return normalized, changed

    lines = source.splitlines()
    changed = 0
    for replacement in replacements:
        if replacement.line_no > len(lines):
            raise PatchError(
                f"Patch line {replacement.line_no} is outside the source file."
            )
        idx = replacement.line_no - 1
        if lines[idx] != replacement.content:
            changed += 1
        lines[idx] = replacement.content
    patched = "\n".join(lines)
    if source.endswith("\n"):
        patched += "\n"
    return patched, changed


def _count_changed_lines(original: str, patched: str) -> int:
    original_lines = original.splitlines()
    patched_lines = patched.splitlines()
    overlap = min(len(original_lines), len(patched_lines))
    changed = sum(
        1 for idx in range(overlap) if original_lines[idx] != patched_lines[idx]
    )
    changed += abs(len(original_lines) - len(patched_lines))
    return changed
