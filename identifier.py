from __future__ import annotations

from pathlib import Path
from typing import Any

from inventory import Item
from protection import executable_missing, is_apple_signed, is_protected_path


CLASS_APPLE = "Apple protected"
CLASS_THIRD_PARTY = "Known third-party"
CLASS_USER = "User-created"
CLASS_ORPHANED = "Orphaned"
CLASS_UNKNOWN = "Unknown"

RISK_SAFE = "Safe"
RISK_CAUTION = "Caution"
RISK_PROTECTED = "Protected"
RISK_UNKNOWN = "Unknown"
RISK_ORPHANED = "Orphaned"


def classify_item(item: Item) -> Item:
    """Apply deterministic local identification to an inventory item in place."""
    from macscope.catalog import lookup_catalog

    classification, risk, protected, explanation = _classify(item)
    item.classification = classification
    item.risk = risk
    item.protected = protected or item.protected
    item.orphan_status = classification == CLASS_ORPHANED or bool(item.orphan_status)
    if explanation:
        item.explanation = explanation
    elif not item.explanation:
        item.explanation = _default_explanation(item, classification)
    catalog = lookup_catalog(item.bundle_id or item.label, item.label, item.name)
    if catalog:
        if not item.publisher and catalog.publisher:
            item.publisher = catalog.publisher
        if not item.removal_guidance and catalog.removal_notes:
            item.removal_guidance = catalog.removal_notes
        if catalog.description and (not item.explanation or item.classification == CLASS_UNKNOWN):
            item.explanation = catalog.description
        item.confidence = item.confidence if item.confidence is not None else 0.85
    elif item.confidence is None:
        item.confidence = 0.9 if classification == CLASS_APPLE else (0.7 if classification != CLASS_UNKNOWN else 0.35)
    item.available_actions = _available_actions(item)
    item.ensure_stable_id()
    return item


def _classify(item: Item) -> tuple[str, str, bool, str]:
    path = item.path or ""
    exe = item.executable_path or (item.details or {}).get("program") or ""
    publisher = item.publisher or item.vendor
    label = item.label or (item.details or {}).get("bundle_id") or ""
    category = item.category

    # Protected / Apple paths and labels take priority over orphan detection.
    if is_protected_path(path) or is_protected_path(str(exe)):
        return (
            CLASS_APPLE,
            RISK_PROTECTED,
            True,
            "Apple system component. Management actions are disabled.",
        )

    if is_apple_signed(publisher if isinstance(publisher, str) else None, str(label) if label else None):
        return (
            CLASS_APPLE,
            RISK_PROTECTED,
            True,
            "Apple-signed protected component. Management actions are disabled.",
        )

    if label and str(label).startswith("com.apple."):
        return (
            CLASS_APPLE,
            RISK_PROTECTED,
            True,
            "Apple system component. Management actions are disabled.",
        )

    # Orphaned: referenced executable missing (non-Apple startup items)
    if category in {"Startup", "Login Items", "Background Items"} and executable_missing(
        item.executable_path or (item.details or {}).get("program")
    ):
        return (
            CLASS_ORPHANED,
            RISK_ORPHANED,
            False,
            "The referenced executable does not exist. This may be an orphaned startup item.",
        )

    # Homebrew items
    if category in {"Homebrew", "Services"} or item.installation_source == "Homebrew":
        return (
            CLASS_THIRD_PARTY,
            RISK_SAFE if category == "Homebrew" else RISK_CAUTION,
            False,
            item.explanation
            or (
                f"Homebrew {item.item_type or item.vendor or 'package'} '{item.name}'."
                if category == "Homebrew"
                else f"Homebrew service '{item.name}' ({item.status or 'unknown'})."
            ),
        )

    # User LaunchAgents
    home = str(Path.home())
    if path.startswith(home) and category in {"Startup", "Login Items"}:
        if "LaunchAgents" in path:
            related = item.related_application or _guess_related_name(item)
            explanation = item.explanation or (
                f"Starts a user {related} application at login."
                if related
                else "User LaunchAgent that runs at login or on demand."
            )
            return CLASS_USER, RISK_CAUTION, False, explanation
        return CLASS_USER, RISK_CAUTION, False, item.explanation or "User-configured login or background item."

    # System third-party launch items
    if path.startswith("/Library/Launch") and not path.startswith("/Library/Apple"):
        related = item.related_application or _guess_related_name(item)
        explanation = item.explanation or (
            f"Launches {related}'s privileged helper."
            if related
            else "Third-party system LaunchAgent or LaunchDaemon."
        )
        return CLASS_THIRD_PARTY, RISK_CAUTION, False, explanation

    if category == "Applications":
        if path.startswith("/Applications") or path.startswith(str(Path.home() / "Applications")):
            if publisher or label:
                return (
                    CLASS_THIRD_PARTY,
                    RISK_SAFE,
                    False,
                    item.explanation or f"Installed application '{item.name}'.",
                )
            return CLASS_UNKNOWN, RISK_UNKNOWN, False, item.explanation or "Application with limited local metadata."

    if category == "Processes":
        if is_protected_path(str(exe)):
            return CLASS_APPLE, RISK_PROTECTED, True, "Apple system component. Management actions are disabled."
        if exe and str(exe).startswith(home):
            return CLASS_USER, RISK_CAUTION, False, item.explanation or "User process running from the home directory."
        if exe and (
            str(exe).startswith("/Applications")
            or str(exe).startswith("/usr/local")
            or "/Cellar/" in str(exe)
            or "/homebrew/" in str(exe).lower()
        ):
            return CLASS_THIRD_PARTY, RISK_CAUTION, False, item.explanation or f"Third-party process '{item.name}'."
        return CLASS_UNKNOWN, RISK_UNKNOWN, False, item.explanation or "Process identity could not be fully determined from local evidence."

    if category == "Network":
        return CLASS_UNKNOWN, RISK_CAUTION, False, item.explanation or f"Listening network endpoint associated with '{item.name}'."

    if category in {"System", "Storage", "Performance", "Security"}:
        return CLASS_APPLE, RISK_PROTECTED, True, "Apple system component. Management actions are disabled."

    return CLASS_UNKNOWN, RISK_UNKNOWN, False, item.explanation or "Insufficient local evidence to classify this item. It is not assumed to be malicious."


