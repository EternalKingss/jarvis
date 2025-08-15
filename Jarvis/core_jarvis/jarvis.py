"""
Main Jarvis class - Core AI Assistant functionality
"""

import os
import time
import logging
import datetime
import threading
import sys
import pygame
import shutil
import inspect
from typing import Optional, Dict, List, Any, Tuple
import speech_recognition as sr

# Import core modules
from core_jarvis.speech import SpeechEngine
from core_jarvis.conversation import ConversationEngine



# Import config modules

# Import GPT-based command handler
from command_jarvis.gpt_command_handler import GPTCommandHandler

# Import system utilities
from utils_jarvis.system_info import get_system_info
from utils_jarvis.log import setup_logging, rotate_log_file
from utils_jarvis.health_monitor import HealthMonitor
try:
    from utils_jarvis.voice_mode import VoiceModeController, MessageType
except ImportError:
    logging.warning("Voice mode controller not available")
    VoiceModeController = None
    MessageType = type('MessageType', (), {'USER_RESPONSE': 'user_response'})

StatusDashboard = None
TrayIcon = None
SettingsPanel = None


class Jarvis:
    """Main Jarvis AI Assistant Class"""

    def __init__(self, config_manager: dict, interface=None):
        """Initialize Jarvis with the provided configuration."""
        self.interface = interface
        self.config_manager = config_manager

        # Set up logging
        log_level = self.config_manager.get("ADVANCED", "log_level", "INFO")
        setup_logging(log_level)
        rotate_log_file()

        # Load configuration
        self.load_config()

        # Create temp directory for audio files
        from utils_jarvis.file_utils import get_writable_temp_dir

        self.temp_dir = get_writable_temp_dir()

        # Initialize pygame for audio playback
        try:
            pygame.mixer.pre_init(
                frequency=22050,  # Lower frequency for better compatibility
                size=-16,         # 16-bit
                channels=2,       # Stereo
                buffer=512        # Smaller buffer for lower latency
            )
            pygame.mixer.init()
            pygame.mixer.music.set_volume(1.0)  # Set volume to maximum
            self.audio_available = True
            logging.info("Pygame audio initialized successfully")
            print("✓ Audio system initialized")
        except Exception as e:
            logging.warning(f"Could not initialize audio: {e}")
            print(f"⚠️ Audio initialization failed: {e}")
            self.audio_available = False

        # Get system information
        self.system_info = get_system_info()

        # Initialize core components
        self.speech_engine = SpeechEngine(self.config_manager, self.temp_dir)

        # Initialize voice mode controller for managing speech output
        if VoiceModeController:
            self.voice_controller = VoiceModeController(self.config_manager)
        else:
            # Create a dummy controller that always allows speech
            self.voice_controller = type('VoiceController', (), {
                'should_speak': lambda self, msg_type, critical: True
            })()

        # IMPORTANT: Set jarvis instance reference in speech engine for sleep mode awareness
        self.speech_engine.jarvis_instance = self

        self.conversation_engine = ConversationEngine(self.config_manager)
        self.recognizer = sr.Recognizer()

        self.dashboard = None
        self.tray_icon = None

        # Initialize GPT-based command handler
        self.gpt_handler = GPTCommandHandler(self, self.config_manager)
        self.health_monitor = HealthMonitor(self)

        # Container for commands registered at runtime
        self.custom_commands: Dict[str, Any] = {}

        # Flag to track when speaking (to prevent self-activation)
        self.is_speaking = False

        # Initialize sleep monitor
        self.sleep_monitor = type('SleepMonitor', (), {
            'is_sleeping': False,
            'wake_word': self.wake_word
        })()
        
        # Start health monitor
        self.health_monitor.start()
        # Play startup video if enabled
        if self.enable_video_startup:
            self.play_startup_video()

        # Announce initialization
        logging.info("Jarvis initialized")
        self.speak("Initializing Jarvis. All systems are now online.")

        # Print debug info if debug mode is enabled
        if self.debug_mode:
            self.print_debug_info()


    def listen(self, timeout: int = 5, phrase_time_limit: int = 5) -> str:
        """Listen to user voice input - delegate to speech engine"""
        return self.speech_engine.listen(timeout, phrase_time_limit)

    def load_config(self):
        """Load configuration from config manager"""
        try:
            # Load API Keys (encrypted)
            self.OPENAI_API_KEY = self.config_manager.get(
                "API_KEYS", "openai", "", is_encrypted=True
            )
            self.YOUTUBE_API_KEY = self.config_manager.get(
                "API_KEYS", "youtube", "", is_encrypted=True
            )
            self.ELEVENLABS_API_KEY = self.config_manager.get(
                "API_KEYS", "elevenlabs", "", is_encrypted=True
            )

            # Load ElevenLabs settings
            self.use_elevenlabs = (
                self.config_manager.get("ELEVENLABS", "enabled", "False").lower()
                == "true"
            )
            self.elevenlabs_voice_id = self.config_manager.get(
                "ELEVENLABS", "voice_id", "EXAVITQu4vr4xnSDxMaL"
            )
            self.elevenlabs_model_id = self.config_manager.get(
                "ELEVENLABS", "model_id", "eleven_multilingual_v2"
            )

            # If ElevenLabs is enabled but no API key, disable it
            if self.use_elevenlabs and not self.ELEVENLABS_API_KEY:
                logging.warning(
                    "ElevenLabs is enabled but no API key is provided. Disabling ElevenLabs."
                )
                self.use_elevenlabs = False

            # Load settings
            self.sleep_timeout = int(
                self.config_manager.get("SETTINGS", "sleep_timeout", "120")
            )
            self.language = self.config_manager.get("SETTINGS", "language", "en-US")
            self.openai_voice = self.config_manager.get("SETTINGS", "voice", "alloy")
            self.enable_video_startup = (
                self.config_manager.get("SETTINGS", "startup_video", "True").lower()
                == "true"
            )
            self.startup_video_path = self.config_manager.get(
                "SETTINGS", "startup_video_path", ""
            )
            self.wake_word = self.config_manager.get(
                "SETTINGS", "wake_word", "jarvis"
            ).lower()

            # Load advanced settings
            self.energy_threshold = float(
                self.config_manager.get("ADVANCED", "energy_threshold", "3000")
            )
            self.pause_threshold = float(
                self.config_manager.get("ADVANCED", "pause_threshold", "0.5")
            )
            self.tts_rate = int(self.config_manager.get("ADVANCED", "tts_rate", "180"))
            self.offline_mode = (
                self.config_manager.get("ADVANCED", "offline_mode", "False").lower()
                == "true"
            )
            self.debug_mode = (
                self.config_manager.get("ADVANCED", "debug_mode", "False").lower()
                == "true"
            )
            self.silent_background_mode = (
                self.config_manager.get(
                    "ADVANCED", "silent_background_mode", "False"
                ).lower()
                == "true"
            )

            # Email settings
            self.email_enabled = (
                self.config_manager.get("EMAIL", "enabled", "False").lower() == "true"
            )
            self.email_address = self.config_manager.get("EMAIL", "email_address", "")
            self.email_password = self.config_manager.get(
                "EMAIL", "email_password", "", is_encrypted=True
            )
            self.imap_server = self.config_manager.get(
                "EMAIL", "imap_server", "imap.gmail.com"
            )
            self.imap_port = int(self.config_manager.get("EMAIL", "imap_port", "993"))

            logging.info("Configuration loaded successfully")
        except Exception as e:
            logging.error(f"Error loading configuration: {str(e)}")
            # Use default values if config fails
            self.OPENAI_API_KEY = ""
            self.YOUTUBE_API_KEY = ""
            self.ELEVENLABS_API_KEY = ""
            self.use_elevenlabs = False
            self.elevenlabs_voice_id = "EXAVITQu4vr4xnSDxMaL"
            self.elevenlabs_model_id = "eleven_multilingual_v2"
            self.sleep_timeout = 120
            self.language = "en-US"
            self.openai_voice = "alloy"
            self.enable_video_startup = True
            self.startup_video_path = ""
            self.wake_word = "jarvis"
            self.energy_threshold = 3000.0
            self.pause_threshold = 0.5
            self.tts_rate = 180
            self.offline_mode = False
            self.debug_mode = False
            self.silent_background_mode = False
            self.email_enabled = False

    def print_debug_info(self):
        """Print debug information about the system"""
        print("\n===== JARVIS DEBUG INFORMATION =====")
        print(f"Operating System: {self.system_info['os']}")
        print(f"Machine: {self.system_info['machine']}")
        print(f"Processor: {self.system_info['processor']}")
        print(f"Hostname: {self.system_info['hostname']}")
        print(f"IP Address: {self.system_info['ip']}")
        print(f"Language: {self.system_info['language']}")
        print(
            f"Available Memory: {round(self.system_info['memory'].total / (1024**3), 2)} GB"
        )

        # TTS info
        if self.use_elevenlabs:
            print(f"Voice System: ElevenLabs")
            print(f"ElevenLabs Voice ID: {self.elevenlabs_voice_id}")
        else:
            print(f"Voice System: OpenAI TTS")
            print(f"TTS Voice: {self.openai_voice}")

        print(f"Wake Word: {self.wake_word}")

        # Print optional features status
        print("\n--- Optional Features Status ---")
        print(f"Offline Mode: {'Enabled' if self.offline_mode else 'Disabled'}")
        print(f"Email: {'Enabled' if self.email_enabled else 'Disabled'}")



        print("===================================\n")

    def play_startup_video(self):
        """Play the Jarvis startup video"""
        from system_jarvis.hardware import play_video

        if not self.enable_video_startup or not os.path.exists(self.startup_video_path):
            logging.warning(
                f"Startup video not found or disabled: {self.startup_video_path}"
            )
            return

        logging.info("Playing Jarvis startup sequence")
        print("Playing Jarvis startup sequence...")

        play_video(self.startup_video_path)

        print("Startup video completed")
        logging.info("Startup video completed")

    def speak(
        self,
        text: str,
        translate_to: Optional[str] = None,
        message_type: str = None,
        critical: bool = False,
    ) -> None:
        """Text-to-speech wrapper that respects voice mode settings"""
        if not text:
            return

        caller = inspect.stack()[1].function
        logging.debug(f"Speech requested by {caller}: {text}")
        
        # Always speak for now - bypass voice controller check
        # if not self.voice_controller.should_speak(message_type, critical):
        #     self.log_internal(text)
        #     return

        # Provide defaults during unit tests when attributes may be missing
        if not hasattr(self, "is_speaking"):
            self.is_speaking = False
        if not hasattr(self, "speech_engine"):
            print(text)
            return

        while self.is_speaking:
            time.sleep(0.05)

        self.is_speaking = True
        self.speech_engine.speak(text, translate_to)
        # Give the microphone time to settle before listening again
        time.sleep(2)
        if hasattr(self.speech_engine, "clear_microphone_buffer"):
            self.speech_engine.clear_microphone_buffer()
        self.is_speaking = False

        # Reset activity timer when speaking

    # ------------------------------------------------------------------
    # Helper methods for separating user speech from internal logging
    # ------------------------------------------------------------------
    def speak_to_user(self, text: str, translate_to: Optional[str] = None) -> None:
        """Public facing speech output."""
        self.speak(text, translate_to)

    def log_internal(self, text: str, level: int = logging.INFO) -> None:
        """Log internal messages that shouldn't be spoken."""
        logging.log(level, text)
        if getattr(self, "interface", None):
            self.interface.emit_log(logging.getLevelName(level), text)

    def register_command(self, command: str, handler: Any) -> None:
        """Register a custom command at runtime."""
        if not callable(handler):
            raise ValueError("Handler must be callable")
        self.custom_commands[command.lower()] = handler


    def set_debug_mode(self, enabled: bool) -> None:
        """Toggle debug logging level."""
        self.debug_mode = enabled
        logging.getLogger("").setLevel(logging.DEBUG if enabled else logging.INFO)

    def open_settings_panel(self) -> None:
        """Show the settings window."""
        if SettingsPanel:
            SettingsPanel(self)

    def emergency_stop(self) -> None:
        """Immediately stop speech and clear task queue."""
        try:
            if hasattr(self, "speech_engine"):
                self.speech_engine.stop()
        except Exception:
            pass
        self.is_speaking = False
        if getattr(self, "interface", None):
            self.interface.emit_status("Emergency stop")

    def shutdown(self):
        """Shutdown Jarvis cleanly."""
        try:
            logging.info("Shutting down Jarvis...")
            if hasattr(self, "health_monitor"):
                self.health_monitor.stop()
                logging.info("Health monitor stopped")

            # Clean up temp directory
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logging.info("Temporary directory cleaned up")

            # Quit pygame
            if pygame.get_init():
                pygame.quit()
                logging.info("Pygame shut down")

            logging.info("Jarvis shutdown complete")

        except Exception as e:
            logging.error(f"Error during shutdown: {str(e)}")

    def run(self):
        """Main loop with continuous microphone listening"""
        try:
            logging.info("Starting main event loop")
            if getattr(self, "interface", None):
                self.interface.emit_status("Ready")
            print("Jarvis is ready.")

            welcome_message = (
                f"Hello. I am {self.wake_word.capitalize()}, your personal AI assistant. "
                "How can I assist you today?"
            )
            self.speak(welcome_message)

            while True:
                try:
                    if getattr(self, "interface", None):
                        self.interface.emit_status("Listening...")
                    command = self.listen(timeout=5)
                    if command:
                        if getattr(self, "interface", None):
                            self.interface.emit_status("Processing command...")
                        self.process_command(command)
                except Exception as listen_error:
                    logging.error(f"Error in main listening loop: {listen_error}")
                    time.sleep(1)
        except KeyboardInterrupt:
            self.speak("Shutting down. Goodbye.")
            logging.info("Jarvis shutdown by keyboard interrupt")
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logging.error(error_msg)
            print(error_msg)
            self.speak("I've encountered an error. Please restart me.")
        finally:
            self.shutdown()
    def process_command(self, command: str) -> bool:
        """Process a command using the GPT handler"""
        if not command:
            return False

        cmd = command.strip()
        print(f"Processing command: '{cmd}'")
        logging.info(f"Processing command: '{cmd}'")
        result = self.gpt_handler.handle_input(cmd)
        return result
