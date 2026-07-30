from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from inventory import Item
from utils import format_bytes


@dataclass
class CleanupCandidate:
    candidate_type: str
    path: str | None
    name: str
    size: float | None
    reason: str
    confidence: float
    last_modified: str | None
    related_software: str | None
    risk: str
    recommended_action: str
    stable_id: str | None = None
    details: dict[str, Any] | None = None


def find_cleanup_candidates(items: list[Item]) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    app_names = {i.name for i in items if i.category == "Applications"}
    app_bundles = {i.bundle_id for i in items if i.category == "Applications" and i.bundle_id}

    for item in items:
        if item.orphan_status or item.classification == "Orphaned" or item.risk == "Orphaned":
            candidates.append(
                CleanupCandidate(
                    candidate_type="Orphaned startup item",
                    path=item.path,
                    name=item.name,
                    size=item.disk_usage,
                    reason=item.explanation or "Referenced executable missing.",
                    confidence=item.confidence or 0.8,
                    last_modified=item.modification_date,
                    related_software=item.related_application,
                    risk="Caution",
                    recommended_action="Disable or move plist to disabled-items backup",
                    stable_id=item.stable_id,
                )
            )
        if item.category == "Docker" and item.item_type == "Container" and (item.running_state == "Stopped" or str(item.status).lower() in {"exited", "created", "stopped"}):
            candidates.append(
                CleanupCandidate(
                    "Stopped Docker container",
                    None,
                    item.name,
                    None,
                    "Container is not running.",
                    0.7,
                    None,
                    "Docker",
                    "Caution",
                    "Remove stopped container after review",
                    item.stable_id,
                )
            )
        if item.category == "Docker" and item.item_type == "Image" and (item.name.startswith("<none>") or ":none" in item.name or item.name.endswith(":<none>")):
            candidates.append(
                CleanupCandidate(
                    "Dangling Docker image",
                    None,
                    item.name,
                    None,
                    "Image appears untagged/dangling.",
                    0.75,
                    None,
                    "Docker",
                    "Caution",
                    "Remove dangling image after review",
                    item.stable_id,
                )
            )
        if item.category == "Python" and item.subtype == "venv" and not item.protected:
            candidates.append(
                CleanupCandidate(
                    "Python virtual environment",
                    item.path,
                    item.name,
                    item.disk_usage,
                    "Project virtual environment — remove only if unused.",
                    0.4,
                    item.modification_date,
                    item.related_application,
                    "Caution",
                    "Delete selected project virtual environment",
                    item.stable_id,
                )
            )
        if item.category == "Node" and item.subtype == "node_modules":
            candidates.append(
                CleanupCandidate(
                    "node_modules folder",
                    item.path,
                    item.name,
                    item.disk_usage,
                    "Can be reinstalled from lockfile.",
                    0.6,
                    item.modification_date,
                    item.related_application,
                    "Caution",
                    "Remove selected node_modules after confirmation",
                    item.stable_id,
                )
            )
        if item.category == "AI" and item.item_type == "Model File":
            candidates.append(
                CleanupCandidate(
                    "AI model file",
                    item.path,
                    item.name,
                    item.disk_usage,
                    "Large local model file.",
                    0.3,
                    item.modification_date,
                    item.related_application,
                    "Caution",
                    "Move selected model to Trash after confirmation",
                    item.stable_id,
                )
            )
        if item.category == "Storage" and item.name in {"Caches", "Logs", "Trash", "Downloads"}:
            candidates.append(
                CleanupCandidate(
                    f"Storage · {item.name}",
                    item.path,
                    item.name,
                    item.disk_usage,
                    f"Bounded scan found {format_bytes(item.disk_usage)} under {item.name}.",
                    0.4,
                    None,
                    None,
                    "Caution",
                    "Reveal and review before deleting anything",
                    item.stable_id,
                )
            )

    # Application support orphans (heuristic)
    support_root = Path.home() / "Library" / "Application Support"
    if support_root.exists():
        try:
            for child in support_root.iterdir():
                if not child.is_dir() or child.name.startswith("."):
                    continue
                if child.name in {"MacScope", "Apple", "com.apple.sharedfilelist"}:
                    continue
                # If folder looks like a reverse-dns bundle and no matching app
                if "." in child.name and child.name not in app_bundles and not any(child.name.endswith(n.replace(" ", "")) for n in app_names):
                    try:
                        mtime = child.stat().st_mtime
                        age_ok = datetime.fromtimestamp(mtime) < datetime.now() - timedelta(days=30)
                    except OSError:
                        age_ok = False
                        mtime = None
                    if age_ok:
                        candidates.append(
                            CleanupCandidate(
                                "Possible orphaned application support folder",
                                str(child),
                                child.name,
                                None,
                                "No matching installed application bundle ID was found (heuristic).",
                                0.35,
                                str(mtime) if mtime else None,
                                child.name,
                                "Caution",
                                "Preview and move to Trash only if confirmed unused",
                                None,
                            )
                        )
        except OSError:
            pass

    # Duplicate AI model filenames
    ai_files = [i for i in items if i.category == "AI" and i.item_type == "Model File" and i.path]
    by_name: dict[str, list[Item]] = {}
    for item in ai_files:
        by_name.setdefault(Path(item.path).name if item.path else item.name, []).append(item)
    for fname, group in by_name.items():
        if len(group) > 1:
            for item in group:
                candidates.append(
                    CleanupCandidate(
                        "Duplicate AI model filename",
                        item.path,
                        fname,
                        item.disk_usage,
                        f"{len(group)} files share this filename (hash comparison not run).",
                        0.5,
                        item.modification_date,
                        "AI",
                        "Caution",
                        "Review duplicates; optionally hash-compare on demand",
                        item.stable_id,
                    )
                )

    # Unused apps: installed, not running, not referenced by startup/login
    startup_names = {
        (i.related_application or i.name or "").lower()
        for i in items
        if i.category in {"Startup", "Login Items", "Background Items"}
    }
    for item in items:
        if item.category != "Applications" or item.protected:
            continue
        if item.running_state == "Running":
            continue
        if (item.name or "").lower() in startup_names:
            continue
        candidates.append(
            CleanupCandidate(
                "Possibly unused application",
                item.path,
                item.name,
                item.disk_usage,
                "Not running and not referenced by startup/login items in this snapshot.",
                0.35,
                item.modification_date,
                item.name,
                "Caution",
                "Review before moving to Trash",
                item.stable_id,
            )
        )

    # Old downloads (>90 days)
    downloads = Path.home() / "Downloads"
    if downloads.exists():
        cutoff = datetime.now() - timedelta(days=90)
        try:
            for child in downloads.iterdir():
                try:
                    st = child.stat()
                    mtime = datetime.fromtimestamp(st.st_mtime)
                    if mtime >= cutoff:
                        continue
                    size = float(st.st_size if child.is_file() else 0)
                    candidates.append(
                        CleanupCandidate(
                            "Old download",
                            str(child),
                            child.name,
                            size if size else None,
                            "File/folder in Downloads older than 90 days.",
                            0.45,
                            str(st.st_mtime),
                            "Downloads",
                            "Caution",
                            "Reveal and review before deleting",
                            None,
                        )
                    )
                except OSError:
                    continue
        except OSError:
            pass

    return candidates


def advisor_rows(items: list[Item]) -> list[dict[str, Any]]:
    """Serialize cleanup advisor recommendations for UI/tables."""
    rows = []
    for c in find_cleanup_candidates(items):
        rows.append(
            {
                "Type": c.candidate_type,
                "Name": c.name,
                "Path": c.path,
                "Estimated reclaim": format_bytes(c.size) if c.size else "—",
                "Size bytes": c.size or 0,
                "Reason": c.reason,
                "Confidence": c.confidence,
                "Risk": c.risk,
                "Recommended action": c.recommended_action,
                "Related": c.related_software,
                "Last modified": c.last_modified,
                "Stable ID": c.stable_id,
            }
        )
    return rows
