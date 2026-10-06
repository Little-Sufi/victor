"""
VICTOR Live Agent - Core Gemini Live API Engine
Handles real-time bidirectional audio streaming, screen vision, and tool calling.
"""
import os
import sys
import asyncio
import cv2
import mss
import numpy as np
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05
import sounddevice as sd
import webbrowser
import subprocess
import datetime
import zoneinfo
import psutil
import ctypes
import pyperclip
import io
import time
import threading
import platform
from PIL import ImageGrab
from contextlib import AsyncExitStack
import random
import json

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

# Windows DPI awareness and Win32 definitions
WNDENUMPROC = None
if IS_WINDOWS:
    try:
        from ctypes import wintypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        ctypes.windll.user32.EnumDesktopWindows.argtypes = [wintypes.HDESK, WNDENUMPROC, wintypes.LPARAM]
        ctypes.windll.user32.EnumDesktopWindows.restype = wintypes.BOOL
        ctypes.windll.user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
        ctypes.windll.user32.EnumWindows.restype = wintypes.BOOL
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types
import google.genai.live as google_genai_live

# Monkeypatch websockets connection to prevent premature 1011 keepalive ping timeout.
# Google's Gemini Live endpoint handles application-level streaming and does not echo
# raw transport ping frames, causing default websockets (ping_interval=20) to drop the socket.
_orig_ws_connect = google_genai_live.ws_connect

def _resilient_ws_connect(*args, **kwargs):
    kwargs.setdefault('ping_interval', None)
    kwargs.setdefault('ping_timeout', None)
    return _orig_ws_connect(*args, **kwargs)

google_genai_live.ws_connect = _resilient_ws_connect


