"""Entry point helpers for launching Jarvis."""

from __future__ import annotations

import logging

from config import load_config, JarvisAuthentication
from core import Jarvis
from utils import setup_logging


def run_jarvis() -> None:
    """Load configuration, authenticate user and start Jarvis."""
    setup_logging()
    config = load_config()

    auth = JarvisAuthentication(config)
    if auth.auth_required and not auth.authenticate_user():
        print("Authentication failed. Exiting.")
        return

    assistant = Jarvis(config)
    try:
        assistant.run()
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    finally:
        assistant.shutdown()


if __name__ == "__main__":
    run_jarvis()
