from __future__ import annotations

"""Local assistant intelligence — answers only from collected evidence."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from macscope.search import search_inventory
from macscope.timeline import list_timeline
from utils import format_bytes


@dataclass
class AssistantAnswer:
    text: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    related_items: list[str] = field(default_factory=list)
    timeline_links: list[str] = field(default_factory=list)
    project_links: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        parts = [self.text, "", f"**Confidence:** {self.confidence:.0%}"]
        if self.evidence:
            parts.append("**Evidence used:**")
            parts.extend(f"- {e}" for e in self.evidence[:12])
        if self.related_items:
            parts.append("**Related items:**")
            parts.extend(f"- {i}" for i in self.related_items[:12])
        if self.timeline_links:
            parts.append("**Timeline links:**")
            parts.extend(f"- {t}" for t in self.timeline_links[:8])
        if self.project_links:
            parts.append("**Project links:**")
            parts.extend(f"- {p}" for p in self.project_links[:8])
        if self.reports:
            parts.append("**Reports:**")
            parts.extend(f"- {r}" for r in self.reports[:6])
        return "\n".join(parts)


def answer_question_detailed(question: str, rows: list[Any]) -> AssistantAnswer:
    q = (question or "").strip()
    if not q:
        return AssistantAnswer(
            "Ask a question about your local MacScope inventory.",
            0.0,
            evidence=["No question provided"],
        )
    ql = q.lower()

    if "using memory" in ql or ("memory" in ql and ("what" in ql or "top" in ql or "most" in ql)):
        procs = [r for r in rows if getattr(r, "category", None) == "Processes"]
        ranked = sorted(procs, key=lambda r: float(getattr(r, "memory", None) or 0), reverse=True)[:10]
        if not ranked:
            return AssistantAnswer(
                "No process memory data is available in the current snapshot.",
                0.2,
                evidence=["Processes category empty or missing memory fields"],
            )
        lines = ["Top memory consumers in the current snapshot:"]
        related = []
        evidence = []
        for r in ranked:
            lines.append(f"- {r.name}: {getattr(r, 'memory', 0):.1f}% (PID {getattr(r, 'pid', '—')})")
            related.append(r.name)
            evidence.append(f"{r.name} memory={getattr(r, 'memory', 0)} pid={getattr(r, 'pid', None)}")
        return AssistantAnswer("\n".join(lines), 0.9, evidence=evidence, related_items=related, reports=["Running Processes inventory"])

    if "uninstall docker" in ql or "remove docker" in ql or "can i uninstall docker" in ql:
        docker = [r for r in rows if getattr(r, "category", None) == "Docker"]
        apps = [r for r in rows if getattr(r, "category", None) == "Applications" and "docker" in (r.name or "").lower()]
        running = [r for r in docker if getattr(r, "running_state", None) == "Running" or str(getattr(r, "status", "")).lower() == "running"]
        projects = [r for r in rows if r.category == "Projects" and "Docker" in (r.subtype or "")]
        facts = [
            f"Docker-related inventory items: {len(docker)}.",
            f"Docker applications found: {', '.join(a.name for a in apps) or 'none in Applications category'}.",
            f"Running Docker containers/services observed: {len(running)}.",
            f"Projects with Docker indicators: {len(projects)}.",
        ]
        if running:
            facts.append("Because containers or the daemon appear running, uninstalling now may interrupt active workloads.")
        facts.append("MacScope will not invent whether you personally need Docker; review dependents first.")
        return AssistantAnswer(
            "\n".join(facts),
            0.75 if docker or apps else 0.4,
            evidence=facts,
            related_items=[a.name for a in apps] + [d.name for d in running[:8]],
            project_links=[p.path or p.name for p in projects[:8]],
            reports=["Docker inventory", "Cleanup Advisor"],
        )

    if "why is this process" in ql or ("why" in ql and "process" in ql):
        name = None
        for marker in ("process ", "running ", "is "):
            if marker in ql:
                name = q[ql.index(marker) + len(marker) :].strip(" ?.")
                break
        candidates = search_inventory(name or q, [r for r in rows if getattr(r, "category", None) == "Processes"])
        if not candidates:
            return AssistantAnswer(
                "I could not find a matching process in the current snapshot. Select a process or include its name.",
                0.1,
                evidence=["No process match in snapshot"],
            )
        proc = candidates[0]
        bits = [
            f"Process: {proc.name}",
            f"Executable: {getattr(proc, 'executable_path', None) or getattr(proc, 'path', None) or 'unknown'}",
            f"User: {getattr(proc, 'user_owner', None) or 'unknown'}",
            f"Parent: {getattr(proc, 'parent_process', None) or 'unknown'}",
            f"Related application: {getattr(proc, 'related_application', None) or 'unknown'}",
            f"Explanation: {getattr(proc, 'explanation', None) or 'No additional local explanation is available.'}",
        ]
        return AssistantAnswer(
            "\n".join(bits),
            0.8 if getattr(proc, "explanation", None) else 0.5,
            evidence=bits,
            related_items=[proc.name, getattr(proc, "related_application", None) or ""],
            project_links=[getattr(proc, "project_key", None) or ""],
        )

    if "changed yesterday" in ql or "what changed" in ql:
        since = datetime.utcnow() - timedelta(days=1)
        events = [e for e in list_timeline(limit=300) if e.created_at and e.created_at >= since]
        if not events:
            return AssistantAnswer(
                "No timeline events from the last 24 hours were found in the local database.",
                0.7,
                evidence=["Timeline query window: last 24 hours returned 0 events"],
                timeline_links=[],
                reports=["System Timeline"],
            )
        lines = [f"Local timeline events in the last 24 hours ({len(events)}):"]
        links = []
        for e in events[:25]:
            lines.append(f"- {e.created_at}: {e.title}")
            links.append(f"{e.created_at}: {e.title}")
        return AssistantAnswer("\n".join(lines), 0.85, evidence=[f"{len(events)} timeline events"], timeline_links=links, reports=["System Timeline"])

    if "launchagent" in ql or "launch agent" in ql or ("why" in ql and "startup" in ql):
        hits = search_inventory(q, [r for r in rows if getattr(r, "category", None) in {"Startup", "Login Items", "Background Items"}])
        if not hits:
            return AssistantAnswer("No matching startup item was found in the current snapshot.", 0.2, evidence=["No startup match"])
        item = hits[0]
        details = getattr(item, "details", None) if isinstance(getattr(item, "details", None), dict) else {}
        knowledge = details.get("knowledge") if isinstance(details, dict) else None
        text = "\n".join(
            [
                f"Startup item: {item.name}",
                f"Type: {getattr(item, 'item_type', None) or item.category}",
                f"Path: {getattr(item, 'path', None) or 'unknown'}",
                f"Executable: {getattr(item, 'executable_path', None) or 'unknown'}",
                f"Startup state: {getattr(item, 'startup_state', None) or 'unknown'}",
                f"Impact: {getattr(item, 'startup_impact', None) or 'not scored'}",
                f"Explanation: {getattr(item, 'explanation', None) or 'No local explanation available.'}",
                f"Knowledge: {knowledge or 'No local knowledge entry attached.'}",
            ]
        )
        return AssistantAnswer(
            text,
            0.75,
            evidence=[text],
            related_items=[item.name, getattr(item, "related_application", None) or ""],
            project_links=[getattr(item, "project_key", None) or ""],
            reports=["Startup Analyzer", "System Explorer"],
        )

    hits = search_inventory(q, rows)
    if not hits:
        return AssistantAnswer(
            "No matching items were found in the current local snapshot. I will not invent an answer.",
            0.0,
            evidence=["search_inventory returned 0 rows", "No cloud inference is used"],
        )
    lines = [f"Found {len(hits)} local inventory match(es):"]
    related = []
    evidence = []
    projects = []
    for row in hits[:15]:
        disk = getattr(row, "disk_usage", None)
        disk_s = f", {format_bytes(disk)}" if disk else ""
        lines.append(f"- [{row.category}] {row.name}{disk_s}")
        related.append(f"{row.category}: {row.name}")
        evidence.append(f"Matched {row.category}/{row.name}")
        if getattr(row, "project_key", None):
            projects.append(row.project_key)
    lines.append("Answers are limited to facts present in the current MacScope snapshot and timeline.")
    return AssistantAnswer(
        "\n".join(lines),
        0.65,
        evidence=evidence,
        related_items=related,
        project_links=sorted(set(projects))[:12],
        reports=["Search", "System Explorer"],
    )


def answer_question(question: str, rows: list[Any]) -> str:
    """Backward-compatible string API used by existing pages/tests."""
    return answer_question_detailed(question, rows).as_markdown()
