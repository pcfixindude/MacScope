from __future__ import annotations

import os
from pathlib import Path

import psutil

from inventory import Item
from protection import is_protected_path, is_protected_process
from utils import logger


class ProcessesCollector:
    name = "Processes"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        # Prime CPU percents
        try:
            for proc in psutil.process_iter(["pid"]):
                try:
                    proc.cpu_percent(interval=None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            import time

            time.sleep(0.15)
        except Exception as exc:
            logger.warning("CPU prime failed: %s", exc)

        our_pid = os.getpid()
        parent_pid = os.getppid()

        for proc in psutil.process_iter(
            [
                "pid",
                "name",
                "exe",
                "username",
                "cpu_percent",
                "memory_percent",
                "cmdline",
                "ppid",
                "status",
            ]
        ):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("Skipping process: %s", exc)
                continue
            try:
                items.append(self._item_from_info(info, our_pid, parent_pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as exc:
                logger.warning("Process collect error: %s", exc)
        return items

    def _item_from_info(self, info: dict, our_pid: int, parent_pid: int) -> Item:
        pid = info.get("pid")
        name = info.get("name") or str(pid)
        path = info.get("exe")
        cmdline = info.get("cmdline") or []
        protected_path = bool(path and is_protected_path(path))
        blocked, reason = is_protected_process(pid=pid, name=name, exe=path)
        protected = protected_path or blocked or pid in {our_pid, parent_pid, 0, 1}

        parent_name = None
        try:
            ppid = info.get("ppid")
            if ppid:
                parent_name = psutil.Process(ppid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            parent_name = None

        related = None
        if path and "/Applications/" in str(path):
            parts = Path(path).parts
            for part in parts:
                if part.endswith(".app"):
                    related = part[:-4]
                    break

        return Item(
            category="Processes",
            name=str(name),
            path=path,
            status="Running",
            vendor=None,
            version=None,
            cpu=float(info.get("cpu_percent") or 0),
            memory=float(info.get("memory_percent") or 0),
            risk="Protected" if protected else "Unknown",
            protected=protected,
            label=None,
            item_type="Process",
            executable_path=path,
            publisher=None,
            installation_source=None,
            running_state="Running",
            startup_state=None,
            related_application=related,
            explanation=reason if blocked else None,
            pid=pid,
            parent_process=parent_name,
            user_owner=info.get("username"),
            command=" ".join(cmdline),
            details={
                "pid": pid,
                "ppid": info.get("ppid"),
                "parent_name": parent_name,
                "user": info.get("username"),
                "command": " ".join(cmdline),
                "proc_status": info.get("status"),
            },
        )
