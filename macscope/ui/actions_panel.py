from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from actions import (
    ActionError,
    backup_plist,
    brew_dependency_review,
    delete_venv,
    disable_launch_agent,
    docker_remove_container,
    docker_remove_image,
    docker_restart,
    docker_start,
    docker_stop,
    enable_launch_agent,
    force_quit_process,
    move_app_to_trash,
    quit_application,
    remove_conda_env,
    remove_node_modules,
    remove_pyenv_version,
    restart_brew_service,
    reveal_in_finder,
    start_brew_service,
    stop_brew_service,
    stop_process,
    system_launch_item_instructions,
    trash_path,
    unload_launch_item,
    uninstall_brew,
    uninstall_npm_global,
)
from macscope.settings import load_settings
from macscope.ui.layout import consume_action_token, ensure_action_token
from utils import json_loads


def _details(row: Any) -> dict:
    return json_loads(getattr(row, "details_json", None))


def _destructive_allowed() -> bool:
    return load_settings().destructive_allowed()


def _action_button(
    label: str,
    *,
    key: str,
    destructive: bool = False,
    disabled: bool = False,
    on_click: Callable[[], None],
) -> None:
    if disabled:
        st.button(label, key=key, disabled=True)
        return
    token = ensure_action_token(key)
    if st.button(label, key=key):
        if destructive and not _destructive_allowed():
            st.error("Destructive actions are disabled. Enable them in Settings and acknowledge the safety notice.")
            return
        if consume_action_token(token):
            try:
                on_click()
            except ActionError as exc:
                st.error(str(exc))
        else:
            st.warning("This action was already processed.")


def render_actions_for_row(row: Any, on_success: Callable[[], None] | None = None) -> None:
    """Render guarded management controls for a selected inventory row."""
    st.subheader("Management actions")
    if getattr(row, "protected", False):
        st.info("Protected item. Management actions are disabled.")
        return

    actions_raw = json_loads(getattr(row, "available_actions", None), default=[])
    if not actions_raw:
        st.caption("No management actions available for this item.")
        return

    if not _destructive_allowed():
        st.caption("Destructive actions are disabled until you acknowledge the safety notice in Settings.")

    category = row.category
    if category == "Processes":
        _process_actions(row, on_success)
    elif category == "Startup":
        _startup_actions(row, on_success)
    elif category in {"Login Items", "Background Items"}:
        _reveal_only(row)
    elif category == "Services":
        _service_actions(row, on_success)
    elif category == "Homebrew":
        _brew_actions(row, on_success)
    elif category == "Applications":
        _app_actions(row, on_success)
    elif category == "Python":
        _python_actions(row, on_success)
    elif category == "Node":
        _node_actions(row, on_success)
    elif category == "Docker":
        _docker_actions(row, on_success)
    elif category == "AI":
        _ai_actions(row, on_success)
    else:
        st.caption("No management actions available for this item.")


def _ok(message: str, on_success: Callable[[], None] | None) -> None:
    st.success(message)
    if on_success:
        on_success()


def _process_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    details = _details(row)
    pid = details.get("pid") or getattr(row, "pid", None)
    if not pid:
        st.error("Process ID missing.")
        return
    st.write(f"Target PID **{pid}** ({row.name})")
    st.code(row.executable_path or row.path or "")

    def stop() -> None:
        stop_process(int(pid), name=row.name, exe=row.executable_path or row.path)
        _ok("Stop signal sent.", on_success)

    _action_button("Stop gracefully (SIGTERM)", key=f"stop_{row.id}_{pid}", on_click=stop)

    confirm1 = st.checkbox("I understand force quit may lose unsaved work.", key=f"fq1_{row.id}")
    confirm2 = st.checkbox("Second confirmation: force quit this process.", key=f"fq2_{row.id}")

    def force() -> None:
        force_quit_process(int(pid), name=row.name, exe=row.executable_path or row.path)
        _ok("Force quit signal sent.", on_success)

    _action_button(
        "Force quit (SIGKILL)",
        key=f"fqbtn_{row.id}_{pid}",
        destructive=True,
        disabled=not (confirm1 and confirm2),
        on_click=force,
    )


