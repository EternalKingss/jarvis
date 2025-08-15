"""
System Commands - Handles system operations and hardware interactions
"""

import os
import logging
import datetime
import subprocess
import psutil
import re
from typing import Any, Dict, List, Optional, Tuple

from config_jarvis.settings import ELEVENLABS_VOICE_IDS, OPENAI_VOICES

# Import system utilities
from system_jarvis.hardware import adjust_volume, take_screenshot
from system_jarvis.monitor import (
    monitor_system_resources,
    list_processes,
    terminate_process,
    monitor_network,
    analyze_disk_usage,
)
from system_jarvis.process import kill_processes_by_name
from utils_jarvis.shell_executor import ShellCommandExecutor


class SystemCommands:
    """System operation commands and hardware interactions"""
    
    def __init__(self, jarvis_instance: Any, config: dict):
        """Initialize system commands with Jarvis instance and configuration"""
        self.jarvis = jarvis_instance
        self.config = config
        
        # Email capabilities check
        try:
            import imaplib
            import email
            from email.header import decode_header
            self.HAVE_EMAIL = True
        except ImportError:
            self.HAVE_EMAIL = False
            logging.warning("Email libraries not available - email features will be disabled")

        # Translator capabilities check
        try:
            from googletrans import Translator
            self.translator = Translator()
            self.HAVE_TRANSLATOR = True
        except ImportError:
            self.HAVE_TRANSLATOR = False
            logging.warning("Translator not available - multi-language support will be limited")
        except Exception as e:
            self.HAVE_TRANSLATOR = False
            logging.error(f"Error initializing translator: {str(e)}")

        # Shell command executor for secure command execution
        self.shell_executor = ShellCommandExecutor(jarvis_instance)
    
    def shutdown_computer(self) -> bool:
        """Shutdown the computer"""
        try:
            self.jarvis.speak("Initiating shutdown sequence. Your computer will shut down in 30 seconds. Say 'cancel shutdown' if you want to stop it.")
            os.system("shutdown /s /t 30")
            logging.info("Initiated computer shutdown with 30-second delay")
            return True
        except Exception as e:
            logging.error(f"Error initiating shutdown: {str(e)}")
            self.jarvis.speak("I had trouble initiating shutdown")
            return False
    
    def restart_computer(self) -> bool:
        """Restart the computer"""
        try:
            self.jarvis.speak("Initiating restart. Your computer will restart in 30 seconds. Say 'cancel shutdown' if you want to stop it.")
            os.system("shutdown /r /t 30")
            logging.info("Initiated computer restart with 30-second delay")
            return True
        except Exception as e:
            logging.error(f"Error initiating restart: {str(e)}")
            self.jarvis.speak("I had trouble initiating restart")
            return False
    
    def cancel_shutdown(self) -> bool:
        """Cancel a pending shutdown"""
        try:
            os.system("shutdown /a")
            self.jarvis.speak("Shutdown canceled")
            logging.info("Canceled pending shutdown")
            return True
        except Exception as e:
            logging.error(f"Error canceling shutdown: {str(e)}")
            self.jarvis.speak("I had trouble canceling the shutdown")
            return False
    
    def lock_computer(self) -> bool:
        """Lock the computer"""
        try:
            os.system("rundll32.exe user32.dll,LockWorkStation")
            self.jarvis.speak("Locking your computer")
            logging.info("Locked computer")
            return True
        except Exception as e:
            logging.error(f"Error locking computer: {str(e)}")
            self.jarvis.speak("I had trouble locking your computer")
            return False
    
    def empty_recycle_bin(self) -> bool:
        """Empty the Windows Recycle Bin"""
        try:
            # Try with winshell if available
            try:
                import winshell
                winshell.recycle_bin().empty(confirm=False, show_progress=False)
            except ImportError:
                # Alternative method using os.system
                os.system('rd /s /q C:\\$Recycle.Bin')
                
            self.jarvis.speak("Recycle bin emptied")
            logging.info("Emptied recycle bin")
            return True
        except Exception as e:
            logging.error(f"Error emptying recycle bin: {str(e)}")
            self.jarvis.speak("I had trouble emptying the recycle bin")
            return False
    
    def adjust_volume(self, direction: str) -> bool:
        """Adjust system volume (wrapper for hardware module)"""
        result = adjust_volume(direction)
        
        if result:
            if direction == "up":
                self.jarvis.speak("Volume increased")
            elif direction == "down":
                self.jarvis.speak("Volume decreased")
            elif direction == "mute":
                self.jarvis.speak("Volume muted")
            return True
        else:
            self.jarvis.speak("I had trouble adjusting the volume")
            return False
    
    def take_screenshot(self) -> bool:
        """Take a screenshot (wrapper for hardware module)"""
        screenshot_path = take_screenshot()
        
        if screenshot_path:
            self.jarvis.speak(f"Screenshot saved to {screenshot_path}")
            return True
        else:
            self.jarvis.speak("I had trouble taking a screenshot")
            return False
    
    def get_current_time(self) -> str:
        """Get the current time formatted nicely"""
        return datetime.datetime.now().strftime("%I:%M %p")
    
    def get_current_date(self) -> str:
        """Get the current date formatted nicely"""
        return datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    def check_system_status(self) -> bool:
        """Check and report system status"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Fix for Windows - use C: drive instead of root
            import os
            if os.name == 'nt':  # Windows
                disk = psutil.disk_usage('C:')
            else:
                disk = psutil.disk_usage('/')
                
            battery = None
            try:
                battery = psutil.sensors_battery()
            except:
                pass

            # FIXED: More robust string building
            try:
                # Try using f-strings first
                cpu_str = f"{cpu_percent:.1f}"
                memory_str = f"{memory.percent:.1f}"
                disk_str = f"{disk.percent:.1f}"
                
                status_message = f"CPU usage: {cpu_str} percent. Memory usage: {memory_str} percent. Disk usage: {disk_str} percent"
                
                if battery and battery.percent is not None:
                    battery_str = f"{battery.percent:.1f}"
                    status_message += f". Battery: {battery_str} percent"
                
                status_message += "."
                
            except Exception as format_error:
                # Fallback to safer string concatenation
                logging.warning(f"String formatting failed, using fallback: {format_error}")
                
                cpu_str = str(round(cpu_percent, 1))
                memory_str = str(round(memory.percent, 1))
                disk_str = str(round(disk.percent, 1))
                
                status_message = "CPU usage: " + cpu_str + " percent. "
                status_message += "Memory usage: " + memory_str + " percent. "
                status_message += "Disk usage: " + disk_str + " percent"
                
                if battery and battery.percent is not None:
                    battery_str = str(round(battery.percent, 1))
                    status_message += ". Battery: " + battery_str + " percent"
                
                status_message += "."
            
            self.jarvis.speak(status_message)
            
            # Also log the status safely
            try:
                logging.info(f"System status reported - CPU: {cpu_percent:.1f}%, Memory: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%")
            except:
                logging.info("System status reported - CPU: " + str(cpu_percent) + "%, Memory: " + str(memory.percent) + "%, Disk: " + str(disk.percent) + "%")
            
            return True
            
        except Exception as e:
            logging.error("Error checking system status: " + str(e))
            self.jarvis.speak("I encountered an error checking your system status.")
            return False
        
    def terminate_process(self, process_name: str) -> bool:
        """Terminate a process (wrapper for monitor module)"""
        result = terminate_process(process_name)
        
        if result:
            self.jarvis.speak(f"Terminated processes matching {process_name}")
            return True
        else:
            self.jarvis.speak(f"No processes found matching {process_name}")
            return False
    
    def monitor_network(self) -> bool:
        """Monitor network connections (wrapper for monitor module)"""
        result = monitor_network()
        
        if result is not None:
            status_counts, interfaces = result
            
            # Report results
            self.jarvis.speak("Network connection summary:")
            for status, count in status_counts.items():
                self.jarvis.speak(f"{count} connections in {status} state")
            
            # Report interfaces
            for interface_name, address in interfaces[:2]:  # Report first 2
                self.jarvis.speak(f"Interface {interface_name}: {address}")
            
            return True
        else:
            self.jarvis.speak("I encountered an error while monitoring the network.")
            return False
    
    def execute_command(self, command: str) -> bool:
        """Execute a system command using the secure shell executor."""
        from utils_jarvis import sanitize_text

        safe_command = sanitize_text(command)
        try:
            return self.shell_executor.execute(safe_command)
        except Exception as e:
            logging.error(f"Error executing system command: {str(e)}")
            self.jarvis.speak(f"I encountered an error while executing the command: {str(e)}")
            return False

    def execute_shell_command(self, command: str) -> bool:
        """Public wrapper for shell command execution"""
        return self.execute_command(command)
    
    def analyze_disk_usage(self, path: Optional[str] = None) -> bool:
        """Analyze disk usage (wrapper for monitor module)"""
        result = analyze_disk_usage(path)
        
        if result is not None:
            total_size, file_count, dir_count, large_files = result
            
            # Report findings
            self.jarvis.speak(f"Analysis complete. Found {file_count} files in {dir_count} directories.")
            self.jarvis.speak(f"Total size is {total_size / (1024**3):.2f} gigabytes.")

            if large_files:
                self.jarvis.speak(f"Found {len(large_files)} files larger than 100 megabytes.")

                for i, (file_name, size) in enumerate(large_files[:3], 1):  # Top 3
                    self.jarvis.speak(f"{i}. {file_name}: {size / (1024**2):.2f} MB")
            
            return True
        else:
            self.jarvis.speak("I encountered an error while analyzing disk usage.")
            return False
    
    def check_email(self) -> bool:
        """Check unread emails"""
        if not self.HAVE_EMAIL:
            self.jarvis.speak("Email functionality is not available. Please install the required packages.")
            return False
            
        email_enabled = str(self.config.get('email_enabled', 'False')).lower() == 'true'
        if not email_enabled:
            self.jarvis.speak("Email functionality is not enabled. Please enable it in the configuration.")
            return False
            
        # Get email settings
        email_address = self.config.get('email_address', '')
        email_password = self.config.get('email_password', '')
        imap_server = self.config.get('imap_server', 'imap.gmail.com')
        imap_port = int(self.config.get('imap_port', 993))
        
        if not email_address or not email_password:
            self.jarvis.speak("Email address or password not configured. Please update your settings.")
            return False
            
        try:
            import imaplib
            import email
            from email.header import decode_header
            
            # Connect to the IMAP server
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(email_address, email_password)
            mail.select('inbox')

            # Search for unread emails
            status, data = mail.search(None, 'UNSEEN')

            if status != 'OK':
                self.jarvis.speak("I had trouble accessing your emails.")
                return False

            email_ids = data[0].split()

            if not email_ids:
                self.jarvis.speak("You have no unread emails.")
                return True

            # Get the 5 most recent unread emails
            recent_emails = email_ids[-5:] if len(email_ids) > 5 else email_ids

            self.jarvis.speak(f"You have {len(email_ids)} unread emails. Here are the most recent ones:")

            for e_id in recent_emails:
                status, msg_data = mail.fetch(e_id, '(RFC822)')

                if status != 'OK':
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()

                # Get sender
                from_ = msg.get("From", "")
                sender_match = re.search(r'<(.+?)>', from_)
                if sender_match:
                    sender = sender_match.group(1)
                else:
                    sender = from_

                self.jarvis.speak(f"Email from {sender} with subject: {subject}")

            mail.close()
            mail.logout()
            return True

        except Exception as e:
            logging.error(f"Error checking email: {str(e)}")
            self.jarvis.speak("I encountered an error checking your email.")
            return False
    
    def translate_text(self, text: str, target_language: str) -> bool:
        """Translate text to another language"""
        if not self.HAVE_TRANSLATOR:
            self.jarvis.speak("Translation functionality is not available. Please install the googletrans package.")
            return False

        try:
            # Normalize language code
            language_map = {
                "english": "en",
                "spanish": "es",
                "french": "fr",
                "german": "de",
                "italian": "it",
                "portuguese": "pt",
                "russian": "ru",
                "japanese": "ja",
                "korean": "ko",
                "chinese": "zh-cn",
                "arabic": "ar",
                "hindi": "hi",
            }

            # Get the language code
            lang_code = None
            for lang, code in language_map.items():
                if lang in target_language.lower():
                    lang_code = code
                    break

            if not lang_code:
                lang_code = target_language  # Use as is if not found

            # Translate the text
            translated = self.translator.translate(text, dest=lang_code)

            # Speak the result
            self.jarvis.speak(f"The translation to {target_language} is: {translated.text}")

            # Also speak the translation in the target language
            self.jarvis.speak(translated.text, translate_to=lang_code)

            logging.info(f"Translated '{text}' to {target_language}")
            return True

        except Exception as e:
            logging.error(f"Error translating text: {str(e)}")
            self.jarvis.speak("I encountered an error while translating.")
            return False
    
    def create_reminder(self, reminder_text: str) -> bool:
        """Create a simple reminder (written to a local file)"""
        try:
            reminders_file = os.path.join(os.path.expanduser("~"), "jarvis_reminders.txt")

            # Get current date and time
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            # Add reminder to file
            with open(reminders_file, "a") as f:
                f.write(f"{timestamp}: {reminder_text}\n")

            self.jarvis.speak(f"I've created a reminder: {reminder_text}")
            logging.info(f"Created reminder: {reminder_text}")
            return True
        except Exception as e:
            logging.error(f"Error creating reminder: {str(e)}")
            self.jarvis.speak("I had trouble creating your reminder")
            return False
    
    def toggle_voice_system(self) -> bool:
        """Toggle between ElevenLabs and OpenAI TTS"""
        elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        
        if elevenlabs_key:
            current_setting = str(self.config.get('elevenlabs_enabled', 'False'))
            new_setting = 'False' if current_setting.lower() == 'true' else 'True'
            self.config['elevenlabs_enabled'] = new_setting

            if new_setting == 'True':
                self.jarvis.speak("Switched to ElevenLabs voice system.")
                logging.info("Switched to ElevenLabs voice system")
            else:
                self.jarvis.speak("Switched to OpenAI voice system.")
                logging.info("Switched to OpenAI voice system")

            return True
        else:
            self.jarvis.speak("ElevenLabs API key is not configured. Please add your API key to use ElevenLabs voices.")
            return False
    
    def change_voice(self, voice_name: str) -> bool:
        """Change the voice used for TTS"""
        voice_name = voice_name.lower()
        
        # Check for ElevenLabs voices
        for name, voice_id in ELEVENLABS_VOICE_IDS.items():
            if voice_name == name.lower():
                self.config['elevenlabs_voice_id'] = voice_id
                self.config['elevenlabs_enabled'] = 'True'
                self.jarvis.speak(f"Switched to ElevenLabs voice: {name}")
                return True
        
        # Check for OpenAI voices
        for voice in OPENAI_VOICES:
            if voice_name == voice.lower():
                self.config['voice'] = voice.lower()
                self.config['elevenlabs_enabled'] = 'False'
                self.jarvis.speak(f"Switched to OpenAI voice: {voice}")
                return True
        
        # Voice not found
        self.jarvis.speak(f"Voice '{voice_name}' not found. Please specify a valid voice name.")
        return False
    
    def list_voices(self) -> bool:
        """List available voices"""
        # Get current voice system and voice
        use_elevenlabs = str(self.config.get('elevenlabs_enabled', 'False')).lower() == 'true'
        elevenlabs_voice_id = self.config.get('elevenlabs_voice_id', '')
        openai_voice = self.config.get('voice', 'alloy')
        
        # Map ElevenLabs voice IDs to names
        elevenlabs_voice_map = {v: k for k, v in ELEVENLABS_VOICE_IDS.items()}
        
        if use_elevenlabs:
            current_system = "ElevenLabs"
            current_voice = elevenlabs_voice_map.get(elevenlabs_voice_id, "Unknown")
        else:
            current_system = "OpenAI"
            current_voice = openai_voice.capitalize()
        
        # List available voices
        elevenlabs_voices = list(ELEVENLABS_VOICE_IDS.keys())
        openai_voices = [v.capitalize() for v in OPENAI_VOICES]
        
        self.jarvis.speak(f"I'm currently using {current_system} voice system with the voice {current_voice}.")
        self.jarvis.speak(f"Available ElevenLabs voices are: {', '.join(elevenlabs_voices)}.")
        self.jarvis.speak(f"Available OpenAI voices are: {', '.join(openai_voices)}.")

        return True

    def monitor_system_resources(self) -> bool:
        """Report basic system resource usage."""
        result = monitor_system_resources()
        if not result:
            self.jarvis.speak("I couldn't retrieve the system status.")
            return False

        cpu_percent, memory_percent, disk_percent, _ = result
        self.jarvis.speak(
            f"CPU usage {cpu_percent:.1f} percent. Memory usage {memory_percent:.1f} percent. Disk usage {disk_percent:.1f} percent."
        )
        return True

    def list_processes(self) -> bool:
        """List top running processes."""
        processes = list_processes()
        if not processes:
            self.jarvis.speak("No processes found.")
            return False

        for name, cpu, mem in processes:
            self.jarvis.speak(f"{name} using {cpu:.1f}% CPU and {mem:.1f}% memory")
        return True

    def kill_processes_by_name(self, name: str) -> bool:
        """Kill all processes matching the given name."""
        count = kill_processes_by_name(name)
        if count:
            self.jarvis.speak(f"Killed {count} processes named {name}")
            return True

        self.jarvis.speak(f"No processes named {name} were running")
        return False
