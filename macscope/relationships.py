from __future__ import annotations

from dataclasses import dataclass

from inventory import Item


@dataclass
class Relation:
    source_stable_id: str
    target_stable_id: str
    relation_type: str
    confidence: float
    evidence: str
    source_name: str = ""
    target_name: str = ""


def build_relationships(items: list[Item]) -> list[Relation]:
    """Derive relationships from collected inventory without external graph libraries."""
    for item in items:
        item.ensure_stable_id()
    by_category: dict[str, list[Item]] = {}
    for item in items:
        by_category.setdefault(item.category, []).append(item)

    apps = by_category.get("Applications", [])
    processes = by_category.get("Processes", [])
    startup = by_category.get("Startup", []) + by_category.get("Login Items", []) + by_category.get("Background Items", [])
    network = by_category.get("Network", [])
    brew = by_category.get("Homebrew", [])
    services = by_category.get("Services", [])
    python_items = by_category.get("Python", [])
    docker = by_category.get("Docker", [])
    ai = by_category.get("AI", [])

    relations: list[Relation] = []

    app_by_name = {a.name.lower(): a for a in apps}
    app_by_bundle = { (a.bundle_id or "").lower(): a for a in apps if a.bundle_id }

    for proc in processes:
        related = None
        if proc.related_application and proc.related_application.lower() in app_by_name:
            related = app_by_name[proc.related_application.lower()]
        elif proc.path and "/Applications/" in proc.path:
            for app in apps:
                if app.path and app.path in (proc.path or ""):
                    related = app
                    break
        if related:
            relations.append(
                Relation(
                    related.stable_id or "",
                    proc.stable_id or "",
                    "application_owns_process",
                    0.9,
                    "Process executable is inside application bundle",
                    related.name,
                    proc.name,
                )
            )

    for agent in startup:
        related = None
        label = (agent.label or agent.name or "").lower()
        for bundle, app in app_by_bundle.items():
            if bundle and bundle in label:
                related = app
                break
        if not related and agent.related_application:
            related = app_by_name.get(agent.related_application.lower())
        if related:
            relations.append(
                Relation(
                    related.stable_id or "",
                    agent.stable_id or "",
                    "application_owns_launch_item",
                    0.8,
                    "Launch label/bundle association",
                    related.name,
                    agent.name,
                )
            )

    for listener in network:
        for proc in processes:
            if listener.pid and proc.pid and listener.pid == proc.pid:
                relations.append(
                    Relation(
                        proc.stable_id or "",
                        listener.stable_id or "",
                        "process_opens_port",
                        0.95,
                        f"PID {listener.pid} owns listener",
                        proc.name,
                        listener.network_ports or listener.name,
                    )
                )
                break

    brew_by_name = {b.name.lower(): b for b in brew}
    for svc in services:
        pkg = brew_by_name.get(svc.name.lower())
        if pkg:
            relations.append(
                Relation(
                    pkg.stable_id or "",
                    svc.stable_id or "",
                    "service_belongs_to_homebrew_formula",
                    0.9,
                    "Matching Homebrew formula/service name",
                    pkg.name,
                    svc.name,
                )
            )

    for proc in processes:
        exe = proc.executable_path or proc.path or ""
        for env in python_items:
            if env.path and env.path in exe:
                relations.append(
                    Relation(
                        proc.stable_id or "",
                        env.stable_id or "",
                        "process_uses_python_environment",
                        0.85,
                        "Process executable path contains environment path",
                        proc.name,
                        env.name,
                    )
                )

    for container in docker:
        if container.item_type != "Container":
            continue
        ports = container.network_ports or ""
        for listener in network:
            if listener.network_ports and listener.network_ports.split(":")[-1] in ports:
                relations.append(
                    Relation(
                        container.stable_id or "",
                        listener.stable_id or "",
                        "docker_container_exposes_port",
                        0.6,
                        "Port string overlap with listener",
                        container.name,
                        listener.network_ports or "",
                    )
                )

    for server in ai:
        if server.item_type != "Local Server":
            continue
        for model in ai:
            if model.item_type in {"Ollama Model", "Model File"} and server.related_application:
                if server.related_application.lower() in (model.installation_source or "").lower() or server.related_application.lower() in model.name.lower() or model.subtype == "ollama":
                    relations.append(
                        Relation(
                            server.stable_id or "",
                            model.stable_id or "",
                            "ai_server_uses_model",
                            0.5,
                            "Heuristic association between local AI server and models",
                            server.name,
                            model.name,
                        )
                    )

    for login in by_category.get("Login Items", []):
        related = app_by_name.get((login.related_application or login.name or "").lower())
        if related:
            relations.append(
                Relation(
                    related.stable_id or "",
                    login.stable_id or "",
                    "login_item_belongs_to_application",
                    0.8,
                    "Login item name matches application",
                    related.name,
                    login.name,
                )
            )

    return relations
