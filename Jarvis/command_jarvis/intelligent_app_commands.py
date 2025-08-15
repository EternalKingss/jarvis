"""
Intelligent App Commands - AI-powered application discovery and launching
"""

import os
import logging
import psutil
import subprocess
import json
from typing import Any, List, Optional, Dict
from pathlib import Path


class IntelligentAppCommands:
    """AI-powered application control that discovers programs dynamically"""
    
    def __init__(self, jarvis_instance: Any, config: dict):
        """Initialize intelligent app commands"""
        self.jarvis = jarvis_instance
        self.config = config
        self.launched_apps: dict[str, list[int]] = {}
        
        # Cache for discovered applications
        self.app_cache: Dict[str, str] = {}
        self.cache_valid = False

    def discover_installed_programs(self) -> List[Dict[str, str]]:
        """Discover all installed programs on the system"""
        programs = []
        
        try:
            # Extended search directories
            search_dirs = [
                "C:\\Program Files",
                "C:\\Program Files (x86)",
                f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Local",
                f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Roaming",
            ]
            
            for directory in search_dirs:
                if os.path.exists(directory):
                    try:
                        items = os.listdir(directory)
                        for item in items:
                            item_path = os.path.join(directory, item)
                            if os.path.isdir(item_path):
                                # Look for .exe files in this directory and subdirectories
                                try:
                                    # Check direct files first
                                    files = os.listdir(item_path)
                                    exe_files = [f for f in files if f.lower().endswith('.exe')]
                                    
                                    if exe_files:
                                        programs.append({
                                            'name': item,
                                            'path': os.path.join(item_path, exe_files[0]),
                                            'type': 'exe'
                                        })
                                    else:
                                        # Check one level deeper for common app structures
                                        for subitem in files[:10]:  # Limit to avoid too much recursion
                                            subitem_path = os.path.join(item_path, subitem)
                                            if os.path.isdir(subitem_path):
                                                try:
                                                    subfiles = os.listdir(subitem_path)
                                                    sub_exe_files = [f for f in subfiles if f.lower().endswith('.exe')]
                                                    if sub_exe_files:
                                                        programs.append({
                                                            'name': item,
                                                            'path': os.path.join(subitem_path, sub_exe_files[0]),
                                                            'type': 'exe'
                                                        })
                                                        break
                                                except (PermissionError, FileNotFoundError):
                                                    pass
                                except (PermissionError, FileNotFoundError):
                                    pass
                    except (PermissionError, FileNotFoundError):
                        pass
            
            # Add some manual entries for hard-to-find apps
            manual_checks = [
                {
                    'name': 'Epic Games Launcher',
                    'paths': [
                        'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe',
                        'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe'
                    ]
                },
                {
                    'name': 'Google Chrome',
                    'paths': [
                        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
                    ]
                },
                {
                    'name': 'Steam',
                    'paths': [
                        'C:\\Program Files (x86)\\Steam\\steam.exe',
                        'C:\\Program Files\\Steam\\steam.exe'
                    ]
                }
            ]
            
            for manual_app in manual_checks:
                for path in manual_app['paths']:
                    if os.path.exists(path):
                        # Check if we already have this app
                        already_exists = any(p['path'] == path for p in programs)
                        if not already_exists:
                            programs.append({
                                'name': manual_app['name'],
                                'path': path,
                                'type': 'exe'
                            })
                        break
            
            logging.info(f"Discovered {len(programs)} programs")
            
            # Log some found programs for debugging
            if programs:
                sample_programs = [p['name'] for p in programs[:10]]
                logging.info(f"Sample programs found: {sample_programs}")
            
            return programs
            
        except Exception as e:
            logging.error(f"Error discovering programs: {e}")
            return []

    def find_best_program_match(self, user_request: str, programs: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Find the best program match using simple matching and GPT fallback"""
        user_request = user_request.lower()
        logging.info(f"Looking for match for '{user_request}' in {len(programs)} programs")
        
        # Log program names for debugging
        program_names = [p['name'] for p in programs[:10]]
        logging.info(f"Sample program names: {program_names}")
        
        # First try simple string matching
        for prog in programs:
            prog_name = prog['name'].lower()
            if user_request in prog_name or prog_name in user_request:
                logging.info(f"Direct match found: {prog['name']}")
                return prog
        
        # Try partial word matching
        request_words = user_request.split()
        for prog in programs:
            prog_name = prog['name'].lower()
            for word in request_words:
                if len(word) > 2 and word in prog_name:
                    logging.info(f"Word match found: {prog['name']} (matched on '{word}')")
                    return prog
        
        # Try common aliases with broader matching
        aliases = {
            'epic': ['epic'],
            'chrome': ['chrome', 'google'],
            'firefox': ['firefox', 'mozilla'],
            'edge': ['edge', 'microsoft'],
            'notepad': ['notepad'],
            'calculator': ['calculator', 'calc'],
            'explorer': ['explorer', 'file'],
            'steam': ['steam'],
            'discord': ['discord'],
            'code': ['code', 'visual studio'],
            'photoshop': ['photoshop', 'adobe'],
            'spotify': ['spotify'],
        }
        
        for alias, keywords in aliases.items():
            if alias in user_request:
                for prog in programs:
                    prog_name = prog['name'].lower()
                    for keyword in keywords:
                        if keyword in prog_name:
                            logging.info(f"Alias match found: {prog['name']} (alias: {alias}, keyword: {keyword})")
                            return prog
        
        # Try GPT matching if available
        try:
            gpt_result = self._gpt_match_program(user_request, programs)
            if gpt_result:
                logging.info(f"GPT match found: {gpt_result['name']}")
                return gpt_result
        except Exception as e:
            logging.debug(f"GPT matching failed: {e}")
        
        logging.info(f"No match found for '{user_request}'")
        return None

    def _gpt_match_program(self, user_request: str, programs: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Use GPT to find the best program match"""
        try:
            import openai
            
            api_key = self.config.get("API_KEYS", "openai", "", is_encrypted=True) or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None
            
            # Create a simple list for GPT
            program_names = [prog['name'] for prog in programs[:30]]  # Limit to avoid token limits
            programs_text = ", ".join(program_names)
            
            prompt = f"""User wants to open: "{user_request}"
Available programs: {programs_text}

Which program name from the list best matches what the user wants? Respond with ONLY the exact program name from the list, or "NONE" if no good match.

Examples:
- "chrome" -> "Google Chrome"
- "discord" -> "Discord" 
- "epic games" -> "Epic Games Launcher"
"""

            if hasattr(openai, 'OpenAI'):
                # New API
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.1
                )
                match_name = response.choices[0].message.content.strip()
            else:
                # Old API
                openai.api_key = api_key
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.1
                )
                match_name = response['choices'][0]['message']['content'].strip()
            
            if match_name == "NONE":
                return None
            
            # Find the program with matching name
            for prog in programs:
                if prog['name'].lower() == match_name.lower():
                    return prog
                    
        except Exception as e:
            logging.debug(f"GPT matching error: {e}")
            return None
        
        return None

    def intelligent_open_application(self, app_request: str) -> bool:
        """Intelligently find and open an application based on user request"""
        try:
            self.jarvis.speak(f"Looking for {app_request}...")
            
            # Discover available programs
            programs = self.discover_installed_programs()
            
            logging.info(f"Found {len(programs)} total programs")
            
            if not programs:
                self.jarvis.speak("I couldn't scan your installed programs. Let me try the basic approach.")
                return self._fallback_open_application(app_request)
            
            # Find the best match
            best_match = self.find_best_program_match(app_request, programs)
            
            if best_match:
                logging.info(f"Found match: {best_match['name']} at {best_match['path']}")
                return self._launch_program(best_match, app_request)
            else:
                logging.info(f"No match found for '{app_request}' among {len(programs)} programs")
                # Log a few program names for debugging
                sample_names = [p['name'] for p in programs[:5]]
                logging.info(f"Sample available programs: {sample_names}")
                
                self.jarvis.speak(f"I couldn't find a program matching '{app_request}'. Let me try a different approach.")
                return self._fallback_open_application(app_request)
                
        except Exception as e:
            logging.error(f"Error in intelligent app opening: {e}")
            self.jarvis.speak(f"I encountered an error. Let me try opening {app_request} using the basic method.")
            return self._fallback_open_application(app_request)

    def _fallback_open_application(self, app_name: str) -> bool:
        """Fallback to basic application opening"""
        try:
            app_lower = app_name.lower()
            
            # Extended common applications with multiple possible paths
            common_apps = {
                'chrome': [
                    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
                ],
                'firefox': [
                    'C:\\Program Files\\Mozilla Firefox\\firefox.exe',
                    'C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe'
                ],
                'edge': [
                    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
                    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
                ],
                'epic': [
                    'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe',
                    'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe',
                    'C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe',
                    'C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe'
                ],
                'steam': [
                    'C:\\Program Files (x86)\\Steam\\steam.exe',
                    'C:\\Program Files\\Steam\\steam.exe'
                ],
                'discord': [
                    f'C:\\Users\\{os.getenv("USERNAME")}\\AppData\\Local\\Discord\\Update.exe --processStart Discord.exe',
                    'C:\\Program Files\\Discord\\Discord.exe',
                    'C:\\Program Files (x86)\\Discord\\Discord.exe'
                ],
                'notepad': ['notepad.exe'],
                'calculator': ['calc.exe'],
                'explorer': ['explorer.exe'],
            }
            
            # Find matching app name
            matched_app = None
            for app_key in common_apps.keys():
                if app_key in app_lower or any(word in app_lower for word in app_key.split()):
                    matched_app = app_key
                    break
            
            if matched_app:
                paths = common_apps[matched_app]
                for path in paths:
                    try:
                        if path.endswith('.exe') and os.path.exists(path):
                            subprocess.Popen([path], shell=False)
                            self.jarvis.speak(f"Opened {matched_app}")
                            logging.info(f"Successfully opened {matched_app} at {path}")
                            return True
                        elif matched_app in ['notepad', 'calculator', 'explorer']:
                            # These are system commands
                            subprocess.Popen(path, shell=True)
                            self.jarvis.speak(f"Opened {matched_app}")
                            return True
                    except Exception as e:
                        logging.debug(f"Failed to launch {path}: {e}")
                        continue
            
            # If no direct match found, try Windows search/start command
            try:
                # Use Windows start command to find and launch applications
                subprocess.Popen(f'start "" "{app_name}"', shell=True)
                self.jarvis.speak(f"Attempting to open {app_name} via Windows search")
                return True
            except Exception as e:
                logging.debug(f"Windows start command failed: {e}")
            
            self.jarvis.speak(f"I couldn't find or open {app_name}")
            return False
            
        except Exception as e:
            logging.error(f"Fallback app opening failed: {e}")
            self.jarvis.speak(f"I couldn't open {app_name}")
            return False

    def _launch_program(self, program: Dict[str, str], original_request: str) -> bool:
        """Launch the selected program"""
        try:
            path = program['path']
            
            if os.path.exists(path):
                subprocess.Popen(path)
                self.jarvis.speak(f"Opening {program['name']}")
                logging.info(f"Successfully opened {program['name']} at {path}")
                return True
            else:
                self.jarvis.speak(f"Found {program['name']} but the file doesn't exist anymore.")
                return False
            
        except Exception as e:
            logging.error(f"Failed to launch {program['name']}: {e}")
            self.jarvis.speak(f"I found {program['name']} but couldn't open it.")
            return False

    def list_available_programs(self) -> bool:
        """List available programs that can be opened"""
        try:
            self.jarvis.speak("Scanning your system for installed programs...")
            programs = self.discover_installed_programs()
            
            if not programs:
                self.jarvis.speak("I couldn't scan your programs, but I can open common applications like Chrome, Firefox, Notepad, and Calculator.")
                return True
            
            # Get unique program names
            unique_programs = list(set(prog['name'] for prog in programs))
            unique_programs.sort()
            
            self.jarvis.speak(f"I found {len(unique_programs)} programs. Here are some examples:")
            for i, prog_name in enumerate(unique_programs[:10], 1):
                self.jarvis.speak(f"{i}. {prog_name}")
            
            if len(unique_programs) > 10:
                self.jarvis.speak(f"And {len(unique_programs) - 10} more programs available.")
            
            return True
            
        except Exception as e:
            logging.error(f"Error listing programs: {e}")
            self.jarvis.speak("I had trouble scanning your programs, but I can open common applications like Chrome, Firefox, and Notepad.")
            return True

    def close_application(self, app_name: str) -> bool:
        """Close applications by process name"""
        try:
            app_name_lower = app_name.lower()
            closed_any = False
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    process_name = proc.info['name'].lower()
                    if app_name_lower in process_name or process_name.startswith(app_name_lower):
                        p = psutil.Process(proc.info['pid'])
                        p.terminate()
                        try:
                            p.wait(timeout=3)
                        except:
                            p.kill()
                        closed_any = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                except Exception as e:
                    logging.debug(f"Error closing process: {e}")
            
            if closed_any:
                self.jarvis.speak(f"Closed {app_name}")
                return True
            else:
                self.jarvis.speak(f"I don't see {app_name} running")
                return False
                
        except Exception as e:
            logging.error(f"Error closing application: {e}")
            self.jarvis.speak(f"I had trouble closing {app_name}")
            return False
