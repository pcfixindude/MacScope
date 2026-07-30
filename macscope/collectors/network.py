from __future__ import annotations

import psutil

from inventory import Item
from utils import logger

COMMON_PORTS = {
    22: "SSH",
    80: "HTTP",
    443: "HTTPS",
    3000: "Dev web server",
    5000: "Flask/AirPlay",
    5432: "PostgreSQL",
    6379: "Redis",
    8000: "Dev web server",
    8080: "HTTP alternate",
    8501: "Streamlit",
    11434: "Ollama",
    1234: "LM Studio",
}


class NetworkCollector:
    name = "Network"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        try:
            connections = psutil.net_connections(kind="inet")
        except psutil.AccessDenied as exc:
            logger.warning("net_connections access denied: %s", exc)
            return []
        except Exception as exc:
            logger.exception("net_connections failed: %s", exc)
            raise

        for conn in connections:
            if conn.status != psutil.CONN_LISTEN and getattr(conn, "type", None) != getattr(psutil, "SOCK_DGRAM", object()):
                # Keep UDP unbound listeners when status empty
                if conn.status and conn.status != psutil.CONN_LISTEN:
                    continue
            if not conn.laddr:
                continue
            # Prefer TCP LISTEN; include UDP with port
            is_udp = str(conn.type).endswith("SOCK_DGRAM") or conn.type == 2
            if not is_udp and conn.status != psutil.CONN_LISTEN:
                continue
            address = f"{conn.laddr.ip}:{conn.laddr.port}"
            ip = conn.laddr.ip
            binding = _classify_binding(ip)
            name = "Unknown"
            exe = None
            user = None
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    name = proc.name()
                    exe = proc.exe()
                    user = proc.username()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    name = f"PID {conn.pid}"
            service = COMMON_PORTS.get(conn.laddr.port)
            explanation = (
                f"Listening on {address} ({binding.replace('_', ' ')})."
                + (f" Common service: {service}." if service else "")
                + " Binding to 0.0.0.0 does not by itself mean exposure to the public internet; firewall and network configuration also matter."
                if binding == "public_interface"
                else (
                    f"Listening on {address} ({binding.replace('_', ' ')})."
                    + (f" Common service: {service}." if service else "")
                )
            )
            item = Item(
                category="Network",
                name=name,
                path=exe,
                status="Listening",
                item_type="Listening Port",
                subtype="UDP" if is_udp else "TCP",
                label=address,
                executable_path=exe,
                user_owner=user,
                pid=conn.pid,
                network_ports=address,
                running_state="Listening",
                related_application=name,
                risk="Caution" if binding == "public_interface" else "Safe",
                explanation=explanation,
                details={
                    "pid": conn.pid,
                    "address": address,
                    "family": str(conn.family),
                    "type": "UDP" if is_udp else "TCP",
                    "binding": binding,
                    "service_hint": service,
                },
            )
            item.ensure_stable_id()
            items.append(item)
        return items


def _classify_binding(ip: str) -> str:
    if ip in {"127.0.0.1", "::1", "localhost"}:
        return "local_only"
    if ip in {"0.0.0.0", "::", "*"}:
        return "public_interface"
    if ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
        return "local_network_reachable"
    return "unknown"


def classify_binding(ip: str) -> str:
    return _classify_binding(ip)
