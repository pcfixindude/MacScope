from __future__ import annotations

"""Storage explorer buckets built from inventory + bounded path scans."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inventory import Item
from utils import dir_size_bytes, format_bytes


@dataclass
class StorageNode:
    name: str
    path: str | None
    size: float
    children: list["StorageNode"] = field(default_factory=list)
    source: str = "scan"


def build_storage_tree(items: list[Item], *, deep: bool = False) -> list[StorageNode]:
    home = Path.home()
    buckets: list[tuple[str, Path | None, str]] = [
        ("Applications", Path("/Applications"), "path"),
        ("AI Models", None, "inventory:AI"),
        ("Python", None, "inventory:Python"),
        ("Node", None, "inventory:Node"),
        ("Docker", None, "inventory:Docker"),
        ("Caches", home / "Library" / "Caches", "path"),
        ("Downloads", home / "Downloads", "path"),
        ("Desktop", home / "Desktop", "path"),
        ("Documents", home / "Documents", "path"),
        ("Other", home / "Library" / "Application Support", "path"),
    ]
    nodes: list[StorageNode] = []
    for name, path, kind in buckets:
        if kind.startswith("inventory:"):
            category = kind.split(":", 1)[1]
            children = []
            total = 0.0
            for item in items:
                if item.category != category:
                    continue
                size = float(item.disk_usage or 0)
                total += size
                children.append(
                    StorageNode(
                        name=item.name,
                        path=item.path,
                        size=size,
                        source="inventory",
                    )
                )
            children.sort(key=lambda n: n.size, reverse=True)
            nodes.append(StorageNode(name=name, path=None, size=total, children=children[:40], source="inventory"))
            continue
        assert path is not None
        if not path.exists():
            nodes.append(StorageNode(name=name, path=str(path), size=0, children=[], source="missing"))
            continue
        limit = 8000 if deep else 2500
        size = float(dir_size_bytes(path, max_files=limit))
        children: list[StorageNode] = []
        try:
            entries = [p for p in path.iterdir() if not p.name.startswith(".")]
            scored: list[tuple[float, Path]] = []
            for child in entries[:80]:
                child_size = float(dir_size_bytes(child, max_files=800 if deep else 400)) if child.is_dir() else float(child.stat().st_size)
                scored.append((child_size, child))
            scored.sort(reverse=True)
            for child_size, child in scored[:15]:
                children.append(StorageNode(name=child.name, path=str(child), size=child_size, source="scan"))
        except OSError:
            pass
        nodes.append(StorageNode(name=name, path=str(path), size=size, children=children, source="scan"))
    nodes.sort(key=lambda n: n.size, reverse=True)
    return nodes


def treemap_dataframe(nodes: list[StorageNode]) -> list[dict[str, Any]]:
    """Flat rows suitable for a simple treemap / bar visualization."""
    rows: list[dict[str, Any]] = []
    for node in nodes:
        rows.append(
            {
                "Bucket": node.name,
                "Item": node.name,
                "Size bytes": node.size,
                "Size": format_bytes(node.size),
                "Path": node.path or "",
            }
        )
        for child in node.children:
            rows.append(
                {
                    "Bucket": node.name,
                    "Item": child.name,
                    "Size bytes": child.size,
                    "Size": format_bytes(child.size),
                    "Path": child.path or "",
                }
            )
    return rows
