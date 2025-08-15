"""
App Commands - Application control commands for Jarvis
"""

import os
import logging
import psutil
import subprocess
from typing import Any, List, Optional

from config_jarvis.settings import DEFAULT_APP_PATHS, PROCESS_NAME_MAP, PROCESS_ALIASES


class AppCommands:
    """Application control commands for Jarvis"""
    
    def __init__(self, jarvis_instance: Any, config: dict):
        """Initialize app commands with Jarvis instance and configuration"""
        self.jarvis = jarvis_instance
        self.config = config
        self.launched_apps: dict[str, list[int]] = {}

    def _find_browser_executable(self, browser: str) -> Optional[str]:
        """Return the first existing executable path for a browser."""
        paths = []
        if browser == "chrome":
            paths = [
                r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            ]
        elif browser == "edge":
            paths = [
                r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            ]
        elif browser == "firefox":
            paths = [
                r"C:\\Program Files\\Mozilla Firefox\\firefox.exe",
                r"C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe",
            ]
        elif browser == "brave":
            paths = [
                r"C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
                r"C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            ]

        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def open_browser(self, preference: str = "chrome") -> bool:
        """Open a web browser with fallbacks."""
        order = []
        if preference:
            order.append(preference.lower())
        for b in ["chrome", "edge", "firefox"]:
            if b not in order:
                order.append(b)

        for browser in order:
            path = self._find_browser_executable(browser)
            if path:
                try:
                    subprocess.Popen(path)
                    logging.info(f"Opened browser: {path}")
                    self.jarvis.speak(f"{browser.capitalize()} opened")
                    return True
                except Exception as e:
                    logging.error(f"Error launching {browser} at {path}: {e}")

        try:
            import webbrowser
            webbrowser.open("")
            logging.info("Opened default browser")
            self.jarvis.speak("Browser opened")
            return True
        except Exception as e:
            logging.error(f"Could not open default browser: {e}")

        self.jarvis.speak("I couldn't find a browser to open")
        return False
    
    def open_application(self, app_name: str) -> bool:
        """Open applications on PC"""
        app_name = app_name.lower()

        if app_name in {"chrome", "edge", "firefox", "brave", "browser"}:
            return self.open_browser("chrome" if app_name == "browser" else app_name)

        # Check in the default app paths
        if app_name in DEFAULT_APP_PATHS:
            try:
                target = DEFAULT_APP_PATHS[app_name]
                if target.startswith(("http", "ms-")):
                    import webbrowser
                    webbrowser.open(target)
                    pid = None
                else:
                    proc = psutil.Popen(target)
                    pid = proc.pid
                if pid:
                    self.launched_apps.setdefault(app_name, []).append(pid)
                logging.info(f"Opened application: {app_name}")
                self.jarvis.speak(f"{app_name.capitalize()} opened")
                return True
            except Exception as e:
                logging.error(f"Error opening application: {str(e)}")
                self.jarvis.speak(f"I had trouble opening {app_name}")
                return False
        else:
            # Try to open it directly as a command
            try:
                proc = psutil.Popen(app_name)
                self.launched_apps.setdefault(app_name, []).append(proc.pid)
                logging.info(f"Opened application: {app_name}")
                self.jarvis.speak(f"{app_name.capitalize()} opened")
                return True
            except Exception as e:
                logging.error(f"Error opening application directly: {str(e)}")
                self.jarvis.speak(f"I don't know how to open {app_name}")
                return False
    
    def close_application(self, app_name: str) -> bool:
        """Close a running application by name"""
        app_name_lower = app_name.lower()

        # Normalize with alias map
        if app_name_lower in PROCESS_ALIASES:
            app_name_lower = PROCESS_ALIASES[app_name_lower].lower()

        # Check if we have stored PIDs for this app
        closed_any = False
        if app_name_lower in self.launched_apps:
            for pid in self.launched_apps.pop(app_name_lower):
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                    except Exception:
                        p.kill()
                    closed_any = True
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    logging.error(f"Error closing PID {pid}: {str(e)}")

        # Check if app is in our process map
        if app_name_lower in PROCESS_NAME_MAP:
            process_names = PROCESS_NAME_MAP[app_name_lower]

            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() in [p.lower() for p in process_names]:
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate()
                        try:
                            p.wait(timeout=3)
                        except Exception:
                            p.kill()
                        closed_any = True
                    except Exception as e:
                        logging.error(f"Error closing {proc.info['name']}: {str(e)}")

            if closed_any:
                self.jarvis.speak(f"Closed {app_name}")
                return True
            else:
                # Friendlier message when the app isn't running
                self.jarvis.speak_to_user(f"I don't see {app_name} open")
                return False
        else:
            # Try to find the process by a partial name match
            closed_any = False
            for proc in psutil.process_iter(['pid', 'name']):
                name = proc.info['name'].lower()
                if app_name_lower in name or name.startswith(app_name_lower):
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate()
                        try:
                            p.wait(timeout=3)
                        except Exception:
                            p.kill()
                        closed_any = True
                    except Exception as e:
                        logging.error(f"Error closing {proc.info['name']}: {str(e)}")
            
            if closed_any:
                self.jarvis.speak(f"Closed processes matching {app_name}")
                return True
            else:
                self.jarvis.speak(f"I don't know how to close {app_name}")
                return False
    
    def list_running_applications(self) -> bool:
        """List currently running applications"""
        try:
            apps = []
            seen = set()
            
            for proc in psutil.process_iter(['pid', 'name']):
                name = proc.info['name']
                
                # Skip system processes and duplicates
                if (name.lower().endswith(('.exe', '.com')) and 
                    not name.lower().startswith(('system', 'svchost', 'runtime', 'conhost', 'winlogon')) and
                    name not in seen):
                    seen.add(name)
                    apps.append(name)
            
            if apps:
                # Sort alphabetically and get the first 10
                apps.sort()
                app_list = apps[:10]
                
                self.jarvis.speak(f"You have {len(apps)} applications running. Here are some of them:")
                for app in app_list:
                    name = app.replace('.exe', '').replace('.com', '')
                    self.jarvis.speak(name)
                
                return True
            else:
                self.jarvis.speak("I couldn't find any user applications running.")
                return False
                
        except Exception as e:
            logging.error(f"Error listing applications: {str(e)}")
            self.jarvis.speak("I had trouble listing your applications")
            return False
    
    def switch_to_application(self, app_name: str) -> bool:
        """Switch to a running application"""
        try:
            # Check if pyautogui is available
            try:
                import pyautogui
                have_pyautogui = True
            except ImportError:
                have_pyautogui = False
                self.jarvis.speak("The pyautogui package is required for this feature. Please install it.")
                return False
            
            # Look for the application
            app_name_lower = app_name.lower()
            found = False
            
            for proc in psutil.process_iter(['pid', 'name']):
                name = proc.info['name'].lower()
                
                # Check for a match either in the process name or in our app map
                if (app_name_lower in name or 
                    any(app_name_lower in k for k, v in PROCESS_NAME_MAP.items() if name in v)):
                    
                    # Use Windows API to bring window to front
                    try:
                        import ctypes
                        from ctypes import wintypes
                        
                        # Define required functions
                        user32 = ctypes.WinDLL('user32', use_last_error=True)
                        user32.EnumWindows.argtypes = [
                            ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM),
                            wintypes.LPARAM
                        ]
                        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
                        
                        # Find the window handle for the process
                        target_pid = proc.info['pid']
                        window_handle = None
                        
                        def enum_windows_callback(hwnd, lparam):
                            result = ctypes.c_ulong()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(result))
                            if result.value == target_pid:
                                nonlocal window_handle
                                window_handle = hwnd
                                return False
                            return True
                        
                        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(enum_windows_callback), 0)
                        
                        if window_handle:
                            user32.SetForegroundWindow(window_handle)
                            found = True
                            break
                    except Exception as win_e:
                        logging.error(f"Error using Windows API: {str(win_e)}")
                        
                        # Fallback to Alt+Tab method if Windows API fails
                        if have_pyautogui:
                            # Fallback method using Alt+Tab
                            pyautogui.keyDown('alt')
                            pyautogui.press('tab')
                            pyautogui.keyUp('alt')
                            found = True
                            break
            
            if found:
                self.jarvis.speak(f"Switched to {app_name}")
                return True
            else:
                self.jarvis.speak(f"I couldn't find {app_name} running")
                return False
                
        except Exception as e:
            logging.error(f"Error switching to application: {str(e)}")
            self.jarvis.speak("I had trouble switching applications")
            return False