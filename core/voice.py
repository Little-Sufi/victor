
"""
VICTOR Voice System - ALWAYS-ON & HIGH ACCURACY
Continuous background mic with multi-pass recognition.
"""
import os
import tempfile
import asyncio
import time
import threading
from dataclasses import dataclass
from enum import Enum
import yaml

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class VoiceGender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


@dataclass
class VoiceCommand:
    text: str
    confidence: float
    is_wake_word: bool
    audio_data = None


class VoiceEngine:
    def __init__(self, config_path="config/settings.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.voice_config = self.config['voice']
        self.sample_rate = 16000
        self.chunk_size = 512
        self.microphone_device_id = self.voice_config.get('microphone_device_id', None)

        self.agent_name = self.config['system'].get('name', 'VICTOR PRIME')
        self.wake_word = self.voice_config.get('wake_word', 'prime').lower()
        # Build a list of wake phrases that should trigger Victor
        self._wake_phrases = [
            self.wake_word,
            "victor",
            "hey victor",
            "hey prime",
            "ok victor",
            "yo victor",
        ]

        gender = self.voice_config.get('voice_gender', self.voice_config.get('gender', 'male'))
        if gender == 'male':
            self.voice_gender = VoiceGender.MALE
        elif gender == 'female':
            self.voice_gender = VoiceGender.FEMALE
        else:
            self.voice_gender = VoiceGender.NEUTRAL

        self.is_listening = False
        self.is_speaking = False
        self.is_processing = False
        self.on_command = None
        self.on_wake_word = None
        self.on_error = None

        self.recognizer = None
        self.microphone = None
        self.bg_stop_fn = None
        self.last_detection_time = 0

        # Always-on listening state
        self._always_on = False
        self._always_on_thread = None
        self._always_on_stop = threading.Event()
        self._ambient_energy = None  # Calibrated ambient noise level

        self.emotion_voices = {
            "happy": {"voice": "en-US-GuyNeural", "rate": "+10%", "pitch": "+5Hz", "style": "cheerful"},
            "sad": {"voice": "en-US-AriaNeural", "rate": "-15%", "pitch": "-10Hz", "style": "sad"},
            "angry": {"voice": "en-US-GuyNeural", "rate": "+20%", "pitch": "+15Hz", "style": "angry"},
            "excited": {"voice": "en-US-AriaNeural", "rate": "+25%", "pitch": "+10Hz", "style": "excited"},
            "sarcastic": {"voice": "en-US-GuyNeural", "rate": "-5%", "pitch": "+3Hz", "style": "chat"},
            "playful": {"voice": "en-US-AriaNeural", "rate": "+15%", "pitch": "+8Hz", "style": "friendly"},
            "serious": {"voice": "en-US-GuyNeural", "rate": "-10%", "pitch": "-5Hz", "style": "serious"},
            "normal": None
        }

        self._init_tts()
        self._init_stt()
        self._init_audio_player()

    def _init_audio_player(self):
        if PYGAME_AVAILABLE:
            pygame.mixer.init()
            print("[Voice] Audio player initialized (pygame mixer)")

    def _init_tts(self):
        if EDGE_TTS_AVAILABLE:
            self.tts_available = True
            if 'tts_voice' in self.voice_config and self.voice_config['tts_voice'] != 'default':
                self.tts_voice = self.voice_config['tts_voice']
            elif 'edge_voice' in self.voice_config:
                self.tts_voice = self.voice_config['edge_voice']
            else:
                gender = self.voice_config.get('voice_gender', self.voice_config.get('gender', 'male'))
                if gender == 'male':
                    self.tts_voice = self.voice_config.get('male_voice', 'en-US-GuyNeural')
                elif gender == 'female':
                    self.tts_voice = self.voice_config.get('female_voice', 'en-US-AriaNeural')
                else:
                    self.tts_voice = 'en-US-AriaNeural'
            print(f"[Voice] TTS: edge_tts initialized with {self.tts_voice}")
        else:
            self.tts_available = False
            print("[Voice] TTS: edge_tts not available")

    def _init_stt(self):
        """Initialize speech-to-text with optimized settings for accuracy."""
        self.recognizer = None

        if SR_AVAILABLE:
            self.recognizer = sr.Recognizer()

            # --- Improved recognition settings ---
            # Use dynamic threshold so it auto-adapts to the room
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.energy_threshold = 300  # Starting point, will auto-adjust

            # Pause threshold: how long silence before phrase is considered complete
            # Lower = faster response, higher = allows natural pauses in speech
            self.recognizer.pause_threshold = 1.0

            # Minimum audio that must be heard before we consider it a phrase
            self.recognizer.phrase_threshold = 0.3

            # How long silence after speech ends before cutting off
            self.recognizer.non_speaking_duration = 0.6

            # Calibrate against ambient noise on startup
            self._calibrate_mic()

            print("[Voice] STT: SpeechRecognition initialized (ADAPTIVE THRESHOLD, CALIBRATED)")
        else:
            print("[Voice] STT not available")

    def _calibrate_mic(self):
        """Do a thorough ambient noise calibration at startup."""
        if not SR_AVAILABLE or not self.recognizer:
            return

        try:
            mic_kwargs = {}
            if self.microphone_device_id is not None:
                mic_kwargs['device_index'] = self.microphone_device_id

            with sr.Microphone(**mic_kwargs) as source:
                print("[Voice] Calibrating microphone for ambient noise (2 seconds)...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2.0)
                self._ambient_energy = self.recognizer.energy_threshold
                print(f"[Voice] Calibrated energy threshold: {self._ambient_energy:.0f}")
        except Exception as e:
            print(f"[Voice] Mic calibration failed (will use defaults): {e}")

    def _is_wake_word(self, text: str) -> bool:
        """Check if text contains any wake phrase using fuzzy matching."""
        text_lower = text.lower().strip()
        for phrase in self._wake_phrases:
            if phrase in text_lower:
                return True

        # Fuzzy match: common misheard variations
        fuzzy_variants = [
            "victor", "viktor", "vikter", "victah", "vicked",
            "prime", "primed", "prim",
        ]
        for variant in fuzzy_variants:
            if variant in text_lower:
                return True

        return False

    def _strip_wake_word(self, text: str) -> str:
        """Remove wake word from the beginning of a command to get the actual query."""
        text_lower = text.lower().strip()

        # Remove common wake prefixes
        prefixes = [
            "hey victor ", "hey prime ", "ok victor ", "yo victor ",
            "victor ", "prime ",
        ]
        for prefix in prefixes:
            if text_lower.startswith(prefix):
                remainder = text[len(prefix):].strip()
                if remainder:
                    return remainder

        return text

    def _recognize_audio(self, audio, retries=2):
        """Recognize audio with multi-engine fallback and retry logic.
        
        Tries Google first (best accuracy for English), then falls back
        to Sphinx (offline) if Google fails.
        Returns (text, confidence) or (None, 0.0).
        """
        language_code = self.voice_config.get('language', 'en-US')
        last_error = None

        for attempt in range(retries + 1):
            # Attempt 1: Google (online, best accuracy)
            try:
                text = self.recognizer.recognize_google(
                    audio,
                    language=language_code,
                    show_all=False
                )
                if text and text.strip():
                    return text.strip().lower(), 0.90
            except sr.UnknownValueError:
                pass  # Audio not understood, try again or fallback
            except sr.RequestError as e:
                last_error = e
                print(f"[Voice] Google STT request error (attempt {attempt+1}): {e}")

            # Attempt 2: Try Google with show_all for partial results
            if attempt == 0:
                try:
                    results = self.recognizer.recognize_google(
                        audio,
                        language=language_code,
                        show_all=True
                    )
                    if results and 'alternative' in results:
                        alternatives = results['alternative']
                        if alternatives:
                            best = alternatives[0]
                            text = best.get('transcript', '')
                            conf = best.get('confidence', 0.5)
                            if text and text.strip():
                                return text.strip().lower(), conf
                except (sr.UnknownValueError, sr.RequestError):
                    pass
                except Exception:
                    pass

        # Fallback: Sphinx (offline, lower accuracy but works without internet)
        try:
            text = self.recognizer.recognize_sphinx(audio)
            if text and text.strip():
                print(f"[Voice] Sphinx fallback recognized: {text}")
                return text.strip().lower(), 0.50
        except Exception:
            pass  # Sphinx might not be installed

        if last_error:
            print(f"[Voice] All recognition engines failed: {last_error}")

        return None, 0.0

    # =========================================================================
    # SPEAKING
    # =========================================================================

    def speak(self, text, block=True):
        """Speak text with robust error handling and smooth operation."""
        if not text or not text.strip():
            return

        print(f"[Voice] speak() called with text: {text[:50]}..., block={block}")

        if self.is_speaking:
            print("[Voice] Already speaking - skipping new speak request")
            return

        self.is_speaking = True
        temp_file_path = None

        try:
            # Always try to use TTS if available!
            if EDGE_TTS_AVAILABLE:
                print("[Voice] Generating TTS...")
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_file.close()
                temp_file_path = temp_file.name

                try:
                    async def _tts():
                        communicate = edge_tts.Communicate(text, self.tts_voice)
                        await communicate.save(temp_file_path)

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_tts())
                    loop.close()
                    print("[Voice] TTS generated successfully!")
                except Exception as tts_err:
                    print(f"[Voice] TTS generation failed: {tts_err}")
                    self.is_speaking = False
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.unlink(temp_file_path)
                        except:
                            pass
                    return

                def play_and_wait():
                    try:
                        if PYGAME_AVAILABLE:
                            try:
                                pygame.mixer.music.load(temp_file_path)
                                pygame.mixer.music.play()
                                while pygame.mixer.music.get_busy() and self.is_speaking:
                                    pygame.time.Clock().tick(10)
                                try:
                                    pygame.mixer.music.unload()
                                except:
                                    pass
                            except Exception as play_err:
                                print(f"[Voice] Audio playback error: {play_err}")
                        else:
                            print("[Voice] pygame not available - skipping audio playback")
                    finally:
                        try:
                            if temp_file_path and os.path.exists(temp_file_path):
                                os.unlink(temp_file_path)
                        except Exception as del_err:
                            print(f"[Voice] Could not delete temp file: {del_err}")

                        self.is_speaking = False

                if block:
                    play_and_wait()
                else:
                    threading.Thread(target=play_and_wait, daemon=True).start()
            else:
                print(f"[Voice] TTS not available - skipping audio")
                self.is_speaking = False
        except Exception as e:
            print(f"[Voice] Critical TTS Error: {e}")
            import traceback
            traceback.print_exc()
            self.is_speaking = False
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

    # =========================================================================
    # SINGLE LISTEN (used by GUI click-to-speak)
    # =========================================================================

    def listen_once(self, timeout=8, phrase_time_limit=15):
        """Listen once with improved recognition.
        
        Args:
            timeout: Max seconds to wait for speech to start
            phrase_time_limit: Max seconds of speech to capture
        """
        if not SR_AVAILABLE or not self.recognizer:
            print("[Voice] STT not available")
            return None

        current_time = time.time()

        # Brief cooldown to avoid double-triggers
        if current_time - self.last_detection_time < 0.3:
            return None

        self.is_listening = True
        self.is_processing = False

        try:
            mic_kwargs = {}
            if self.microphone_device_id is not None:
                mic_kwargs['device_index'] = self.microphone_device_id

            with sr.Microphone(**mic_kwargs) as source:
                # Quick recalibration for ambient noise
                try:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                except:
                    pass

                print("[Voice] Listening...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )

                self.is_processing = True
                print("[Voice] Recognizing...")

                text, confidence = self._recognize_audio(audio, retries=1)

                if text:
                    print(f"[Voice] Heard: '{text}' (confidence: {confidence:.2f})")

                    is_wake = self._is_wake_word(text)
                    if is_wake:
                        self.last_detection_time = time.time()

                    return VoiceCommand(
                        text=text,
                        confidence=confidence,
                        is_wake_word=is_wake
                    )
                else:
                    print("[Voice] Could not understand audio")

        except sr.WaitTimeoutError:
            pass  # Normal timeout, not an error
        except Exception as e:
            print(f"[Voice] Listen error: {e}")
        finally:
            self.is_listening = False
            self.is_processing = False

        return None

    # =========================================================================
    # ALWAYS-ON BACKGROUND LISTENING (continuous wake word + command loop)
    # =========================================================================

    def start_always_on(self, on_wake_word=None, on_command=None):
        """Start always-on continuous listening.
        
        The mic stays open permanently. When a wake word is detected,
        or any speech is heard, the appropriate callback is fired.
        
        Args:
            on_wake_word: callback() when wake word is heard
            on_command: callback(VoiceCommand) for every recognized phrase
        """
        if self._always_on:
            print("[Voice] Always-on already active")
            return

        if not SR_AVAILABLE or not self.recognizer:
            print("[Voice] Cannot start always-on: STT unavailable")
            return

        self.on_wake_word = on_wake_word
        self.on_command = on_command
        self._always_on = True
        self._always_on_stop.clear()

        self._always_on_thread = threading.Thread(
            target=self._always_on_loop, daemon=True, name="VictorAlwaysOn"
        )
        self._always_on_thread.start()
        print("[Voice] ✅ ALWAYS-ON MIC ACTIVE — Say 'Hey Victor' anytime!")

    def stop_always_on(self):
        """Stop always-on listening."""
        if not self._always_on:
            return
        self._always_on = False
        self._always_on_stop.set()
        if self._always_on_thread:
            self._always_on_thread.join(timeout=3)
            self._always_on_thread = None
        print("[Voice] Always-on mic stopped")

    def _always_on_loop(self):
        """Main loop for always-on listening. Runs in background thread."""
        mic_kwargs = {}
        if self.microphone_device_id is not None:
            mic_kwargs['device_index'] = self.microphone_device_id

        consecutive_errors = 0
        max_errors = 10

        while self._always_on and not self._always_on_stop.is_set():
            # Skip if Victor is speaking (don't pick up own voice)
            if self.is_speaking:
                self._always_on_stop.wait(0.3)
                continue

            try:
                with sr.Microphone(**mic_kwargs) as source:
                    # Quick ambient recalibration every loop
                    try:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    except:
                        pass

                    self.is_listening = True

                    try:
                        # Wait for speech (long timeout so we don't busy-loop)
                        audio = self.recognizer.listen(
                            source,
                            timeout=None,  # Wait forever for speech
                            phrase_time_limit=15  # Max 15s per phrase
                        )
                    except sr.WaitTimeoutError:
                        self.is_listening = False
                        continue

                    self.is_listening = False
                    self.is_processing = True

                    # Skip if speaking started while we were recording
                    if self.is_speaking:
                        self.is_processing = False
                        continue

                    text, confidence = self._recognize_audio(audio, retries=1)

                    self.is_processing = False

                    if not text:
                        consecutive_errors = 0  # Not an error, just ambient noise
                        continue

                    consecutive_errors = 0
                    print(f"[Voice] Always-on heard: '{text}' (conf: {confidence:.2f})")

                    is_wake = self._is_wake_word(text)

                    if is_wake:
                        self.last_detection_time = time.time()
                        print(f"[Voice] 🎤 WAKE WORD DETECTED!")

                        # Extract the actual command after the wake word
                        command_text = self._strip_wake_word(text)

                        if self.on_wake_word:
                            try:
                                self.on_wake_word()
                            except Exception as e:
                                print(f"[Voice] Wake callback error: {e}")

                        if self.on_command:
                            try:
                                cmd = VoiceCommand(
                                    text=command_text,
                                    confidence=confidence,
                                    is_wake_word=True
                                )
                                self.on_command(cmd)
                            except Exception as e:
                                print(f"[Voice] Command callback error: {e}")

                    # Even without wake word, fire command callback if confidence is good
                    elif confidence >= 0.7 and self.on_command:
                        try:
                            cmd = VoiceCommand(
                                text=text,
                                confidence=confidence,
                                is_wake_word=False
                            )
                            self.on_command(cmd)
                        except Exception as e:
                            print(f"[Voice] Command callback error: {e}")

            except OSError as e:
                consecutive_errors += 1
                print(f"[Voice] Mic error ({consecutive_errors}/{max_errors}): {e}")
                if consecutive_errors >= max_errors:
                    print("[Voice] Too many mic errors — stopping always-on")
                    break
                self._always_on_stop.wait(2.0)  # Wait before retrying

            except Exception as e:
                consecutive_errors += 1
                print(f"[Voice] Always-on error ({consecutive_errors}): {e}")
                if consecutive_errors >= max_errors:
                    break
                self._always_on_stop.wait(1.0)

        self._always_on = False
        self.is_listening = False
        self.is_processing = False
        print("[Voice] Always-on loop ended")

    # =========================================================================
    # LEGACY BACKGROUND WAKE WORD (kept for compatibility)
    # =========================================================================

    def start_background_wake_word(self, callback):
        """Start background wake word detection with robust error handling."""
        if not SR_AVAILABLE or not self.recognizer:
            print("[Voice] Cannot start background wake word: STT unavailable.")
            return
        if self.bg_stop_fn:
            print("[Voice] Wake word detection already running.")
            return

        self.on_wake_word = callback
        mic_kwargs = {}

        if self.microphone_device_id is not None:
            mic_kwargs['device_index'] = self.microphone_device_id

        try:
            source = sr.Microphone(**mic_kwargs)
            with source:
                try:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                except Exception as adj_err:
                    print(f"[Voice] Ambient noise adjustment failed: {adj_err}")

            self.last_detection_time = 0

            def bg_callback(recognizer, audio):
                """Background callback for wake word detection."""
                if self.is_speaking:
                    return

                current_time = time.time()

                if current_time - self.last_detection_time < 0.5:
                    return

                try:
                    text, confidence = self._recognize_audio(audio, retries=0)

                    if text and self._is_wake_word(text):
                        print(f"[Voice] Wake word detected: {text}")
                        self.last_detection_time = current_time
                        if self.on_wake_word:
                            try:
                                self.on_wake_word()
                            except Exception as cb_err:
                                print(f"[Voice] Wake word callback error: {cb_err}")
                except Exception as e:
                    pass  # Silently ignore errors in background

            self.bg_stop_fn = self.recognizer.listen_in_background(source, bg_callback, phrase_time_limit=5)
            print("[Voice] Continuous wake word listening active (Say 'Hey Victor')")
        except Exception as e:
            print(f"[Voice] Failed to start background listening: {e}")
            import traceback
            traceback.print_exc()

    def stop_background_wake_word(self):
        """Stop background wake word detection safely."""
        if self.bg_stop_fn:
            try:
                self.bg_stop_fn(wait_for_stop=False)
                self.bg_stop_fn = None
                print("[Voice] Background wake word detection stopped")
            except Exception as e:
                print(f"[Voice] Error stopping background detection: {e}")
                self.bg_stop_fn = None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def stop_speaking(self):
        if self.is_speaking and PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except:
                pass
        self.is_speaking = False

    def speak_with_emotion(self, text, emotion="happy", block=True):
        """Speak text with a specific emotional tone."""
        emotion_settings = self.emotion_voices.get(emotion)

        if emotion_settings is None:
            emotion = "normal"
            emotion_settings = None

        original_voice = self.tts_voice

        if emotion_settings:
            self.tts_voice = emotion_settings["voice"]

        self.speak(text, block=block)

        self.tts_voice = original_voice

        return f"Spoken with {emotion} emotion"

    def set_agent_name(self, name):
        """Set the agent name."""
        self.agent_name = name

    def set_voice_gender(self, gender):
        """Set the voice gender."""
        self.voice_gender = gender
        self._init_tts()

    def reset(self):
        """Reset voice system to a clean state (safety feature)."""
        print("[Voice] Resetting voice system...")

        try:
            self.stop_speaking()
        except:
            pass

        try:
            self.stop_always_on()
        except:
            pass

        try:
            self.stop_background_wake_word()
        except:
            pass

        self.is_listening = False
        self.is_speaking = False
        self.is_processing = False
        self.last_detection_time = 0

        print("[Voice] System reset complete")

    def safe_speak(self, text, block=True, fallback_text="I'm having trouble speaking right now."):
        """Safely speak text with automatic fallback."""
        try:
            self.speak(text, block=block)
        except Exception as e:
            print(f"[Voice] Safe speak failed: {e}")
            try:
                if fallback_text:
                    self.is_speaking = False
                    self.speak(fallback_text, block=block)
            except:
                pass

    def shutdown(self):
        """Graceful shutdown of voice system."""
        print("[Voice] Shutting down voice system...")
        try:
            self.stop_always_on()
        except:
            pass
        try:
            self.stop_background_wake_word()
        except:
            pass
        try:
            self.stop_speaking()
        except:
            pass
        try:
            if PYGAME_AVAILABLE:
                pygame.mixer.quit()
        except:
            pass
        self.is_listening = False
        self.is_speaking = False
        self.is_processing = False
        print("[Voice] Voice system shutdown complete")
