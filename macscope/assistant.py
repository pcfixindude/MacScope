from __future__ import annotations

"""Local assistant that answers only from inventory/timeline facts."""

from datetime import datetime, timedelta
from typing import Any

from macscope.search import search_inventory
from macscope.timeline import list_timeline
from utils import format_bytes


def answer_question(question: str, rows: list[Any]) -> str:
    q = (question or "").strip()
    if not q:
        return "Ask a question about your local MacScope inventory."
    ql = q.lower()

    if "using memory" in ql or "memory" in ql and ("what" in ql or "top" in ql or "most" in ql):
        procs = [r for r in rows if getattr(r, "category", None) == "Processes"]
        ranked = sorted(procs, key=lambda r: float(getattr(r, "memory", None) or 0), reverse=True)[:10]
        if not ranked:
            return "No process memory data is available in the current snapshot."
        lines = ["Top memory consumers in the current snapshot:"]
        for r in ranked:
            lines.append(f"- {r.name}: {getattr(r, 'memory', 0):.1f}% (PID {getattr(r, 'pid', '—')})")
        return "\n".join(lines)

    if "uninstall docker" in ql or "remove docker" in ql or "can i uninstall docker" in ql:
        docker = [r for r in rows if getattr(r, "category", None) == "Docker"]
        apps = [r for r in rows if getattr(r, "category", None) == "Applications" and "docker" in (r.name or "").lower()]
        running = [r for r in docker if getattr(r, "running_state", None) == "Running" or str(getattr(r, "status", "")).lower() == "running"]
        facts = [
            f"Docker-related inventory items: {len(docker)}.",
            f"Docker applications found: {', '.join(a.name for a in apps) or 'none in Applications category'}.",
            f"Running Docker containers/services observed: {len(running)}.",
        ]
        if running:
            facts.append("Because containers or the daemon appear running, uninstalling now may interrupt active workloads.")
        facts.append("MacScope can help quit/stop Docker components, but you should review dependents before uninstalling.")
        facts.append("This answer uses only local snapshot facts and does not claim whether you personally need Docker.")
        return "\n".join(facts)

    if "why is this process" in ql or ("why" in ql and "process" in ql):
        # Prefer explicit name after 'process'
        name = None
        for marker in ("process ", "running ", "is "):
            if marker in ql:
                name = q[ql.index(marker) + len(marker) :].strip(" ?.")
                break
        candidates = search_inventory(name or q, [r for r in rows if getattr(r, "category", None) == "Processes"])
        if not candidates:
            return "I could not find a matching process in the current snapshot. Select a process or include its name."
        proc = candidates[0]
        bits = [
            f"Process: {proc.name}",
            f"Executable: {getattr(proc, 'executable_path', None) or getattr(proc, 'path', None) or 'unknown'}",
            f"User: {getattr(proc, 'user_owner', None) or 'unknown'}",
            f"Parent: {getattr(proc, 'parent_process', None) or 'unknown'}",
            f"Related application: {getattr(proc, 'related_application', None) or 'unknown'}",
            f"Explanation: {getattr(proc, 'explanation', None) or 'No additional local explanation is available.'}",
        ]
        return "\n".join(bits)

    if "changed yesterday" in ql or "what changed" in ql:
        since = datetime.utcnow() - timedelta(days=1)
        events = [e for e in list_timeline(limit=300) if e.created_at and e.created_at >= since]
        if not events:
            return "No timeline events from the last 24 hours were found in the local database."
        lines = [f"Local timeline events in the last 24 hours ({len(events)}):"]
        for e in events[:25]:
            lines.append(f"- {e.created_at}: {e.title}")
        return "\n".join(lines)

    if "launchagent" in ql or "launch agent" in ql or ("why" in ql and "startup" in ql):
        hits = search_inventory(q, [r for r in rows if getattr(r, "category", None) in {"Startup", "Login Items", "Background Items"}])
        if not hits:
            return "No matching startup item was found in the current snapshot."
        item = hits[0]
        return "\n".join(
            [
                f"Startup item: {item.name}",
                f"Type: {getattr(item, 'item_type', None) or item.category}",
                f"Path: {getattr(item, 'path', None) or 'unknown'}",
                f"Executable: {getattr(item, 'executable_path', None) or 'unknown'}",
                f"Startup state: {getattr(item, 'startup_state', None) or 'unknown'}",
                f"Impact: {getattr(item, 'startup_impact', None) or 'not scored'}",
                f"Explanation: {getattr(item, 'explanation', None) or 'No local explanation available.'}",
                f"Knowledge: {((getattr(item, 'details', None) or {}) if isinstance(getattr(item, 'details', None), dict) else {})}",
            ]
        )

    # Generic grounded search summary
    hits = search_inventory(q, rows)
    if not hits:
        return "No matching items were found in the current local snapshot. I will not invent an answer."
    lines = [f"Found {len(hits)} local inventory match(es):"]
    for row in hits[:15]:
        disk = getattr(row, "disk_usage", None)
        disk_s = f", {format_bytes(disk)}" if disk else ""
        lines.append(f"- [{row.category}] {row.name}{disk_s}")
    lines.append("Answers are limited to facts present in the current MacScope snapshot and timeline.")
    return "\n".join(lines)
