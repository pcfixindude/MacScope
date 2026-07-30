from __future__ import annotations

"""Local natural-language inventory search (rule-based, no cloud AI)."""

import re
from typing import Any


def search_inventory(query: str, rows: list[Any]) -> list[Any]:
    """Return inventory rows matching a natural-language or keyword query."""
    q = (query or "").strip().lower()
    if not q:
        return list(rows)

    size_match = re.search(r"(?:larger|bigger|over|above|>)\s*than\s*(\d+(?:\.\d+)?)\s*(gb|mb|g|m)?", q)
    min_bytes = None
    if size_match:
        amount = float(size_match.group(1))
        unit = (size_match.group(2) or "gb").lower()
        min_bytes = amount * (1024**3 if unit.startswith("g") else 1024**2)

    publisher_match = re.search(r"(?:by|from|publisher|vendor)\s+([a-z0-9 ._+\-]+)", q)
    publisher = publisher_match.group(1).strip() if publisher_match else None

    def _text(row: Any) -> str:
        parts = [
            getattr(row, "name", None),
            getattr(row, "category", None),
            getattr(row, "item_type", None),
            getattr(row, "publisher", None),
            getattr(row, "vendor", None),
            getattr(row, "path", None),
            getattr(row, "explanation", None),
            getattr(row, "classification", None),
            getattr(row, "bundle_id", None),
            getattr(row, "label", None),
            getattr(row, "network_ports", None),
            getattr(row, "project_key", None),
        ]
        return " ".join(str(p) for p in parts if p).lower()

    results = []
    for row in rows:
        text = _text(row)
        category = (getattr(row, "category", None) or "").lower()
        ok = True

        if "python" in q and "python" not in text and category != "python":
            if "apps using python" in q or "using python" in q:
                ok = category in {"python", "processes", "projects"} and "python" in text
            else:
                ok = category == "python" or "python" in text
        if "startup" in q or "launch agent" in q or "login item" in q:
            ok = ok and category in {"startup", "login items", "background items"}
        if "ai " in q or q.startswith("ai") or "model" in q and "ai" in q:
            ok = ok and (category == "ai" or "ollama" in text or "lm studio" in text or "gguf" in text)
        if "listen" in q or "port" in q:
            ok = ok and (category == "network" or bool(getattr(row, "network_ports", None)))
        if "unused" in q or "orphan" in q:
            ok = ok and (
                bool(getattr(row, "orphan_status", False))
                or (getattr(row, "risk", "") in {"Orphaned", "Caution"} and category in {"python", "node", "ai", "startup"})
            )
        if "adobe" in q or (publisher and "adobe" in publisher):
            ok = ok and ("adobe" in text)
        elif publisher:
            ok = ok and publisher.lower() in text
        if min_bytes is not None:
            disk = getattr(row, "disk_usage", None) or 0
            ok = ok and float(disk) >= min_bytes
        if "docker" in q:
            ok = ok and (category == "docker" or "docker" in text)
        if "homebrew" in q or "brew" in q:
            ok = ok and category in {"homebrew", "services"}
        if "application" in q or "apps" in q:
            if "using python" not in q:
                ok = ok and category == "applications"

        # Fallback keyword AND match for generic queries (skip when structured filters already applied)
        structured = any(
            k in q
            for k in (
                "python",
                "startup",
                "ai",
                "listen",
                "port",
                "unused",
                "adobe",
                "docker",
                "homebrew",
                "apps",
                "application",
                "larger",
                "bigger",
                "over",
                "above",
                "gb",
                "mb",
            )
        )
        tokens = [
            t
            for t in re.split(r"\W+", q)
            if t
            and t not in {
                "than",
                "using",
                "software",
                "the",
                "and",
                "for",
                "on",
                "by",
                "from",
                "larger",
                "bigger",
                "over",
                "above",
                "gb",
                "mb",
                "g",
                "m",
            }
            and not t.isdigit()
        ]
        if ok and not structured:
            ok = all(tok in text for tok in tokens[:6]) if tokens else True

        if ok:
            results.append(row)
    return results
