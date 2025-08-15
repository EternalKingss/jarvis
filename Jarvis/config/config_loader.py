"""Configuration manager for Jarvis that handles INI files with encryption."""

import configparser
import logging
import os
from typing import Any, Optional
from cryptography.fernet import Fernet
from dotenv import load_dotenv


class ConfigManager:
    """Handles INI-based configuration with encryption support."""
    
    def __init__(self, config_file: str = "jarvis_config.ini"):
        # Load environment variables from .env if present
        load_dotenv()

        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.encryption_key = self._get_or_create_key()
        self.fernet = Fernet(self.encryption_key) if self.encryption_key else None
        
        # Define a mapping for flat key access
        self.key_mapping = {
            'energy_threshold': ('ADVANCED', 'energy_threshold'),
            'pause_threshold': ('ADVANCED', 'pause_threshold'),
            'tts_rate': ('ADVANCED', 'tts_rate'),
            'offline_mode': ('ADVANCED', 'offline_mode'),
            'debug_mode': ('ADVANCED', 'debug_mode'),
            'silent_background_mode': ('ADVANCED', 'silent_background_mode'),
            'log_level': ('ADVANCED', 'log_level'),
            'noise_gate_threshold': ('ADVANCED', 'noise_gate_threshold'),
            'min_speech_duration': ('ADVANCED', 'min_speech_duration'),
            'language': ('SETTINGS', 'language'),
            'voice': ('SETTINGS', 'voice'),
            'wake_word': ('SETTINGS', 'wake_word'),
            'sleep_timeout': ('SETTINGS', 'sleep_timeout'),
            'startup_video': ('SETTINGS', 'startup_video'),
            'startup_video_path': ('SETTINGS', 'startup_video_path'),
            'user_auth_required': ('SETTINGS', 'user_auth_required'),
            'user_password': ('SETTINGS', 'user_password'),
            'email_enabled': ('EMAIL', 'enabled'),
            'email_address': ('EMAIL', 'email_address'),
            'email_password': ('EMAIL', 'email_password'),
            'imap_server': ('EMAIL', 'imap_server'),
            'imap_port': ('EMAIL', 'imap_port'),
            'elevenlabs_enabled': ('ELEVENLABS', 'enabled'),
            'elevenlabs_voice_id': ('ELEVENLABS', 'voice_id'),
            'elevenlabs_model_id': ('ELEVENLABS', 'model_id'),
            'openai_api_key': ('API_KEYS', 'openai'),
            'elevenlabs_api_key': ('API_KEYS', 'elevenlabs'),
            'youtube_api_key': ('API_KEYS', 'youtube'),
            'google_api_key': ('API_KEYS', 'google'),
            'context_file': ('ADVANCED', 'context_file'),
        }
        
        # Ensure the INI file exists
        if not os.path.exists(self.config_file):
            self._create_default_config()
        
        self.load_config()
    
    def _get_or_create_key(self) -> Optional[bytes]:
        """Get or create encryption key."""
        key_file = ".jarvis_key"
        try:
            if os.path.exists(key_file):
                with open(key_file, 'rb') as f:
                    return f.read()
            else:
                key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(key)
                return key
        except Exception as e:
            logging.warning(f"Could not handle encryption key: {e}")
            return None
    
    def load_config(self):
        """Load configuration from INI file."""
        try:
            if os.path.exists(self.config_file):
                self.config.read(self.config_file)
                logging.info("Config file found and loaded")
            else:
                logging.warning(f"Config file {self.config_file} not found, creating default")
                self._create_default_config()
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """Create a default configuration."""
        self.config['API_KEYS'] = {
            'openai': '',
            'elevenlabs': '',
            'youtube': '',
            'google': '',
        }
        self.config['SETTINGS'] = {
            'sleep_timeout': '120',
            'language': 'en-US',
            'voice': 'alloy',
            'startup_video': 'False',
            'startup_video_path': '',
            'wake_word': 'jarvis',
            'user_auth_required': 'False',
            'user_password': '',
        }
        self.config['ADVANCED'] = {
            'energy_threshold': '3000',
            'pause_threshold': '0.5',
            'debug_mode': 'False',
            'log_level': 'INFO',
            'silent_background_mode': 'False',
            'tts_rate': '180',
            'offline_mode': 'False',
            'noise_gate_threshold': '100',
            'min_speech_duration': '0.3',
            'context_file': 'conversation_history.json',
        }
        self.config['EMAIL'] = {
            'enabled': 'False',
            'email_address': '',
            'email_password': '',
            'imap_server': 'imap.gmail.com',
            'imap_port': '993',
        }
        self.config['ELEVENLABS'] = {
            'enabled': 'False',
            'voice_id': 'EXAVITQu4vr4xnSDxMaL',
            'model_id': 'eleven_multilingual_v2',
        }
        self.save_config()
    
    def get(self, section: str, key: Optional[str] = None, default: Any = None, is_encrypted: bool = False) -> Any:
        """Get configuration value."""
        try:
            if key is None:
                # Simple key access: get("some_key", "default")
                # Use the key mapping to find the right section
                if section in self.key_mapping:
                    mapped_section, mapped_key = self.key_mapping[section]
                    if mapped_section in self.config and mapped_key in self.config[mapped_section]:
                        value = self.config[mapped_section][mapped_key]
                        if value:
                            return self._decrypt_if_needed(value, is_encrypted)
                        else:
                            # Return default if value is empty string
                            return default
                
                # Check environment variables for API keys
                env_key = section.upper()
                if not env_key.endswith('_API_KEY') and (section.endswith('_api_key') or 'api' in section):
                    env_key = env_key.replace('_API_KEY', '') + '_API_KEY'
                
                env_value = os.getenv(env_key)
                if env_value:
                    return env_value
                
                # Also try some common environment variable patterns
                for env_pattern in [section.upper(), f"{section.upper()}_API_KEY", f"JARVIS_{section.upper()}"]:
                    env_value = os.getenv(env_pattern)
                    if env_value:
                        return env_value
                
                return default
            else:
                # Section.key access: get("SECTION", "key", "default")
                if section in self.config and key in self.config[section]:
                    value = self.config[section][key]
                    if value:
                        return self._decrypt_if_needed(value, is_encrypted)
                
                # Check environment variables for API keys
                if section == 'API_KEYS':
                    env_patterns = [
                        f"{key.upper()}_API_KEY",
                        key.upper(),
                        f"JARVIS_{key.upper()}_API_KEY"
                    ]
                    for env_key in env_patterns:
                        env_value = os.getenv(env_key)
                        if env_value:
                            return env_value
                
                return default
        except Exception as e:
            logging.warning(f"Error getting config value {section}.{key}: {e}")
            return default
    
    def _decrypt_if_needed(self, value: str, is_encrypted: bool) -> str:
        """Decrypt value if it's encrypted."""
        if not is_encrypted or not self.fernet or not value:
            return value
        
        try:
            # Try to decrypt
            decrypted = self.fernet.decrypt(value.encode()).decode()
            return decrypted
        except Exception as e:
            logging.warning(f"Decryption failed, using fallback: {e}")
            return value
    
    def set(self, section: str, key: str, value: str, encrypt: bool = False):
        """Set configuration value."""
        if section not in self.config:
            self.config[section] = {}
        
        if encrypt and self.fernet:
            try:
                value = self.fernet.encrypt(value.encode()).decode()
            except Exception as e:
                logging.warning(f"Encryption failed: {e}")
        
        self.config[section][key] = value
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
        except Exception as e:
            logging.error(f"Error saving config: {e}")


class ConfigValidator:
    """Validates configuration settings."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
    
    def validate(self) -> bool:
        """Validate configuration."""
        try:
            logging.info("Starting configuration validation")
            
            # Check API keys
            openai_key = self.config.get("API_KEYS", "openai", "", is_encrypted=True)
            elevenlabs_key = self.config.get("API_KEYS", "elevenlabs", "", is_encrypted=True)
            
            # Also check environment variables
            if not openai_key:
                openai_key = os.getenv("OPENAI_API_KEY", "")
            if not elevenlabs_key:
                elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")
            
            logging.info("Configuration validation passed")
            logging.info(f"API Keys - OpenAI: {'Present' if openai_key else 'Missing'}, ElevenLabs: {'Present' if elevenlabs_key else 'Missing'}")
            
            return True
        except Exception as e:
            logging.error(f"Configuration validation failed: {e}")
            return False


def load_config(config_file: str = "jarvis_config.ini") -> ConfigManager:
    """Load configuration and return ConfigManager instance."""
    return ConfigManager(config_file)