def _startup_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    path = row.path or ""
    st.code(path)
    if "View admin instructions" in (json_loads(row.available_actions, default=[]) or []):
        st.warning("Administrator workflow required. Privilege elevation is not available in Version 1.")
        st.text(system_launch_item_instructions(path))
        return

    def backup() -> None:
        dest = backup_plist(path)
        st.success(f"Backup written to {dest}")

    _action_button("Back up plist", key=f"bak_{row.id}", on_click=backup)

    def reveal() -> None:
        reveal_in_finder(path)
        st.success("Finder reveal requested.")

    _action_button("Reveal plist in Finder", key=f"rev_{row.id}", on_click=reveal)

    st.markdown("**Unload now** stops the item for the current launchd domain. The plist is preserved.")
    confirm_unload = st.checkbox("Confirm unload", key=f"cu_{row.id}")

    def unload() -> None:
        unload_launch_item(path)
        _ok("Item unloaded.", on_success)

    _action_button("Unload now", key=f"ul_{row.id}", disabled=not confirm_unload, on_click=unload)

    st.markdown(
        "**Disable persistently** backs up the plist, unloads it, and renames it to `.plist.disabled`."
    )
    confirm_disable = st.checkbox("Confirm persistent disable", key=f"cd_{row.id}")

    def disable() -> None:
        disabled = disable_launch_agent(path)
        _ok(f"Disabled as {disabled.name}", on_success)

    _action_button(
        "Disable persistently",
        key=f"dis_{row.id}",
        destructive=True,
        disabled=not confirm_disable,
        on_click=disable,
    )

    st.markdown("**Re-enable** restores a `.plist.disabled` file and bootstraps it.")
    confirm_enable = st.checkbox("Confirm re-enable", key=f"ce_{row.id}")

    def enable() -> None:
        enabled = enable_launch_agent(path if path.endswith(".plist") else path + ".disabled")
        _ok(f"Re-enabled {enabled.name}", on_success)

    _action_button("Re-enable", key=f"en_{row.id}", disabled=not confirm_enable, on_click=enable)


def _reveal_only(row: Any) -> None:
    path = row.path or row.executable_path
    if not path:
        st.caption("No path available to reveal.")
        return

    def reveal() -> None:
        reveal_in_finder(path)
        st.success("Finder reveal requested.")

    _action_button("Reveal in Finder", key=f"revli_{row.id}", on_click=reveal)


def _service_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    name = row.name
    c1, c2, c3 = st.columns(3)
    with c1:

        def stop() -> None:
            stop_brew_service(name)
            _ok("Service stopped.", on_success)

        _action_button("Stop service", key=f"ss_{row.id}", on_click=stop)
    with c2:

        def start() -> None:
            start_brew_service(name)
            _ok("Service started.", on_success)

        _action_button("Start service", key=f"st_{row.id}", on_click=start)
    with c3:

        def restart() -> None:
            restart_brew_service(name)
            _ok("Service restarted.", on_success)

        _action_button("Restart service", key=f"rs_{row.id}", on_click=restart)


def _brew_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    name = row.name
    cask = (row.vendor == "Cask") or ((row.item_type or "") == "Cask")
    with st.expander("Dependency review", expanded=True):
        try:
            st.text(brew_dependency_review(name, cask=cask))
        except ActionError as exc:
            st.error(str(exc))
    confirm = st.checkbox(
        "I reviewed dependencies and understand dependent software may stop working.",
        key=f"bu_{row.id}",
    )

    def uninstall() -> None:
        uninstall_brew(name, cask=cask)
        _ok("Package uninstalled.", on_success)

    _action_button(
        "Uninstall formula or cask",
        key=f"bubtn_{row.id}",
        destructive=True,
        disabled=not confirm,
        on_click=uninstall,
    )


def _app_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    path = row.path or ""
    st.code(path)

    def reveal() -> None:
        reveal_in_finder(path)
        st.success("Finder reveal requested.")

    _action_button("Reveal in Finder", key=f"apprev_{row.id}", on_click=reveal)

    if row.running_state == "Running":

        def quit() -> None:
            quit_application(path)
            _ok("Quit requested.", on_success)

        _action_button("Quit if running", key=f"appquit_{row.id}", on_click=quit)

    st.markdown("**Move to Trash** moves the `.app` bundle only. Support files are not deleted in Version 1.")
    confirm = st.checkbox(
        "I understand this moves the application to Trash; support files remain.",
        key=f"apptrash_{row.id}",
    )

    def trash() -> None:
        dest = move_app_to_trash(path)
        _ok(f"Moved to {dest}", on_success)

    _action_button(
        "Move application to Trash",
        key=f"apptrashbtn_{row.id}",
        destructive=True,
        disabled=not confirm,
        on_click=trash,
    )


