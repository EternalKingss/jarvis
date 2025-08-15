"""JarvisAuthentication - simple password authentication."""

from __future__ import annotations

import getpass
import os
import logging
from typing import Optional


class JarvisAuthentication:
    """User authentication for Jarvis."""

    def __init__(self, config_manager) -> None:
        self.config_manager = config_manager
        env_required = os.getenv("JARVIS_AUTH_REQUIRED", "False").lower() == "true"
        
        # Get auth settings from config manager
        self.auth_required = (
            self.config_manager.get("SETTINGS", "user_auth_required", "False").lower() == "true"
            or env_required
        )
        self.password = (
            self.config_manager.get("SETTINGS", "user_password", "", is_encrypted=True)
            or os.getenv("JARVIS_PASSWORD", "")
        )
        self.authenticated = False

    def authenticate_user(self, password_attempt: Optional[str] = None) -> bool:
        """Authenticate user with password."""
        if not self.auth_required:
            self.authenticated = True
            return True

        if not self.password:
            logging.info("No password set. Prompting user to create one.")
            new_password = getpass.getpass("Enter new password: ")
            confirm_password = getpass.getpass("Confirm password: ")
            if new_password == confirm_password:
                self.password = new_password
                self.config_manager.set("SETTINGS", "user_password", new_password, encrypt=True)
                self.config_manager.save_config()
                logging.info("Password set successfully")
                self.authenticated = True
                return True
            logging.warning("Password confirmation failed")
            return False

        if password_attempt:
            if password_attempt == self.password:
                self.authenticated = True
                return True
            return False

        attempts = 0
        while attempts < 3:
            password_attempt = getpass.getpass("Enter password: ")
            if password_attempt == self.password:
                self.authenticated = True
                return True
            attempts += 1
            logging.warning("Invalid password attempt")
            print(f"Invalid password. {3 - attempts} attempts remaining.")

        logging.error("Authentication failed")
        return False