def _guess_related_name(item: Item) -> str | None:
    if item.related_application:
        return item.related_application
    label = item.label or item.name or ""
    # com.docker.helper -> Docker
    parts = str(label).split(".")
    if len(parts) >= 2:
        brand = parts[1]
        if brand.lower() not in {"apple", "macos", "osx"}:
            return brand[:1].upper() + brand[1:]
    exe = item.executable_path or (item.details or {}).get("program") or ""
    if exe:
        name = Path(str(exe).split()[0]).name
        if name:
            return name
    return None


def _default_explanation(item: Item, classification: str) -> str:
    if classification == CLASS_APPLE:
        return "Apple system component. Management actions are disabled."
    if classification == CLASS_ORPHANED:
        return "The referenced executable does not exist. This may be an orphaned startup item."
    if classification == CLASS_USER:
        return "User-created or user-installed item based on path conventions."
    if classification == CLASS_THIRD_PARTY:
        return "Known third-party item based on install location or metadata."
    return "Insufficient local evidence to classify this item. It is not assumed to be malicious."


def _available_actions(item: Item) -> list[str]:
    if item.protected or item.classification == CLASS_APPLE:
        return []
    actions: list[str] = []
    category = item.category
    if category == "Processes" and item.running_state == "Running":
        actions.extend(["Stop gracefully", "Force quit"])
    elif category == "Startup":
        path = item.path or ""
        home_agents = str(Path.home() / "Library" / "LaunchAgents")
        if path.startswith(home_agents):
            actions.extend(
                [
                    "Unload now",
                    "Disable persistently",
                    "Re-enable",
                    "Reveal plist in Finder",
                    "Back up plist",
                ]
            )
        elif path.startswith("/Library/Launch"):
            actions.append("View admin instructions")
    elif category in {"Login Items", "Background Items"}:
        actions.append("Reveal in Finder")
    elif category == "Services":
        actions.extend(["Stop service", "Start service", "Restart service"])
    elif category == "Homebrew":
        actions.append("Uninstall formula or cask")
    elif category == "Applications":
        if item.running_state == "Running":
            actions.append("Quit if running")
        actions.extend(["Reveal in Finder", "Move to Trash"])
    return actions


def enrich_items(items: list[Item]) -> list[Item]:
    """Classify every collected item."""
    return [classify_item(item) for item in items]


def summary_flags(item: Item | Any) -> dict[str, bool]:
    """Boolean flags used by UI filters."""
    classification = getattr(item, "classification", None) or ""
    risk = getattr(item, "risk", None) or ""
    running_state = getattr(item, "running_state", None) or ""
    status = getattr(item, "status", None) or ""
    running = running_state in {"Running", "Listening"} or status in {"Running", "started", "Listening"}

    startup_state = (getattr(item, "startup_state", None) or "").lower()
    details = getattr(item, "details", None)
    startup = startup_state in {
        "enabled",
        "run at load",
        "configured",
        "login item",
        "background item",
        "keep alive",
    }
    if isinstance(details, dict) and details.get("run_at_load"):
        startup = True
    if getattr(item, "category", None) in {"Startup", "Login Items", "Background Items"}:
        if startup_state and startup_state not in {"disabled", "not loaded"}:
            startup = True

    return {
        "running": running,
        "starts_automatically": startup,
        "third_party": classification == CLASS_THIRD_PARTY,
        "apple": classification == CLASS_APPLE,
        "safe": risk == RISK_SAFE,
        "caution": risk == RISK_CAUTION,
        "protected": bool(getattr(item, "protected", False)) or risk == RISK_PROTECTED,
        "unknown": classification == CLASS_UNKNOWN or risk == RISK_UNKNOWN,
        "orphaned": classification == CLASS_ORPHANED or risk == RISK_ORPHANED,
    }