def _python_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    details = _details(row)
    path = row.path or ""
    subtype = getattr(row, "subtype", None) or details.get("kind")

    if path:
        st.code(path)

    if "Reveal environment" in (json_loads(row.available_actions, default=[]) or []):

        def reveal() -> None:
            reveal_in_finder(path)
            st.success("Finder reveal requested.")

        _action_button("Reveal environment", key=f"pyrev_{row.id}", on_click=reveal)

    if "Copy activation command" in (json_loads(row.available_actions, default=[]) or []):
        activate = details.get("activate") or f"source {path}/bin/activate"

        def copy_cmd() -> None:
            import subprocess

            subprocess.run(["pbcopy"], input=activate, text=True, check=True, timeout=10)
            st.success("Activation command copied to clipboard.")

        _action_button("Copy activation command", key=f"pycopy_{row.id}", on_click=copy_cmd)

    if "Delete virtual environment" in (json_loads(row.available_actions, default=[]) or []):
        confirm = st.checkbox("Confirm delete virtual environment", key=f"pydel_{row.id}")

        def delete() -> None:
            delete_venv(path)
            _ok("Virtual environment deleted.", on_success)

        _action_button(
            "Delete virtual environment",
            key=f"pydelbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=delete,
        )

    if "Remove Conda environment" in (json_loads(row.available_actions, default=[]) or []):
        confirm = st.checkbox("Confirm remove Conda environment", key=f"condadel_{row.id}")
        env_name = row.name.replace("conda · ", "", 1) if row.name.startswith("conda · ") else row.name

        def remove() -> None:
            remove_conda_env(env_name)
            _ok("Conda environment removed.", on_success)

        _action_button(
            "Remove Conda environment",
            key=f"condadelbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=remove,
        )

    if "Remove pyenv version" in (json_loads(row.available_actions, default=[]) or []):
        confirm = st.checkbox("Confirm remove pyenv version", key=f"pyenvdel_{row.id}")
        version = details.get("version") or (path.split("/")[-1] if path else row.name.replace("pyenv · ", "", 1))

        def remove() -> None:
            remove_pyenv_version(version)
            _ok("pyenv version removed.", on_success)

        _action_button(
            "Remove pyenv version",
            key=f"pyenvdelbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=remove,
        )

    if subtype and not path:
        st.caption(f"Python item subtype: {subtype}")


def _node_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    details = _details(row)
    path = row.path or ""
    subtype = getattr(row, "subtype", None)

    if "Uninstall global npm package" in (json_loads(row.available_actions, default=[]) or []):
        confirm = st.checkbox("Confirm uninstall global npm package", key=f"npmun_{row.id}")

        def uninstall() -> None:
            uninstall_npm_global(row.name)
            _ok("Global npm package uninstalled.", on_success)

        _action_button(
            "Uninstall global npm package",
            key=f"npmunbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=uninstall,
        )

    if "Reveal project" in (json_loads(row.available_actions, default=[]) or []):
        project = details.get("project") or (str(path).rsplit("/node_modules", 1)[0] if path else "")

        def reveal() -> None:
            reveal_in_finder(project)
            st.success("Finder reveal requested.")

        _action_button("Reveal project", key=f"nrev_{row.id}", on_click=reveal)

    if "Copy reinstall command" in (json_loads(row.available_actions, default=[]) or []):
        reinstall = details.get("reinstall") or "npm install"

        def copy_cmd() -> None:
            import subprocess

            subprocess.run(["pbcopy"], input=reinstall, text=True, check=True, timeout=10)
            st.success("Reinstall command copied to clipboard.")

        _action_button("Copy reinstall command", key=f"ncopy_{row.id}", on_click=copy_cmd)

    if "Remove node_modules" in (json_loads(row.available_actions, default=[]) or []):
        st.code(path)
        confirm = st.checkbox("Confirm remove node_modules", key=f"nmdel_{row.id}")

        def remove() -> None:
            remove_node_modules(path)
            _ok("node_modules removed.", on_success)

        _action_button(
            "Remove node_modules",
            key=f"nmdelbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=remove,
        )

    if subtype:
        st.caption(f"Node item subtype: {subtype}")


