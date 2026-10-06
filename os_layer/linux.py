
from .base import OSInterface
import subprocess
import os


class LinuxOS(OSInterface):
    @property
    def platform_name(self):
        return "linux"

    def get_system_stats(self):
        stats = super().get_system_stats()
        return stats

    def launch_application(self, app_name: str):
        app_map = {
            "terminal": "gnome-terminal",
            "firefox": "firefox",
            "chrome": "google-chrome",
            "nautilus": "nautilus",
            "files": "nautilus",
            "calculator": "gnome-calculator",
            "calc": "gnome-calculator",
            "text editor": "gedit",
            "settings": "gnome-control-center",
        }
        
        app_name_lower = app_name.lower()
        if app_name_lower in app_map:
            app = app_map[app_name_lower]
        else:
            app = app_name
        
        try:
            subprocess.Popen([app])
            return f"Launched {app_name}"
        except Exception as e:
            return f"Failed to launch {app_name}: {e}"

