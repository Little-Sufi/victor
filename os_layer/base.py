
from abc import ABC, abstractmethod
import os
import subprocess
import platform
import psutil
from typing import Optional


class OSInterface(ABC):
    @property
    @abstractmethod
    def platform_name(self):
        pass

    def get_system_stats(self):
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return {
            "system": platform.system(),
            "release": platform.release(),
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_total": memory.total,
            "memory_used": memory.used,
            "disk_percent": disk.percent,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "uptime_seconds": int(psutil.boot_time())
        }

    def get_active_window(self):
        return None

    def launch_application(self, app_name: str):
        """Launch an application by name or path."""
        try:
            if platform.system() == "Windows":
                os.startfile(app_name)
            else:
                subprocess.Popen([app_name])
            return f"Launched {app_name}"
        except Exception as e:
            return f"Failed to launch {app_name}: {e}"

