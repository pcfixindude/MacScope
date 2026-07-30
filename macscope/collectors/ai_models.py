from __future__ import annotations

from pathlib import Path

from inventory import Item
from macscope.settings import load_settings
from utils import dir_size_bytes, logger, run_command


MODEL_SUFFIXES = {".gguf", ".safetensors", ".bin", ".pt", ".onnx", ".mlx"}


class AICollector:
    name = "AI"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        items.extend(self._apps())
        items.extend(self._ollama())
        items.extend(self._model_files())
        items.extend(self._servers())
        return items

    def _apps(self) -> list[Item]:
        candidates = [
            ("LM Studio", Path("/Applications/LM Studio.app")),
            ("MacWhisper", Path("/Applications/MacWhisper.app")),
            ("Ollama", Path("/Applications/Ollama.app")),
        ]
        items: list[Item] = []
        for name, path in candidates:
            if not path.exists():
                continue
            item = Item(
                category="AI",
                name=name,
                path=str(path),
                status="Installed",
                item_type="Application",
                subtype="ai-app",
                installation_source="Applications",
                related_application=name,
                risk="Safe",
                explanation=f"{name} is installed locally.",
                available_actions=["Reveal model", "Reveal containing folder"],
                details={"kind": "ai-app"},
            )
            item.ensure_stable_id()
            items.append(item)
        return items

    def _ollama(self) -> list[Item]:
        items: list[Item] = []
        rc, out, err = run_command(["ollama", "list"], timeout=20)
        if rc != 0:
            logger.info("ollama list unavailable: %s", err or out)
            return items
        lines = out.splitlines()
        for line in lines[1:]:
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            item = Item(
                category="AI",
                name=name,
                status="Installed",
                item_type="Ollama Model",
                subtype="ollama",
                installation_source="Ollama",
                version=parts[1] if len(parts) > 1 else None,
                risk="Caution",
                explanation=f"Ollama model '{name}'.",
                available_actions=["Reveal containing folder", "Copy launch command"],
                details={"raw": line, "serve": f"ollama run {name}"},
            )
            item.ensure_stable_id()
            items.append(item)
        return items

    def _model_files(self) -> list[Item]:
        settings = load_settings()
        items: list[Item] = []
        seen: set[str] = set()
        for root in settings.ai_scan_roots:
            base = Path(root).expanduser()
            if not base.exists():
                continue
            try:
                count = 0
                for path in base.rglob("*"):
                    if count > 400:
                        break
                    if not path.is_file():
                        continue
                    if path.suffix.lower() not in MODEL_SUFFIXES and path.name not in {
                        "config.json",
                        "params.json",
                    }:
                        if path.suffix.lower() not in MODEL_SUFFIXES:
                            continue
                    if path.suffix.lower() not in MODEL_SUFFIXES:
                        continue
                    count += 1
                    key = str(path)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        size = float(path.stat().st_size)
                        mtime = str(path.stat().st_mtime)
                    except OSError:
                        size = None
                        mtime = None
                    quant = None
                    lower = path.name.lower()
                    for marker in ("q4_0", "q4_k", "q5_0", "q5_k", "q8_0", "f16", "fp16", "int4", "int8"):
                        if marker in lower:
                            quant = marker
                            break
                    item = Item(
                        category="AI",
                        name=path.name,
                        path=str(path),
                        status="Installed",
                        item_type="Model File",
                        subtype=path.suffix.lower().lstrip(".") or "model",
                        installation_source=str(base),
                        disk_usage=size,
                        modification_date=mtime,
                        risk="Caution",
                        explanation=f"Local AI model file ({path.suffix}).",
                        available_actions=["Reveal model", "Reveal containing folder", "Move selected model to Trash"],
                        details={"quantization": quant, "format": path.suffix.lower()},
                    )
                    item.ensure_stable_id()
                    items.append(item)
            except OSError as exc:
                logger.warning("AI model scan failed under %s: %s", base, exc)
        # Hugging Face cache summary
        hf = Path.home() / ".cache" / "huggingface"
        if hf.exists():
            size = float(dir_size_bytes(hf, max_files=8000))
            item = Item(
                category="AI",
                name="Hugging Face cache",
                path=str(hf),
                status="Present",
                item_type="Cache",
                subtype="huggingface",
                disk_usage=size,
                risk="Caution",
                explanation="Local Hugging Face model/cache directory.",
                available_actions=["Reveal containing folder"],
                details={"kind": "hf-cache"},
            )
            item.ensure_stable_id()
            items.append(item)
        return items

    def _servers(self) -> list[Item]:
        items: list[Item] = []
        # Common local AI ports
        known = {
            11434: "Ollama",
            1234: "LM Studio",
            7860: "Gradio/ComfyUI",
            8188: "ComfyUI",
        }
        import psutil

        try:
            conns = psutil.net_connections(kind="inet")
        except Exception as exc:
            logger.warning("AI server port scan failed: %s", exc)
            return items
        for conn in conns:
            if conn.status != psutil.CONN_LISTEN or not conn.laddr:
                continue
            port = conn.laddr.port
            if port not in known:
                continue
            name = known[port]
            proc_name = None
            if conn.pid:
                try:
                    proc_name = psutil.Process(conn.pid).name()
                except Exception:
                    proc_name = None
            item = Item(
                category="AI",
                name=f"{name} server",
                status="Listening",
                item_type="Local Server",
                subtype="ai-server",
                pid=conn.pid,
                network_ports=f"{conn.laddr.ip}:{port}",
                running_state="Running",
                related_application=name,
                risk="Caution",
                explanation=f"{name} appears to be listening on port {port}"
                + (f" via process {proc_name}." if proc_name else "."),
                available_actions=["Stop related local server"],
                details={"port": port, "process": proc_name},
            )
            item.ensure_stable_id()
            items.append(item)
        return items
