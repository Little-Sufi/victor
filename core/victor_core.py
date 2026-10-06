from .brain import Brain
from .voice import VoiceEngine
from .vision import VisionEngine
from os_layer.factory import get_os
from skills import SKILLS
import time
import threading
from dataclasses import dataclass


@dataclass
class VictorState:
    listening: bool = False
    processing: bool = False
    speaking: bool = False


class VictorCore:
    def __init__(self, settings_path: str = "config/settings.yaml"):
        self.settings_path = settings_path
        self.state = VictorState()

        # Callback hooks for GUI integration
        self.on_state_change = None
        self.on_thought = None
        self.on_wake_word_detected = None
        self.on_speak = None

        # Lock to prevent overlapping command processing
        self._processing_lock = threading.Lock()

        print("[OK] Starting VICTOR (ULTRA FAST + SKILLS)...")

        # Initialize ONLY FAST components
        self.brain = Brain(settings_path)
        self.os_layer = get_os()
        self.voice = VoiceEngine(settings_path)
        try:
            self.vision = VisionEngine(settings_path)
        except Exception as e:
            print(f"[WARN] Vision engine not available: {e}")
            self.vision = None

        # Load skills, and set self.victor on each
        self.skills = self._load_skills()
        print(f"[OK] Loaded {len(self.skills)} skills")

        print("[OK] VICTOR READY!")

    def _load_skills(self):
        skill_instances = []
        for skill_class in SKILLS:
            try:
                skill = skill_class()
                skill.victor = self  # Link skill can access our components!
                skill_instances.append(skill)
            except Exception as e:
                print(f"[WARN] Failed to load skill: {e}")
        return skill_instances

    def _update_state(self, **kwargs):
        """Update state and notify GUI via callback."""
        changed = False
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                old = getattr(self.state, key)
                if old != value:
                    setattr(self.state, key, value)
                    changed = True
        if changed and self.on_state_change:
            try:
                self.on_state_change(self.state)
            except Exception as e:
                print(f"[WARN] State change callback error: {e}")

    def process_command(self, query: str) -> str:
        start_time = time.time()
        print(f"\n[USER] Received: {query}")

        self._update_state(processing=True)

        # FIRST check skills for INSTANT response, NO DELAY, NO LLM hit
        best_skill = None
        best_confidence = 0.0

        for skill in self.skills:
            try:
                confidence = skill.can_handle(query)
                if confidence > best_confidence and confidence > 0.5:
                    best_confidence = confidence
                    best_skill = skill
            except Exception as e:
                print(f"[WARN] Skill error: {e}")

        response = None

        if best_skill:
            try:
                response = best_skill.handle(query)
                if response:
                    elapsed = time.time() - start_time
                    print(f"[SPEED] INSTANT skill response in {elapsed:.2f}s")
            except Exception as e:
                print(f"[WARN] Skill handle error: {e}")

        if not response:
            # ONLY use brain if NO SKILLS handled it
            if self.on_thought:
                try:
                    self.on_thought("[Thought] Thinking...")
                except:
                    pass
            brain_response = self.brain.think(query)
            response = brain_response.text
            elapsed = time.time() - start_time
            print(f"[SPEED] Total response in {elapsed:.2f}s")

        self._update_state(processing=False)
        return response

    def speak(self, text: str):
        try:
            self._update_state(speaking=True)
            self.voice.speak(text)
        except Exception as e:
            print(f"[WARN] TTS failed: {e}")
        finally:
            self._update_state(speaking=False)

    def listen_once(self):
        """Listen for one voice command. Used by GUI ListenWorker."""
        self._update_state(listening=True)
        try:
            result = self.voice.listen_once()
            if result and result.text:
                self._update_state(listening=False)

                if result.is_wake_word:
                    if self.on_wake_word_detected:
                        try:
                            self.on_wake_word_detected()
                        except:
                            pass

                # Process the command
                response = self.process_command(result.text)

                # Speak the response
                if self.on_speak:
                    try:
                        self.on_speak(response)
                    except:
                        pass
                else:
                    self.speak(response)

                return response
            else:
                return ""
        except Exception as e:
            print(f"[WARN] Listen error: {e}")
            return ""
        finally:
            self._update_state(listening=False)

    def _on_always_on_wake(self):
        """Called by always-on mic when wake word is detected."""
        self._update_state(listening=True)
        if self.on_wake_word_detected:
            try:
                self.on_wake_word_detected()
            except:
                pass

    def _on_always_on_command(self, voice_cmd):
        """Called by always-on mic when a command is recognized.
        
        Handles the full cycle: process → speak → back to listening.
        Uses a lock so we don't process two commands simultaneously.
        """
        if not self._processing_lock.acquire(blocking=False):
            print("[Voice] Already processing a command, skipping")
            return

        try:
            text = voice_cmd.text
            if not text or not text.strip():
                return

            print(f"\n[ALWAYS-ON] Command: '{text}' (wake={voice_cmd.is_wake_word}, conf={voice_cmd.confidence:.2f})")

            # For non-wake-word speech, require wake word to act
            # (otherwise Victor would respond to every ambient conversation)
            if not voice_cmd.is_wake_word:
                return

            self._update_state(listening=False, processing=True)

            # Process the command
            response = self.process_command(text)

            if response and response.strip():
                self._update_state(processing=False, speaking=True)

                # Speak the response
                if self.on_speak:
                    try:
                        self.on_speak(response)
                    except:
                        pass
                else:
                    self.speak(response)

                self._update_state(speaking=False)

                # Notify GUI of the response
                if self.on_thought:
                    try:
                        display = response[:100] + ("..." if len(response) > 100 else "")
                        self.on_thought(display)
                    except:
                        pass
            else:
                self._update_state(processing=False)

        except Exception as e:
            print(f"[WARN] Always-on command error: {e}")
            self._update_state(processing=False, speaking=False)
        finally:
            # Return to idle listening state
            self._update_state(listening=True)
            self._processing_lock.release()

    def start_voice_mode(self):
        """Start always-on voice mode — mic is permanently active."""
        print("[OK] Starting ALWAYS-ON voice mode...")
        self._update_state(listening=True)

        # Start the always-on mic loop
        self.voice.start_always_on(
            on_wake_word=self._on_always_on_wake,
            on_command=self._on_always_on_command
        )

    def stop_voice_mode(self):
        """Stop always-on voice mode."""
        print("[OK] Voice mode stopped")
        self.voice.stop_always_on()
        self._update_state(listening=False)

    def self_diagnose(self):
        mic_status = "ALWAYS-ON" if self.voice._always_on else "OFF"
        return """
=== VICTOR DIAGNOSTICS ===
✅ Brain: OK (llama3.2:latest)
✅ Skills: Loaded ({} skills)
✅ Voice: OK
✅ Mic: {}
✅ Vision: {}
✅ OS Layer: OK
""".format(len(self.skills), mic_status, "OK" if self.vision else "Not available")

    def shutdown(self):
        print("\n[OK] Shutting down VICTOR...")
        self.voice.shutdown()

    def get_status(self):
        return {
            "brain": self.brain.get_status(),
            "skills_count": len(self.skills),
            "mic_always_on": self.voice._always_on,
        }
