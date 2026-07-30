from __future__ import annotations

"""Scored recommendation engine — explains WHY, never blindly deletes."""

from dataclasses import dataclass, field
from typing import Any

from database import SessionLocal
from inventory import Item
from macscope.cleanup import CleanupCandidate, find_cleanup_candidates
from macscope.timeline import list_timeline
from models import RecommendationRecord
from utils import format_bytes, json_dumps


@dataclass
class Recommendation:
    category: str
    title: str
    why: str
    confidence: float
    impact: str
    estimated_benefit: str
    risk: str
    supporting_evidence: list[str] = field(default_factory=list)
    related_items: list[str] = field(default_factory=list)
    timeline_references: list[str] = field(default_factory=list)
    project_references: list[str] = field(default_factory=list)
    recommended_action: str = "Review carefully"
    stable_id: str | None = None
    score: float = 0.0


def _impact_from_size(size: float | None) -> str:
    if not size:
        return "Low"
    if size >= 5 * 1024**3:
        return "High"
    if size >= 500 * 1024**2:
        return "Medium"
    return "Low"


def _score(confidence: float, impact: str, risk: str) -> float:
    impact_w = {"High": 1.0, "Medium": 0.7, "Low": 0.4}.get(impact, 0.4)
    risk_penalty = {"Safe": 0.0, "Caution": 0.15, "Dangerous": 0.4, "Unknown": 0.2}.get(risk, 0.2)
    return max(0.0, min(1.0, confidence * impact_w * (1.0 - risk_penalty)))


def build_recommendations(items: list[Item], *, snapshot_id: int | None = None) -> list[Recommendation]:
    """Build scored recommendations from cleanup heuristics + inventory context."""
    candidates = find_cleanup_candidates(items)
    by_stable = {i.stable_id: i for i in items if i.stable_id}
    recent = list_timeline(limit=100)
    recs: list[Recommendation] = []

    for cand in candidates:
        item = by_stable.get(cand.stable_id) if cand.stable_id else None
        impact = _impact_from_size(cand.size)
        evidence = [
            f"Heuristic type: {cand.candidate_type}",
            f"Reason: {cand.reason}",
        ]
        if cand.path:
            evidence.append(f"Path observed: {cand.path}")
        if cand.last_modified:
            evidence.append(f"Last modified: {cand.last_modified}")
        if item and item.explanation:
            evidence.append(f"Inventory explanation: {item.explanation}")
        if item and item.running_state:
            evidence.append(f"Running state: {item.running_state}")

        related = []
        if cand.related_software:
            related.append(cand.related_software)
        if item and item.related_application:
            related.append(item.related_application)
        if item and item.name:
            related.append(item.name)

        project_refs = []
        if item and item.project_key:
            project_refs.append(item.project_key)

        timeline_refs = []
        for event in recent:
            if cand.stable_id and event.stable_id == cand.stable_id:
                timeline_refs.append(f"{event.created_at}: {event.title}")
            elif cand.name and cand.name.lower() in (event.title or "").lower():
                timeline_refs.append(f"{event.created_at}: {event.title}")
            if len(timeline_refs) >= 3:
                break

        why = (
            f"{cand.reason} This is not an automatic delete instruction. "
            f"Review related items and timeline evidence before acting."
        )
        action = cand.recommended_action
        if "delete" in action.lower() or "remove" in action.lower() or "trash" in action.lower():
            action = f"Review, then optionally: {action}"

        rec = Recommendation(
            category=cand.candidate_type,
            title=f"{cand.candidate_type}: {cand.name}",
            why=why,
            confidence=float(cand.confidence or 0.0),
            impact=impact,
            estimated_benefit=format_bytes(cand.size) if cand.size else "Unknown / qualitative",
            risk=cand.risk or "Caution",
            supporting_evidence=evidence,
            related_items=sorted(set(related)),
            timeline_references=timeline_refs,
            project_references=project_refs,
            recommended_action=action,
            stable_id=cand.stable_id,
        )
        rec.score = _score(rec.confidence, rec.impact, rec.risk)
        recs.append(rec)

    # Additional non-deletion insights
    high_startup = [i for i in items if i.startup_impact == "High"]
    if high_startup:
        names = ", ".join(i.name for i in high_startup[:8])
        recs.append(
            Recommendation(
                category="Startup impact",
                title=f"{len(high_startup)} high-impact startup item(s)",
                why="These items are scored High for startup impact based on observed metrics/config. Investigate before disabling.",
                confidence=0.6,
                impact="Medium",
                estimated_benefit="Faster login / lower background load (qualitative)",
                risk="Caution",
                supporting_evidence=[f"High-impact items include: {names}"],
                related_items=[i.name for i in high_startup[:12]],
                timeline_references=[],
                project_references=[],
                recommended_action="Open Startup Analyzer and review each item before changing state",
                score=0.55,
            )
        )

    recs.sort(key=lambda r: r.score, reverse=True)
    if snapshot_id is not None:
        _persist(recs[:80], snapshot_id)
    return recs


def recommendation_rows(items: list[Item]) -> list[dict[str, Any]]:
    rows = []
    for rec in build_recommendations(items):
        rows.append(
            {
                "Score": round(rec.score, 3),
                "Category": rec.category,
                "Title": rec.title,
                "Why": rec.why,
                "Confidence": rec.confidence,
                "Impact": rec.impact,
                "Estimated benefit": rec.estimated_benefit,
                "Risk": rec.risk,
                "Recommended action": rec.recommended_action,
                "Evidence": " | ".join(rec.supporting_evidence[:4]),
                "Related": ", ".join(rec.related_items[:6]),
                "Timeline": " | ".join(rec.timeline_references[:3]),
                "Projects": ", ".join(rec.project_references[:3]),
                "Stable ID": rec.stable_id,
            }
        )
    return rows


def _persist(recs: list[Recommendation], snapshot_id: int) -> None:
    try:
        with SessionLocal() as db:
            for rec in recs:
                db.add(
                    RecommendationRecord(
                        snapshot_id=snapshot_id,
                        category=rec.category,
                        title=rec.title[:512],
                        why=rec.why,
                        confidence=rec.confidence,
                        impact=rec.impact,
                        estimated_benefit=rec.estimated_benefit,
                        risk=rec.risk,
                        evidence_json=json_dumps(rec.supporting_evidence),
                        related_json=json_dumps(rec.related_items),
                        timeline_refs_json=json_dumps(rec.timeline_references),
                        project_refs_json=json_dumps(rec.project_references),
                        recommended_action=rec.recommended_action,
                        stable_id=rec.stable_id,
                    )
                )
            db.commit()
    except Exception:
        pass


# Back-compat alias used by older advisor UI
def advisor_from_recommendations(items: list[Item]) -> list[CleanupCandidate]:
    return find_cleanup_candidates(items)
