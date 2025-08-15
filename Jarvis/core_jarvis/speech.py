"""
Speech Engine - Speech synthesis and recognition for Jarvis
"""

import os
import time
import logging
import tempfile
from pathlib import Path
import threading
import pygame
import speech_recognition as sr
import audioop
from typing import Optional




class SpeechEngine:
    """Speech synthesis and recognition for Jarvis"""

    def __init__(self, config_manager: dict, temp_dir: str):
        """Initialize speech engine with configuration"""
        self.config_manager = config_manager
        self.temp_dir = temp_dir

        # Load configuration settings
        # Try environment variable first, then config
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not self.OPENAI_API_KEY:
            # Try to get from config
            api_key_from_config = self.config_manager.get("API_KEYS", "openai", "")
            if api_key_from_config and not api_key_from_config.startswith("gAAAAA"):
                self.OPENAI_API_KEY = api_key_from_config
            elif api_key_from_config:
                # Try to decrypt if it looks encrypted
                try:
                    decrypted = self.config_manager._decrypt_if_needed(api_key_from_config, True)
                    if decrypted:
                        self.OPENAI_API_KEY = decrypted
                except:
                    pass
        
        if self.OPENAI_API_KEY:
            logging.info(f"OpenAI API key loaded: {self.OPENAI_API_KEY[:10]}...")
        else:
            logging.warning("No OpenAI API key found!")

        self.language = self.config_manager.get("language", "en-US") or "en-US"
        self.openai_voice = self.config_manager.get("voice", "alloy") or "alloy"

        self.energy_threshold = float(
            self.config_manager.get("energy_threshold", "3000") or "3000"
        )
        self.pause_threshold = float(
            self.config_manager.get("pause_threshold", "0.5") or "0.5"
        )

        # Lock to prevent overlapping speech
        self.speech_lock = threading.Lock()

        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = self.energy_threshold
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.pause_threshold = self.pause_threshold

        self.noise_gate_threshold = float(
            self.config_manager.get("noise_gate_threshold", "100") or "100"
        )
        self.min_speech_duration = float(
            self.config_manager.get("min_speech_duration", "0.3") or "0.3"
        )

        # Optional VAD for noise filtering
        try:
            import webrtcvad

            self.vad = webrtcvad.Vad(2)
        except Exception:
            self.vad = None

        # Calibrate microphone to current ambient noise
        self._calibrate_microphone()

        # Initialize translator if available
        self.translator = None
        try:
            # Skip googletrans if it has issues
            import importlib
            if importlib.util.find_spec('googletrans'):
                try:
                    from googletrans import Translator
                    self.translator = Translator()
                    logging.info("Translator initialized successfully")
                except Exception as e:
                    logging.warning(f"Translator initialization failed: {e}")
                    logging.warning("Translation features will be disabled")
        except ImportError:
            logging.warning(
                "Translator not available - multi-language support will be limited"
            )
        except Exception as e:
            logging.error(f"Error initializing translator: {str(e)}")

        # Jarvis instance reference (will be set by jarvis.py)
        self.jarvis_instance = None

    def _get_temp_file_path(self) -> Path:
        """Return a writable temporary file path for audio output."""
        from utils_jarvis.file_utils import get_writable_temp_dir

        # Ensure the current temp dir is writable
        if not os.access(self.temp_dir, os.W_OK):
            self.temp_dir = get_writable_temp_dir()

        try:
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp3", dir=self.temp_dir
            )
            path = Path(tmp.name)
            tmp.close()
            return path
        except Exception as e:
            logging.error(f"Failed to create temp file in {self.temp_dir}: {e}")

        fallback_dirs = [
            os.path.join(os.getenv("APPDATA", ""), "Jarvis", "temp"),
            os.path.join(os.getcwd(), "temp"),
        ]
        for d in fallback_dirs:
            try:
                os.makedirs(d, exist_ok=True)
                if os.access(d, os.W_OK):
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=".mp3", dir=d
                    )
                    path = Path(tmp.name)
                    tmp.close()
                    self.temp_dir = d
                    logging.info(f"Using fallback temp dir {d}")
                    return path
            except Exception as ex:
                logging.error(f"Fallback temp dir failed {d}: {ex}")

        # Last resort - system temp directory
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        path = Path(tmp.name)
        tmp.close()
        self.temp_dir = os.path.dirname(path)
        return path

    def _calibrate_microphone(self) -> None:
        """Calibrate microphone for ambient noise."""
        try:
            with sr.Microphone() as source:
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                self.energy_threshold = self.recognizer.energy_threshold
                logging.info(
                    f"Calibrated microphone with threshold {self.recognizer.energy_threshold}"
                )
        except Exception as e:
            logging.warning(f"Microphone calibration failed: {e}")

    def speak(self, text: str, translate_to: Optional[str] = None) -> None:
        """Convert text to speech using selected TTS service"""
        if not text:
            return

        # Translate text if requested and translator is available
        if translate_to and self.translator:
            try:
                text = self.translator.translate(text, dest=translate_to).text
                logging.info(f"Translated text to {translate_to}")
            except Exception as e:
                logging.error(f"Translation error: {str(e)}")

        print(f"Jarvis: {text}")
        logging.info(f"Jarvis: {text}")
        
        # Try OpenAI TTS first
        success = self._speak_openai(text)
        
        # If OpenAI fails, try Windows TTS as fallback
        if not success:
            self._speak_windows_fallback(text)
    
    def _speak_openai(self, text: str) -> bool:
        """Try to speak using OpenAI TTS."""
        # Debug: Check if pygame is initialized
        if not pygame.mixer.get_init():
            logging.error("Pygame mixer not initialized!")
            try:
                pygame.mixer.init()
                logging.info("Pygame mixer re-initialized")
            except Exception as e:
                logging.error(f"Failed to initialize pygame mixer: {e}")
                return False
        
        with self.speech_lock:
            try:
                from utils_jarvis.api_helpers import get_openai_audio

                logging.info(f"Generating audio for: {text[:50]}...")
                audio = get_openai_audio(
                    api_key=self.OPENAI_API_KEY,
                    text=text,
                    voice=self.openai_voice,
                )

                if not audio:
                    logging.error("OpenAI TTS API returned no audio")
                    return False
                    
                logging.info(f"Audio generated: {len(audio)} bytes")

                temp_file = self._get_temp_file_path()
                logging.info(f"Saving audio to: {temp_file}")
                
                with open(temp_file, "wb") as f:
                    f.write(audio)

                # Set volume to maximum
                pygame.mixer.music.set_volume(1.0)
                
                pygame.mixer.music.load(str(temp_file))
                pygame.mixer.music.play()
                
                logging.info("Playing audio...")

                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)

                logging.info("Audio playback completed")
                
                # Stop and unload the music to release the file
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                time.sleep(0.5)

                self.cleanup_audio_files()
                return True
                
            except Exception as e:
                logging.error(f"Error with OpenAI TTS: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    def _speak_windows_fallback(self, text: str) -> None:
        """Fallback to Windows TTS if OpenAI fails."""
        try:
            logging.info("Using Windows TTS fallback")
            # Use PowerShell to speak
            import subprocess
            ps_command = f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak("{text}")'
            subprocess.run(['powershell', '-Command', ps_command], capture_output=True)
            logging.info("Windows TTS completed")
        except Exception as e:
            logging.error(f"Windows TTS also failed: {e}")


    def cleanup_audio_files(self) -> None:
        """Clean up old audio files from temp directory, keeping the 5 most recent ones"""
        try:
            temp_path = Path(self.temp_dir)
            audio_files = [
                temp_path / f
                for f in os.listdir(self.temp_dir)
                if f.startswith("jarvis_speech_") and f.endswith(".mp3")
            ]

            # Sort by creation time (oldest first)
            audio_files.sort(key=lambda x: x.stat().st_ctime)

            # Delete all but the 5 most recent files
            for file in audio_files[:-5]:
                try:
                    file.unlink(missing_ok=True)
                except:
                    pass
        except Exception as e:
            logging.error(f"Error cleaning up audio files: {str(e)}")

    def stop(self) -> None:
        """Immediately stop any ongoing speech playback."""
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def clear_microphone_buffer(self) -> None:
        """Flush any leftover audio from the microphone buffer."""
        try:
            with sr.Microphone() as source:
                self.recognizer.listen(source, timeout=0.1, phrase_time_limit=0.1)
        except Exception:
            pass

    def listen(self, timeout: int = 5, phrase_time_limit: int = 5) -> str:
        """Listen to user voice input and convert to text with improved wake word detection"""
        with sr.Microphone() as source:
            # Check if we're in sleep mode (if jarvis instance is available)
            is_sleeping = False
            wake_word = "jarvis"

            # Try to get sleep status from jarvis instance (if available)
            try:
                # This assumes the speech engine has access to jarvis instance
                # We'll need to modify the speech engine initialization for this
                if hasattr(self, "jarvis_instance") and self.jarvis_instance:
                    is_sleeping = self.jarvis_instance.sleep_monitor.is_sleeping
                    wake_word = self.jarvis_instance.sleep_monitor.wake_word
            except AttributeError:
                # If we can't access jarvis instance, continue normally
                pass

            # Adjust listening behavior based on sleep state
            if is_sleeping:
                print("💤 Sleep mode - Listening for wake word...")
                logging.info("Sleep mode - Listening for wake word")
            else:
                print("Listening...")
                logging.info("Listening for command")

            try:
                # Adjust energy threshold for sleep mode
                original_threshold = self.recognizer.energy_threshold

                if is_sleeping:
                    # Lower the threshold when sleeping to make wake word detection more sensitive
                    self.recognizer.energy_threshold = min(
                        self.recognizer.energy_threshold * 0.5, 1000
                    )
                    print(
                        f"Sleep mode: Using lower energy threshold: {self.recognizer.energy_threshold}"
                    )

                # Shorter ambient noise adjustment for responsiveness
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)

                # Use longer timeout when in sleep mode to wait for wake word
                actual_timeout = 15 if is_sleeping else timeout
                actual_phrase_limit = 10 if is_sleeping else phrase_time_limit

                # Listen for audio
                audio = self.recognizer.listen(
                    source,
                    timeout=actual_timeout,
                    phrase_time_limit=actual_phrase_limit,
                )

                rms = audioop.rms(audio.frame_data, audio.sample_width)
                if rms < self.noise_gate_threshold:
                    logging.debug(
                        f"Noise gate filtered audio with RMS {rms}"
                    )
                    return ""

                duration = len(audio.frame_data) / (
                    audio.sample_rate * audio.sample_width
                )
                if duration < self.min_speech_duration:
                    logging.debug(
                        f"Ignoring speech shorter than {self.min_speech_duration}s"
                    )
                    return ""

                if self.vad:
                    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
                    frame_len = int(16000 * 0.03) * 2
                    if not any(
                        self.vad.is_speech(raw[i : i + frame_len], 16000)
                        for i in range(0, len(raw), frame_len)
                    ):
                        logging.debug("VAD detected no speech")
                        return ""

                # Restore original threshold
                if is_sleeping:
                    self.recognizer.energy_threshold = original_threshold

                print("Processing...")
                logging.info("Processing audio")

                try:
                    # Use the configured language for recognition
                    query = self.recognizer.recognize_google(
                        audio, language=self.language
                    ).lower()

                    # Log what was heard
                    if is_sleeping:
                        print(f"Sleep mode - Heard: '{query}'")
                        logging.info(f"Sleep mode - Heard: {query}")

                        # Check if this contains a wake word
                        wake_patterns = [
                            f"hey {wake_word}",
                            f"wake up {wake_word}",
                            "wake up",
                            f"ok {wake_word}",
                            "hey jarvis",
                            "wake up jarvis",
                            "wake",
                            "jarv",
                            "wake jar",
                        ]

                        contains_wake_word = any(
                            pattern in query.lower() for pattern in wake_patterns
                        )
                        if contains_wake_word:
                            print(f"*** WAKE WORD DETECTED: '{query}' ***")
                            logging.info(f"Wake word detected in: {query}")
                    else:
                        print(f"User: {query}")
                        logging.info(f"User: {query}")

                    return query
                except sr.UnknownValueError:
                    if is_sleeping:
                        logging.debug("Sleep mode: Could not understand audio")
                    else:
                        logging.info("Could not understand audio")
                        print("Could not understand audio")
                    return ""
                except sr.RequestError as e:
                    logging.error(
                        f"Could not request results from speech recognition service: {e}"
                    )
                    print("Could not request results from speech recognition service")
                    return ""
            except sr.WaitTimeoutError:
                # Handle timeout more gracefully
                if is_sleeping:
                    logging.debug("Sleep mode: Listening timed out")
                else:
                    logging.info("Listening timed out. No speech detected.")
                return ""
            except Exception as e:
                logging.error(f"Error during listening: {str(e)}")
                print(f"Error during listening: {str(e)}")
                return ""
