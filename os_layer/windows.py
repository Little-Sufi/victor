
from .base import OSInterface
import platform
import subprocess
import os


class WindowsOS(OSInterface):
    @property
    def platform_name(self):
        return "windows"

    def get_system_stats(self):
        stats = super().get_system_stats()
        return stats

    def get_active_window(self):
        try:
            import win32gui
            window = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(window)
            return {"title": title, "hwnd": window}
        except:
            return None

    def launch_application(self, app_name: str):
        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "settings": "ms-settings:",
            "task manager": "taskmgr.exe",
            "control panel": "control.exe",
        }
        
        app_name_lower = app_name.lower()
        if app_name_lower in app_map:
            app = app_map[app_name_lower]
        else:
            app = app_name
        
        try:
            if app.startswith("ms-"):
                os.startfile(app)
            else:
                subprocess.Popen(app, shell=True)
            return f"Launched {app_name}"
        except Exception as e:
            return f"Failed to launch {app_name}: {e}"

