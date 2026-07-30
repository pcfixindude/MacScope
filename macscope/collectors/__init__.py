from __future__ import annotations

from macscope.collectors.applications import ApplicationsCollector
from macscope.collectors.ai_models import AICollector
from macscope.collectors.brew import BrewCollector
from macscope.collectors.docker_env import DockerCollector
from macscope.collectors.launch import LaunchItemsCollector
from macscope.collectors.login_items import LoginItemsCollector
from macscope.collectors.network import NetworkCollector
from macscope.collectors.node_envs import NodeCollector
from macscope.collectors.processes import ProcessesCollector
from macscope.collectors.python_envs import PythonCollector
from macscope.collectors.storage import StorageCollector
from macscope.collectors.system import SystemCollector

__all__ = [
    "ApplicationsCollector",
    "ProcessesCollector",
    "LaunchItemsCollector",
    "LoginItemsCollector",
    "BrewCollector",
    "NetworkCollector",
    "SystemCollector",
    "PythonCollector",
    "NodeCollector",
    "DockerCollector",
    "AICollector",
    "StorageCollector",
]