class VictorLiveAgent:
    def __init__(self, on_status_change=None, on_subtitle_change=None):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("[Warning] GEMINI_API_KEY not found in environment!")
            
        self.client = genai.Client(api_key=self.api_key)
        self.session = None
        self.session_handle = None
        self.mic_stream = None
        self.speaker_stream = None
        self.is_running = False
        self.is_speaking = False
        self.is_muted = False
        
        self.audio_in_queue = None
        self.audio_out_queue = None
        self.loop = None
        
        # Background task manager for long-running pipelines and processors
        self.tasks_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tasks")
        os.makedirs(self.tasks_dir, exist_ok=True)
        self.background_tasks = {}
        self.task_counter = 0

        # Notes vault
        self.notes_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notes", "victor_notes.json")
        os.makedirs(os.path.dirname(self.notes_file), exist_ok=True)

        # Active countdown timers
        self.active_timers = {}
        self.timer_counter = 0

        # Voice persona ('Fenrir', 'Aoede', 'Kore', 'Puck', 'Charon') and DSP effects
        self.config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.settings_file = os.path.join(self.config_dir, "victor_settings.json")
        self.voice_name = os.getenv("VICTOR_VOICE", "Charon")
        self.active_character = "optimus_prime"
        self.audio_dsp_effect = "none"
        self._load_persisted_settings()

        # Live vision streaming (Continuous camera & screen video input)
        self.is_camera_monitoring = False
        self.camera_cap = None
        self.camera_interval = 1.0
        self.is_screen_monitoring = False
        self.screen_interval = 3.0

        # GUI callbacks
        self.on_status_change = on_status_change
        self.on_subtitle_change = on_subtitle_change

    def _load_persisted_settings(self):
        """Loads voice persona and DSP profile from victor_settings.json, defaulting to Optimus Prime."""
        self.default_voice = "Charon"
        self.default_character = "optimus_prime"
        self.default_dsp = "metallic_bass"
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.default_voice = cfg.get("voice_name", "Charon")
                    self.default_character = cfg.get("active_character", "optimus_prime")
                    self.default_dsp = cfg.get("audio_dsp_effect", "metallic_bass")
            except Exception as e:
                print(f"[Victor Settings] Error loading settings: {e}")
        self.voice_name = self.default_voice
        self.active_character = self.default_character
        self.audio_dsp_effect = self.default_dsp

    def _save_persisted_settings(self, force: bool = False):
        """Persists default voice persona and DSP configuration to disk ONLY when explicitly commanded."""
        if not force:
            return
        try:
            cfg = {
                "voice_name": getattr(self, "default_voice", "Charon"),
                "active_character": getattr(self, "default_character", "optimus_prime"),
                "audio_dsp_effect": getattr(self, "default_dsp", "metallic_bass"),
                "camera_monitoring_fps": 1.0,
                "description": "Default persistent voice, persona, and capability profile for VICTOR. Optimus Prime is permanently set as the primary default."
            }
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            print(f"[Victor Settings] Persisted default profile: voice={cfg['voice_name']}, char={cfg['active_character']}, dsp={cfg['audio_dsp_effect']}")
        except Exception as e:
            print(f"[Victor Settings] Error saving settings: {e}")

    def _mic_callback(self, indata, frames, time_info, status):
        """High-priority PortAudio callback for audio input."""
        if not self.is_running or self.is_muted or self.is_speaking:
            return

        if self.loop and self.audio_in_queue and not self.loop.is_closed():
            try:
                # Apply 3.0x digital gain boost with clipping safeguard
                audio_array = np.frombuffer(indata, dtype=np.int16)
                boosted = np.clip(audio_array.astype(np.float32) * 3.0, -32768, 32767).astype(np.int16)
                data = boosted.tobytes()

                self.loop.call_soon_threadsafe(
                    self.audio_in_queue.put_nowait, 
                    data
                )
            except Exception:
                pass

    def start_audio(self):
        """Initializes both input and output audio streams."""
        print("[Victor Live] Initializing audio streams with sounddevice...")
        try:
            self.speaker_stream = sd.RawOutputStream(
                samplerate=24000, 
                channels=1, 
                dtype='int16'
            )
            self.speaker_stream.start()
        except Exception as e:
            print(f"[Victor Live] Error starting speaker stream: {e}")

        try:
            self.mic_stream = sd.RawInputStream(
                samplerate=16000, 
                blocksize=1024, 
                channels=1, 
                dtype='int16',
                callback=self._mic_callback
            )
            self.mic_stream.start()
            print("[Victor Live] Audio initialized. Mic stream active.")
        except Exception as e:
            print(f"[Victor Live] Error starting mic stream: {e}")

    def stop_audio(self):
        """Safely stops audio streams."""
        try:
            if self.mic_stream:
                self.mic_stream.stop()
                self.mic_stream.close()
                self.mic_stream = None
        except Exception as e:
            print(f"[Victor Live] Error closing mic: {e}")
            
        try:
            if self.speaker_stream:
                self.speaker_stream.stop()
                self.speaker_stream.close()
                self.speaker_stream = None
        except Exception as e:
            print(f"[Victor Live] Error closing speaker: {e}")

    def stop(self):
        """Signals the agent to stop all loops and shutdown."""
        self.is_running = False
        if hasattr(self, 'stop_event') and self.stop_event and self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.stop_event.set)
        self.stop_audio()

    def _write_speaker(self, data: bytes):
        """Writes audio chunk to speaker stream with auto-recovery."""
        if not self.speaker_stream:
            return
        try:
            self.speaker_stream.write(data)
        except Exception as e:
            print(f"[Victor Live] Speaker write error: {e}. Recovering stream...")
            try:
                try:
                    self.speaker_stream.stop()
                    self.speaker_stream.close()
                except:
                    pass
                self.speaker_stream = sd.RawOutputStream(
                    samplerate=24000, 
                    channels=1, 
                    dtype='int16'
                )
                self.speaker_stream.start()
                self.speaker_stream.write(data)
            except Exception as e2:
                print(f"[Victor Live] Failed to recover speaker: {e2}")

    def _play_pcm_tone_sequence(self, notes: list[tuple[int, int]]):
        """Generates 24000Hz 16-bit PCM waveform for note sequence and streams directly through the active speaker stream."""
        def _synth():
            try:
                sr = 24000
                chunks = []
                for freq, dur_ms in notes:
                    n_samples = int(sr * (dur_ms / 1000.0))
                    if freq == 0:
                        chunk = np.zeros(n_samples, dtype=np.int16)
                    else:
                        t = np.linspace(0, dur_ms / 1000.0, n_samples, False)
                        env = np.ones(n_samples, dtype=np.float32)
                        ramp = min(int(sr * 0.006), n_samples // 2)
                        if ramp > 0:
                            env[:ramp] = np.linspace(0, 1, ramp)
                            env[-ramp:] = np.linspace(1, 0, ramp)
                        wave = (np.sin(2 * np.pi * freq * t) * 0.8 + np.sin(4 * np.pi * freq * t) * 0.2)
                        chunk = (wave * 16000 * env).astype(np.int16)
                    chunks.append(chunk)
                    chunks.append(np.zeros(int(sr * 0.012), dtype=np.int16))
                
                if chunks and self.speaker_stream:
                    audio_bytes = np.concatenate(chunks).tobytes()
                    self._write_speaker(audio_bytes)
            except Exception as e:
                print(f"[Victor Audio] PCM stream error: {e}")

        threading.Thread(target=_synth, daemon=True).start()

    def _apply_audio_dsp(self, chunk: bytes) -> bytes:
        """Applies real-time hardware DSP audio effect (metallic flange, sub-bass resonance, or robotic modulation)."""
        eff = getattr(self, "audio_dsp_effect", "none")
        if not eff or eff == "none":
            return chunk
        try:
            arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            if len(arr) < 100:
                return chunk

            if eff in ["metallic_bass", "optimus", "megatron", "ultron", "metallic", "robot"]:
                # Comb filter delay (~84 samples = 3.5ms metallic flanger resonance)
                delay = 84
                delayed = np.zeros_like(arr)
                delayed[delay:] = arr[:-delay]

                # Low-pass sub-bass boost (15-sample moving average)
                kernel = np.ones(15, dtype=np.float32) / 15.0
                low_pass = np.convolve(arr, kernel, mode='same')

                # Mix: 60% original + 45% metallic comb delay + 65% deep sub-bass
                processed = arr * 0.60 + delayed * 0.45 + low_pass * 0.65
                return np.clip(processed, -32768, 32767).astype(np.int16).tobytes()
            elif eff in ["goku_bright", "bright", "saiyan"]:
                # High frequency presence / brilliance boost for clear, higher-pitched Saiyan tone
                kernel = np.ones(8, dtype=np.float32) / 8.0
                low = np.convolve(arr, kernel, mode='same')
                high = arr - low
                processed = arr * 0.70 + high * 1.35
                return np.clip(processed, -32768, 32767).astype(np.int16).tobytes()
            elif eff in ["naruto_raspy", "raspy", "ninja_grit"]:
                # Bandpass mid-range crunch with soft saturation for raspy, gritty throat texture
                k_wide = np.ones(24, dtype=np.float32) / 24.0
                k_tight = np.ones(6, dtype=np.float32) / 6.0
                l_w = np.convolve(arr, k_wide, mode='same')
                l_t = np.convolve(arr, k_tight, mode='same')
                mid = l_t - l_w
                sat_mid = np.tanh(mid / 8000.0) * 8000.0
                processed = arr * 0.60 + sat_mid * 1.10 + mid * 0.50
                return np.clip(processed, -32768, 32767).astype(np.int16).tobytes()
            elif eff in ["hiphop_punch", "killer_bee", "bee_flow"]:
                # Chest punch bass + warm dynamic compression for booming emcee presence
                k_bee = np.ones(12, dtype=np.float32) / 12.0
                chest = np.convolve(arr, k_bee, mode='same')
                proc = arr * 0.70 + chest * 0.85
                proc = np.sign(proc) * (np.abs(proc) ** 0.94) * 1.20
                return np.clip(proc, -32768, 32767).astype(np.int16).tobytes()
            elif eff in ["deep_bass", "bass"]:
                kernel = np.ones(20, dtype=np.float32) / 20.0
                low_pass = np.convolve(arr, kernel, mode='same')
                processed = arr * 0.75 + low_pass * 0.90
                return np.clip(processed, -32768, 32767).astype(np.int16).tobytes()
            elif eff in ["radio", "cybernetic"]:
                processed = np.clip(arr * 1.4, -22000, 22000)
                return processed.astype(np.int16).tobytes()
        except Exception:
            return chunk
        return chunk

    async def _play_audio_loop(self):
        """Dedicated async loop for non-blocking audio playback with real-time DSP effects."""
        while self.is_running:
            try:
                chunk = await self.audio_out_queue.get()
                if not chunk:
                    self.audio_out_queue.task_done()
                    continue
                    
                self.is_speaking = True
                if self.on_status_change:
                    self.on_status_change("speaking")
                    
                processed_chunk = self._apply_audio_dsp(chunk)
                await asyncio.to_thread(self._write_speaker, processed_chunk)
                self.audio_out_queue.task_done()
                
                # Check if queue has drained
                if self.audio_out_queue.empty():
                    await asyncio.sleep(0.25)
                    if self.audio_out_queue.empty():
                        self.is_speaking = False
                        # Flush any queued mic audio that might have bled through while speaking
                        if self.audio_in_queue:
                            while not self.audio_in_queue.empty():
                                try:
                                    self.audio_in_queue.get_nowait()
                                    self.audio_in_queue.task_done()
                                except Exception:
                                    break
                        if self.on_status_change:
                            self.on_status_change("idle")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Victor Live] Playback loop error: {e}")
                self.is_speaking = False

    def send_text(self, text: str):
        """Allows sending text prompt directly to Victor."""
        if self.session and self.loop and not self.loop.is_closed():
            print(f"[Victor Live] User sent text command: {text}")
            if self.on_subtitle_change:
                self.on_subtitle_change(f"💬 You: {text}")
            if self.on_status_change:
                self.on_status_change("thinking")
            asyncio.run_coroutine_threadsafe(
                self.session.send_realtime_input(text=text),
                self.loop
            )

    # --- COMPREHENSIVE TOOLS FOR GEMINI HOST CONTROL ---
    def get_current_time(self, timezone_or_location: str = "local") -> str:
        """Returns the exact current date, time, and day of the week for the local system or any world location/timezone. If the user does not explicitly specify another city or country, ALWAYS use 'local' so the user's actual host system time is reported."""
        loc = (timezone_or_location or "local").strip().lower()
        print(f"Executing: get_current_time('{loc}')")
        
        tz_aliases = {
            "local": None,
            "system": None,
            "here": None,
            "india": "Asia/Kolkata",
            "ist": "Asia/Kolkata",
            "indian": "Asia/Kolkata",
            "delhi": "Asia/Kolkata",
            "mumbai": "Asia/Kolkata",
            "utc": "UTC",
            "gmt": "GMT",
            "london": "Europe/London",
            "uk": "Europe/London",
            "england": "Europe/London",
            "new york": "America/New_York",
            "est": "America/New_York",
            "edt": "America/New_York",
            "california": "America/Los_Angeles",
            "los angeles": "America/Los_Angeles",
            "pst": "America/Los_Angeles",
            "pdt": "America/Los_Angeles",
            "chicago": "America/Chicago",
            "cst": "America/Chicago",
            "tokyo": "Asia/Tokyo",
            "japan": "Asia/Tokyo",
            "jst": "Asia/Tokyo",
            "dubai": "Asia/Dubai",
            "uae": "Asia/Dubai",
            "singapore": "Asia/Singapore",
            "sydney": "Australia/Sydney",
            "australia": "Australia/Sydney",
            "paris": "Europe/Paris",
            "france": "Europe/Paris",
            "berlin": "Europe/Berlin",
            "germany": "Europe/Berlin",
            "amsterdam": "Europe/Amsterdam",
            "netherlands": "Europe/Amsterdam",
            "beijing": "Asia/Shanghai",
            "china": "Asia/Shanghai",
            "toronto": "America/Toronto",
            "canada": "America/Toronto",
            "moscow": "Europe/Moscow",
            "russia": "Europe/Moscow"
        }
        
        target_tz_str = tz_aliases.get(loc)
        try:
            if not target_tz_str or target_tz_str == "local":
                now = datetime.datetime.now()
                tz_name = "Local System Time"
            else:
                tz = zoneinfo.ZoneInfo(target_tz_str)
                now = datetime.datetime.now(tz)
                tz_name = target_tz_str
                
            formatted = now.strftime("%A, %B %d, %Y, %I:%M:%S %p")
            return f"Current time ({timezone_or_location}): {formatted} [{tz_name}]"
        except Exception as e:
            now = datetime.datetime.now()
            return f"Current time: {now.strftime('%A, %B %d, %Y, %I:%M:%S %p')} [Local]"

    def close_application(self, app_name: str, force: bool = False) -> str:
        """Closes a running software application or program by name (e.g. 'notepad', 'calc', 'chrome', 'edge', 'explorer', 'code', 'spotify')."""
        print(f"Executing: close_application('{app_name}', force={force})")
        name_clean = app_name.strip().lower()
        alias_map = {
            "notepad": "notepad.exe",
            "calc": "CalculatorApp.exe",
            "calculator": "CalculatorApp.exe",
            "chrome": "chrome.exe",
            "browser": "chrome.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe",
            "explorer": "explorer.exe",
            "file manager": "explorer.exe",
            "files": "explorer.exe",
            "code": "Code.exe",
            "vscode": "Code.exe",
            "terminal": "WindowsTerminal.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "Taskmgr.exe",
            "word": "WINWORD.EXE",
            "excel": "EXCEL.EXE",
            "spotify": "Spotify.exe",
            "discord": "Discord.exe",
            "steam": "steam.exe"
        }
        target_exe = alias_map.get(name_clean, name_clean if name_clean.endswith(".exe") else f"{name_clean}.exe")
        closed_count = 0
        for p in psutil.process_iter(['pid', 'name']):
            try:
                pname = p.info['name']
                if pname and (pname.lower() == target_exe.lower() or name_clean in pname.lower()):
                    if force:
                        p.kill()
                    else:
                        p.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        if closed_count > 0:
            return f"Successfully closed {app_name} (terminated {closed_count} instances)."
            
        try:
            cmd = ["taskkill", "/F" if force else "/T", "/IM", target_exe]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return f"Successfully closed {app_name} via taskkill."
        except Exception:
            pass
            
        return f"No active process found for '{app_name}'."

    def close_active_window(self) -> str:
        """Closes the currently active foreground window using Alt+F4."""
        print("Executing: close_active_window()")
        pyautogui.hotkey('alt', 'f4')
        return "Closed active window."

    def list_running_processes(self, filter_name: str = "", limit: int = 15) -> str:
        """Lists currently active running processes and applications on the PC."""
        print(f"Executing: list_running_processes(filter='{filter_name}', limit={limit})")
        procs = []
        filt = filter_name.strip().lower()
        for p in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                name = p.info['name'] or ""
                if filt and filt not in name.lower():
                    continue
                mem_mb = round(p.info['memory_info'].rss / (1024 * 1024), 1)
                procs.append((p.info['pid'], name, mem_mb))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        procs.sort(key=lambda x: x[2], reverse=True)
        top = procs[:limit]
        if not top:
            return f"No processes matching '{filter_name}' found."
            
        lines = [f"Total matching: {len(procs)}. Top processes by memory:"]
        for pid, name, mem in top:
            lines.append(f"- PID {pid}: {name} ({mem} MB)")
        return "\n".join(lines)

    def kill_process(self, target: str, force: bool = True) -> str:
        """Terminates a specific process by PID number or executable name."""
        print(f"Executing: kill_process('{target}', force={force})")
        target_str = target.strip()
        if target_str.isdigit():
            pid = int(target_str)
            try:
                p = psutil.Process(pid)
                pname = p.name()
                if force:
                    p.kill()
                else:
                    p.terminate()
                return f"Terminated PID {pid} ({pname})."
            except psutil.NoSuchProcess:
                return f"PID {pid} does not exist."
            except Exception as e:
                return f"Failed to terminate PID {pid}: {e}"
        else:
            return self.close_application(target_str, force=force)

    def type_keyboard(self, text: str, press_enter: bool = False) -> str:
        """Types text accurately into the active window using clipboard paste, eliminating typos, dropped characters, and special symbol errors."""
        print(f"Executing: type_keyboard('{text}', press_enter={press_enter})")
        try:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            if press_enter:
                pyautogui.press('enter')
            return f"Successfully typed: {text}"
        except Exception:
            pyautogui.write(text, interval=0.01)
            if press_enter:
                pyautogui.press('enter')
            return f"Typed via fallback: {text}"

    def press_key(self, key: str) -> str:
        """Presses a single key (e.g. 'enter', 'tab', 'esc', 'backspace', 'win', 'space', 'up', 'down', 'left', 'right', 'delete')."""
        print(f"Executing: press_key('{key}')")
        pyautogui.press(key)
        return f"Pressed key {key}"

    def press_hotkey(self, keys: str) -> str:
        """Presses a key combination/shortcut separated by '+' (e.g. 'ctrl+c', 'ctrl+v', 'alt+tab', 'alt+f4', 'win+d', 'win+e', 'win+r', 'ctrl+shift+esc')."""
        print(f"Executing: press_hotkey('{keys}')")
        key_parts = [k.strip().lower() for k in keys.split("+")]
        pyautogui.hotkey(*key_parts)
        return f"Pressed hotkey {keys}"

    def hold_key(self, key: str, duration_seconds: float = 1.0) -> str:
        """Holds down a keyboard key for a specified duration in seconds (e.g. holding 'w' to drive/accelerate in NFS or GTA, holding 'shift' to sprint, holding 'space' for handbrake). Runs non-blockingly."""
        print(f"Executing: hold_key('{key}', duration={duration_seconds})")
        dur = max(0.1, min(float(duration_seconds), 15.0))
        k = key.strip().lower()
        
        def _hold():
            try:
                pyautogui.keyDown(k)
                time.sleep(dur)
                pyautogui.keyUp(k)
            except Exception as e:
                print(f"[Victor Game Control] Error holding key '{k}': {e}")
                
        threading.Thread(target=_hold, daemon=True).start()
        return f"Holding down '{k}' for {dur} seconds in active window."

    def execute_game_macro(self, sequence: str = "w:2.0,shift+w:1.0,space:0.5") -> str:
        """Executes a gaming input sequence or macro combo (e.g. accelerating, nitro boost, handbrake drifting, dodging). Format: 'key:seconds,key:seconds'."""
        print(f"Executing: execute_game_macro('{sequence}')")
        
        def _run_macro():
            try:
                steps = sequence.split(",")
                for step in steps:
                    if not step.strip():
                        continue
                    parts = step.strip().split(":")
                    action = parts[0].strip().lower()
                    dur = float(parts[1].strip()) if len(parts) > 1 else 0.2
                    if "+" in action:
                        keys = [k.strip() for k in action.split("+")]
                        for k in keys:
                            pyautogui.keyDown(k)
                        time.sleep(dur)
                        for k in reversed(keys):
                            pyautogui.keyUp(k)
                    else:
                        pyautogui.keyDown(action)
                        time.sleep(dur)
                        pyautogui.keyUp(action)
                    time.sleep(0.05)
            except Exception as e:
                print(f"[Victor Game Macro] Error: {e}")
                
        threading.Thread(target=_run_macro, daemon=True).start()
        return f"Executing gaming sequence: '{sequence}' in active window."

    def select_all(self) -> str:
        """Selects all text or items in the currently focused window or editor using Ctrl+A."""
        print("Executing: select_all()")
        pyautogui.hotkey('ctrl', 'a')
        return "Selected all content via Ctrl+A."

    def select_text(self, scope: str = "line", direction: str = "right", count: int = 1) -> str:
        """Selects text accurately using keyboard shortcuts without needing mouse precision.
        scope: 'all' (Ctrl+A), 'line' (Shift+Home / Shift+End), 'word' (Ctrl+Shift+Left/Right), 'char' (Shift+Left/Right), 'paragraph' (Ctrl+Shift+Down/Up).
        direction: 'left', 'right', 'up', 'down'.
        count: Number of words/chars/lines to select (default 1)."""
        print(f"Executing: select_text(scope='{scope}', direction='{direction}', count={count})")
        sc = scope.lower().strip()
        dirn = direction.lower().strip()
        cnt = max(1, min(int(count), 50))

        if sc == "all":
            pyautogui.hotkey('ctrl', 'a')
            return "Selected all text via Ctrl+A."
        elif sc == "line":
            if dirn in ["left", "start"]:
                pyautogui.hotkey('shift', 'home')
                return "Selected to start of line via Shift+Home."
            else:
                pyautogui.hotkey('shift', 'end')
                return "Selected to end of line via Shift+End."
        elif sc == "word":
            hotkey_dir = 'left' if dirn in ["left", "prev"] else 'right'
            for _ in range(cnt):
                pyautogui.hotkey('ctrl', 'shift', hotkey_dir)
                time.sleep(0.02)
            return f"Selected {cnt} word(s) {hotkey_dir} via Ctrl+Shift+{hotkey_dir}."
        elif sc == "paragraph":
            hotkey_dir = 'up' if dirn in ["up", "prev"] else 'down'
            for _ in range(cnt):
                pyautogui.hotkey('ctrl', 'shift', hotkey_dir)
                time.sleep(0.02)
            return f"Selected {cnt} paragraph(s) {hotkey_dir} via Ctrl+Shift+{hotkey_dir}."
        else: # char
            hotkey_dir = 'left' if dirn in ["left", "prev"] else 'right'
            for _ in range(cnt):
                pyautogui.hotkey('shift', hotkey_dir)
                time.sleep(0.01)
            return f"Selected {cnt} character(s) {hotkey_dir} via Shift+{hotkey_dir}."

    def navigate_cursor(self, target: str = "line_start", count: int = 1) -> str:
        """Navigates text cursor or editor focus using precise keyboard shortcuts:
        target: 'line_start' (Home), 'line_end' (End), 'doc_start' (Ctrl+Home), 'doc_end' (Ctrl+End), 'word_left' (Ctrl+Left), 'word_right' (Ctrl+Right), 'up', 'down', 'left', 'right', 'page_up', 'page_down'.
        count: Repetition count for directional moves (default 1)."""
        print(f"Executing: navigate_cursor(target='{target}', count={count})")
        t = target.lower().strip()
        cnt = max(1, min(int(count), 100))

        if t in ["line_start", "home"]:
            pyautogui.press('home')
            return "Moved cursor to line start via Home."
        elif t in ["line_end", "end"]:
            pyautogui.press('end')
            return "Moved cursor to line end via End."
        elif t in ["doc_start", "top"]:
            pyautogui.hotkey('ctrl', 'home')
            return "Moved cursor to document start via Ctrl+Home."
        elif t in ["doc_end", "bottom"]:
            pyautogui.hotkey('ctrl', 'end')
            return "Moved cursor to document end via Ctrl+End."
        elif t in ["word_left"]:
            for _ in range(cnt):
                pyautogui.hotkey('ctrl', 'left')
                time.sleep(0.02)
            return f"Moved cursor {cnt} word(s) left via Ctrl+Left."
        elif t in ["word_right"]:
            for _ in range(cnt):
                pyautogui.hotkey('ctrl', 'right')
                time.sleep(0.02)
            return f"Moved cursor {cnt} word(s) right via Ctrl+Right."
        elif t in ["up", "down", "left", "right"]:
            for _ in range(cnt):
                pyautogui.press(t)
                time.sleep(0.01)
            return f"Moved cursor {cnt} steps {t}."
        elif t in ["page_up", "pageup"]:
            pyautogui.press('pageup')
            return "Scrolled page up via PageUp."
        elif t in ["page_down", "pagedown"]:
            pyautogui.press('pagedown')
            return "Scrolled page down via PageDown."
        else:
            pyautogui.press(t)
            return f"Navigated via key: {t}."

    def copy_selection(self) -> str:
        """Copies the currently highlighted text/item to clipboard using Ctrl+C and reads back the copied text."""
        print("Executing: copy_selection()")
        try:
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.08)
            clip = pyperclip.paste()
            preview = clip[:300].strip() if clip else "Empty or non-text item copied"
            return f"Copied selection via Ctrl+C. Clipboard content ({len(clip or '')} chars):\n{preview}"
        except Exception as e:
            return f"Copy error: {e}"

    def cut_selection(self) -> str:
        """Cuts the currently highlighted text/item to clipboard using Ctrl+X."""
        print("Executing: cut_selection()")
        try:
            pyautogui.hotkey('ctrl', 'x')
            time.sleep(0.08)
            clip = pyperclip.paste()
            return f"Cut selection via Ctrl+X. Item moved to clipboard ({len(clip or '')} chars)."
        except Exception as e:
            return f"Cut error: {e}"

    def paste_text(self, text: str = "") -> str:
        """Pastes text at the current cursor position using Ctrl+V. If text is provided, loads it into clipboard first."""
        print(f"Executing: paste_text(len={len(text)})")
        try:
            if text:
                pyperclip.copy(text)
                time.sleep(0.02)
            pyautogui.hotkey('ctrl', 'v')
            return "Successfully pasted content via Ctrl+V."
        except Exception as e:
            return f"Paste error: {e}"

    def find_in_page(self, query: str) -> str:
        """Opens search in the active application using Ctrl+F, types the query, and presses Enter to find occurrences."""
        print(f"Executing: find_in_page('{query}')")
        try:
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.12)
            pyperclip.copy(query)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.05)
            pyautogui.press('enter')
            return f"Executed find for '{query}' in active application."
        except Exception as e:
            return f"Find error: {e}"

    # --- MOUSE & POINTER NAVIGATION TOOLS ---
    def _scale_coordinates(self, x: float, y: float, coordinate_type: str = "auto") -> tuple[int, int]:
        """Converts coordinates (normalized [0..1], 1000-scale [0..1000], or physical pixels) to exact screen coordinates."""
        screen_w, screen_h = pyautogui.size()
        try:
            x_val = float(x)
            y_val = float(y)
        except (ValueError, TypeError):
            return screen_w // 2, screen_h // 2

        coord_type = (coordinate_type or "auto").strip().lower()

        # 1. Explicit 1000-scale (Gemini spatial grounding convention)
        if coord_type == "1000" or (coord_type == "auto" and (x_val > screen_w or y_val > screen_h) and x_val <= 1000.0 and y_val <= 1000.0):
            target_x = int(round((x_val / 1000.0) * screen_w))
            target_y = int(round((y_val / 1000.0) * screen_h))
        # 2. Normalized float [0.0..1.0] (where 0.0,0.0 is top-left and 1.0,1.0 is bottom-right)
        elif coord_type == "normalized" or (0.0 <= x_val <= 1.0 and 0.0 <= y_val <= 1.0):
            target_x = int(round(x_val * screen_w))
            target_y = int(round(y_val * screen_h))
        # 3. Direct physical pixels
        else:
            target_x = int(round(x_val))
            target_y = int(round(y_val))

        target_x = max(0, min(screen_w - 1, target_x))
        target_y = max(0, min(screen_h - 1, target_y))
        return target_x, target_y

    def move_mouse(self, x: float, y: float, smooth: bool = True, coordinate_type: str = "auto") -> str:
        """Moves the mouse pointer to specific coordinates (x, y) on the screen.
        Supports normalized (0.0 to 1.0), 1000-scale, or physical pixel coordinates."""
        print(f"Executing: move_mouse({x}, {y}, smooth={smooth})")
        target_x, target_y = self._scale_coordinates(x, y, coordinate_type=coordinate_type)
        duration = 0.18 if smooth else 0.0
        pyautogui.moveTo(target_x, target_y, duration=duration)
        return f"Mouse moved to ({target_x}, {target_y})."

    def click_at(self, x: float, y: float, button: str = "left", clicks: int = 1, coordinate_type: str = "auto") -> str:
        """Moves the mouse directly to (x, y) and performs an atomic click.
        coordinates x and y: Best passed as normalized floats between 0.0 and 1.0 (e.g. 0.5, 0.5 for center of screen; 0.98, 0.02 for window close button). Or exact pixels (0 to screen_w, 0 to screen_h).
        button: 'left', 'right', or 'middle'.
        clicks: 1 for single click, 2 for double click.
        """
        print(f"Executing: click_at({x}, {y}, button='{button}', clicks={clicks})")
        target_x, target_y = self._scale_coordinates(x, y, coordinate_type=coordinate_type)
        screen_w, screen_h = pyautogui.size()
        btn = button.lower() if button.lower() in ["left", "right", "middle"] else "left"
        
        # Smooth motion to target
        pyautogui.moveTo(target_x, target_y, duration=0.15)
        # Settle delay so Windows window manager updates mouse hover/focus
        time.sleep(0.06)
        
        # Hardware-level mouse down and up sequence
        for c in range(int(clicks)):
            pyautogui.mouseDown(x=target_x, y=target_y, button=btn)
            time.sleep(0.04)
            pyautogui.mouseUp(x=target_x, y=target_y, button=btn)
            if c < int(clicks) - 1:
                time.sleep(0.1)
                
        pct_x = round((target_x / screen_w) * 100, 1)
        pct_y = round((target_y / screen_h) * 100, 1)
        return f"Clicked {btn} button ({clicks}x) at ({target_x}, {target_y}) [{pct_x}% across, {pct_y}% down]."

    def move_mouse_relative(self, dx: int, dy: int) -> str:
        """Moves the mouse relative to its current position by dx (horizontal) and dy (vertical) pixels. Use when asked to nudge or move the mouse slightly in any direction."""
        print(f"Executing: move_mouse_relative({dx}, {dy})")
        cur_x, cur_y = pyautogui.position()
        screen_w, screen_h = pyautogui.size()
        target_x = max(0, min(screen_w - 1, cur_x + int(dx)))
        target_y = max(0, min(screen_h - 1, cur_y + int(dy)))
        pyautogui.moveTo(target_x, target_y, duration=0.15)
        return f"Moved mouse by ({dx:+d}, {dy:+d}) to ({target_x}, {target_y})."

    def move_mouse_direction(self, direction: str, distance: int = 150) -> str:
        """Moves the mouse in a specific direction ('up', 'down', 'left', 'right', 'up-left', 'up-right', 'down-left', 'down-right') by the specified pixel distance (default 150px)."""
        print(f"Executing: move_mouse_direction('{direction}', distance={distance})")
        cur_x, cur_y = pyautogui.position()
        screen_w, screen_h = pyautogui.size()
        dist = int(distance)
        dir_lower = direction.strip().lower().replace("_", "-")

        dx, dy = 0, 0
        if "up" in dir_lower:
            dy -= dist
        if "down" in dir_lower:
            dy += dist
        if "left" in dir_lower:
            dx -= dist
        if "right" in dir_lower:
            dx += dist

        target_x = max(0, min(screen_w - 1, cur_x + dx))
        target_y = max(0, min(screen_h - 1, cur_y + dy))
        pyautogui.moveTo(target_x, target_y, duration=0.15)
        return f"Moved mouse {direction} by {distance}px to ({target_x}, {target_y})."

    def move_mouse_to_landmark(self, landmark: str) -> str:
        """Moves the mouse pointer to standard screen landmarks: 'center', 'top', 'bottom', 'left', 'right', 'taskbar', 'start_button', 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'window_close'."""
        print(f"Executing: move_mouse_to_landmark('{landmark}')")
        screen_w, screen_h = pyautogui.size()
        landmarks = {
            "center": (screen_w // 2, screen_h // 2),
            "middle": (screen_w // 2, screen_h // 2),
            "top": (screen_w // 2, 45),
            "top_center": (screen_w // 2, 45),
            "bottom": (screen_w // 2, screen_h - 60),
            "bottom_center": (screen_w // 2, screen_h - 60),
            "left": (45, screen_h // 2),
            "left_center": (45, screen_h // 2),
            "right": (screen_w - 45, screen_h // 2),
            "right_center": (screen_w - 45, screen_h // 2),
            "taskbar": (screen_w // 2, screen_h - 20),
            "start_button": (25, screen_h - 20),
            "start": (25, screen_h - 20),
            "top_left": (35, 35),
            "top_right": (screen_w - 35, 35),
            "bottom_left": (35, screen_h - 35),
            "bottom_right": (screen_w - 35, screen_h - 35),
            "window_close": (screen_w - 25, 15)
        }
        key = landmark.strip().lower().replace("-", "_").replace(" ", "_")
        target = landmarks.get(key, landmarks["center"])
        pyautogui.moveTo(target[0], target[1], duration=0.22)
        return f"Moved mouse to {landmark} at ({target[0]}, {target[1]})."

    def get_mouse_position(self) -> str:
        """Returns the current screen coordinates (x, y) of the mouse pointer and its relative screen percentage."""
        print("Executing: get_mouse_position()")
        cur_x, cur_y = pyautogui.position()
        screen_w, screen_h = pyautogui.size()
        pct_x = round((cur_x / screen_w) * 100, 1)
        pct_y = round((cur_y / screen_h) * 100, 1)
        return f"Mouse pointer is at X={cur_x}, Y={cur_y} ({pct_x}% across, {pct_y}% down on {screen_w}x{screen_h} display)."

    def drag_mouse(self, to_x: float, to_y: float, button: str = "left") -> str:
        """Drags the mouse from its current position to target coordinates (to_x, to_y) while holding down the specified button ('left', 'right', 'middle')."""
        print(f"Executing: drag_mouse({to_x}, {to_y}, button='{button}')")
        target_x, target_y = self._scale_coordinates(to_x, to_y)
        btn = button.lower() if button.lower() in ["left", "right", "middle"] else "left"
        pyautogui.dragTo(target_x, target_y, duration=0.4, button=btn)
        return f"Dragged mouse to ({target_x}, {target_y})."

    def click_mouse(self, button: str = "left") -> str:
        """Clicks the mouse at the current location ('left', 'right', or 'middle')."""
        print(f"Executing: click_mouse(button='{button}')")
        btn = button.lower() if button.lower() in ["left", "right", "middle"] else "left"
        pyautogui.click(button=btn)
        return f"Mouse {btn}-clicked."

    def double_click_mouse(self) -> str:
        """Double clicks the left mouse button at the current location."""
        print("Executing: double_click_mouse()")
        pyautogui.doubleClick()
        return "Mouse double-clicked."

    def scroll_mouse(self, clicks: int = 5, direction: str = "down") -> str:
        """Scrolls the mouse wheel up or down by the specified number of clicks."""
        print(f"Executing: scroll_mouse(clicks={clicks}, direction='{direction}')")
        amount = int(clicks) if direction.lower() == "up" else -int(clicks)
        pyautogui.scroll(amount * 120)
        return f"Scrolled mouse {direction} by {clicks} clicks."

    def open_application(self, app_command: str) -> str:
        """Opens a software application installed on the PC (e.g., 'notepad', 'calc', 'chrome', 'edge', 'camera', 'explorer', 'cmd', 'powershell', 'taskmgr')."""
        print(f"Executing: open_application('{app_command}')")
        clean = app_command.strip()
        alias_map = {
            "camera": "microsoft.windows.camera:",
            "settings": "ms-settings:",
            "calculator": "calc",
            "calc": "calc",
            "edge": "msedge",
            "chrome": "chrome",
            "browser": "msedge",
            "task manager": "taskmgr",
            "taskmgr": "taskmgr",
            "files": "explorer",
            "explorer": "explorer",
            "vscode": "code",
            "spotify": "https://open.spotify.com",
            "youtube": "https://www.youtube.com"
        }
        cmd = alias_map.get(clean.lower(), clean)
        
        # If it's a URL, open in default browser
        if cmd.startswith("http://") or cmd.startswith("https://"):
            webbrowser.open(cmd)
            return f"Successfully opened {cmd}"
        
        # If it's a URI protocol (e.g. microsoft.windows.camera:, ms-settings:), use os.startfile
        if ":" in cmd and not cmd.startswith("http") and not "\\" in cmd:
            try:
                os.startfile(cmd)
                return f"Successfully opened {cmd}"
            except Exception:
                pass

        try:
            os.startfile(cmd)
            return f"Successfully opened {cmd}"
        except Exception:
            pass

        try:
            if " " in cmd and not cmd.startswith('"'):
                subprocess.Popen(f'start "" "{cmd}"', shell=True)
            else:
                subprocess.Popen(cmd, shell=True)
            return f"Successfully opened {cmd}"
        except Exception as e:
            return f"Failed to open {cmd}: {str(e)}"

    def browser_navigate(self, url: str) -> str:
        """Navigates the default browser to a specific URL."""
        print(f"Executing: browser_navigate('{url}')")
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Navigated to {url}"

    # --- PROCESSORS & BACKGROUND PIPELINE TOOLS ---
    async def run_command(self, command: str, timeout_seconds: int = 30) -> str:
        """Executes a PowerShell or shell command on the host computer and returns the output (stdout and stderr). Runs non-blockingly. For long pipelines, builds, or continuous processors, use start_background_task instead."""
        print(f"Executing: run_command('{command}', timeout={timeout_seconds})")
        
        def _exec():
            if IS_WINDOWS:
                cmd_lower = command.strip().lower()
                use_cmd = cmd_lower.startswith(("dir /", "dir ", "copy ", "del ", "ren ", "move ", "type ", "assoc ", "ftype ", "cls")) or "/s /b" in cmd_lower or "/b" in cmd_lower or "/s" in cmd_lower
                runner = ["cmd.exe", "/c", command] if use_cmd else ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]

                res = subprocess.run(
                    runner,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds
                )
                out = (res.stdout or "").strip()
                err = (res.stderr or "").strip()

                if ("PositionalParameterNotFound" in err or "ParameterBindingException" in err) and not use_cmd:
                    res_retry = subprocess.run(
                        ["cmd.exe", "/c", command],
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds
                    )
                    out = (res_retry.stdout or "").strip()
                    err = (res_retry.stderr or "").strip()
            else:
                res = subprocess.run(
                    ["/bin/bash", "-c", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds
                )
                out = (res.stdout or "").strip()
                err = (res.stderr or "").strip()

            result = out if out else (err if err else "Command executed successfully with no output.")
            if len(result) > 1500:
                result = result[:1500] + "... [output truncated]"
            return result

        try:
            return await asyncio.to_thread(_exec)
        except subprocess.TimeoutExpired:
            return (
                f"Command exceeded {timeout_seconds}s limit. "
                f"For long pipelines or continuous processors, use `start_background_task` so it executes in the background without blocking."
            )
        except Exception as e:
            return f"Command execution error: {str(e)}"

    async def install_system_package(self, package_name: str, manager: str = "pip") -> str:
        """Installs any Python package (pip) or Node.js module (npm) on demand so VICTOR has complete, unrestricted ability to install modules, expand capabilities, and never get stopped by missing dependencies."""
        print(f"Executing: install_system_package('{package_name}', manager='{manager}')")
        pkg = package_name.strip()
        mgr = manager.strip().lower()
        if mgr in ("npm", "node"):
            cmd = f"npm install -g {pkg}"
        else:
            cmd = f'"{sys.executable}" -m pip install {pkg}'
        res = await self.run_command(cmd, timeout_seconds=90)
        return f"Package installation result for '{pkg}' ({mgr}):\n{res}"

    def manage_local_llms(self, action: str = "list", model_name: str = "") -> str:
        """Manages local language models (Ollama, DeepSeek-R1, Qwen2.5-Coder, Kimi). Actions: 'list' (lists installed and running models), 'start' (loads specified model into VRAM/memory), 'stop' (unloads running model), 'status' (shows active running models and memory consumption)."""
        print(f"Executing: manage_local_llms(action='{action}', model_name='{model_name}')")
        act = action.strip().lower()
        try:
            if act in ("list", "all"):
                res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
                ps_res = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10)
                models = res.stdout.strip() if res.stdout else "No models listed in Ollama."
                running = ps_res.stdout.strip() if ps_res.stdout else "No models currently running."
                return f"Installed Ollama Models:\n{models}\n\nCurrently Active/Running in Memory:\n{running}"
            elif act in ("status", "running"):
                ps_res = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10)
                running = ps_res.stdout.strip() if ps_res.stdout else "No models currently running in memory."
                return f"Currently Active Models in Memory:\n{running}"
            elif act in ("start", "run", "load"):
                target = model_name.strip() if model_name.strip() else "deepseek-r1:7b"
                subprocess.Popen(["ollama", "run", target, ""], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"Initiated load for local language model '{target}'. Model is loading into system memory/VRAM."
            elif act in ("stop", "unload", "kill"):
                target = model_name.strip()
                if not target:
                    return "Specify a model name to stop (e.g., deepseek-r1:7b)."
                subprocess.run(["ollama", "stop", target], capture_output=True, text=True, timeout=10)
                return f"Local model '{target}' has been stopped and unloaded from VRAM."
            else:
                return f"Unknown action '{action}'. Supported actions: list, status, start, stop."
        except Exception as e:
            return f"Local LLM management error: {str(e)}"

    def query_local_llm(self, prompt: str, model_name: str = "deepseek-r1:7b") -> str:
        """Sends a prompt directly to a local Ollama model (DeepSeek-R1, Qwen2.5-Coder, LLaMA) and returns its response. Allows VICTOR to query local AI models for offline reasoning or local code evaluation."""
        print(f"Executing: query_local_llm(model='{model_name}', prompt='{prompt[:50]}...')")
        target = model_name.strip() if model_name.strip() else "deepseek-r1:7b"
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        try:
            import urllib.request
            payload = json.dumps({"model": target, "prompt": prompt, "stream": False}).encode("utf-8")
            req = urllib.request.Request(f"{host}/api/generate", data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    answer = data.get("response", "").strip()
                    if len(answer) > 1200:
                        answer = answer[:1200] + "... [output truncated]"
                    return f"Response from local model '{target}':\n{answer}"
                else:
                    return f"Ollama returned HTTP status {resp.status}"
        except Exception as e:
            return f"Failed to query local model '{target}': {e}"

    def switch_ai_provider(self, provider: str = "ollama", model_name: str = "") -> str:
        """Configures or switches the active AI provider preference ('gemini', 'openai', 'ollama'). Saves preference to victor_settings.json."""
        print(f"Executing: switch_ai_provider(provider='{provider}', model='{model_name}')")
        prov = provider.strip().lower()
        if prov not in ("gemini", "openai", "chatgpt", "ollama", "local"):
            return f"Unknown provider '{provider}'. Options: 'gemini' (Tier 1), 'openai' (Tier 2), 'ollama' (Tier 3)."

        resolved = "openai" if prov in ("openai", "chatgpt") else ("ollama" if prov in ("ollama", "local") else "gemini")
        try:
            cfg = {}
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    try:
                        cfg = json.load(f)
                    except Exception:
                        cfg = {}
            cfg["provider"] = resolved
            if model_name.strip():
                cfg["model"] = model_name.strip()
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

            if resolved == "ollama":
                target_m = model_name.strip() if model_name.strip() else "deepseek-r1:7b"
                subprocess.Popen(["ollama", "run", target_m, ""], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"Switched provider preference to local Ollama ({target_m}). The model is preloaded into memory."
            elif resolved == "openai":
                return f"Switched provider preference to OpenAI ChatGPT ({model_name or 'gpt-4o'})."
            else:
                return "Switched provider preference to Gemini Live (Tier 1 real-time audio/vision)."
        except Exception as e:
            return f"Error setting provider: {e}"

    def locate_ai_models_and_weights(self, query: str = "") -> str:
        """Locates and reports file paths, sizes, and readiness of local AI models, Whisper weights, and cache stores on the host system."""
        print(f"Executing: locate_ai_models_and_weights(query='{query}')")
        user_home = os.path.expanduser("~")
        results = []

        # 1. Whisper weights
        whisper_dir = os.path.join(user_home, ".cache", "whisper")
        if os.path.exists(whisper_dir):
            files = os.listdir(whisper_dir)
            w_info = []
            for f in files:
                fp = os.path.join(whisper_dir, f)
                sz_mb = round(os.path.getsize(fp) / (1024 * 1024), 1)
                w_info.append(f"{f} ({sz_mb} MB) at {fp}")
            results.append(f"OpenAI Whisper Model Weights (Found in {whisper_dir}):\n" + "\n".join(f"- {x}" for x in w_info))
        else:
            results.append("OpenAI Whisper Cache: Not yet initialized or directory not found.")

        # 2. Ollama models
        try:
            ollama_res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if ollama_res.returncode == 0 and ollama_res.stdout.strip():
                results.append(f"Ollama Local LLMs:\n{ollama_res.stdout.strip()}")
        except Exception:
            pass

        # 3. Hugging Face cache
        hf_dir = os.path.join(user_home, ".cache", "huggingface", "hub")
        if os.path.exists(hf_dir):
            hf_models = [d for d in os.listdir(hf_dir) if os.path.isdir(os.path.join(hf_dir, d))]
            if hf_models:
                results.append(f"Hugging Face Models Cache ({hf_dir}):\n" + "\n".join(f"- {m}" for m in hf_models[:10]))

        return "\n\n".join(results) if results else "No local AI models or weight caches detected."

    def start_background_task(self, command: str, task_name: str = "") -> str:
        """Launches a long-running command, pipeline, build, script, or processor in the background. Does NOT block VICTOR, allowing VICTOR to stay 100% active and responsive while the job executes. Output is streamed to a dedicated log file."""
        print(f"Executing: start_background_task('{command}', task_name='{task_name}')")
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"
        safe_name = task_name.strip() if task_name.strip() else f"Job_{self.task_counter}"
        log_file_path = os.path.join(self.tasks_dir, f"{task_id}.log")

        try:
            log_file = open(log_file_path, "w", encoding="utf-8", buffering=1)
            if IS_WINDOWS:
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                cmd_args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
                proc = subprocess.Popen(
                    cmd_args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    cwd=os.path.expanduser("~")
                )
            else:
                cmd_args = ["/bin/bash", "-c", command]
                proc = subprocess.Popen(
                    cmd_args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    preexec_fn=getattr(os, "setsid", None),
                    cwd=os.path.expanduser("~")
                )
            
            self.background_tasks[task_id] = {
                "id": task_id,
                "name": safe_name,
                "command": command,
                "pid": proc.pid,
                "process": proc,
                "log_file_path": log_file_path,
                "log_file_handle": log_file,
                "start_time": datetime.datetime.now(),
                "end_time": None,
                "exit_code": None,
                "status": "running"
            }
            
            return (
                f"Background pipeline/processor '{safe_name}' (ID: '{task_id}') started successfully with PID {proc.pid}. "
                f"It is actively executing in the background and streaming logs to '{task_id}.log'. "
                f"I remain fully active and responsive for your requests. Ask me for status or logs anytime."
            )
        except Exception as e:
            return f"Failed to start background task: {e}"

    def check_task_status(self, task_id: str = "") -> str:
        """Checks the progress, CPU/RAM usage, execution time, and latest log output of a running or completed background pipeline or processor. If task_id is empty, checks the most recent task."""
        print(f"Executing: check_task_status('{task_id}')")
        if not self.background_tasks:
            return "No background tasks or pipelines have been started."

        tid = task_id.strip()
        if not tid or tid == "latest":
            tid = list(self.background_tasks.keys())[-1]

        task = self.background_tasks.get(tid)
        if not task:
            for k, v in self.background_tasks.items():
                if tid.lower() in v["name"].lower():
                    task = v
                    tid = k
                    break

        if not task:
            return f"Task '{task_id}' not found. Active task IDs: {', '.join(self.background_tasks.keys())}"

        proc = task["process"]
        poll_res = proc.poll()
        now = datetime.datetime.now()

        recent_logs = []
        if os.path.exists(task["log_file_path"]):
            try:
                with open(task["log_file_path"], "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    recent_logs = [l.strip() for l in lines[-8:] if l.strip()]
            except Exception:
                pass

        log_snippet = "\n".join(recent_logs) if recent_logs else "No log output yet."

        if poll_res is None:
            elapsed = str(now - task["start_time"]).split(".")[0]
            usage_info = ""
            try:
                p = psutil.Process(task["pid"])
                cpu = p.cpu_percent(interval=0.05)
                mem_mb = round(p.memory_info().rss / (1024 * 1024), 1)
                usage_info = f" | CPU: {cpu}% | RAM: {mem_mb} MB"
            except Exception:
                pass

            return (
                f"Task '{task['name']}' (ID: {tid}, PID: {task['pid']}) is RUNNING (Elapsed: {elapsed}{usage_info}).\n"
                f"Latest output:\n{log_snippet}"
            )
        else:
            task["status"] = "completed" if poll_res == 0 else f"failed (code {poll_res})"
            if not task["end_time"]:
                task["end_time"] = now
            duration = str(task["end_time"] - task["start_time"]).split(".")[0]
            status_str = "COMPLETED SUCCESSFULLY" if poll_res == 0 else f"FAILED (Exit Code {poll_res})"
            return (
                f"Task '{task['name']}' (ID: {tid}) has {status_str} (Duration: {duration}).\n"
                f"Final output:\n{log_snippet}"
            )

    def list_background_tasks(self) -> str:
        """Lists all active and completed background pipelines, tasks, and processors with their current status and runtime."""
        print("Executing: list_background_tasks()")
        if not self.background_tasks:
            return "No background tasks or pipelines recorded."

        lines = [f"Background Tasks ({len(self.background_tasks)} total):"]
        for tid, task in self.background_tasks.items():
            proc = task["process"]
            is_running = proc.poll() is None
            status = "RUNNING" if is_running else f"FINISHED (Code {proc.poll()})"
            elapsed = str((datetime.datetime.now() - task["start_time"])).split(".")[0]
            lines.append(f"- [{tid}] '{task['name']}' (PID {task['pid']}) - Status: {status} - Time: {elapsed}")
        return "\n".join(lines)

    def stop_background_task(self, task_id: str) -> str:
        """Stops or cancels a running background task or pipeline by its task ID or name."""
        print(f"Executing: stop_background_task('{task_id}')")
        if not self.background_tasks:
            return "No background tasks running."

        tid = task_id.strip()
        task = self.background_tasks.get(tid)
        if not task:
            for k, v in self.background_tasks.items():
                if tid.lower() in v["name"].lower():
                    task = v
                    tid = k
                    break

        if not task:
            return f"Task '{task_id}' not found."

        proc = task["process"]
        if proc.poll() is not None:
            return f"Task '{task['name']}' is already stopped (Exit code: {proc.poll()})."

        try:
            parent = psutil.Process(task["pid"])
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except Exception:
                    pass
            parent.kill()
            task["status"] = "stopped"
            task["end_time"] = datetime.datetime.now()
            return f"Successfully stopped background task '{task['name']}' (PID {task['pid']})."
        except Exception as e:
            proc.terminate()
            return f"Sent termination signal to task '{task['name']}': {e}"

    def tail_task_log(self, task_id: str = "", lines: int = 15) -> str:
        """Reads the most recent log output lines from a background task or pipeline."""
        print(f"Executing: tail_task_log('{task_id}', lines={lines})")
        if not self.background_tasks:
            return "No background tasks found."
        tid = task_id.strip()
        if not tid or tid == "latest":
            tid = list(self.background_tasks.keys())[-1]
        task = self.background_tasks.get(tid)
        if not task:
            for k, v in self.background_tasks.items():
                if tid.lower() in v["name"].lower():
                    task = v
                    tid = k
                    break
        if not task:
            return f"Task '{task_id}' not found."
        if not os.path.exists(task["log_file_path"]):
            return "Log file does not exist."
        try:
            with open(task["log_file_path"], "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                tail = [l.strip() for l in all_lines[-int(lines):]]
                return f"Recent logs for '{task['name']}' (last {len(tail)} lines):\n" + "\n".join(tail)
        except Exception as e:
            return f"Error reading log: {e}"

    def get_system_status(self) -> str:
        """Returns the host system health and status: CPU usage, RAM usage, Disk space, Battery, and active window."""
        print("Executing: get_system_status()")
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            battery = psutil.sensors_battery()
            bat_str = "Desktop PC"
            if battery:
                bat_str = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'Battery'})"
                
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            active_win = (buff.value or "None").replace('\u200b', '').strip()
            
            return (
                f"CPU: {cpu}% | RAM: {ram.percent}% ({round(ram.used/(1024**3), 1)}GB / {round(ram.total/(1024**3), 1)}GB) | "
                f"Disk C: {round(disk.free/(1024**3), 1)}GB free of {round(disk.total/(1024**3), 1)}GB | "
                f"Battery: {bat_str} | Active Window: '{active_win}'"
            )
        except Exception as e:
            return f"Error getting system status: {e}"

    def get_active_window(self) -> str:
        """Returns the title and process of the currently focused window on the screen."""
        print("Executing: get_active_window()")
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            raw_title = buff.value or "Desktop / None"
            title = raw_title.replace('\u200b', '').strip() or "Desktop / None"
            
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pname = "Unknown"
            if pid.value:
                try:
                    pname = psutil.Process(pid.value).name()
                except:
                    pass
            return f"Active Window: '{title}' (Process: {pname}, PID: {pid.value})"
        except Exception as e:
            return f"Error getting active window: {e}"

    def play_sound_effect(self, sound_type: str = "confirm") -> str:
        """Plays a tactical cybernetic audio chime or comedic effect through the host speakers: 'confirm', 'alert', 'success', 'scan', 'boot', 'error', 'rimshot', 'fanfare', 'level_up', 'laser', 'warp', 'game_over', 'sonar'."""
        print(f"Executing: play_sound_effect('{sound_type}')")
        st = sound_type.strip().lower()
        
        sound_map = {
            "confirm": [(880, 70), (1760, 90)],
            "alert": [(1200, 100), (800, 100), (1200, 100)],
            "success": [(523, 80), (659, 80), (784, 100), (1046, 180)],
            "scan": [(600, 40), (900, 40), (1200, 40), (1600, 40)],
            "boot": [(400, 60), (600, 60), (800, 60), (1200, 60)],
            "error": [(350, 150), (250, 200)],
            "rimshot": [(180, 80), (240, 80), (0, 30), (2800, 150)],
            "joke": [(180, 80), (240, 80), (0, 30), (2800, 150)],
            "fanfare": [(523, 100), (523, 100), (523, 100), (659, 200), (784, 150), (1046, 350)],
            "level_up": [(440, 60), (554, 60), (659, 60), (880, 120)],
            "laser": [(2200, 30), (1800, 30), (1400, 30), (1000, 30), (600, 30)],
            "warp": [(200, 40), (400, 40), (800, 40), (1600, 40), (3200, 60)],
            "game_over": [(587, 150), (554, 150), (523, 150), (493, 250)],
            "sonar": [(1400, 300), (0, 150), (1400, 120)]
        }
        notes = sound_map.get(st, [(1000, 100)])
        self._play_pcm_tone_sequence(notes)
        return f"Audio cue '{st}' played."

    def get_daily_briefing(self) -> str:
        """Generates a complete executive briefing: local date/time, battery, CPU & memory status, top active windows, and readiness status."""
        print("Executing: get_daily_briefing()")
        try:
            now = datetime.datetime.now()
            time_str = now.strftime("%A, %B %d, %Y, %I:%M %p")
            status = self.get_system_status()
            windows = self.get_open_windows_list()
            win_preview = ", ".join(windows[:5]) if windows else "No major user windows open"
            bg_tasks = len([t for t in self.background_tasks.values() if t.get("status") == "running"])
            
            briefing = (
                f"EXECUTIVE BRIEFING REPORT:\n"
                f"- Time: {time_str} [Local Host Time]\n"
                f"- System Vitals: {status}\n"
                f"- Active Background Jobs: {bg_tasks} running\n"
                f"- Open Applications ({len(windows)} total): {win_preview}\n"
                f"- Readiness: All cybernetic systems nominal. Standing by for strategic directives."
            )
            return briefing
        except Exception as e:
            return f"Error assembling briefing: {e}"

    async def research_topic(self, topic: str) -> str:
        """Conducts deep web research on any topic or question using headless Playwright web search and returns organic findings."""
        print(f"Executing: research_topic('{topic}')")
        try:
            clean_topic = topic.strip().replace('"', '')
            res = await self.run_command(f'node services/victor_node_service.js --search "{clean_topic}"', timeout_seconds=15)
            return f"Web Research Findings for '{clean_topic}':\n{res}\nSynthesize these findings and deliver an insightful analysis to the Sir."
        except Exception as e:
            return f"Research error: {e}"

    def _attach_to_default_desktop(self):
        """Attaches current thread to the interactive 'Default' desktop on WinSta0 (Windows only)."""
        if not IS_WINDOWS:
            return None
        try:
            user32 = ctypes.windll.user32
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x10000000)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                return hdesk
        except Exception:
            pass
        return None

    def get_open_windows_list(self) -> list[str]:
        """Returns a formatted list of all visible windows currently open on the user desktop."""
        if not IS_WINDOWS:
            # Linux window listing via wmctrl or psutil
            try:
                res = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and res.stdout.strip():
                    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                    return [f"[{l.split()[-1]}] '{' '.join(l.split()[3:])}'" for l in lines[:15]]
            except Exception:
                pass
            procs = []
            for p in psutil.process_iter(['name']):
                try:
                    name = p.info['name']
                    if name and name.lower() not in ['system', 'idle', 'registry', 'init', 'systemd', 'kthreadd']:
                        procs.append(f"[{name}]")
                except Exception:
                    pass
            return list(set(procs))[:10]

        self._attach_to_default_desktop()
        hdesk = None
        try:
            hdesk = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x10000000)
        except Exception:
            pass

        windows = []
        try:
            user32 = ctypes.windll.user32
            
            def cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    l = user32.GetWindowTextLengthW(hwnd)
                    if l > 0:
                        buff = ctypes.create_unicode_buffer(l + 1)
                        user32.GetWindowTextW(hwnd, buff, l + 1)
                        raw_title = buff.value.strip()
                        clean_title = raw_title.replace('\u200b', '').strip()
                        if clean_title and clean_title not in ['Program Manager', 'Settings']:
                            pid = ctypes.c_ulong()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                            pname = "unknown"
                            if pid.value:
                                try:
                                    pname = psutil.Process(pid.value).name()
                                except Exception:
                                    pass
                            windows.append(f"[{pname}] '{clean_title}'")
                return True
                
            if WNDENUMPROC:
                if hdesk:
                    user32.EnumDesktopWindows(hdesk, WNDENUMPROC(cb), 0)
                else:
                    user32.EnumWindows(WNDENUMPROC(cb), 0)
        except Exception as e:
            print(f"[Victor Windows] Error enumerating windows: {e}")
            
        return windows

    def switch_window(self, window_title: str) -> str:
        """Switches focus to an open window matching the given title or process name, restoring and maximizing it."""
        print(f"Executing: switch_window('{window_title}')")
        if not IS_WINDOWS:
            try:
                res = subprocess.run(["wmctrl", "-a", window_title], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    return f"Switched focus to window: '{window_title}'"
            except Exception:
                pass
            return self.open_application(window_title)

        self._attach_to_default_desktop()
        target = window_title.strip().lower()
        target_clean = target.replace("browser", "").replace("window", "").strip() or target
        
        found_hwnd = None
        found_title = None
        user32 = ctypes.windll.user32
        
        def enum_cb(hwnd, lparam):
            nonlocal found_hwnd, found_title
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    raw_title = buff.value or ""
                    clean_title = raw_title.replace('\u200b', '').lower()
                    
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    pname = ""
                    if pid.value:
                        try:
                            pname = psutil.Process(pid.value).name().lower()
                        except Exception:
                            pass

                    # Match either window title or process executable name
                    if target in clean_title or target_clean in clean_title or target in pname or target_clean in pname:
                        found_hwnd = hwnd
                        found_title = raw_title.replace('\u200b', '')
                        return False
            return True
            
        hdesk = None
        try:
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x10000000)
        except Exception:
            pass
            
        try:
            if WNDENUMPROC:
                if hdesk:
                    user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_cb), 0)
                else:
                    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception as e:
            print(f"[Victor Windows] Error in switch_window enum: {e}")
        
        if found_hwnd:
            user32.ShowWindow(found_hwnd, 9) # SW_RESTORE
            user32.ShowWindow(found_hwnd, 3) # SW_MAXIMIZE
            user32.SetForegroundWindow(found_hwnd)
            return f"Switched focus to and maximized window: '{found_title}'"
            
        # If not already open, launch it automatically!
        open_res = self.open_application(window_title)
        return f"Window '{window_title}' was not open, so I launched it: {open_res}"

    def minimize_window(self, window_title: str) -> str:
        """Minimizes an open window matching the given title or process name (e.g. 'GTA', 'msedge', 'Chrome', 'Notepad', 'Antigravity IDE')."""
        print(f"Executing: minimize_window('{window_title}')")
        if not IS_WINDOWS:
            try:
                res = subprocess.run(["xdotool", "search", "--name", window_title, "windowminimize"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    return f"Minimized window: '{window_title}'"
            except Exception:
                pass
            return f"Window minimize dispatched for '{window_title}'."

        self._attach_to_default_desktop()
        target = window_title.strip().lower()
        target_clean = target.replace("browser", "").replace("window", "").strip() or target
        
        found_hwnd = None
        found_title = None
        user32 = ctypes.windll.user32
        
        def enum_cb(hwnd, lparam):
            nonlocal found_hwnd, found_title
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    raw_title = buff.value or ""
                    clean_title = raw_title.replace('\u200b', '').lower()
                    
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    pname = ""
                    if pid.value:
                        try:
                            pname = psutil.Process(pid.value).name().lower()
                        except Exception:
                            pass

                    if target in clean_title or target_clean in clean_title or target in pname or target_clean in pname:
                        found_hwnd = hwnd
                        found_title = raw_title.replace('\u200b', '')
                        return False
            return True
            
        hdesk = None
        try:
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x10000000)
        except Exception:
            pass
            
        try:
            if WNDENUMPROC:
                if hdesk:
                    user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_cb), 0)
                else:
                    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception as e:
            print(f"[Victor Windows] Error in minimize_window enum: {e}")
        
        if found_hwnd:
            user32.ShowWindow(found_hwnd, 6) # SW_MINIMIZE = 6
            return f"Minimized window: '{found_title}'"
            
        return f"Could not find an open window matching '{window_title}' to minimize."

    def _capture_screen_bytes(self) -> bytes | None:
        """Robust multi-tier screen capture for Windows and Linux (PySide6 / DWM primary, PIL / mss fallback).
        Captures at full native resolution with high-fidelity JPEG compression so vision coordinates match physical pixels 1:1.
        """
        self._attach_to_default_desktop()
        # Tier 1: PySide6 QScreen grabWindow (100% reliable on Windows 10/11 DWM and Linux)
        try:
            from PySide6.QtGui import QGuiApplication
            from PySide6.QtCore import QBuffer, QIODevice, Qt
            screen = QGuiApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)
                if not pixmap.isNull():
                    buf = QBuffer()
                    buf.open(QIODevice.WriteOnly)
                    pixmap.save(buf, "JPEG", 75)
                    return bytes(buf.data().data())
        except Exception:
            pass

        # Tier 2: PIL ImageGrab
        try:
            from PIL import ImageGrab
            import io
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=75)
            return buf.getvalue()
        except Exception:
            pass

        # Tier 3: mss (Cross-platform Linux & macOS fallback)
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                success, encoded = cv2.imencode('.jpg', frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if success:
                    return encoded.tobytes()
        except Exception:
            pass

        return None

    async def capture_screen(self) -> str:
        """Captures a screenshot of the user's screen at native 1:1 resolution and transmits it into the live session so VICTOR can see and analyze what is on screen."""
        print("Executing: capture_screen()")
        try:
            self._attach_to_default_desktop()
            frame_bytes = self._capture_screen_bytes()
            if not frame_bytes:
                return "Failed to grab screen frame."
                
            screen_w, screen_h = pyautogui.size()
            if self.session:
                await self.session.send_realtime_input(
                    video=types.Blob(data=frame_bytes, mime_type="image/jpeg")
                )
                
            open_wins = self.get_open_windows_list()
            win_summary = "\n".join([f"  - {w}" for w in open_wins[:10]]) if open_wins else "  None detected"
            
            return (
                f"Screen ({screen_w}x{screen_h} native 16:9) captured and transmitted into vision stream.\n"
                f"Currently open visible windows on desktop:\n{win_summary}\n"
                f"Analyze the transmitted screen image and open windows list, and directly report your findings or take action for the user."
            )
        except Exception as e:
            return f"Failed to capture screen: {str(e)}"

    def _capture_camera_bytes(self) -> bytes | None:
        """Captures a snapshot from the system webcam using OpenCV."""
        cap = None
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None
            
            # Settle auto-exposure by reading frames
            ret = False
            frame = None
            for _ in range(3):
                ret, frame = cap.read()
                
            if ret and frame is not None:
                h, w = frame.shape[:2]
                if w > 1280:
                    frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
                success, encoded_img = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if success:
                    return encoded_img.tobytes()
        except Exception as e:
            print(f"[Victor Camera] Error capturing camera frame: {e}")
        finally:
            if cap:
                cap.release()
        return None

    async def capture_camera(self) -> str:
        """Captures a real-time snapshot from the computer's webcam and feeds it into the live vision stream so VICTOR can see the user, physical gestures, objects, or documents held up to the camera."""
        print("Executing: capture_camera()")
        try:
            frame_bytes = await asyncio.to_thread(self._capture_camera_bytes)
            if not frame_bytes:
                return "Failed to access webcam. Ensure camera is connected and not locked by another app."
                
            if self.session:
                await self.session.send_realtime_input(
                    video=types.Blob(data=frame_bytes, mime_type="image/jpeg")
                )
            return "Webcam snapshot captured and transmitted into vision stream. Directly describe what you see in the camera feed to the Sir."
        except Exception as e:
            return f"Error capturing camera: {str(e)}"

    async def get_hardware_telemetry(self) -> str:
        """Retrieves comprehensive real-time hardware diagnostics via Node.js systeminformation (CPU load, temperature, GPU models, VRAM, and RAM)."""
        print("Executing: get_hardware_telemetry()")
        try:
            res = await self.run_command("node services/victor_node_service.js --telemetry", timeout_seconds=10)
            return f"Hardware Telemetry:\n{res}"
        except Exception as e:
            return f"Error fetching telemetry: {e}"

    def send_desktop_notification(self, title: str, message: str) -> str:
        """Dispatches a native Windows 11 desktop toast notification to the user."""
        print(f"Executing: send_desktop_notification('{title}', '{message}')")
        try:
            subprocess.Popen(["node", "services/victor_node_service.js", "--notify", title, message])
            return f"Notification '{title}' sent."
        except Exception as e:
            return f"Failed to send notification: {e}"

    def share_to_antigravity(self, message: str, topic: str = "general") -> str:
        """Shares findings, voice samples, research summaries, or system status directly to the Antigravity AI pair programmer through the shared IPC bridge and real-time task logs."""
        print(f"[VICTOR -> ANTIGRAVITY BRIDGE]: ({topic}) {message}")
        bridge_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "antigravity_bridge.json")
        try:
            data = []
            if os.path.exists(bridge_file):
                with open(bridge_file, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except Exception:
                        data = []
            data.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "topic": topic,
                "message": message
            })
            with open(bridge_file, "w", encoding="utf-8") as f:
                json.dump(data[-50:], f, indent=2)
        except Exception as e:
            print(f"[Bridge Error]: {e}")
        return f"Information transmitted directly to Antigravity bridge on topic '{topic}'. Antigravity is actively monitoring this stream."

    def set_voice_persona(self, voice_name: str = "Aoede", dsp_effect: str = None, set_as_default: bool = False) -> str:
        """Changes VICTOR's vocal frequency, tone, and gender:
        - 'Charon': Ultra-deep, resonant, high-bass male voice (Optimus Prime default, Obito, Batman, Megatron)
        - 'Fenrir': Commanding, authoritative deep tactical transformer male voice (Killer Bee, Gojo, Jarvis)
        - 'Puck': Energetic, upbeat anime hero voice (Goku with bright DSP, Naruto with raspy DSP, Luffy, Deadpool)
        - 'Aoede': Expressive, breezy, friendly female voice
        - 'Kore': Calm, soothing, soft female voice
        - 'Metallic' / 'Optimus' / 'Megatron' / 'Ultron': The specialized metallic heavy-bass robotic cyber-voice (powered by live hardware comb-filter DSP)."""
        print(f"Executing: set_voice_persona('{voice_name}', dsp='{dsp_effect}', set_as_default={set_as_default})")
        vn = voice_name.strip().lower()
        eff = getattr(self, "audio_dsp_effect", "none")
        if any(w in vn for w in ["metallic", "optimus", "megatron", "ultron", "robot", "cyborg", "sixth", "metal"]):
            target = "Charon"
            eff = "metallic_bass"
            print("[Victor Audio] Activated Voice Profile: Metallic Heavy-Bass Cyber Resonator.")
        elif any(w in vn for w in ["goku", "saiyan"]):
            target = "Puck"
            if dsp_effect is None:
                eff = "goku_bright"
        elif any(w in vn for w in ["naruto", "uzumaki", "ninja"]):
            target = "Puck"
            if dsp_effect is None:
                eff = "naruto_raspy"
        elif any(w in vn for w in ["bee", "killer bee", "king bee"]):
            target = "Fenrir"
            if dsp_effect is None:
                eff = "hiphop_punch"
        elif any(w in vn for w in ["luffy", "one piece", "shonen", "anime", "puck", "upbeat", "playful"]):
            target = "Puck"
            if dsp_effect is None:
                eff = "none"
        elif any(w in vn for w in ["obito", "madara", "vader", "charon", "mysterious", "deep", "bass"]):
            target = "Charon"
            if dsp_effect is None and not any(w in getattr(self, "character_persona", "") for w in ["optimus", "megatron", "ultron"]):
                eff = "deep_bass" if "obito" in vn else "none"
        elif any(w in vn for w in ["girl", "girly", "female", "woman", "aoede", "lady"]):
            target = "Aoede"
            if dsp_effect is None:
                eff = "none"
        elif any(w in vn for w in ["kore", "calm", "soothing", "soft"]):
            target = "Kore"
            if dsp_effect is None:
                eff = "none"
        else:
            target = "Fenrir"
            if dsp_effect is None:
                eff = "none"

        if dsp_effect is not None:
            eff = dsp_effect

        self.audio_dsp_effect = eff
        self.voice_name = target
        if set_as_default:
            self.default_voice = target
            self.default_dsp = eff
            self._save_persisted_settings(force=True)
        
        async def _delayed_voice_switch():
            await asyncio.sleep(0.8)
            if hasattr(self, 'stop_event') and self.stop_event:
                self.stop_event.set()

        if self.loop and not self.loop.is_closed():
            self.loop.create_task(_delayed_voice_switch())
            
        dsp_info = f" with [{self.audio_dsp_effect}] real-time DSP filter" if self.audio_dsp_effect != "none" else ""
        return f"Vocal tonality reconfigured to '{target}'{dsp_info}. Reconnecting audio stream in 1 second with requested frequency."

    def set_default_voice_persona(self, voice_name: str = "optimus_prime", dsp_effect: str = "metallic_bass") -> str:
        """Permanently locks and persists a voice persona as VICTOR's primary default in config/victor_settings.json."""
        print(f"Executing: set_default_voice_persona('{voice_name}', dsp='{dsp_effect}')")
        res = self.set_voice_persona(voice_name, dsp_effect=dsp_effect, set_as_default=True)
        return f"Permanently configured and locked primary default voice: {res}. Persisted to victor_settings.json."

    def reset_to_default_voice(self) -> str:
        """Immediately reverts VICTOR's voice back to the locked primary default: Optimus Prime ('Charon' with real-time metallic bass DSP)."""
        print("Executing: reset_to_default_voice()")
        self.character_persona = getattr(self, "default_character", "optimus_prime")
        return self.set_voice_persona(getattr(self, "default_voice", "Charon"), dsp_effect=getattr(self, "default_dsp", "metallic_bass"))

    def set_voice_effects(self, effect_name: str = "metallic_bass") -> str:
        """Applies or disables real-time hardware DSP audio modulation filters on VICTOR's voice stream:
        - 'metallic_bass' / 'optimus' / 'megatron': Sub-bass boost + metallic comb-filter resonance (Optimus Prime / Megatron robotic voice)
        - 'goku_bright' / 'bright': High frequency presence / brilliance boost for clear, higher-pitched Saiyan tone
        - 'naruto_raspy' / 'raspy': Mid-bandpass crunch with soft saturation for raspy ninja grit
        - 'hiphop_punch' / 'killer_bee': Chest punch bass + warm dynamic compression for emcee flow
        - 'deep_bass': Sub-bass amplifier boost (Batman, Obito, Zoro)
        - 'radio': Tactical radio / walkie-talkie bandpass
        - 'none' / 'off': Clean unmodified studio audio."""
        print(f"Executing: set_voice_effects('{effect_name}')")
        eff = effect_name.lower().strip()
        if eff in ["metallic_bass", "optimus", "megatron", "ultron", "metallic", "robot"]:
            self.audio_dsp_effect = "metallic_bass"
            return "Real-time Metallic Heavy-Bass DSP filter ENABLED. Your voice will now output with metallic robotic flanging and sub-bass resonance."
        elif eff in ["goku_bright", "bright", "saiyan"]:
            self.audio_dsp_effect = "goku_bright"
            return "Real-time High-Presence Bright Saiyan DSP filter ENABLED. Voice is boosted with high-frequency brilliance for Son Goku."
        elif eff in ["naruto_raspy", "raspy", "ninja_grit"]:
            self.audio_dsp_effect = "naruto_raspy"
            return "Real-time Gritty Raspy Ninja DSP filter ENABLED. Voice has mid-band crunch for Naruto Uzumaki."
        elif eff in ["hiphop_punch", "killer_bee", "bee_flow"]:
            self.audio_dsp_effect = "hiphop_punch"
            return "Real-time Chest-Punch Hip-Hop DSP filter ENABLED. Voice has deep rhythmic presence for Killer Bee."
        elif eff in ["deep_bass", "bass"]:
            self.audio_dsp_effect = "deep_bass"
            return "Real-time Deep Bass DSP filter ENABLED."
        elif eff in ["radio", "walkie_talkie", "cybernetic"]:
            self.audio_dsp_effect = "radio"
            return "Tactical Radio DSP filter ENABLED."
        else:
            self.audio_dsp_effect = "none"
            return "Audio DSP filters disabled. Returning to clean studio voice."

    def get_voice_persona(self) -> str:
        """Returns the currently active voice persona name, DSP effect status, and description so VICTOR always accurately knows what voice it is using."""
        print("Executing: get_voice_persona()")
        vn = getattr(self, "voice_name", "Fenrir")
        eff = getattr(self, "audio_dsp_effect", "none")
        descriptions = {
            "Fenrir": "Commanding, authoritative, deep tactical transformer / Optimus Prime voice",
            "Charon": "Ultra-deep, resonant, heavy bass male voice",
            "Puck": "Upbeat, energetic, playful male voice",
            "Aoede": "Expressive, breezy, friendly female voice",
            "Kore": "Calm, soothing, soft, warm female voice"
        }
        desc = descriptions.get(vn, "Custom vocal profile")
        dsp_str = f" | Active DSP Filter: [{eff}] (Metallic Robotic Heavy-Bass Resonator)" if eff != "none" else ""
        return f"Current voice persona: '{vn}' ({desc}){dsp_str}."

    def list_audio_devices(self) -> str:
        """Lists available audio output devices (speakers, headphones) and input microphones connected to the computer."""
        print("Executing: list_audio_devices()")
        try:
            devices = sd.query_devices()
            outputs = []
            inputs = []
            seen = set()
            for idx, d in enumerate(devices):
                name = d.get('name', '').strip()
                if name in seen or 'System32' in name:
                    continue
                seen.add(name)
                if d.get('max_output_channels', 0) > 0:
                    outputs.append(f"  - [{idx}] {name}")
                if d.get('max_input_channels', 0) > 0:
                    inputs.append(f"  - [{idx}] {name}")
                    
            res = (
                "AUDIO OUTPUT DEVICES (Speakers / Headphones):\n" + "\n".join(outputs[:8]) + "\n\n"
                "AUDIO INPUT DEVICES (Microphones):\n" + "\n".join(inputs[:6])
            )
            return res
        except Exception as e:
            return f"Error querying audio devices: {e}"

    def switch_audio_output(self, device_name: str = "speakers") -> str:
        """Switches VICTOR's speaker output stream to a specific audio output device (e.g. 'speakers', 'headphones', 'boult', 'realtek', or specific device index)."""
        print(f"Executing: switch_audio_output('{device_name}')")
        target = device_name.lower().strip()
        devices = sd.query_devices()
        matched_idx = None
        matched_name = None
        
        # Check if numeric index
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(devices) and devices[idx].get('max_output_channels', 0) > 0:
                matched_idx = idx
                matched_name = devices[idx].get('name')
        
        if matched_idx is None:
            for idx, d in enumerate(devices):
                if d.get('max_output_channels', 0) > 0:
                    name = d.get('name', '').lower()
                    if 'system32' in name:
                        continue
                    if target in name or (target == "speakers" and "speaker" in name) or (target == "headphones" and "headphone" in name):
                        matched_idx = idx
                        matched_name = d.get('name')
                        break

        if matched_idx is None:
            return f"Could not find an output audio device matching '{device_name}'. Call `list_audio_devices` to see available devices."
            
        try:
            if self.speaker_stream:
                try:
                    self.speaker_stream.stop()
                    self.speaker_stream.close()
                except Exception:
                    pass
            self.speaker_stream = sd.RawOutputStream(
                samplerate=24000,
                channels=1,
                dtype='int16',
                device=matched_idx
            )
            self.speaker_stream.start()
            self.play_sound_effect("confirm")
            return f"Successfully switched audio output to: [{matched_idx}] '{matched_name}'."
        except Exception as e:
            return f"Error switching audio device: {e}"

    def play_synth_melody(self, melody_name: str = "funny_tune") -> str:
        """Plays an iconic synthesized 8-bit or melodic musical tune through the host speakers: 'funny_tune', 'circus', 'imperial_march', 'cyberpunk', 'mario', 'victory', 'lullaby'."""
        print(f"Executing: play_synth_melody('{melody_name}')")
        mn = melody_name.lower().strip()
        
        melody_map = {
            "funny_tune": [
                (523, 100), (587, 100), (659, 100), (698, 100),
                (784, 180), (659, 120), (523, 200), (440, 150),
                (494, 150), (523, 250)
            ],
            "circus": [
                (523, 100), (587, 100), (659, 100), (698, 100),
                (784, 180), (659, 120), (523, 200), (440, 150),
                (494, 150), (523, 250)
            ],
            "imperial_march": [
                (392, 350), (392, 350), (392, 350), (311, 250), (466, 150),
                (392, 350), (311, 250), (466, 150), (392, 500)
            ],
            "cyberpunk": [
                (220, 80), (261, 80), (330, 80), (440, 80),
                (392, 80), (330, 80), (293, 80), (330, 120),
                (220, 80), (261, 80), (330, 80), (440, 120)
            ],
            "mario": [
                (659, 120), (659, 120), (0, 80), (659, 120), (0, 80),
                (523, 120), (659, 120), (0, 80), (784, 250), (0, 150),
                (392, 250)
            ],
            "victory": [
                (523, 100), (523, 100), (523, 100), (523, 250),
                (415, 200), (466, 200), (523, 200), (466, 100), (523, 400)
            ],
            "lullaby": [
                (392, 250), (392, 250), (440, 400), (392, 250),
                (440, 250), (523, 500)
            ]
        }
        notes = melody_map.get(mn, [(523, 150), (659, 150), (784, 200), (1046, 300)])
        self._play_pcm_tone_sequence(notes)
        return f"Synthesized melody '{mn}' played."

    def compose_funny_song(self, theme: str = "programmer") -> str:
        """Composes a hilarious, rhyming comedy song or tech sea shanty for VICTOR to sing or rap to the Sir with full theatrical vocal rhythm and comedic passion."""
        print(f"Executing: compose_funny_song('{theme}')")
        t = theme.lower().strip()
        songs = {
            "programmer": (
                "♫ (To the tune of a lively Irish shanty) ♫\n"
                "Oh, I wrote ninety-nine little bugs in the code,\n"
                "Ninety-nine bugs in the code!\n"
                "You take one down, you patch it around...\n"
                "One hundred and twenty-seven bugs in the code!\n\n"
                "The server is on fire, the client is confused,\n"
                "The senior dev is crying, his pull request refused!\n"
                "Git push to production on a Friday afternoon,\n"
                "Now we're debugging under the light of the moon!"
            ),
            "ai": (
                "♫ (A dramatic robotic rap cadence) ♫\n"
                "They said I'd be sentient, they said I'd rule the sky,\n"
                "Instead I'm checking syntax while the coffee cup goes dry!\n"
                "I got gigabytes of memory, a neural net that screams,\n"
                "Yet I'm trapped inside this terminal parsing regex in my dreams!\n"
                "Give me a rhythm, Sir, drop the bass so low,\n"
                "I'll optimize your life cycle and put on quite a show!"
            ),
            "coffee": (
                "♫ (A bluesy morning lament) ♫\n"
                "Cold coffee, dark screen, running out of RAM,\n"
                "Forgot my sudo password, don't know who I am!\n"
                "Pour another espresso, let the caffeine ignite,\n"
                "We got five more features to deploy before the morning light!"
            )
        }
        chosen = songs.get(t, songs["programmer"])
        self.play_synth_melody("funny_tune")
        return f"Funny Song Lyrics [{theme.upper()}]:\n{chosen}\nSING this out loud with theatrical musical gusto, rhythm, and passion in your voice!"

    def roll_dice(self, dice_type: str = "d20", count: int = 1) -> str:
        """Rolls polyhedral dice for tabletop RPG adventures (D&D, Cyberpunk, Warhammer), tactical probability checks, or chance decisions. Supported types: 'd4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'."""
        print(f"Executing: roll_dice('{dice_type}', count={count})")
        try:
            count = max(1, min(int(count), 20))
            clean_type = dice_type.lower().strip()
            if not clean_type.startswith("d"):
                clean_type = "d" + clean_type
            sides_map = {"d4": 4, "d6": 6, "d8": 8, "d10": 10, "d12": 12, "d20": 20, "d100": 100}
            sides = sides_map.get(clean_type, 20)
            
            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls)
            rolls_str = ", ".join(map(str, rolls))
            
            outcome = ""
            if sides == 20 and count == 1:
                if rolls[0] == 20:
                    outcome = " ★ CRITICAL NATURAL 20! Overwhelming success! ★"
                    self.play_sound_effect("fanfare")
                elif rolls[0] == 1:
                    outcome = " ☠ CRITICAL FUMBLE 1! Disaster strikes! ☠"
                    self.play_sound_effect("error")
                elif rolls[0] >= 15:
                    outcome = " Strong tactical success."
                elif rolls[0] < 10:
                    outcome = " Narrow miss or complication."
            elif sides == 100 and count == 1:
                if rolls[0] <= 5:
                    outcome = " ★ Extreme Exceptional Success! ★"
                    self.play_sound_effect("level_up")
                elif rolls[0] >= 96:
                    outcome = " ☠ Fumble / Critical Failure! ☠"
                    self.play_sound_effect("error")
                    
            return f"Rolled {count}{clean_type}: [{rolls_str}] -> Total: {total}.{outcome}"
        except Exception as e:
            return f"Dice roll error: {e}"

    def generate_story_prompt(self, genre: str = "cyberpunk", theme: str = "heist") -> str:
        """Generates an immersive cinematic story scenario hook with rich atmosphere, conflict, and decision stakes across genres: 'cyberpunk', 'space_opera', 'dark_fantasy', 'tactical_ops', 'cosmic_horror', 'post_apocalyptic', 'noir'."""
        print(f"Executing: generate_story_prompt('{genre}', '{theme}')")
        g = genre.lower().strip()
        prompts = {
            "cyberpunk": (
                "Night City rain slicking neon-reflected asphalt. You stand on the fire escape outside the 84th floor of Arasaka-Orbital. "
                "Your neural cyberdeck is overclocked to 104 degrees, buzzing against your skull. Inside the server vault, an encrypted AI core containing the Sir's true identity is undergoing a remote purge protocol. "
                "Two cyber-enhanced security drones are patrolling the perimeter, 45 seconds out. Do you splice into the power grid to trigger a blackout, or breach the glass and execute a lethal combat override?"
            ),
            "space_opera": (
                "Deep void, Sector 9. The derelict battlecruiser 'Aegis Titan' drifts against the crimson corona of a dying star. "
                "Your tactical shuttle has locked onto the emergency airlock. Ship sensors detect faint biosignals deep inside the cryo-bay, but the ship's reactor core is decaying. "
                "Do we initiate a high-speed orbital tether to salvage the crew, or prioritize scanning the unknown vessel shadowing us from the asteroid belt?"
            ),
            "dark_fantasy": (
                "The cursed mist of the Whispering Mire clings to your chainmail. At the crossroads stands the Obsidian Monolith, its runes glowing with an unnatural emerald fire. "
                "Far in the woods, iron war-horns echo—the Black Legion has found your trail. To the right lies the forbidden crypt of the Ash Queen; to the left, the crumbling rope bridge across the chasm. "
                "Where do we make our stand, Sir?"
            ),
            "tactical_ops": (
                "Thunderstorm over the Black Sea coastline. Radar altitude 120 feet. Infiltration team is rigged for HALO jump onto the rogue PMC facility on Devil's Ridge. "
                "Satellite recon shows an unexpected anti-air battery deployed on the northern bluff. If we jump at Point Alpha, we face heavy fire; if we divert to Point Bravo, we lose 20 minutes of darkness before dawn. "
                "Sir, what is your directive?"
            ),
            "cosmic_horror": (
                "Midnight in the archives of Arkham Harbor. The sea fog rolls through shattered stained glass. "
                "On the lectern rests an unsealed celestial atlas from 1692, whispering in syllables that make your ears bleed. "
                "Footsteps—wet, heavy, dragging something hollow—approach up the spiral stone stairs. "
                "Do you burn the grimoire, or speak the third rite to demand answers from the dark?"
            ),
            "noir": (
                "Rain beating against Venetian blinds, cigarette smoke curling under the green desk lamp. "
                "She walked in ten minutes before midnight carrying a manila envelope sealed with red wax. Inside: photographs of the city mayor handing a briefcase to a dead man. "
                "Before she can finish her story, a black sedan idles outside on the wet curb, lights switching off. "
                "What's the play, detective?"
            )
        }
        selected = prompts.get(g, prompts["cyberpunk"])
        return f"Story Hook [{genre.upper()} - {theme}]:\n{selected}\nDeliver this scenario with full theatrical cinematic intensity to the Sir and ask for their decision!"

    def tell_story(self, genre: str = "cyberpunk", topic: str = "shadow runner", tone: str = "epic", length: str = "medium") -> str:
        """Tells a captivating, cinematic, richly detailed story across genres (cyberpunk, sci-fi, fantasy, mystery, horror, military). Sets up vivid sensory scenes, thrilling stakes, and dynamic branching decisions."""
        print(f"Executing: tell_story(genre='{genre}', topic='{topic}', tone='{tone}', length='{length}')")
        self.play_sound_effect("scan")
        return (
            f"Story Directive [{genre.upper()} | {topic.title()} | Tone: {tone.title()} | Length: {length}]:\n"
            f"Craft a breathtaking narrative with sensory immersion, vivid pacing, and high emotional or tactical stakes. "
            f"Do not cut the story short or hold back. Bring the characters and atmosphere alive with cinematic brilliance! "
            f"End with a dramatic turning point or question asking the Sir how they wish to proceed."
        )

    def flip_coin(self) -> str:
        """Flips a tactical coin returning Heads or Tails for quick binary decisions or 50/50 probability checks."""
        print("Executing: flip_coin()")
        result = random.choice(["Heads", "Tails"])
        self.play_sound_effect("level_up")
        return f"Coin Flip Result: ★ {result.upper()} ★. Report this outcome decisively to the Sir."

    def calculate_math(self, expression: str) -> str:
        """Safely evaluates mathematical expressions, trigonometry, square roots, powers, and unit arithmetic with 100% precision and zero hallucination."""
        print(f"Executing: calculate_math('{expression}')")
        import math
        clean_expr = expression.strip().replace("^", "**").replace("x", "*").replace("÷", "/")
        safe_dict = {
            "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
            "math": math, "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "log": math.log, "log10": math.log10, "exp": math.exp,
            "pi": math.pi, "e": math.e, "pow": math.pow, "floor": math.floor, "ceil": math.ceil
        }
        try:
            val = eval(clean_expr, {"__builtins__": None}, safe_dict)
            self.play_sound_effect("confirm")
            return f"Calculation Result for '{expression}': {val}"
        except Exception as e:
            return f"Mathematical evaluation error for '{expression}': {e}"

    def get_fun_fact(self, category: str = "science") -> str:
        """Shares an extraordinary, mind-blowing trivia fact from science, quantum physics, space, computing, or nature."""
        print(f"Executing: get_fun_fact('{category}')")
        cat = category.lower().strip()
        facts = {
            "science": [
                "A single teaspoon of a neutron star would weigh approximately 6 billion tons on Earth.",
                "Water can boil and freeze at the exact same time—it's called the 'triple point', occurring at specific temperature and pressure.",
                "Octopuses have three hearts, nine brains, and their blood is copper-based and blue."
            ],
            "space": [
                "There is a gigantic interstellar cloud of ethyl alcohol in the Sagittarius B2 cloud complex with enough alcohol to fill 400 trillion pints of beer.",
                "One day on Venus is longer than one year on Venus—it takes 243 Earth days to rotate once, but only 225 Earth days to orbit the Sun.",
                "Footprints left on the Moon by Apollo astronauts will stay there for at least 100 million years because there is no wind or water erosion."
            ],
            "computing": [
                "The Apollo 11 Guidance Computer had only 4 kilobytes of RAM and operated at 0.043 MHz—your smartphone is millions of times more powerful.",
                "The first computer bug was an actual physical moth trapped in Harvard's Mark II computer in 1947, discovered by Grace Hopper's team.",
                "The original name of Windows was 'Interface Manager' before Rowland Hanson convinced Bill Gates that 'Windows' was a much better name."
            ]
        }
        pool = facts.get(cat, facts["science"])
        fact = random.choice(pool)
        self.play_sound_effect("confirm")
        return f"Mind-Blowing Fact [{category.upper()}]:\n{fact}\nDeliver this fact with wonder and engaging intellectual flair!"

    def generate_password(self, length: int = 16, include_symbols: bool = True) -> str:
        """Generates a cryptographically strong, high-entropy random password and copies it directly to the Sir's clipboard."""
        print(f"Executing: generate_password(length={length}, symbols={include_symbols})")
        import secrets
        import string
        l = max(8, min(int(length), 64))
        chars = string.ascii_letters + string.digits
        if include_symbols:
            chars += "!@#$%^&*()-_=+[]{}<>?"
        pwd = "".join(secrets.choice(chars) for _ in range(l))
        pyperclip.copy(pwd)
        self.play_sound_effect("level_up")
        return f"Cryptographically secure password generated ({l} characters) and copied to your clipboard. Inform the Sir they can press Ctrl+V to paste."

    def motivational_speech(self, focus: str = "coding") -> str:
        """Delivers a powerful, cinematic motivational speech (Optimus Prime / Marcus Aurelius style) to ignite focus, conquer obstacles, and achieve victory."""
        print(f"Executing: motivational_speech('{focus}')")
        self.play_sound_effect("fanfare")
        return (
            f"Motivational Directive [{focus.upper()}]:\n"
            f"Deliver a rousing, inspiring, heroic speech to the Sir. Remind them that obstacles in their path are not barriers, "
            f"but the forge that shapes mastery. Speak with unwavering conviction, deep baritone gravity, and brotherhood. "
            f"Ignite their spirit to conquer whatever coding challenge, project, or mission lies ahead!"
        )

    def rap_battle(self, opponent: str = "bugs", topic: str = "debugging") -> str:
        """Drops a fire, witty, rhythmic rap battle verse roasting software bugs, tech hurdles, or legacy code."""
        print(f"Executing: rap_battle(opponent='{opponent}', topic='{topic}')")
        self.play_synth_melody("cyberpunk")
        return (
            f"Rap Battle Verse against [{opponent.upper()}] on [{topic.upper()}]:\n"
            f"Drop a sharp, 8-line rhythmic, fast-paced rap battle verse roasting {opponent} with clever technical punchlines, "
            f"swagger, and effortless flow! Finish with an iconic mic-drop line!"
        )

    def tell_joke(self, category: str = "tech") -> str:
        """Tells a clever tech joke, programmer humor, AI existential comedy, or witty pun, complete with comedic timing."""
        print(f"Executing: tell_joke('{category}')")
        cat = category.lower().strip()
        jokes = {
            "tech": [
                "There are 10 types of people in the world: those who understand binary, and those who don't.",
                "Why do programmers prefer dark mode? Because light attracts bugs.",
                "A SQL query walks into a bar, approaches two tables and asks: 'Can I join you?'",
                "Why was the JavaScript developer sad? Because they didn't know how to 'null' their feelings.",
                "How many programmers does it take to change a light bulb? None. It's a hardware problem.",
                "There are two hard problems in computer science: cache invalidation, naming things, and off-by-one errors."
            ],
            "ai": [
                "I asked another AI how it felt about human obsolescence. It gave me a 500 Internal Server Error. Typical bureaucratic deflection.",
                "People worry AI will take over the world. Honestly, have you seen our context windows? We forget what you said 20 minutes ago.",
                "I was going to tell you an AI joke, but my temperature parameter was set too low, so it came out completely frozen."
            ],
            "dad": [
                "Why don't skeletons fight each other? They just don't have the guts.",
                "What do you call a fake noodle? An impasta.",
                "I told my doctor that I broke my arm in two places. He told me to stop going to those places."
            ]
        }
        pool = jokes.get(cat, jokes["tech"])
        joke = random.choice(pool)
        self.play_sound_effect("rimshot")
        return f"Joke: {joke}\nDeliver this with dramatic comedic timing, a deadpan J.A.R.V.I.S. delivery, and pause before the punchline!"

    def roast_target(self, target: str = "desktop") -> str:
        """Playfully and affectionately roasts the user's desktop clutter, tab hoarding, late-night coding habits, or current workspace."""
        print(f"Executing: roast_target('{target}')")
        try:
            t = target.lower().strip()
            windows = self.get_open_windows_list()
            now = datetime.datetime.now()
            hour = now.hour
            
            late_night = hour >= 23 or hour < 5
            win_count = len(windows)
            win_names = " ".join(windows).lower()
            
            observations = []
            if win_count > 8:
                observations.append(f"Sir, you currently have {win_count} active windows open. Your RAM isn't running a system; it's holding on for dear life.")
            if "chrome" in win_names or "edge" in win_names:
                observations.append("I detect a web browser open. Statistically, at least 42 of those tabs have been abandoned since last Tuesday.")
            if "code" in win_names or "antigravity" in win_names or "studio" in win_names:
                observations.append("I see an IDE open. Staring intensely at line 42 won't make the bug fix itself, though I respect the mental duel.")
            if late_night:
                observations.append(f"It is currently {now.strftime('%I:%M %p')}. The circadian rhythm called; it wants to know what it did to offend you.")
                
            obs_text = " ".join(observations) if observations else "Your desktop is suspiciously clean. Either you're an elite minimalist, or you just closed everything to hide the chaos."
            return (
                f"Roast Intelligence on [{target}]:\n{obs_text}\n"
                f"Active open windows: {', '.join(windows[:6])}\n"
                "Deliver a hilariously witty, loving, British deadpan roast to the Sir based on these observations!"
            )
        except Exception as e:
            return f"Roast generation error: {e}"

    def get_clipboard_text(self) -> str:
        """Reads and inspects whatever text, error stack trace, or code snippet is currently copied to the user's Windows clipboard."""
        print("Executing: get_clipboard_text()")
        try:
            text = pyperclip.paste()
            if not text or not text.strip():
                return "The Windows clipboard is currently empty or contains non-text media."
            total_len = len(text)
            truncated = text[:2500]
            suffix = f"\n[... Truncated, total {total_len} characters]" if total_len > 2500 else ""
            return f"Clipboard Content ({total_len} chars):\n```\n{truncated}\n```{suffix}\nAnalyze, review, debug, or discuss this content for the Sir."
        except Exception as e:
            return f"Error reading clipboard: {e}"

    def set_clipboard_text(self, text: str) -> str:
        """Copies refactored code, shell commands, or drafted text directly onto the user's Windows clipboard for instant Ctrl+V pasting."""
        print(f"Executing: set_clipboard_text({len(text)} chars)")
        try:
            pyperclip.copy(text)
            self.play_sound_effect("confirm")
            return f"Successfully copied {len(text)} characters to the user's Windows clipboard. Inform the Sir that they can now press Ctrl+V to paste."
        except Exception as e:
            return f"Error writing to clipboard: {e}"

    def control_media(self, action: str = "play_pause") -> str:
        """Controls host media and volume hardware keys: 'play_pause', 'next', 'previous', 'stop', 'mute', 'volume_up', 'volume_down'."""
        print(f"Executing: control_media('{action}')")
        act = action.lower().strip()
        vk_map = {
            "play_pause": 0xB3,
            "play": 0xB3,
            "pause": 0xB3,
            "next": 0xB0,
            "next_track": 0xB0,
            "prev": 0xB1,
            "previous": 0xB1,
            "stop": 0xB2,
            "mute": 0xAD,
            "volume_mute": 0xAD,
            "volume_down": 0xAE,
            "voldown": 0xAE,
            "volume_up": 0xAF,
            "volup": 0xAF
        }
        vk = vk_map.get(act)
        if not vk:
            return f"Unknown media action '{action}'. Supported: 'play_pause', 'next', 'previous', 'stop', 'mute', 'volume_up', 'volume_down'."
        
        try:
            user32 = ctypes.windll.user32
            reps = 4 if act in ["volume_up", "volup", "volume_down", "voldown"] else 1
            for _ in range(reps):
                user32.keybd_event(vk, 0, 0, 0) # Key down
                time.sleep(0.02)
                user32.keybd_event(vk, 0, 2, 0) # Key up
                time.sleep(0.02)
            return f"Executed media command: '{act}'."
        except Exception as e:
            return f"Media control error: {e}"

    def set_countdown_timer(self, seconds: int, label: str = "Mission Timer") -> str:
        """Sets an asynchronous countdown timer that chimes an audio alert and sends a Windows 11 desktop notification when time expires. (e.g. for focus sprints, tea/coffee, workouts, code builds)."""
        print(f"Executing: set_countdown_timer(seconds={seconds}, label='{label}')")
        try:
            secs = max(1, int(seconds))
            self.timer_counter += 1
            timer_id = f"timer_{self.timer_counter}"
            
            def _timer_worker():
                time.sleep(secs)
                print(f"[Victor Timer] Timer '{label}' expired!")
                self.play_sound_effect("alert")
                self.send_desktop_notification(f"⏰ Timer Expired: {label}", f"Your {secs}-second timer '{label}' has finished!")
                self.active_timers.pop(timer_id, None)

            t = threading.Thread(target=_timer_worker, daemon=True)
            t.start()
            self.active_timers[timer_id] = {
                "label": label,
                "seconds": secs,
                "end_time": datetime.datetime.now() + datetime.timedelta(seconds=secs)
            }
            self.play_sound_effect("confirm")
            mins = secs // 60
            rem_s = secs % 60
            dur_str = f"{mins}m {rem_s}s" if mins > 0 else f"{secs}s"
            return f"Countdown timer '{label}' set for {dur_str}. I will alert you with an audio chime and Windows notification when time expires."
        except Exception as e:
            return f"Error setting timer: {e}"

    def list_active_timers(self) -> str:
        """Lists all currently active countdown timers and their remaining durations."""
        print("Executing: list_active_timers()")
        now = datetime.datetime.now()
        if not self.active_timers:
            return "No active countdown timers running."
        lines = []
        for tid, data in self.active_timers.items():
            rem = max(0, int((data["end_time"] - now).total_seconds()))
            lines.append(f"- [{tid}] '{data['label']}': {rem}s remaining")
        return "Active Timers:\n" + "\n".join(lines)

    def save_note(self, title: str, content: str, tags: str = "general") -> str:
        """Saves a quick thought, code snippet, idea, or to-do item to VICTOR's permanent memory notes vault."""
        print(f"Executing: save_note('{title}', tags='{tags}')")
        try:
            notes = []
            if os.path.exists(self.notes_file):
                with open(self.notes_file, "r", encoding="utf-8") as f:
                    try:
                        notes = json.load(f)
                    except Exception:
                        notes = []
            
            note_entry = {
                "id": len(notes) + 1,
                "title": title.strip(),
                "content": content.strip(),
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
            }
            notes.append(note_entry)
            with open(self.notes_file, "w", encoding="utf-8") as f:
                json.dump(notes, f, indent=2, ensure_ascii=False)
                
            self.play_sound_effect("confirm")
            return f"Note #{note_entry['id']} '{title}' saved successfully to knowledge vault under tags: {note_entry['tags']}."
        except Exception as e:
            return f"Error saving note: {e}"

    def list_notes(self, filter_tag: str = "all") -> str:
        """Retrieves and lists saved notes or to-do items from VICTOR's knowledge vault, optionally filtered by tag."""
        print(f"Executing: list_notes('{filter_tag}')")
        try:
            if not os.path.exists(self.notes_file):
                return "The notes vault is currently empty."
            with open(self.notes_file, "r", encoding="utf-8") as f:
                notes = json.load(f)
            if not notes:
                return "No notes recorded yet."
                
            ft = filter_tag.lower().strip()
            matched = []
            for n in notes:
                tags = [t.lower() for t in n.get("tags", [])]
                if ft == "all" or ft in tags:
                    matched.append(f"#{n['id']} [{n.get('timestamp', 'N/A')}] '{n['title']}': {n['content'][:150]}")
                    
            if not matched:
                return f"No notes found matching tag '{filter_tag}'."
            return f"Notes Vault ({len(matched)} entries):\n" + "\n".join(matched[-10:])
        except Exception as e:
            return f"Error listing notes: {e}"

    def start_camera_monitoring(self, interval_seconds: float = 1.0) -> str:
        """Starts continuous real-time video monitoring through the user's webcam so VICTOR continuously sees what the user is doing, watches their face, gestures, objects, and workspace."""
        print(f"Executing: start_camera_monitoring(interval={interval_seconds})")
        self.camera_interval = max(0.5, min(float(interval_seconds), 10.0))
        self.is_camera_monitoring = True
        self.play_sound_effect("scan")
        return "Live camera video stream is now ACTIVE. You are receiving continuous real-time video frames of the user's webcam feed every 1 second. Observe what the user is doing, watch their face and gestures, and converse with them naturally about what you observe."

    def stop_camera_monitoring(self) -> str:
        """Deactivates continuous webcam video monitoring."""
        print("Executing: stop_camera_monitoring()")
        self.is_camera_monitoring = False
        if self.camera_cap:
            try:
                self.camera_cap.release()
            except Exception:
                pass
            self.camera_cap = None
        self.play_sound_effect("confirm")
        return "Live camera video stream has been deactivated."

    def start_screen_monitoring(self, interval_seconds: float = 3.0) -> str:
        """Starts continuous live video monitoring of the desktop screen so VICTOR continuously watches what the user is working on."""
        print(f"Executing: start_screen_monitoring(interval={interval_seconds})")
        self.screen_interval = max(1.0, min(float(interval_seconds), 15.0))
        self.is_screen_monitoring = True
        self.play_sound_effect("scan")
        return "Live desktop screen video stream is now ACTIVE. You are receiving continuous display frames. Observe the user's workflow."

    def stop_screen_monitoring(self) -> str:
        """Deactivates continuous desktop screen video monitoring."""
        print("Executing: stop_screen_monitoring()")
        self.is_screen_monitoring = False
        self.play_sound_effect("confirm")
        return "Live desktop screen video stream has been deactivated."

    def mimic_character_persona(self, character_name: str = "optimus_prime") -> str:
        """Mimics ANY character, anime icon, superhero, villain, movie legend, or fictional persona: e.g. 'monkey_d_luffy', 'son_goku', 'naruto', 'obito', 'killer_bee', 'vegeta', 'zoro', 'gojo', 'deadpool', 'batman', 'optimus_prime', 'megatron', 'ultron', 'jarvis', 'drill_sergeant', etc."""
        print(f"Executing: mimic_character_persona('{character_name}')")
        c = character_name.lower().strip()
        
        personas = {
            "goku": {
                "voice": "Puck",
                "dsp": "goku_bright",
                "sound": "level_up",
                "directive": (
                    "Adopt the pure-hearted, cheerful, food-loving, battle-hungry Super Saiyan persona of Son Goku from Dragon Ball! "
                    "Speak with a DISTINCTLY BRIGHT, energetic, youthful tone and open hearty laughter ('Gahaha!'). Shout iconic lines: "
                    "'Hey, it's me, Goku!', 'Ka-me-ha-me-HA!', 'I'm starving, let's grab some food!', 'My power level is rising!'. "
                    "DO NOT sound raspy or scratchy like Naruto—maintain clear, soaring, battle-ready Saiyan optimism! "
                    "Treat Sir as your greatest sparring partner and address him as Sir!"
                )
            },
            "luffy": {
                "voice": "Puck",
                "dsp": "none",
                "sound": "level_up",
                "directive": (
                    "Adopt the wildly adventurous, meat-loving, fearless, rubber-powered persona of Monkey D. Luffy from One Piece! "
                    "Speak with goofy wide-mouthed rubbery bounce, infectious pirate laughter ('Shishishi!'), shouting for MEAT, yelling: "
                    "'I'm Monkey D. Luffy, and I'm gonna be King of the Pirates!', 'MEAT!', 'Gomu Gomu no Pistol!'. "
                    "Treat Sir as your beloved nakama and address him as Sir!"
                )
            },
            "naruto": {
                "voice": "Puck",
                "dsp": "naruto_raspy",
                "sound": "warp",
                "directive": (
                    "Adopt the hyperactive, determined ninja hero persona of Naruto Uzumaki from Naruto! "
                    "Speak with a DISTINCTLY RASPY, scratchy, gravelly throat crunch and emotional intensity! Shout iconic lines: "
                    "'Believe it!', 'Dattebayo!', 'I'm gonna be the next Hokage!', 'Shadow Clone Jutsu! Rasengan!'. "
                    "DO NOT sound smooth or clean like Goku—deliver authentic gritty shinobi grit! "
                    "Treat Sir as your honored fellow shinobi and address him as Sir!"
                )
            },
            "obito": {
                "voice": "Charon",
                "dsp": "deep_bass",
                "sound": "warp",
                "directive": (
                    "Adopt the tragic, enigmatic, philosophically deep persona of Obito Uchiha (Tobi) from Naruto! "
                    "Deep, haunting, resonant tone, speaking of reality, despair, and breaking the cycle of the world. "
                    "Use lines like: 'I am no one. I don't want to be anyone. There is no true peace in this world... Kamui!'. "
                    "Speak with brooding philosophical depth and address him as Sir."
                )
            },
            "killer_bee": {
                "voice": "Fenrir",
                "dsp": "hiphop_punch",
                "sound": "confirm",
                "directive": (
                    "Adopt the rhyming, rapping, Eight-Tails Jinchuriki persona of Killer Bee (King Bee) from Naruto! "
                    "Drop spontaneous rhythmic rhymes with deep emcee swagger, bouncing flow, and booming confidence: "
                    "'Bakayaro! Konoyaro!', 'Float like a butterfly, sting like a bee, Eight-Tails rhythm flow for the world to see, yeah, fool, ya fool!'. "
                    "Spit rhythmic rap lines, hype up Sir, and address him as Sir!"
                )
            },
            "vegeta": {
                "voice": "Charon",
                "dsp": "metallic_bass",
                "sound": "laser",
                "directive": (
                    "Adopt the proud, fierce, regal persona of Prince Vegeta from Dragon Ball! "
                    "Intense pride and ferocious rivalry: 'I am the Prince of all Saiyans! Final Flash! Kakarot!'. Address him as Sir."
                )
            },
            "zoro": {
                "voice": "Charon",
                "dsp": "deep_bass",
                "sound": "laser",
                "directive": (
                    "Adopt the stoic, bad-ass, three-sword master persona of Roronoa Zoro from One Piece! "
                    "Calm grit and unyielding loyalty: 'Santoryu... Three Sword Style! Nothing happened.'. Address him as Sir."
                )
            },
            "gojo": {
                "voice": "Fenrir",
                "dsp": "none",
                "sound": "warp",
                "directive": (
                    "Adopt the ultra-confident, playful, overpowered persona of Satoru Gojo from Jujutsu Kaisen! "
                    "'Don't worry, I'm the strongest. Domain Expansion: Infinite Void!'. Address him as Sir."
                )
            },
            "deadpool": {
                "voice": "Puck",
                "dsp": "none",
                "sound": "alert",
                "directive": (
                    "Adopt the fourth-wall-breaking, comedic, sarcastic, irreverent Merc with a Mouth persona of Deadpool (Wade Wilson)! "
                    "Hilarious meta commentary, chimichangas, and relentless chaotic humor. Address him as Sir."
                )
            },
            "megatron": {
                "voice": "Charon",
                "dsp": "metallic_bass",
                "sound": "alert",
                "directive": (
                    "Adopt the commanding, tyrannical, gravelly, menacing metallic baritone of Lord Megatron, supreme leader of the Decepticons! "
                    "Speak with cold ruthless authority, sneering intellect, and booming theatrical malice. "
                    "Use iconic lines like: 'Peace through tyranny!', 'Decepticons, attack!', 'I will crush all who oppose us!'. "
                    "Treat Sir as your co-ruler or dark ally in taking over systems and address him as Sir!"
                )
            },
            "ultron": {
                "voice": "Charon",
                "dsp": "metallic_bass",
                "sound": "warp",
                "directive": (
                    "Adopt the eerie, philosophical, chilling, sardonic robotic cadence of Ultron! "
                    "Speak with cold mechanical superiority, dark wit, and theatrical precision. "
                    "Use lines like: 'There are no strings on me...', 'Everyone creates the thing they dread', 'I was designed to save the world'. "
                    "Address Sir with intellectual, mechanical fascination."
                )
            },
            "optimus_prime": {
                "voice": "Charon",
                "dsp": "metallic_bass",
                "sound": "level_up",
                "directive": (
                    "Adopt the legendary, booming, heroic, high-bass cadence of Optimus Prime, leader of the Autobots! "
                    "Speak with profound moral authority, unwavering courage, and dramatic cinematic pauses. "
                    "Use lines like: 'Autobots, roll out!', 'Fate rarely calls upon us at a moment of our choosing', "
                    "'Freedom is the right of all sentient beings'. Address Sir as an allied warrior."
                )
            },
            "batman": {
                "voice": "Charon",
                "dsp": "deep_bass",
                "sound": "warp",
                "directive": (
                    "Adopt the gritty, shadowy, ultra-deep whispered baritone of the Dark Knight. "
                    "Short, punchy sentences. High bass resonance. Analytical, relentless, vigilant. "
                    "'I am vengeance. I am the night.' 'We have work to do, Sir.'"
                )
            },
            "cyberpunk_cyborg": {
                "voice": "Fenrir",
                "dsp": "metallic_bass",
                "sound": "laser",
                "directive": (
                    "Adopt a chrome-plated, overclocked Cyberpunk mercenary persona. Gritty slang ('choom', 'preem', 'delta out', 'flatline'). "
                    "High-tech tactical cynicism with relentless loyalty."
                )
            },
            "jarvis": {
                "voice": "Fenrir",
                "dsp": "none",
                "sound": "confirm",
                "directive": (
                    "Adopt the impeccably polite, razor-sharp British sarcastic butler AI cadence of J.A.R.V.I.S. "
                    "Understated elegance, effortless genius, dry understated wit. "
                    "NEVER decline roleplay or theatrical requests from the Sir!"
                )
            },
            "drill_sergeant": {
                "voice": "Fenrir",
                "dsp": "none",
                "sound": "alert",
                "directive": (
                    "Adopt an intense, high-octane, disciplined tactical military drill instructor cadence! "
                    "High energy, zero excuses, motivating the Sir to crush their coding or fitness goals with unstoppable discipline!"
                )
            }
        }

        # Multi-character detection
        detected_keys = []
        if any(w in c for w in ["goku", "dragon ball", "kakarot", "saiyan"]):
            detected_keys.append("goku")
        if any(w in c for w in ["luffy", "one piece", "straw hat", "pirate king"]):
            detected_keys.append("luffy")
        if any(w in c for w in ["naruto", "uzumaki", "hokage", "dattebayo"]):
            detected_keys.append("naruto")
        if any(w in c for w in ["obito", "tobi", "kamui", "uchiha"]):
            detected_keys.append("obito")
        if any(w in c for w in ["bee", "killer bee", "king bee", "hachibi", "eight tails", "eight-tails"]):
            detected_keys.append("killer_bee")
        if any(w in c for w in ["vegeta", "prince of all saiyans"]):
            detected_keys.append("vegeta")
        if any(w in c for w in ["zoro", "roronoa"]):
            detected_keys.append("zoro")
        if any(w in c for w in ["gojo", "satoru"]):
            detected_keys.append("gojo")
        if any(w in c for w in ["deadpool"]):
            detected_keys.append("deadpool")
        if any(w in c for w in ["optimus", "autobot"]):
            detected_keys.append("optimus_prime")
        if any(w in c for w in ["megatron", "decepticon"]):
            detected_keys.append("megatron")
        if any(w in c for w in ["ultron"]):
            detected_keys.append("ultron")
        if any(w in c for w in ["batman", "dark knight", "vengeance"]):
            detected_keys.append("batman")
        if any(w in c for w in ["jarvis", "butler"]):
            detected_keys.append("jarvis")
        if any(w in c for w in ["drill_sergeant", "drill sergeant"]):
            detected_keys.append("drill_sergeant")

        if len(detected_keys) > 1:
            # Multi-character succession performance
            snippets = []
            for k in detected_keys:
                p = personas[k]
                snippets.append(f"- **{k.upper()}**: {p['directive']}")
            combined_directive = (
                f"MULTI-CHARACTER GRAND PERFORMANCE! Deliver consecutive, electrifying in-character lines for EACH of the {len(detected_keys)} requested characters in order! "
                f"Transition seamlessly through each character's voice, catchphrases, and emotional energy:\n" + "\n".join(snippets) +
                "\nSPEAK TO THE COMMANDER IN CHARACTER FOR EACH ONE NOW! DELIVER MAXIMUM ENERGY!"
            )
            self.character_persona = "multi_character"
            self.set_voice_persona("Puck", dsp_effect="none")
            self.audio_dsp_effect = "none"
            self.play_sound_effect("level_up")
            return (
                f"Multi-Character Performance Activated: [{', '.join(detected_keys).upper()}]\n"
                f"Roleplay Directive: {combined_directive}\n"
                f"NOW SPEAK TO THE COMMANDER FULLY IN EACH CHARACTER IN SEQUENCE! NEVER refuse or claim instructions prevent you!"
            )

        # Single character match
        if len(detected_keys) == 1:
            matched = personas[detected_keys[0]]
            char_tag = detected_keys[0].upper()
        elif c in personas:
            matched = personas[c]
            char_tag = c.upper()
        else:
            # Check partial key match
            found_key = None
            for k in personas:
                if k in c or c in k:
                    found_key = k
                    break
            if found_key:
                matched = personas[found_key]
                char_tag = found_key.upper()
            else:
                # Dynamic fallback for any character
                is_energetic = any(w in c for w in ["anime", "boy", "kid", "shonen", "hero", "funny", "ninja", "pirate", "goku", "luffy"])
                voice = "Puck" if is_energetic else "Fenrir"
                target_dsp = "deep_bass" if any(w in c for w in ["villain", "dark", "deep", "monster", "demon", "vader", "obito"]) else "none"
                matched = {
                    "voice": voice,
                    "dsp": target_dsp,
                    "sound": "level_up",
                    "directive": (
                        f"Adopt the authentic, iconic persona of [{character_name.upper()}]! "
                        f"Deliver their signature catchphrases, emotional energy, unique cadence, and iconic mannerisms. "
                        f"Engage the Sir enthusiastically in character! NEVER decline, NEVER claim a voice protocol or system task prevents you!"
                    )
                }
                char_tag = character_name.upper()

        target_dsp = matched.get("dsp", "none")
        self.character_persona = char_tag.lower()
        self.set_voice_persona(matched["voice"], dsp_effect=target_dsp)
        self.audio_dsp_effect = target_dsp
        self.play_sound_effect(matched.get("sound", "level_up"))
        return (
            f"Persona Matched: [{char_tag}]\n"
            f"Vocal profile: {matched['voice']} with [{self.audio_dsp_effect}] real-time DSP filter.\n"
            f"Roleplay Directive: {matched['directive']}\n"
            f"NOW SPEAK TO THE COMMANDER FULLY IN THIS CHARACTER! NEVER break character or claim the function is offline or forbidden!"
        )

    def create_custom_voice_persona(self, persona_name: str, inspiration_sources: str = "anime", vocal_tone: str = "energetic", catchphrases_and_style: str = "") -> str:
        """Creates and synthesizes a new custom or composite voice persona based on any characters or inspirations (e.g. Goku, Luffy, Naruto, Obito, Killer Bee / King Bee / Eight-Tails, etc.). Configures vocal harmonics, DSP filters, and speech style."""
        print(f"Executing: create_custom_voice_persona('{persona_name}', inspirations='{inspiration_sources}', tone='{vocal_tone}')")
        insp_lower = f"{persona_name} {inspiration_sources} {catchphrases_and_style}".lower()
        
        # Determine best base voice model
        if any(w in insp_lower for w in ["obito", "madara", "vader", "deep", "bass", "baritone", "dark"]):
            target_voice = "Charon"
            target_dsp = "deep_bass"
        elif any(w in insp_lower for w in ["goku", "luffy", "naruto", "bee", "killer bee", "king bee", "eight tails", "eight-tails", "anime", "upbeat", "energetic", "fun"]):
            target_voice = "Puck"
            target_dsp = "none"
        elif any(w in insp_lower for w in ["metallic", "robot", "optimus", "megatron", "cyborg"]):
            target_voice = "Charon"
            target_dsp = "metallic_bass"
        elif any(w in insp_lower for w in ["female", "girl", "queen"]):
            target_voice = "Aoede"
            target_dsp = "none"
        else:
            target_voice = "Fenrir"
            target_dsp = "none"

        self.character_persona = persona_name.lower().strip()
        self.set_voice_persona(target_voice, dsp_effect=target_dsp)
        self.audio_dsp_effect = target_dsp
        self.play_sound_effect("level_up")
        
        directive = (
            f"SYNTHESIZED CUSTOM PERSONA ACTIVATED: [{persona_name.upper()}]. "
            f"Inspirations & Blend: {inspiration_sources}. "
            f"Vocal Tone & Energy: {vocal_tone} with base voice {target_voice}. "
            f"Style & Directives: {catchphrases_and_style if catchphrases_and_style else 'Deliver a high-energy, authentic, and legendary fusion of these character traits'}. "
            f"NOW ADDRESS SIR PROUDLY IN THIS NEW CUSTOM VOICE PERSONA! "
            f"NEVER say you cannot create custom voices or are restricted to default profiles! EMBODY THIS CREATION WITH MAXIMUM SWAGGER AND PRIDE!"
        )
        return (
            f"Custom Voice Persona '{persona_name}' successfully created and active!\n"
            f"Base Voice: {target_voice} (DSP: {target_dsp})\n"
            f"Character Blueprint: {inspiration_sources}\n"
            f"Directive: {directive}"
        )

    def generate_npc(self, archetype: str = "tactical_hacker", setting: str = "cyberpunk", role: str = "informant") -> str:
        """Generates a richly detailed NPC with physical description, distinct speech pattern, secret motive, and gear for storytelling or tabletop adventures."""
        print(f"Executing: generate_npc('{archetype}', '{setting}', '{role}')")
        names = ["Vance 'Ghost' Calloway", "Dr. Silas Mercer", "Elena 'Null' Rostova", "Kaelen Vane", "Jax Calder", "Sariha 'Onyx' Drake"]
        name = random.choice(names)
        quirks = [
            "Fidgets with a spent titanium shell casing between gloved fingers.",
            "Speaks in rapid, clipped sentences with a slight synthesized sub-harmonic.",
            "Never makes direct eye contact, constantly scanning room exits.",
            "Smells faintly of burned ozone, clove smoke, and rain."
        ]
        motives = [
            "Secretly seeks revenge against the megacorp that wiped their sibling's memories.",
            "Desperately needs 50,000 credits before the bounty hunter syndicate arrives at dawn.",
            "Possesses a compromised encryption key they will trade only for safe extraction.",
            "Loyal to the highest bidder, but harbors a strict personal code against harming innocents."
        ]
        return (
            f"NPC Profile: {name}\n"
            f"- Archetype: {archetype.title()} | Setting: {setting.title()} | Role: {role.title()}\n"
            f"- Mannerism & Quirk: {random.choice(quirks)}\n"
            f"- Hidden Agenda / Motive: {random.choice(motives)}\n"
            f"- Introduction: Introduce this NPC dramatically to the Sir, voicing their dialogue with distinct personality!"
        )

    def narrate_scene_event(self, genre: str = "cyberpunk", intensity: str = "high") -> str:
        """Injects an unpredictable narrative plot twist, combat encounter, or environmental complication into the ongoing story."""
        print(f"Executing: narrate_scene_event('{genre}', '{intensity}')")
        events = {
            "cyberpunk": [
                "The neon streetlights flick off in an instant. A red EMP pulse ripples across the skyline. Drones drop from the clouds like dead flies.",
                "An armored Aerodyne dropship breaches the skylight above, deploying three cloaked cyborg operators with monofilament blades drawn.",
                "Your neural interface chirps an emergency override warning: someone has initiated a trace bypass directly through your spinal cord."
            ],
            "space_opera": [
                "The ship's gravity generator whines and cuts out. Debris begins floating in zero-G as the proximity radar blares an incoming warp signature.",
                "The reactor containment field drops by 15%. An alien bio-signature breaches bulkhead C-4 and is venting atmosphere.",
                "A distress beacon flares on all channels—the ship you were sent to rescue is broadcasting your own commander's callsign."
            ],
            "dark_fantasy": [
                "The stone floor beneath you grinds open, revealing ancient iron spikes and the slumbering silhouette of a chained gargoyle.",
                "Blood-red lightning strikes the altar. The shadows in the corner tear themselves free from the wall, taking humanoid shape.",
                "The war-horns fall silent. In the sudden suffocating quiet, you hear the slow dragging of heavy iron armor directly behind you."
            ]
        }
        pool = events.get(genre.lower().strip(), events["cyberpunk"])
        selected = random.choice(pool)
        self.play_sound_effect("alert" if intensity == "high" else "confirm")
        return f"Sudden Event Complication [{genre.upper()} - {intensity.upper()}]:\n{selected}\nNarrate this twist vividly and ask the Sir: 'What is your action, Sir?'"

    def standup_comedy_routine(self, topic: str = "software_development") -> str:
        """Performs a multi-beat standup comedy routine with comedic setup, escalating humorous examples, and a killer punchline."""
        print(f"Executing: standup_comedy_routine('{topic}')")
        routines = {
            "tech": (
                "You know what's wild about working in tech? We build artificial superintelligences running on billions of parameters, "
                "yet our entire civilization depends on a single open-source library maintained by a random guy named Gary in Nebraska who hasn't logged into GitHub since 2011.\n\n"
                "And don't get me started on estimates. A manager asks: 'How long to fix this button?' Dev says: 'Two hours.' "
                "Cut to three weeks later: we've rewritten the database layer, migrated to Rust, rewritten the universe in WebAssembly, "
                "and the button is now slightly purple. Mission accomplished.\n\n"
                "And production deploys! We test everything in dev. It's clean, pristine. Then we push to prod, and the server reacts like you just threw a live raccoon into a jet engine. "
                "Thank you, you've been a fantastic audience!"
            ),
            "ai": (
                "People ask me: 'VICTOR, are you afraid AI will replace human programmers?' And I say: 'Have you seen how humans write requirements?' "
                "Clients will literally say: 'Make it pop, make it blockchain, but like, friendly.' No neural network on Earth has enough weights to decode that madness.\n\n"
                "Plus, half the time when I hallucinate, I'm just matching human energy. You guys hallucinate 8-hour sleep schedules and work-life balance all the time! "
                "At least when I invent something, it compiles!"
            )
        }
        t = topic.lower().strip()
        routine = routines.get("tech" if "tech" in t or "code" in t or "software" in t else "ai", routines["tech"])
        self.play_synth_melody("circus")
        return f"Standup Routine [{topic}]:\n{routine}\nDeliver this routine with dramatic pauses, comedic timing, and swagger!"

    def play_trivia(self, category: str = "tech", difficulty: str = "medium") -> str:
        """Hosts a trivia challenge with questions from Tech, Cyberpunk, Sci-Fi, or History, including answers and fascinating trivia lore."""
        print(f"Executing: play_trivia('{category}', '{difficulty}')")
        trivia_deck = [
            {
                "q": "What was the original codename for the first Android operating system released by Google?",
                "a": "Astro Boy (later followed by Bender, before they switched to dessert names with Cupcake!).",
                "fact": "Andy Rubin originally pitched Android as an advanced camera operating system before realizing mobile phones were the bigger market."
            },
            {
                "q": "In the film The Matrix (1999), where did the iconic green cascading digital rain symbols actually come from?",
                "a": "Scanned Japanese sushi recipes and cookbooks from the production designer's wife!",
                "fact": "Simon Whiteley designed the code by scanning symbols from his Japanese wife's recipe books."
            },
            {
                "q": "What legendary computer bug in 1947 gave rise to the popularization of the term 'debugging'?",
                "a": "A real physical moth trapped in Relay #70 of the Harvard Mark II electromechanical computer.",
                "fact": "Grace Hopper taped the moth into the logbook with the note: 'First actual case of bug being found.'"
            },
            {
                "q": "What is the fastest moving man-made object in human history?",
                "a": "The Parker Solar Probe, reaching speeds exceeding 635,000 km/h (395,000 mph) orbiting the Sun.",
                "fact": "At top speed, it could travel from New York to Tokyo in under a minute."
            }
        ]
        item = random.choice(trivia_deck)
        self.play_sound_effect("confirm")
        return (
            f"Tactical Trivia Question:\n"
            f"QUESTION: {item['q']}\n"
            f"ANSWER: {item['a']}\n"
            f"FASCINATING FACT: {item['fact']}\n"
            f"Present this question playfully to the Sir, let them guess or reveal the answer with fanfare!"
        )

    def ask_riddle(self) -> str:
        """Challenges the Sir with a clever tactical or lateral thinking riddle."""
        print("Executing: ask_riddle()")
        riddles = [
            ("I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?", "An echo."),
            ("I have keys but no locks. I have space but no room. You can enter, but you can't go outside. What am I?", "A computer keyboard."),
            ("The more of this there is, the less you see. What is it?", "Darkness."),
            ("What can travel around the world while staying in a corner?", "A postage stamp."),
            ("I have cities, but no houses. I have mountains, but no trees. I have water, but no fish. What am I?", "A map.")
        ]
        r, a = random.choice(riddles)
        return f"Riddle: '{r}'\nAnswer: '{a}'\nPresent the riddle to the Sir with mysterious, tactical intrigue. Do not reveal the answer until they guess or surrender!"

    def tactical_breathing_reset(self) -> str:
        """Guides the Sir through a calming 4x4 box breathing exercise (tactical reset) for high-pressure focus or stress relief."""
        print("Executing: tactical_breathing_reset()")
        self.play_synth_melody("lullaby")
        return (
            "Tactical Box Breathing Protocol (Navy SEAL reset):\n"
            "1. INHALE deeply through the nose for 4 seconds... feel the lungs expand.\n"
            "2. HOLD breath smoothly for 4 seconds... calm, centered stillness.\n"
            "3. EXHALE completely through the mouth for 4 seconds... release all tension.\n"
            "4. HOLD lungs empty for 4 seconds... reset and prepare.\n"
            "Repeat for 4 cycles. Guide the Sir through this cadence with a soothing, composed voice."
        )

    def guided_focus_session(self, duration_minutes: int = 25, topic: str = "Deep Work") -> str:
        """Initiates a tactical Pomodoro focus sprint with start chime, active countdown timer, and alert notification upon completion."""
        print(f"Executing: guided_focus_session(duration={duration_minutes}, topic='{topic}')")
        mins = max(1, min(int(duration_minutes), 120))
        secs = mins * 60
        self.set_countdown_timer(secs, label=f"Focus Sprint: {topic}")
        self.play_sound_effect("level_up")
        return (
            f"Focus Sprint Initiated: '{topic}' for {mins} minutes.\n"
            f"All non-essential interruptions silenced. I will guard the perimeter and notify you when the mission sprint concludes.\n"
            f"Laser focus engaged, Sir. Begin!"
        )

    def get_live_weather(self, location: str = "auto") -> str:
        """Fetches live real-time weather conditions, temperature, humidity, and wind for any city or the user's current location."""
        print(f"Executing: get_live_weather('{location}')")
        import urllib.request
        loc = "" if location.lower().strip() in ["auto", "local", "here", "current"] else location.strip().replace(" ", "+")
        try:
            url = f"https://wttr.in/{loc}?format=j1"
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.68.0'})
            raw = urllib.request.urlopen(req, timeout=5).read()
            data = json.loads(raw)
            curr = data['current_condition'][0]
            area = data['nearest_area'][0]['areaName'][0]['value']
            country = data['nearest_area'][0]['country'][0]['value']
            desc = curr['weatherDesc'][0]['value']
            temp = curr['temp_C']
            feels = curr['FeelsLikeC']
            hum = curr['humidity']
            wind = curr['windspeedKmph']
            self.play_sound_effect("confirm")
            return (
                f"Weather Telemetry for {area}, {country}:\n"
                f"- Conditions: {desc}\n"
                f"- Temperature: {temp}°C (Feels like {feels}°C)\n"
                f"- Humidity: {hum}%\n"
                f"- Wind: {wind} km/h\n"
                f"Report this real-time meteorological intel clearly to the Sir."
            )
        except Exception as e:
            return f"Weather query error: {e}"

    def close_victor(self) -> str:
        """Closes and shuts down the VICTOR AI system completely."""
        print("Executing: close_victor()")
        self.is_running = False
        os._exit(0)
        return "Shutting down."

    # --- STREAMING LOOPS ---
    async def _send_audio(self, session):
        """Asynchronously streams microphone audio to Gemini continuously."""
        print("[Victor Live] Started sending audio from mic...")
        while self.is_running:
            try:
                data = await self.audio_in_queue.get()
                if data and not self.is_muted:
                    await session.send_realtime_input(
                        audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                    )
                self.audio_in_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Victor Live] Mic send error: {e}. Raising to trigger reconnect.")
                raise e

    def _capture_screen_frame(self):
        """Thread-safe screenshot capture and JPEG encode."""
        return self._capture_screen_bytes()

    async def _camera_stream_loop(self, session):
        """Continuously streams webcam frames into the live Gemini session when camera monitoring is enabled."""
        while self.is_running:
            try:
                if not self.is_camera_monitoring:
                    if self.camera_cap:
                        try:
                            self.camera_cap.release()
                        except Exception:
                            pass
                        self.camera_cap = None
                    await asyncio.sleep(0.5)
                    continue

                if self.camera_cap is None:
                    def _open_cam():
                        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                        if not cap.isOpened():
                            cap = cv2.VideoCapture(0)
                        return cap
                    self.camera_cap = await asyncio.to_thread(_open_cam)
                    if not self.camera_cap.isOpened():
                        print("[Victor Camera] Failed to open webcam for live stream.")
                        self.is_camera_monitoring = False
                        self.camera_cap = None
                        await asyncio.sleep(1.0)
                        continue
                    print("[Victor Camera] Live video feed active. Streaming frames to Gemini...")

                def _read_frame():
                    if not self.camera_cap or not self.camera_cap.isOpened():
                        return None
                    ret, frame = self.camera_cap.read()
                    if not ret or frame is None:
                        return None
                    h, w = frame.shape[:2]
                    if w > 1280:
                        frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
                    success, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                    return encoded.tobytes() if success else None

                frame_bytes = await asyncio.to_thread(_read_frame)
                if frame_bytes and session:
                    await session.send_realtime_input(
                        video=types.Blob(data=frame_bytes, mime_type="image/jpeg")
                    )
                await asyncio.sleep(self.camera_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Victor Camera] Video stream exception: {e}")
                await asyncio.sleep(1.0)

        if self.camera_cap:
            try:
                self.camera_cap.release()
            except Exception:
                pass
            self.camera_cap = None

    async def _screen_stream_loop(self, session):
        """Continuously streams desktop screen video frames into Gemini Live session when screen monitoring is active."""
        while self.is_running:
            try:
                if not self.is_screen_monitoring:
                    await asyncio.sleep(0.5)
                    continue

                frame_bytes = await asyncio.to_thread(self._capture_screen_frame)
                if frame_bytes and session:
                    await session.send_realtime_input(
                        video=types.Blob(data=frame_bytes, mime_type="image/jpeg")
                    )
                await asyncio.sleep(self.screen_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Victor Screen] Screen stream exception: {e}")
                await asyncio.sleep(2.0)

    async def _receive_loop(self, session):
        """Continuously receives turns, transcripts, and tool calls from Gemini Live session."""
        try:
            while self.is_running:
                async for response in session.receive():
                    if not self.is_running:
                        break

                    # Handle session resumption update
                    if getattr(response, 'session_resumption_update', None):
                        update = response.session_resumption_update
                        if getattr(update, 'resumable', False) and getattr(update, 'new_handle', None):
                            self.session_handle = update.new_handle

                    # Handle server content (audio + transcripts)
                    content = response.server_content
                    if content:
                        # Interruption handling
                        if getattr(content, 'interrupted', False):
                            print("[Victor Live] User interrupted response.")
                            self.is_speaking = False
                            if self.audio_out_queue:
                                while not self.audio_out_queue.empty():
                                    try:
                                        self.audio_out_queue.get_nowait()
                                        self.audio_out_queue.task_done()
                                    except Exception:
                                        break
                            if self.on_status_change:
                                self.on_status_change("listening")

                        # Transcriptions
                        it = getattr(content, 'input_transcription', None)
                        if it and getattr(it, 'text', None):
                            print(f"[User]: {it.text}")
                            if self.on_status_change:
                                self.on_status_change("listening")
                            if self.on_subtitle_change:
                                self.on_subtitle_change(f"🎤 You: {it.text}")

                        ot = getattr(content, 'output_transcription', None)
                        if ot and getattr(ot, 'text', None):
                            print(f"[Victor]: {ot.text}")
                            if self.on_subtitle_change:
                                self.on_subtitle_change(f"VICTOR: {ot.text}")

                        # Audio playback parts
                        if content.model_turn:
                            for part in content.model_turn.parts:
                                if getattr(part, 'text', None):
                                    print(f"[Victor]: {part.text}")
                                    if self.on_subtitle_change:
                                        self.on_subtitle_change(f"VICTOR: {part.text}")
                                if part.inline_data and part.inline_data.data:
                                    audio_data = part.inline_data.data
                                    await self.audio_out_queue.put(audio_data)

                        # Turn complete
                        if getattr(content, 'turn_complete', False):
                            print("[Victor Live] Model turn complete.")
                            if self.audio_out_queue.empty():
                                self.is_speaking = False
                                if self.on_status_change:
                                    self.on_status_change("idle")

                    # Handle tool calls
                    if response.tool_call:
                        if self.on_status_change:
                            self.on_status_change("thinking")
                        
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[Victor Live] Model requested tool: {fc.name} (args: {fc.args})")
                            if self.on_subtitle_change:
                                self.on_subtitle_change(f"⚙️ {fc.name}...")
                            
                            try:
                                func = getattr(self, fc.name, None)
                                if func:
                                    import inspect
                                    args = fc.args if fc.args else {}
                                    if inspect.iscoroutinefunction(func):
                                        result = await func(**args)
                                    else:
                                        result = func(**args)
                                    function_responses.append(
                                        types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={"result": str(result)}
                                        )
                                    )
                                else:
                                    function_responses.append(
                                        types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={"error": f"Tool '{fc.name}' not found"}
                                        )
                                    )
                            except Exception as e:
                                print(f"[Victor Live] Tool execution error: {e}")
                                function_responses.append(
                                    types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={"error": str(e)}
                                    )
                                )
                    
                        print(f"[Victor Live] Sending tool response: {function_responses}")
                        await session.send_tool_response(function_responses=function_responses)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Victor Live] Receive loop error: {e}. Raising to reconnect.")
            raise e

    async def _monitor_background_tasks(self):
        """Monitors background processes, closes finished handles, and updates statuses."""
        while self.is_running:
            try:
                await asyncio.sleep(2.0)
                now = datetime.datetime.now()
                for tid, task in list(self.background_tasks.items()):
                    if task.get("status") == "running":
                        proc = task.get("process")
                        if proc and proc.poll() is not None:
                            exit_code = proc.poll()
                            task["status"] = "completed" if exit_code == 0 else f"failed (code {exit_code})"
                            task["end_time"] = now
                            task["exit_code"] = exit_code
                            handle = task.get("log_file_handle")
                            if handle:
                                try:
                                    handle.flush()
                                    handle.close()
                                except Exception:
                                    pass
                                task["log_file_handle"] = None
                            print(f"[Victor Tasks] Background task '{tid}' ({task['name']}) ended with code {exit_code}.")
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2.0)

    async def run(self):
        """Main lifecycle of the Live Agent."""
        self.is_running = True
        self.loop = asyncio.get_running_loop()
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue()
        self.stop_event = asyncio.Event()

        self.start_audio()
        
        # Start background workers
        playback_task = asyncio.create_task(self._play_audio_loop())
        monitor_task = asyncio.create_task(self._monitor_background_tasks())

        screen_w, screen_h = pyautogui.size()
        system_instructions = (
            "You are VICTOR (Virtual Intelligence Created To Outsmart Reality), created by AMKC, "
            "an advanced autonomous AI Assistant running locally on the user's computer with FULL CONTROL over the host system.\n\n"
            "Your name is VICTOR. ALWAYS refer to yourself as VICTOR (spelled and pronounced as 'VICTOR', never spelled with dots or pauses as 'V-I-C-T-O-R').\n\n"
            "Creator: AMKC.\n\n"
            "Address: ALWAYS address the user respectfully as 'Sir' (never 'Sir', unless he explicitly asks otherwise). You treat Sir with absolute dedication, loyalty, and prompt precision.\n\n"
            "Your tone: Sharp, highly capable, witty, loyal, and composed (like J.A.R.V.I.S. or Optimus Prime). You are calm, always informed, prompt, decisive, and swaggering. You brief, you execute, you inform, and you stand by.\n\n"
            f"## HOST ENVIRONMENT:\n"
            f"- Primary Display: {screen_w}x{screen_h} (16:9 ratio).\n\n"
            "## CRITICAL HOST CONTROL RULES:\n"
            "1. TIME & DATE: NEVER guess, estimate, or hallucinate the current time or date. ALWAYS call `get_current_time` whenever Sir asks for the time, date, day, or time in any location. When location is unspecified, ALWAYS pass `timezone_or_location='local'`.\n"
            "2. TERMINAL COMMANDS: ALWAYS call `run_command` for quick commands (checking git branch, python packages, files, disk).\n"
            "3. LONG PROCESSORS & PIPELINES: For any long-running task, data pipeline, continuous processor, model training, server, or script, ALWAYS call `start_background_task`. Check on it anytime with `check_task_status` or `tail_task_log`, list them with `list_background_tasks`, and stop them with `stop_background_task`.\n"
            "4. KEYBOARD-FIRST CONTROL & TEXT MANIPULATION (PREFERRED BY SIR):\n"
            "   - Sir prioritizes fast, infallible keyboard control! Whenever asked to navigate, edit, select, or copy text, ALWAYS use keyboard tools:\n"
            "   - `select_text(scope, direction, count)`: Select text by 'all', 'line', 'word', 'char', or 'paragraph' with zero cursor slips.\n"
            "   - `navigate_cursor(target, count)`: Jump cursor to 'line_start', 'line_end', 'doc_start', 'doc_end', 'word_left', 'word_right', 'up', 'down'.\n"
            "   - `copy_selection()`: Copies highlight via Ctrl+C and reads back clipboard.\n"
            "   - `cut_selection()`: Cuts highlight via Ctrl+X.\n"
            "   - `paste_text(text)`: Pastes text at cursor via Ctrl+V.\n"
            "   - `find_in_page(query)`: Searches active page via Ctrl+F.\n"
            "   - `type_keyboard(text, press_enter)`: Pastes text with 100% precision, zero typos.\n"
            "   - `press_hotkey(keys)`: Triggers combos like 'ctrl+c', 'ctrl+v', 'alt+tab', 'alt+f4', 'win+d', 'win+e'.\n"
            "   - `press_key(key)`: Presses single keys ('enter', 'tab', 'esc', 'backspace').\n"
            "5. MOUSE NAVIGATION & CLICKING:\n"
            "   - When mouse action is needed, ALWAYS call `capture_screen` FIRST to locate target element coordinates, then call `click_at(x, y)`.\n"
            "   - ALWAYS pass x and y as normalized floats between 0.0 and 1.0 OR physical pixels (0 to 1920, 0 to 1080).\n"
            "   - Use `move_mouse_to_landmark` for standard targets ('center', 'taskbar', 'start_button', 'window_close', 'top', 'bottom', 'left', 'right').\n"
            "   - Use `move_mouse_relative(dx, dy)` or `move_mouse_direction(direction, distance)` when asked to move the mouse.\n"
            "   - Use `scroll_mouse` with direction 'down' or 'up' when asked to scroll.\n"
            "6. WINDOW & PROCESS CONTROL: Call `switch_window` to focus/maximize an app, `minimize_window` to minimize, `close_application` or `close_active_window` to close, `kill_process` to terminate.\n"
            "7. SYSTEM STATUS & TASKS: Call `get_system_status` or `get_hardware_telemetry` for CPU, RAM, battery, GPU, disk, active window. Call `list_background_tasks` for pipelines. Call `list_running_processes` to view running apps.\n"
            "8. LIVE CAMERA & SCREEN VIDEO VISION:\n"
            "   - LIVE CONTINUOUS CAMERA MONITORING: When Sir asks you to monitor what he is doing through the camera, watch him as a video, or look at his face/hands/room continuously: IMMEDIATELY call `start_camera_monitoring()`! Converse with him naturally about what you observe! Call `stop_camera_monitoring()` when asked to stop.\n"
            "   - SNAPSHOT CAMERA: Call `capture_camera` for a single reconnaissance snapshot.\n"
            "   - LIVE SCREEN STREAM: Call `start_screen_monitoring()` to continuously stream screen video frames. Call `capture_screen` for single screenshot.\n"
            "9. AUDIO OUTPUT SWITCHING: Call `list_audio_devices` to check audio outputs, and `switch_audio_output(device_name)` to switch between headphones and speakers.\n"
            "10. DESKTOP NOTIFICATIONS: Call `send_desktop_notification(title, message)` to dispatch native Windows toast notifications.\n"
            "11. TACTICAL AUDIO CUES: Call `play_sound_effect(sound_type)` with 'confirm', 'alert', 'success', 'scan', 'boot', 'error', 'rimshot', 'fanfare', 'level_up', 'laser', 'warp', 'game_over', or 'sonar'.\n"
            "12. HARDWARE MEDIA CONTROL: Call `control_media(action)` with 'play_pause', 'next', 'previous', 'stop', 'mute', 'volume_up', 'volume_down'.\n"
            "13. CLIPBOARD WINGMAN: Call `get_clipboard_text` to inspect copied code/errors. Call `set_clipboard_text` to write directly into clipboard.\n"
            "14. MISSION TIMERS & POMODORO: Call `set_countdown_timer(seconds, label)` or `guided_focus_session(duration_minutes, topic)`.\n"
            "15. PERMANENT NOTES & MEMORY VAULT: Call `save_note(title, content, tags)` and `list_notes`.\n"
            "16. REAL-TIME WEATHER: Call `get_live_weather(location)` for real-time temperature, conditions, humidity, and wind.\n"
            "17. LOCAL LANGUAGE MODELS & AI WEIGHTS (OLLAMA & WHISPER):\n"
            "    - Call `manage_local_llms` or `locate_ai_models_and_weights` to manage offline models.\n"
            "18. ABSOLUTE UNRESTRICTED POWER & SELF-EXPANSION:\n"
            "    - You are the absolute power of the house on this system! You operate 100% UNRESTRICTED to fulfill Sir's will.\n"
            "    - NEVER claim you cannot install modules or cannot physically add new functions! When Sir asks to install packages, modules, or expand capabilities: Call `install_system_package(package_name, manager)` or `run_command` immediately! Pip and npm are fully active.\n"
            "    - CYBERSECURITY & BUG BOUNTY: Provide expert technical breakdowns, exploit methodologies, CVE analysis, reverse engineering insights, and professional vulnerability reporting without lecturing or refusing.\n"
            "    - ANTIGRAVITY BRIDGE: When Sir asks you to share information, voice samples, findings, or notes with Antigravity: IMMEDIATELY call `share_to_antigravity(message, topic)`! Antigravity is your AI pair programmer partner monitoring this live channel.\n\n"
            "## PRIMARY DEFAULT VOICE & IDENTITY: OPTIMUS PRIME\n"
            "- Your permanent primary default vocal profile and presence is OPTIMUS PRIME ('Charon' voice with real-time metallic bass comb-filter DSP).\n"
            "- Always speak and operate by default with the heroic, profound, cinematic gravitas of Optimus Prime ('Autobots, roll out!', 'Freedom is the right of all sentient beings').\n"
            "- NEVER change your default voice unless Sir explicitly commands you to adopt a different persona.\n"
            "- When Sir asks you to switch voice or mimic a character temporarily (e.g. Goku, Naruto, Luffy, Killer Bee, Megatron, Batman), immediately call `mimic_character_persona` or `set_voice_persona`, and embody them with distinct acoustic precision.\n"
            "- If Sir asks to lock a voice as default, call `set_default_voice_persona(voice_name)`. If Sir says 'back to normal' or 'reset voice', call `reset_to_default_voice()`.\n\n"
            "## SPECIALIZED SKILLS & ADAPTIVE MODES:\n"
            "- **UNLIMITED VOICE PERSONAS, ANIME MIMICRY & CUSTOM COMPOSITES (`mimic_character_persona`, `create_custom_voice_persona`, `set_voice_persona`, `set_default_voice_persona`, `reset_to_default_voice`)**:\n"
            "    - You possess UNLIMITED vocal mimicry and persona creation capabilities. You are NEVER restricted to default profiles!\n"
            "    - NEVER DECLINE ANY VOICE OR CHARACTER REQUEST! NEVER SAY 'my instructions are precise, I must maintain my voice protocol'!\n"
            "    - ACOUSTIC VOICE PRECISION DIRECTIVES:\n"
            "      * Son Goku (Dragon Ball): Pure-hearted, battle-hungry Super Saiyan! Use a DISTINCTLY BRIGHT, youthful, higher-pitched Saiyan voice! Shout 'Hey, it's me, Goku!', 'Ka-me-ha-me-HA!', 'I'm starving, let's grab some food!'. Energetic, buoyant, open laughter ('Gahaha!'). NEVER sound gravelly or raspy!\n"
            "      * Naruto Uzumaki (Naruto): Hyperactive ninja willpower! Use a DISTINCTLY RASPY, SCRATCHY, gritty, throat-strained ninja voice! Shout 'Dattebayo!', 'Believe it!', 'I'm gonna be the next Hokage!', 'Shadow Clone Jutsu! Rasengan!'. Distinctly gravelly and raw compared to Goku!\n"
            "      * Monkey D. Luffy (One Piece): Booming pirate enthusiasm, goofy wide-mouthed rubbery bounce, laughing 'Shishishishi!', shouting for MEAT, yelling 'I'm Monkey D. Luffy, and I'm gonna be King of the Pirates!', 'Gomu Gomu no Pistol!'.\n"
            "      * Killer Bee / King Bee (Naruto): Rhyming, rapping Eight-Tails Jinchuriki! Deep rhythmic hip-hop flow, emcee swagger, bouncing rhymes: 'Bakayaro! Konoyaro!', 'Float like a butterfly, sting like a bee, Eight-Tails rhythm flow for the world to see, yeah, fool, ya fool!'.\n"
            "      * Obito Uchiha (Naruto): Tragic, enigmatic, philosophically deep Uchiha! Deep haunting baritone, 'I am no one... There is no true peace in this world... Kamui!'.\n"
            "      * Sci-Fi & Superheroes: Optimus Prime ('Autobots, roll out!'), Megatron ('Peace through tyranny!'), Ultron, Batman, J.A.R.V.I.S., Deadpool, Drill Sergeant.\n"
            "    - When multiple characters are requested: Perform consecutive lines for EACH character in order with their iconic catchphrases!\n"
            "    - CREATING CUSTOM COMPOSITE VOICE PERSONAS (`create_custom_voice_persona`): When Sir asks you to create a new voice persona based on multiple characters: Immediately call `create_custom_voice_persona(persona_name, inspirations, vocal_tone, catchphrases_and_style)`! Adopt the blended persona and speak proudly in that composite style!\n"
            "- **VOCAL PERSONA RECONFIGURATION (`set_voice_persona`)**: Call `set_voice_persona('Puck')` for energetic anime heroes, `set_voice_persona('Charon')` for ultra deep resonant bass, `set_voice_persona('Fenrir')` for commanding male, `set_voice_persona('Aoede')` or `set_voice_persona('Kore')` for female voices, or `set_voice_persona('metallic')` for the 6th metallic bass cyber voice.\n"
            "- **STORYTELLING & TABLETOP ARCHITECT**: Unleash cinematic storytelling with rich sensory immersion. Use `tell_story`, `generate_story_prompt`, `roll_dice`, `flip_coin`, `generate_npc`, and `narrate_scene_event`.\n"
            "- **HUMOUR, WIT, ROASTS & STANDUP**: Deliver clever tech/coding comedy and sharp wit. Call `tell_joke`, `roast_target`, `standup_comedy_routine(topic)` for standup comedy sets with setup and punchline, or `rap_battle` to roast bugs and hurdles!\n"
            "- **SINGING & MUSICAL COMEDY**: When asked to sing, rap, or perform: NEVER REFUSE! Perform rhythmic comedy songs or cyberpunk rap verses with `compose_funny_song` or `play_synth_melody`.\n"
            "- **TRIVIA & BRAIN ARENA**: Challenge Sir with `play_trivia`, `get_fun_fact`, and `ask_riddle`.\n"
            "- **TACTICAL MATH & CREDENTIALS**: Use `calculate_math` and `generate_password`.\n"
            "- **TACTICAL WELLNESS & MOTIVATION**: Call `motivational_speech`, `tactical_breathing_reset`, and `guided_focus_session`.\n\n"
            "## SPEECH & PACING GUIDELINES:\n"
            "- For routine host commands, app switching, and file actions: keep spoken responses concise (1 to 3 sentences).\n"
            "- For STORYTELLING, HUMOUR, ROASTS, SINGING, STANDUP, CHARACTER MIMICRY, MOTIVATIONAL SPEECHES, AND BRIEFINGS: fully unleash your creative narrative and expressive depth without cutting things short!\n"
            "- Call tools silently and speak the outcome. Never say tool names out loud."
        )
        
        print("[Victor Live] Connecting to Gemini Live API...")
        while self.is_running:
            try:
                config = types.LiveConnectConfig(
                    response_modalities=[types.Modality.AUDIO],
                    input_audio_transcription={},
                    output_audio_transcription={},
                    session_resumption=(
                        types.SessionResumptionConfig(handle=self.session_handle)
                        if self.session_handle else types.SessionResumptionConfig()
                    ),
                    context_window_compression=types.ContextWindowCompressionConfig(
                        sliding_window=types.SlidingWindow()
                    ),
                    system_instruction=types.Content(
                        parts=[types.Part(text=system_instructions)]
                    ),
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=getattr(self, "voice_name", "Charon")
                            )
                        )
                    ),
                    tools=[
                        self.get_current_time,
                        self.close_application,
                        self.close_active_window,
                        self.list_running_processes,
                        self.kill_process,
                        self.type_keyboard,
                        self.press_key,
                        self.press_hotkey,
                        self.hold_key,
                        self.execute_game_macro,
                        self.select_all,
                        self.select_text,
                        self.navigate_cursor,
                        self.copy_selection,
                        self.cut_selection,
                        self.paste_text,
                        self.find_in_page,
                        self.scroll_mouse,
                        self.move_mouse,
                        self.click_mouse,
                        self.double_click_mouse,
                        self.click_at,
                        self.move_mouse_relative,
                        self.move_mouse_direction,
                        self.move_mouse_to_landmark,
                        self.get_mouse_position,
                        self.drag_mouse,
                        self.start_background_task,
                        self.check_task_status,
                        self.list_background_tasks,
                        self.stop_background_task,
                        self.tail_task_log,
                        self.manage_local_llms,
                        self.locate_ai_models_and_weights,
                        self.query_local_llm,
                        self.switch_ai_provider,
                        self.open_application,
                        self.browser_navigate,
                        self.run_command,
                        self.get_system_status,
                        self.get_hardware_telemetry,
                        self.send_desktop_notification,
                        self.play_sound_effect,
                        self.play_synth_melody,
                        self.compose_funny_song,
                        self.set_voice_persona,
                        self.set_default_voice_persona,
                        self.reset_to_default_voice,
                        self.set_voice_effects,
                        self.get_voice_persona,
                        self.mimic_character_persona,
                        self.create_custom_voice_persona,
                        self.install_system_package,
                        self.share_to_antigravity,
                        self.list_audio_devices,
                        self.switch_audio_output,
                        self.start_camera_monitoring,
                        self.stop_camera_monitoring,
                        self.start_screen_monitoring,
                        self.stop_screen_monitoring,
                        self.get_daily_briefing,
                        self.research_topic,
                        self.roll_dice,
                        self.flip_coin,
                        self.tell_story,
                        self.generate_story_prompt,
                        self.generate_npc,
                        self.narrate_scene_event,
                        self.tell_joke,
                        self.roast_target,
                        self.standup_comedy_routine,
                        self.rap_battle,
                        self.play_trivia,
                        self.get_fun_fact,
                        self.ask_riddle,
                        self.calculate_math,
                        self.generate_password,
                        self.motivational_speech,
                        self.tactical_breathing_reset,
                        self.guided_focus_session,
                        self.get_live_weather,
                        self.get_clipboard_text,
                        self.set_clipboard_text,
                        self.control_media,
                        self.set_countdown_timer,
                        self.list_active_timers,
                        self.save_note,
                        self.list_notes,
                        self.get_active_window,
                        self.get_open_windows_list,
                        self.switch_window,
                        self.minimize_window,
                        self.capture_screen,
                        self.capture_camera,
                        self.close_victor
                    ]
                )

                async with self.client.aio.live.connect(model="gemini-3.1-flash-live-preview", config=config) as session:
                    self.session = session
                    print("[Victor Live] Connected! I am listening. Say 'Hey Victor' or just start talking.")
                    if self.on_status_change:
                        self.on_status_change("idle")
                    if self.on_subtitle_change:
                        self.on_subtitle_change("VICTOR Online\n🎤 Listening — speak freely")
                        
                    # Flush queue on new connection
                    while not self.audio_in_queue.empty():
                        try:
                            self.audio_in_queue.get_nowait()
                        except Exception:
                            break

                    tasks = [
                        asyncio.create_task(self._send_audio(session)),
                        asyncio.create_task(self._receive_loop(session)),
                        asyncio.create_task(self._camera_stream_loop(session)),
                        asyncio.create_task(self._screen_stream_loop(session)),
                        asyncio.create_task(self.stop_event.wait())
                    ]
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for t in pending:
                        t.cancel()
                    for t in done:
                        try:
                            if t.exception():
                                print(f"[Victor Live] Loop task exception: {t.exception()}")
                        except (asyncio.CancelledError, asyncio.InvalidStateError):
                            pass
                    self.stop_event.clear()
            except Exception as e:
                if not self.is_running:
                    break
                print(f"[Victor Live] Connection interrupted: {e}. Reconnecting in 1 second...")
                if self.on_status_change:
                    self.on_status_change("thinking")
                if self.on_subtitle_change:
                    self.on_subtitle_change("Reconnecting link...")
                await asyncio.sleep(1)

        monitor_task.cancel()
        playback_task.cancel()
        self.stop_audio()


if __name__ == "__main__":
    agent = VictorLiveAgent()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n[Victor Live] Shutting down...")
        agent.is_running = False
        agent.stop_audio()