def _docker_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    details = _details(row)
    name = row.name
    item_type = row.item_type or ""
    container_id = details.get("ID") or details.get("Id") or row.label or name

    if item_type == "Container":
        st.write(f"Container **{name}**")
        c1, c2, c3 = st.columns(3)
        with c1:

            def start() -> None:
                docker_start(str(container_id))
                _ok("Container started.", on_success)

            _action_button("Start container", key=f"dstart_{row.id}", on_click=start)
        with c2:

            def stop() -> None:
                docker_stop(str(container_id))
                _ok("Container stopped.", on_success)

            _action_button("Stop container", key=f"dstop_{row.id}", on_click=stop)
        with c3:

            def restart() -> None:
                docker_restart(str(container_id))
                _ok("Container restarted.", on_success)

            _action_button("Restart container", key=f"drestart_{row.id}", on_click=restart)

        confirm = st.checkbox("Confirm remove container", key=f"drm_{row.id}")

        def remove() -> None:
            docker_remove_container(str(container_id))
            _ok("Container removed.", on_success)

        _action_button(
            "Remove stopped container",
            key=f"drmbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=remove,
        )

    elif item_type == "Image":
        st.write(f"Image **{name}**")
        confirm = st.checkbox("Confirm remove image", key=f"dimg_{row.id}")

        def remove() -> None:
            docker_remove_image(name)
            _ok("Image removed.", on_success)

        _action_button(
            "Remove image",
            key=f"dimgbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=remove,
        )

    if "Show inspect data" in (json_loads(row.available_actions, default=[]) or []):
        with st.expander("Inspect data", expanded=False):
            st.json(details)


def _ai_actions(row: Any, on_success: Callable[[], None] | None) -> None:
    details = _details(row)
    path = row.path or ""
    actions = json_loads(row.available_actions, default=[]) or []

    if "Reveal model" in actions and path:

        def reveal_model() -> None:
            reveal_in_finder(path)
            st.success("Finder reveal requested.")

        _action_button("Reveal model", key=f"aimodel_{row.id}", on_click=reveal_model)

    if "Reveal containing folder" in actions:
        folder = path or details.get("project") or ""

        def reveal_folder() -> None:
            target = folder if folder else path
            reveal_in_finder(target)
            st.success("Finder reveal requested.")

        _action_button("Reveal containing folder", key=f"aifolder_{row.id}", on_click=reveal_folder)

    if "Copy launch command" in actions:
        command = details.get("serve") or details.get("raw") or ""

        def copy_cmd() -> None:
            import subprocess

            subprocess.run(["pbcopy"], input=command, text=True, check=True, timeout=10)
            st.success("Launch command copied to clipboard.")

        _action_button("Copy launch command", key=f"aicopy_{row.id}", on_click=copy_cmd)

    if "Move selected model to Trash" in actions and path:
        settings = load_settings()
        allowed = settings.ai_scan_roots or []
        confirm = st.checkbox("Confirm move model to Trash", key=f"aitrash_{row.id}")

        def trash() -> None:
            dest = trash_path(path, allowed)
            _ok(f"Moved to {dest}", on_success)

        _action_button(
            "Move selected model to Trash",
            key=f"aitrashbtn_{row.id}",
            destructive=True,
            disabled=not confirm,
            on_click=trash,
        )

    if "Stop related local server" in actions:
        pid = details.get("pid") or getattr(row, "pid", None)
        if pid:
            confirm = st.checkbox("Confirm stop local AI server process", key=f"aistop_{row.id}")

            def stop() -> None:
                stop_process(int(pid), name=row.name)
                _ok("Stop signal sent.", on_success)

            _action_button(
                "Stop related local server",
                key=f"aistopbtn_{row.id}",
                destructive=True,
                disabled=not confirm,
                on_click=stop,
            )
