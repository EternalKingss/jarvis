import threading
import time
import logging
from typing import Any

class HealthMonitor:
    """Periodic health checks for critical Jarvis components."""

    def __init__(self, jarvis: Any, interval: int = 90) -> None:
        self.jarvis = jarvis
        self.interval = interval
        self.thread: threading.Thread | None = None
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

    def _monitor(self) -> None:
        while self.running:
            try:
                self._check_microphone()
                self._check_api_keys()
                self._update_system_stats()
            except Exception as exc:  # pragma: no cover - runtime safeguard
                logging.error(f"Health monitor error: {exc}")
            time.sleep(self.interval)

    def _check_microphone(self) -> None:
        try:
            import speech_recognition as sr
            sr.Microphone.list_microphone_names()
        except Exception as exc:
            logging.error(f"Microphone check failed: {exc}")

    def _check_api_keys(self) -> None:
        if self.jarvis.offline_mode:
            return
        try:
            from utils_jarvis.api_helpers import make_api_request
            openai_key = self.jarvis.config_manager.get('API_KEYS', 'openai', '', is_encrypted=True)
            if openai_key:
                resp = make_api_request(
                    url='https://api.openai.com/v1/models',
                    headers={'Authorization': f'Bearer {openai_key}'},
                    timeout=5,
                )
                if not resp.get('success'):
                    logging.error(f"OpenAI API unresponsive: {resp.get('error')}")
            eleven_key = self.jarvis.config_manager.get('API_KEYS', 'elevenlabs', '', is_encrypted=True)
            if self.jarvis.use_elevenlabs and eleven_key:
                resp = make_api_request(
                    url='https://api.elevenlabs.io/v1/voices',
                    headers={'xi-api-key': eleven_key},
                    timeout=5,
                )
                if not resp.get('success'):
                    logging.error(f"ElevenLabs API unresponsive: {resp.get('error')}")
        except Exception as exc:
            logging.error(f"API health check failed: {exc}")


    def _update_system_stats(self) -> None:
        try:
            from system_jarvis.monitor import monitor_system_resources
            stats = monitor_system_resources()
            if stats:
                cpu, mem, disk, _ = stats
                if getattr(self.jarvis, 'interface', None):
                    self.jarvis.interface.emit_health(cpu, mem, disk)
        except Exception as exc:
            logging.error(f"System stats update failed: {exc}")


