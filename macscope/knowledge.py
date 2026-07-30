from __future__ import annotations

"""Local knowledge engine. Extends the V2 catalog; no network access."""

from dataclasses import dataclass, field

from macscope.catalog import CATALOG, CatalogEntry, lookup_catalog
from inventory import Item


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
    )


KNOWLEDGE: dict[str, KnowledgeEntry] = {}
for _entry in CATALOG:
    ke = _from_catalog(_entry)
    KNOWLEDGE[ke.key] = ke


# Additional explicit knowledge not fully covered by catalog display names
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
    for key, entry in KNOWLEDGE.items():
        if key.replace("_", " ") in nm or key in nm:
            return entry
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
        item.explanation = knowledge.purpose
    if not item.publisher and knowledge.developer:
        item.publisher = knowledge.developer
    if not item.removal_guidance and knowledge.safety_notes:
        item.removal_guidance = knowledge.safety_notes
    details = dict(item.details or {})
    details["knowledge"] = {
        "purpose": knowledge.purpose,
        "developer": knowledge.developer,
        "documentation": knowledge.documentation,
        "removal_generally_safe": knowledge.removal_generally_safe,
        "typical_startup": knowledge.typical_startup,
        "common_ports": list(knowledge.common_ports),
        "dependencies": list(knowledge.dependencies),
    }
    item.details = details
    return item
