
#!/usr/bin/env python3
"""
Victor - Main Entry Point
Run this file to start VICTOR.

Usage:
    python main.py              # Start with GUI
    python main.py --cli        # Start in CLI mode
    python main.py --voice      # Start with voice active
    python main.py --diagnose   # Run diagnostics

Prerequisites:
    1. Install Ollama: https://ollama.com
    2. Pull models: ollama pull llama3.2 llava codellama phi3
    3. Install Python deps: pip install -r requirements.txt
"""
import sys
import argparse
import json
import os
import tempfile
import time

# Single-instance lock
LOCK_FILE = os.path.join(tempfile.gettempdir(), "victor_prime.lock")


def is_already_running():
    """Check if Victor is already running by checking lock file."""
    try:
        if os.path.exists(LOCK_FILE):
            # Check if process is actually still running
            try:
                with open(LOCK_FILE, 'r') as f:
                    pid = f.read().strip()
                if pid:
                    import psutil
                    try:
                        proc = psutil.Process(int(pid))
                        if proc.is_running() and 'python' in proc.name().lower():
                            return True
                    except:
                        pass
            except:
                pass
        return False
    except:
        return False


def create_lock_file():
    """Create lock file with current PID."""
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except:
        pass


def remove_lock_file():
    """Remove lock file on exit."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass


def run_gui():
    """Run with PySide6 GUI."""
    from interface.main_window import main
    main()


def run_cli():
    """Run in command-line mode."""
    from core.victor_core import VictorCore

    print("\n" + "="*60)
    print("   Victor Command Line Interface")
    print("   Type 'exit' to quit, 'voice' to toggle voice mode")
    print("="*60 + "\n")

    victor = VictorCore()

    # Optional: start voice
    victor.start_voice_mode()

    while True:
        try:
            query = input("\nYou > ").strip()

            if query.lower() in ['exit', 'quit', 'bye']:
                victor.shutdown()
                break

            if query.lower() == 'voice':
                if victor.state.listening:
                    victor.stop_voice_mode()
                    print("Voice mode disabled")
                else:
                    victor.start_voice_mode()
                    print("Voice mode enabled - say 'Hey VICTOR'")
                continue

            if query.lower() == 'status':
                status = victor.get_status()
                print(f"\nStatus: {json.dumps(status, indent=2)}")
                continue

            if query.lower() == 'diagnose':
                print(victor.self_diagnose())
                continue

            if not query:
                continue

            response = victor.process_command(query)
            print(f"\nVICTOR > {response}")

            # Optional TTS
            victor.speak(response)

        except KeyboardInterrupt:
            print("\n\nShutting down...")
            victor.shutdown()
            break
        except Exception as e:
            print(f"Error: {e}")


def run_diagnose():
    """Run system diagnostics."""
    from core.victor_core import VictorCore
    victor = VictorCore()
    print(victor.self_diagnose())
    victor.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Victor - Local AI Assistant")
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode')
    parser.add_argument('--voice', action='store_true', help='Start with voice active')
    parser.add_argument('--diagnose', action='store_true', help='Run diagnostics')

    args = parser.parse_args()

    # Diagnose doesn't need single-instance check
    if args.diagnose:
        run_diagnose()
        return

    # Check if already running
    if is_already_running():
        print("Victor is already running! Only one instance allowed.")
        return

    # Create lock file
    create_lock_file()

    # Ensure lock file is removed on exit
    import atexit
    atexit.register(remove_lock_file)

    try:
        if args.cli:
            run_cli()
        else:
            try:
                run_gui()
            except ImportError as e:
                print(f"GUI not available: {e}")
                print("Falling back to CLI mode...")
                run_cli()
    finally:
        remove_lock_file()


if __name__ == "__main__":
    main()


