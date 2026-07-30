from __future__ import annotations

import hashlib
from typing import Any


def stable_id(*parts: Any, prefix: str = "") -> str:
    """Deterministic stable identifier from canonical parts."""
    normalized = "|".join("" if p is None else str(p).strip() for p in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}{digest}" if prefix else digest


def item_stable_id(
    *,
    category: str,
    name: str | None = None,
    path: str | None = None,
    label: str | None = None,
    bundle_id: str | None = None,
    executable_path: str | None = None,
    extra: str | None = None,
) -> str:
    """Stable ID for inventory entities that persist across snapshots."""
    return stable_id(
        category,
        bundle_id or label or "",
        name or "",
        path or "",
        executable_path or "",
        extra or "",
        prefix=f"{category.lower().replace(' ', '_')}:",
    )
