from __future__ import annotations

"""Unified System Explorer — connected navigation across inventory facts."""

from dataclasses import dataclass, field
from typing import Any

from snapshot import get_relationships


@dataclass
class ExplorerNode:
    stable_id: str
    category: str
    name: str
    path: str | None = None
    summary: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExplorerEdge:
    source: str
    target: str
    relation_type: str
    evidence: str = ""


@dataclass
class ExplorerGraph:
    root: ExplorerNode
    nodes: list[ExplorerNode]
    edges: list[ExplorerEdge]
    path_labels: list[str]


def _node_from_row(row: Any) -> ExplorerNode:
    return ExplorerNode(
        stable_id=getattr(row, "stable_id", None) or "",
        category=getattr(row, "category", "") or "",
        name=getattr(row, "name", "") or "",
        path=getattr(row, "path", None),
        summary=getattr(row, "explanation", None) or getattr(row, "item_type", None) or "",
        meta={
            "project_key": getattr(row, "project_key", None),
            "startup_impact": getattr(row, "startup_impact", None),
            "knowledge_key": getattr(row, "knowledge_key", None),
            "running_state": getattr(row, "running_state", None),
            "network_ports": getattr(row, "network_ports", None),
            "disk_usage": getattr(row, "disk_usage", None),
            "risk": getattr(row, "risk", None),
        },
    )


def find_rows(rows: list[Any], query: str) -> list[Any]:
    q = (query or "").strip().lower()
    if not q:
        return []
    hits = []
    for row in rows:
        blob = " ".join(
            str(x)
            for x in (
                getattr(row, "name", None),
                getattr(row, "path", None),
                getattr(row, "bundle_id", None),
                getattr(row, "label", None),
                getattr(row, "project_key", None),
            )
            if x
        ).lower()
        if q in blob:
            hits.append(row)
    return hits


def build_explorer_graph(
    snapshot_id: int,
    rows: list[Any],
    *,
    root_query: str | None = None,
    root_stable_id: str | None = None,
    max_depth: int = 3,
) -> ExplorerGraph | None:
    by_id = {r.stable_id: r for r in rows if getattr(r, "stable_id", None)}
    root_row = None
    if root_stable_id and root_stable_id in by_id:
        root_row = by_id[root_stable_id]
    elif root_query:
        hits = find_rows(rows, root_query)
        root_row = hits[0] if hits else None
    if root_row is None:
        return None

    rels = get_relationships(snapshot_id)
    adjacency: dict[str, list[tuple[str, str, str]]] = {}
    for rel in rels:
        adjacency.setdefault(rel.source_stable_id, []).append(
            (rel.target_stable_id, rel.relation_type, rel.evidence or "")
        )
        adjacency.setdefault(rel.target_stable_id, []).append(
            (rel.source_stable_id, f"rev:{rel.relation_type}", rel.evidence or "")
        )

    root = _node_from_row(root_row)
    nodes = {root.stable_id: root}
    edges: list[ExplorerEdge] = []
    frontier = [(root.stable_id, 0)]
    seen_edges: set[tuple[str, str, str]] = set()

    while frontier:
        current, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        for neighbor, rel_type, evidence in adjacency.get(current, []):
            key = (current, neighbor, rel_type)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(ExplorerEdge(current, neighbor, rel_type, evidence))
            if neighbor not in nodes and neighbor in by_id:
                nodes[neighbor] = _node_from_row(by_id[neighbor])
                frontier.append((neighbor, depth + 1))

    # Soft-link project members even if relationship rows missing
    project_key = getattr(root_row, "project_key", None) or (
        root_row.path if root_row.category == "Projects" else None
    )
    if project_key:
        for row in rows:
            if getattr(row, "project_key", None) == project_key and row.stable_id and row.stable_id not in nodes:
                nodes[row.stable_id] = _node_from_row(row)
                edges.append(ExplorerEdge(root.stable_id, row.stable_id, "project_member", "project_key association"))

    path_labels = _preferred_path_labels(root, list(nodes.values()), edges)
    return ExplorerGraph(root=root, nodes=list(nodes.values()), edges=edges, path_labels=path_labels)


def _preferred_path_labels(root: ExplorerNode, nodes: list[ExplorerNode], edges: list[ExplorerEdge]) -> list[str]:
    """Build a readable chain emphasizing understanding questions."""
    order_pref = [
        "Applications",
        "Processes",
        "Startup",
        "Login Items",
        "Background Items",
        "Projects",
        "Python",
        "Node",
        "Docker",
        "Network",
        "AI",
        "Homebrew",
        "Services",
    ]
    by_cat: dict[str, list[ExplorerNode]] = {}
    for node in nodes:
        by_cat.setdefault(node.category, []).append(node)
    labels = [f"{root.category}: {root.name}"]
    for cat in order_pref:
        if cat == root.category:
            continue
        group = by_cat.get(cat) or []
        if group:
            labels.append(f"{cat}: {group[0].name}" + (f" (+{len(group)-1})" if len(group) > 1 else ""))
    labels.extend(["Reports", "Timeline", "Cleanup", "Knowledge"])
    return labels


def explorer_table(graph: ExplorerGraph) -> list[dict[str, Any]]:
    by_id = {n.stable_id: n for n in graph.nodes}
    rows = []
    for edge in graph.edges:
        src = by_id.get(edge.source)
        dst = by_id.get(edge.target)
        rows.append(
            {
                "From": src.name if src else edge.source,
                "From category": src.category if src else "",
                "Relation": edge.relation_type,
                "To": dst.name if dst else edge.target,
                "To category": dst.category if dst else "",
                "Evidence": edge.evidence,
            }
        )
    return rows
