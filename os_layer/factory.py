
import platform


def get_os():
    system = platform.system()
    if system == "Windows":
        from .windows import WindowsOS
        return WindowsOS()
    elif system == "Linux":
        from .linux import LinuxOS
        return LinuxOS()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

