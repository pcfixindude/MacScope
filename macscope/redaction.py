from __future__ import annotations

import getpass
import re
from pathlib import Path
from typing import Any

from macscope.settings import Settings, load_settings


def redact_text(text: str | None, settings: Settings | None = None) -> str:
    if not text:
        return ""
    cfg = settings or load_settings()
    result = text
    home = str(Path.home())
    user = getpass.getuser()
    if cfg.redact_home_path and home:
        result = result.replace(home, "~")
    if cfg.redact_username and user:
        result = re.sub(rf"\b{re.escape(user)}\b", "<user>", result)
    if cfg.redact_local_ips:
        result = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<ip>", result)
        result = re.sub(r"\b([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\b", "<ipv6>", result)
    return result


_SENSITIVE_ARG_RE = re.compile(
    r"(?i)(--?(?:password|token|secret|api[_-]?key|authorization|passwd|access[_-]?key)(?:=|\s+))\S+"
)


def redact_command(command: str | None, settings: Settings | None = None) -> str:
    if not command:
        return ""
    cfg = settings or load_settings()
    result = command
    if cfg.redact_command_args:
        result = _SENSITIVE_ARG_RE.sub(r"\1<redacted>", result)
        result = re.sub(
            r"(?i)\b([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z0-9_]*)=([^\s]+)",
            r"\1=<redacted>",
            result,
        )
    return redact_text(result, cfg)


def redact_mapping(data: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or load_settings()
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            if "command" in key.lower() or "cmdline" in key.lower():
                out[key] = redact_command(value, cfg)
            else:
                out[key] = redact_text(value, cfg)
        elif isinstance(value, dict):
            out[key] = redact_mapping(value, cfg)
        else:
            out[key] = value
    if cfg.redact_hostname and "hostname" in out and isinstance(out["hostname"], str):
        out["hostname"] = "<host>"
    return out
