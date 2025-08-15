"""Simplified entry point for Jarvis."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from dotenv import load_dotenv

# Fixed imports
from config.config_loader import load_config
from config_jarvis.auth import JarvisAuthentication
from core_jarvis.jarvis import Jarvis


def _ensure_requirements() -> None:
    """Install dependencies from requirements.txt if missing."""
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if not os.path.exists(req_path):
        return
    subprocess.call([sys.executable, "-m", "pip", "install", "-r", req_path])


def main() -> None:
    _ensure_requirements()
    load_dotenv()
    from utils_jarvis.log import setup_logging
    setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    
    # Load config manager instance
    config_manager = load_config()
    
    # Pass config manager to auth
    auth = JarvisAuthentication(config_manager)
    if auth.auth_required and not auth.authenticate_user():
        print("Authentication failed. Exiting.")
        return

    jarvis = Jarvis(config_manager)
    try:
        jarvis.run()
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    finally:
        jarvis.shutdown()


if __name__ == "__main__":
    main()
