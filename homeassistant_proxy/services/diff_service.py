from __future__ import annotations

from difflib import unified_diff


def create_unified_diff(*, target_path: str, base_content: str, proposed_content: str) -> str:
    diff_lines = unified_diff(
        base_content.splitlines(keepends=True),
        proposed_content.splitlines(keepends=True),
        fromfile=target_path,
        tofile=target_path,
        lineterm="\n",
    )
    return "".join(diff_lines)
