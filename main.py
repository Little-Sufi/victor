#!/usr/bin/env python3
"""
Victor - Main Entry Point
Run this file to start VICTOR.

Usage:
    python main.py              # Start with GUI Orb
    python main.py --cli        # Start in CLI mode
"""
import os
import sys
import argparse
import tempfile
import time

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class TeeLogger(object):
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]
    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass
    def writelines(self, datas):
        for s in self.streams:
            try:
                s.writelines(datas)
                s.flush()
            except Exception:
                pass
    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass
    def __getattr__(self, attr):
        if self.streams:
            return getattr(self.streams[0], attr)
        return None

log_path = os.path.join(os.path.dirname(__file__), "victor_error.log")
try:
    # Use append mode so we keep execution history
    log_file = open(log_path, "a", encoding="utf-8")
    sys.stdout = TeeLogger(sys.__stdout__, log_file)
    sys.stderr = TeeLogger(sys.__stderr__, log_file)
    print(f"\n==================================================")
    print(f"   VICTOR Session: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==================================================")
except Exception:
    pass

def attach_to_default_desktop():
    """Attaches current thread to the interactive 'Default' desktop on WinSta0 so GUI and screen capture are always live."""
    try:
        import ctypes
        # Set Windows process DPI awareness to guarantee 1:1 physical pixel alignment
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        user32 = ctypes.windll.user32
        GENERIC_ALL = 0x10000000
        hdesk = user32.OpenDesktopW("Default", 0, False, GENERIC_ALL)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            return hdesk
    except Exception:
        pass
    return None

attach_to_default_desktop()

# Single-instance kernel lock
_lock_file_handle = None

def acquire_instance_lock():
    """Acquires an exclusive OS-level kernel file lock."""
    global _lock_file_handle
    lock_path = os.path.join(tempfile.gettempdir(), "victor_prime.lock")
    try:
        _lock_file_handle = open(lock_path, "w")
        if msvcrt:
            msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        _lock_file_handle.write(str(os.getpid()))
        _lock_file_handle.flush()
        return True
    except (IOError, OSError):
        return False

def release_instance_lock():
    """Releases the OS-level lock on exit."""
    global _lock_file_handle
    if _lock_file_handle:
        try:
            if msvcrt:
                _lock_file_handle.seek(0)
                msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        try:
            _lock_file_handle.close()
        except Exception:
            pass
        _lock_file_handle = None


def run_gui():
    """Run with PySide6 GUI."""
    from interface.main_window import main
    main()


def run_cli(provider: str = "gemini"):
    """Run in command-line mode based on resolved provider tier."""
    import asyncio

    if provider == "openai":
        from core.openai_agent import VictorOpenAIAgent
        agent = VictorOpenAIAgent()
        asyncio.run(agent.run())
    elif provider == "ollama":
        from core.ollama_agent import VictorOllamaAgent
        agent = VictorOllamaAgent()
        asyncio.run(agent.run())
    else:
        # Default Tier 1: Gemini Live API
        from core.gemini_live import VictorLiveAgent
        print("\n" + "="*60)
        print("   VICTOR Live - Powered by Gemini Live API (Tier 1)")
        print("   Press Ctrl+C to quit")
        print("="*60 + "\n")

        agent = VictorLiveAgent()
        try:
            asyncio.run(agent.run())
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            agent.is_running = False
            agent.stop_audio()


def main():
    from core.provider_manager import get_active_provider, get_provider_status
    provider = get_active_provider()
    status = get_provider_status()

    # If no provider is available and user is missing all keys/services:
    if not status["tier1_gemini"]["configured"] and not status["tier2_openai"]["configured"] and not status["tier3_ollama"]["configured"]:
        from interface.api_setup import get_api_key
        new_key = get_api_key()
        if new_key:
            with open(".env", "a") as f:
                f.write(f'\nGEMINI_API_KEY="{new_key}"\n')
            os.environ["GEMINI_API_KEY"] = new_key
            provider = "gemini"
        else:
            print("[Victor] No Gemini/OpenAI API key configured and Ollama not running.")
            sys.exit(0)

    parser = argparse.ArgumentParser(description="Victor - Autonomous AI Assistant")
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode')
    parser.add_argument('--provider', choices=['gemini', 'openai', 'ollama'], default=None, help='Force specific provider')

    args = parser.parse_args()
    if args.provider:
        provider = args.provider

    # Check kernel lock to guarantee strictly one instance
    if not acquire_instance_lock():
        print("[Victor] Another instance is already running. Exiting.")
        return

    import atexit
    atexit.register(release_instance_lock)

    try:
        if args.cli or provider in ("openai", "ollama"):
            run_cli(provider=provider)
        else:
            try:
                run_gui()
            except ImportError as e:
                print(f"GUI not available: {e}")
                print("Falling back to CLI mode...")
                run_cli(provider=provider)
    finally:
        release_instance_lock()


if __name__ == "__main__":
    main()
