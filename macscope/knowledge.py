from __future__ import annotations

"""Local knowledge engine v2 — catalog + offline knowledge pack (no network)."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from inventory import Item
from macscope.catalog import CATALOG, CatalogEntry, lookup_catalog


@dataclass(frozen=True)
class KnowledgeEntry:
    key: str
    purpose: str
    developer: str = ""
    documentation: str = ""
    removal_generally_safe: bool = False
    typical_startup: str = "Unknown"
    common_ports: tuple[int, ...] = ()
    dependencies: tuple[str, ...] = ()
    homepage: str = ""
    safety_notes: str = ""
    name: str = ""
    kind: str = "application"
    risk_notes: str = ""
    description: str = ""


def _from_catalog(entry: CatalogEntry) -> KnowledgeEntry:
    key = entry.display_name.lower().replace(" ", "_")
    safe = "do not remove" not in (entry.removal_notes or "").lower() and "apple" not in entry.publisher.lower()
    ports: tuple[int, ...] = ()
    startup = "May install login/background helpers"
    deps: tuple[str, ...] = ()
    name = entry.display_name.lower()
    if "docker" in name:
        ports = (2375, 2376)
        startup = "Often starts privileged helpers at login"
        deps = ("Virtualization.framework",)
    elif "postgres" in name:
        ports = (5432,)
        startup = "Homebrew service may start at login"
    elif "mysql" in name:
        ports = (3306,)
        startup = "Homebrew service may start at login"
    elif "redis" in name:
        ports = (6379,)
    elif "nginx" in name:
        ports = (80, 443, 8080)
    elif "ollama" in name:
        ports = (11434,)
        startup = "Local server may listen when launched"
    elif "lm studio" in name:
        ports = (1234,)
    elif "streamlit" in name:
        ports = (8501,)
    elif "chrome" in name:
        startup = "May enable background update helpers"
    return KnowledgeEntry(
        key=key,
        purpose=entry.description or entry.display_name,
        developer=entry.publisher,
        documentation=entry.documentation or entry.homepage,
        removal_generally_safe=safe and bool(entry.removal_notes),
        typical_startup=startup,
        common_ports=ports,
        dependencies=deps,
        homepage=entry.homepage,
        safety_notes=entry.safety_notes or entry.removal_notes,
        name=entry.display_name,
        description=entry.description,
        risk_notes=entry.safety_notes,
    )


@lru_cache(maxsize=1)
def _load_pack() -> dict[str, KnowledgeEntry]:
    pack_path = Path(__file__).resolve().parent / "data" / "knowledge_pack.json"
    out: dict[str, KnowledgeEntry] = {}
    if pack_path.exists():
        try:
            raw = json.loads(pack_path.read_text(encoding="utf-8"))
            for row in raw.get("entries", []):
                key = str(row.get("key") or "").strip()
                if not key:
                    continue
                out[key] = KnowledgeEntry(
                    key=key,
                    purpose=str(row.get("purpose") or row.get("description") or key),
                    developer=str(row.get("publisher") or ""),
                    documentation=str(row.get("documentation") or ""),
                    removal_generally_safe=bool(row.get("removal_generally_safe")),
                    typical_startup=str(row.get("typical_startup") or "Unknown"),
                    common_ports=tuple(int(p) for p in (row.get("common_ports") or [])),
                    dependencies=tuple(str(d) for d in (row.get("dependencies") or [])),
                    homepage=str(row.get("documentation") or ""),
                    safety_notes=str(row.get("removal_notes") or row.get("risk_notes") or ""),
                    name=str(row.get("name") or key),
                    kind=str(row.get("kind") or "application"),
                    risk_notes=str(row.get("risk_notes") or ""),
                    description=str(row.get("description") or ""),
                )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return out


def knowledge_count() -> int:
    return len(KNOWLEDGE) + len(_load_pack())


KNOWLEDGE: dict[str, KnowledgeEntry] = {}
for _entry in CATALOG:
    ke = _from_catalog(_entry)
    KNOWLEDGE[ke.key] = ke

KNOWLEDGE.update(
    {
        "macos": KnowledgeEntry(
            "macos",
            "Apple operating system components",
            "Apple",
            "https://support.apple.com",
            False,
            "Always present",
            (),
            (),
            safety_notes="Never remove system components.",
            name="macOS",
            kind="system",
            risk_notes="System integrity protected.",
        ),
        "homebrew": KnowledgeEntry(
            "homebrew",
            "Community package manager for macOS",
            "Homebrew",
            "https://docs.brew.sh",
            True,
            "Services optional via brew services",
            (),
            ("Xcode CLT",),
            name="Homebrew",
            kind="package_manager",
        ),
    }
)


def lookup_knowledge(
    *,
    bundle_id: str | None = None,
    label: str | None = None,
    name: str | None = None,
    category: str | None = None,
) -> KnowledgeEntry | None:
    cat = lookup_catalog(bundle_id, label, name)
    if cat:
        return _from_catalog(cat)
    nm = (name or "").lower()
    lab = (label or "").lower()
    pack = _load_pack()
    # Exact / substring against packed and core knowledge
    for store in (KNOWLEDGE, pack):
        for key, entry in store.items():
            hay = f"{key} {entry.name} {entry.description}".lower()
            if nm and (key.replace("_", " ") in nm or key in nm or (entry.name and entry.name.lower() in nm)):
                return entry
            if lab and (key in lab or lab in hay):
                return entry
    # Port knowledge
    if category == "Network" and name:
        digits = "".join(ch for ch in name if ch.isdigit())
        if digits:
            port_key = f"port_{digits}"
            if port_key in pack:
                return pack[port_key]
    if category == "System":
        return KNOWLEDGE.get("macos")
    return None


def enrich_item_knowledge(item: Item) -> Item:
    knowledge = lookup_knowledge(
        bundle_id=item.bundle_id or item.label,
        label=item.label,
        name=item.name,
        category=item.category,
    )
    if not knowledge:
        return item
    item.knowledge_key = knowledge.key
    if not item.explanation:
        item.explanation = knowledge.description or knowledge.purpose
    if not item.publisher and knowledge.developer:
        item.publisher = knowledge.developer
    if not item.removal_guidance and (knowledge.safety_notes or knowledge.risk_notes):
        item.removal_guidance = knowledge.safety_notes or knowledge.risk_notes
    details = dict(item.details or {})
    details["knowledge"] = {
        "purpose": knowledge.purpose,
        "developer": knowledge.developer,
        "documentation": knowledge.documentation,
        "removal_generally_safe": knowledge.removal_generally_safe,
        "typical_startup": knowledge.typical_startup,
        "common_ports": list(knowledge.common_ports),
        "dependencies": list(knowledge.dependencies),
        "risk_notes": knowledge.risk_notes,
        "kind": knowledge.kind,
        "name": knowledge.name,
    }
    item.details = details
    return item
