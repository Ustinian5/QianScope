from __future__ import annotations

import os
from pathlib import Path


def resolve_project_resource(relative_path: str | Path, *, module_file: str) -> Path:
    """Resolve a repository resource in source checkouts and installed containers."""

    relative = Path(relative_path)
    configured_root = os.getenv("QIANSCOPE_RESOURCE_ROOT")
    roots = [Path(configured_root)] if configured_root else []
    roots.extend((Path.cwd(), Path(module_file).resolve().parents[3]))
    checked: list[Path] = []
    for root in roots:
        candidate = (root / relative).resolve()
        if candidate in checked:
            continue
        checked.append(candidate)
        if candidate.is_file():
            return candidate
    checked_locations = ", ".join(str(path) for path in checked)
    raise FileNotFoundError(
        f"QianScope resource {relative.as_posix()} was not found; checked {checked_locations}"
    )


__all__ = ["resolve_project_resource"]
