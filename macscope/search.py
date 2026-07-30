from __future__ import annotations

"""Local natural-language inventory search v2 (rule-based, no cloud AI)."""

import re
from datetime import datetime, timedelta
from typing import Any

from macscope.timeline import list_timeline, timeline_for_period


def search_inventory(query: str, rows: list[Any]) -> list[Any]:
    """Return inventory rows matching a natural-language or keyword query."""
    q = (query or "").strip().lower()
    if not q:
        return list(rows)

    # Temporal inventory questions answered via timeline-backed filters when possible
    if "installed this week" in q or "what installed" in q:
        events = timeline_for_period("weekly", limit=300)
        names = {(e.title or "").split(": ", 1)[-1].lower() for e in events if e.event_type in {"software_installed", "software_updated"}}
        return [r for r in rows if (r.name or "").lower() in names] or [
            r for r in rows if r.category == "Applications" and any((r.name or "").lower() in (e.title or "").lower() for e in events)
        ]

    if "changed yesterday" in q or "what changed yesterday" in q:
        since = datetime.utcnow() - timedelta(days=1)
        events = list_timeline(limit=300, since=since)
        names = {(e.title or "").split(": ", 1)[-1].lower() for e in events}
        return [r for r in rows if (r.name or "").lower() in names]

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
            getattr(row, "subtype", None),
            getattr(row, "knowledge_key", None),
        ]
        details = getattr(row, "details", None)
        if isinstance(details, dict):
            parts.append(str(details.get("indicators")))
        return " ".join(str(p) for p in parts if p).lower()

    results = []
    for row in rows:
        text = _text(row)
        category = (getattr(row, "category", None) or "").lower()
        ok = True

        if "what uses docker" in q or ("uses docker" in q):
            ok = ("docker" in text) or category in {"docker", "projects"} and "docker" in text
            if category == "projects":
                ok = "docker" in (getattr(row, "subtype", "") or "").lower()
            elif category == "docker":
                ok = True
            elif "docker" in text:
                ok = True
            else:
                ok = False

        if "which projects use python" in q or ("projects use python" in q) or ("projects" in q and "python" in q):
            ok = category == "projects" and "python" in (getattr(row, "subtype", "") or "").lower()

        if "inactive application" in q or "inactive applications" in q or "show inactive" in q:
            ok = category == "applications" and (getattr(row, "running_state", None) != "Running")

        if "ai models are unused" in q or ("unused" in q and "ai" in q and "model" in q):
            ok = category == "ai" and (
                bool(getattr(row, "orphan_status", False))
                or getattr(row, "risk", "") in {"Orphaned", "Caution", "Unknown"}
            )

        if "python" in q and "python" not in text and category != "python" and "projects use python" not in q:
            if "apps using python" in q or "using python" in q:
                ok = category in {"python", "processes", "projects"} and "python" in text
            else:
                ok = category == "python" or "python" in text
        if "startup" in q or "launch agent" in q or "login item" in q:
            ok = ok and category in {"startup", "login items", "background items"}
        if ("ai " in q or q.startswith("ai") or ("model" in q and "ai" in q)) and "unused" not in q:
            ok = ok and (category == "ai" or "ollama" in text or "lm studio" in text or "gguf" in text)
        if "listen" in q or ("port" in q and "report" not in q):
            ok = ok and (category == "network" or bool(getattr(row, "network_ports", None)))
        if ("unused" in q or "orphan" in q) and "ai" not in q:
            ok = ok and (
                bool(getattr(row, "orphan_status", False))
                or (getattr(row, "risk", "") in {"Orphaned", "Caution"} and category in {"python", "node", "ai", "startup", "applications"})
            )
        if "adobe" in q or (publisher and "adobe" in publisher):
            ok = ok and ("adobe" in text)
        elif publisher:
            ok = ok and publisher.lower() in text
        if min_bytes is not None:
            disk = getattr(row, "disk_usage", None) or 0
            ok = ok and float(disk) >= min_bytes
        if "docker" in q and "uses docker" not in q and "what uses docker" not in q:
            ok = ok and (category == "docker" or "docker" in text)
        if "homebrew" in q or ("brew" in q and "homebrew" in q):
            ok = ok and category in {"homebrew", "services"}
        if ("application" in q or "apps" in q) and "inactive" not in q:
            if "using python" not in q:
                ok = ok and category == "applications"

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
                "inactive",
                "projects",
                "installed",
                "changed",
            )
        )
        tokens = [
            t
            for t in re.split(r"\W+", q)
            if t
            and t
            not in {
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
                "what",
                "which",
                "show",
                "are",
                "is",
                "this",
                "week",
                "yesterday",
            }
            and not t.isdigit()
        ]
        if ok and not structured:
            ok = all(tok in text for tok in tokens[:6]) if tokens else True

        if ok:
            results.append(row)
    return results


def save_search(name: str, query: str) -> None:
    from macscope.annotations import upsert_annotation

    upsert_annotation(f"saved_search:{name}", "saved_search", value=query, display_name=name)


def list_saved_searches() -> list[tuple[str, str]]:
    from macscope.annotations import list_annotations

    out = []
    for row in list_annotations(kind="saved_search"):
        out.append((row.display_name or row.stable_id, row.value))
    return out
