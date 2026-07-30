from __future__ import annotations

from typing import Any


def health_score(items: list[Any]) -> tuple[int, list[str]]:
    score = 100
    notes: list[str] = []
    unknown = len([i for i in items if getattr(i, "risk", None) == "Unknown"])
    orphaned = len([i for i in items if getattr(i, "risk", None) == "Orphaned" or getattr(i, "classification", None) == "Orphaned"])
    startup = len(
        [
            i
            for i in items
            if getattr(i, "category", None) == "Startup" and not getattr(i, "protected", False)
        ]
    )
    listeners = len([i for i in items if getattr(i, "category", None) == "Network"])
    if unknown:
        score -= min(10, unknown // 10)
        notes.append(f"{unknown} unclassified items")
    if orphaned:
        score -= min(15, orphaned * 2)
        notes.append(f"{orphaned} orphaned startup items")
    if startup > 20:
        score -= 5
        notes.append(f"{startup} third-party startup items")
    if listeners > 15:
        score -= 5
        notes.append(f"{listeners} listening network ports")
    return max(score, 0), notes
