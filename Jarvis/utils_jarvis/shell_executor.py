import os
import subprocess
import shlex
import time
import uuid
import logging
import ctypes
from typing import Any, Dict, Tuple


class ShellCommandExecutor:
    """Safely execute shell commands with confirmation and permission checks."""

    # Safe commands that can run without confirmation
    SAFE = {
        # Basic commands
        "ls", "dir", "pwd", "whoami", "date", "echo", "uptime", "time", "ver", "hostname",
        # Network information (read-only)
        "ipconfig", "ping", "nslookup", "netstat", "arp", "tracert", "pathping",
        "netsh", "route",
        # System information (read-only)
        "systeminfo", "tasklist", "wmic", "driverquery", "gpresult", "msinfo32",
        "powercfg", "sfc", "chkdsk",
        # File/directory listing (read-only)
        "tree", "findstr", "find", "where", "which", "type", "more", "sort",
        # Environment and variables
        "set", "path", "echo", "cls", "color",
        # Process information
        "tasklist", "query",
        # Windows specific safe commands
        "vol", "label", "diskpart", "fsutil", "bcdedit", "reg",
        # PowerShell (safe when used for queries)
        "powershell", "pwsh",
    }
    
    # Commands that need confirmation but are generally safe
    CONFIRM = {
        "pip", "apt", "apt-get", "brew", "npm", "git", "mkdir", "rmdir", "md", "rd",
        "copy", "xcopy", "robocopy", "move", "ren", "rename", "attrib", "cacls",
        "takeown", "icacls", "cipher", "compact", "expand",
    }
    
    # Dangerous commands that need admin privileges
    DANGEROUS = {
        "rm", "del", "erase", "deltree", "shutdown", "reboot", "poweroff", "kill", 
        "mkfs", "dd", "systemctl", "service", "taskkill", "sc", "net", "runas",
        "format", "fdisk", "diskpart", "bcdedit", "bootrec", "sfc", "dism",
    }

    def __init__(self, jarvis_instance: Any) -> None:
        self.jarvis = jarvis_instance
        self.pending: Dict[str, Tuple[str, str, float]] = {}
        self.log_file = "command_history.log"

    def classify(self, command: str) -> str:
        """Classify command into safe, confirm or dangerous."""
        try:
            # Handle complex commands with arguments
            parts = shlex.split(command)
            if not parts:
                return "dangerous"
            
            first_cmd = parts[0].lower()
            
            # Handle Windows command variations
            if first_cmd.endswith('.exe'):
                first_cmd = first_cmd[:-4]
            
            # Special handling for common safe patterns
            if first_cmd in self.SAFE:
                return "safe"
            
            # Special cases for commands with arguments that are safe
            if first_cmd == "wmic" or command.lower().startswith("wmic "):
                return "safe"  # WMIC is generally safe for querying
            
            if first_cmd == "netsh" and any(x in command.lower() for x in ["show", "dump", "export"]):
                return "safe"  # Read-only netsh commands
            
            if first_cmd == "reg" and "query" in command.lower():
                return "safe"  # Registry queries are safe
                
            if first_cmd == "sc" and "query" in command.lower():
                return "safe"  # Service queries are safe
                
            if first_cmd == "powercfg" and any(x in command.lower() for x in ["/list", "/query", "/batteryreport", "/energy"]):
                return "safe"  # Power config queries are safe
            
            # PowerShell read-only commands are safe
            if first_cmd == "powershell" and any(x in command.lower() for x in ["get-", "select-", "format-", "where-object"]):
                return "safe"  # PowerShell Get commands are safe
                
            if first_cmd == "powershell" and "get-ciminstance" in command.lower():
                return "safe"  # CIM instance queries are safe
            
            # Check other categories
            if first_cmd in self.CONFIRM:
                return "confirm"
            if first_cmd in self.DANGEROUS:
                return "dangerous"
                
            # Default to safe for most Windows built-in commands that are informational
            common_safe_patterns = [
                "ipconfig", "ping", "tracert", "nslookup", "netstat", "arp",
                "systeminfo", "tasklist", "ver", "whoami", "hostname", "date", "time"
            ]
            
            if any(pattern in first_cmd for pattern in common_safe_patterns):
                return "safe"
                
        except Exception:
            return "dangerous"
        
        # Default to dangerous for unknown commands
        return "dangerous"

    def _check_admin(self) -> bool:
        """Check if current process has admin/root privileges."""
        if os.name == "nt":
            try:
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception:
                return False
        result = subprocess.run(["sudo", "-n", "true"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        return result.returncode == 0

    def _log(self, command: str) -> None:
        """Log executed command with timestamp."""
        logging.info("Executed command: %s", command)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_file, "a", encoding="utf-8") as fh:
                fh.write(f"{ts} - {command}\n")
        except Exception as exc:  # pragma: no cover - logging failure
            logging.error("Failed to log command: %s", exc)

    def _request_confirmation(self, command: str, keyword: str) -> bool:
        cmd_id = uuid.uuid4().hex[:8]
        self.pending[cmd_id] = (command, keyword, time.time())
        self.jarvis.speak(f"Say {keyword} to proceed or cancel to abort")
        start = time.time()
        while time.time() - start < 30:
            response = self.jarvis.listen(timeout=3)
            if not response:
                continue
            r = response.lower()
            if "cancel" in r:
                self.jarvis.speak("Command cancelled")
                self.pending.pop(cmd_id, None)
                return False
            if keyword in r:
                self.pending.pop(cmd_id, None)
                return True
        self.jarvis.speak("Confirmation timed out")
        self.pending.pop(cmd_id, None)
        return False

    def _run(self, command: str) -> bool:
        """Execute the command and handle output."""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            self._log(command)
            
            if result.returncode == 0:
                out = result.stdout.strip()
                if out:
                    # For systeminfo command, show much more output
                    if "systeminfo" in command.lower():
                        lines = out.split('\n')
                        if len(lines) > 20:
                            # Show more lines for system info - first 15 and last 10
                            summary_lines = lines[:15] + ['...'] + lines[-10:]
                            summary = '\n'.join(summary_lines)
                            self.jarvis.speak(f"Command executed successfully. Here's the system information: {summary[:800]}")
                        else:
                            self.jarvis.speak(f"Command executed successfully. Output: {out[:600]}")
                    # For long outputs, just give a summary and key info
                    elif len(out.split('\n')) > 10:
                        lines = out.split('\n')
                        # Summarize long output
                        summary_lines = lines[:3] + ['...'] + lines[-2:]
                        summary = '\n'.join(summary_lines)
                        self.jarvis.speak(f"Command executed successfully. Here's a summary of the output: {summary[:300]}")
                    else:
                        # Short output, read it all
                        self.jarvis.speak(f"Command executed successfully. Output: {out[:400]}")
                else:
                    self.jarvis.speak("Command executed successfully with no output")
                return True
            else:
                error = result.stderr.strip()
                if error:
                    self.jarvis.speak(f"Command failed with error: {error[:200]}")
                else:
                    self.jarvis.speak("Command failed with no error message")
                return False
                
        except subprocess.TimeoutExpired:
            self.jarvis.speak("Command timed out after 30 seconds")
            return False
        except Exception as e:
            logging.error(f"Error executing command: {e}")
            self.jarvis.speak(f"Error executing command: {str(e)[:100]}")
            return False

    def execute(self, command: str) -> bool:
        """Execute a shell command with safety checks."""
        if not command or not command.strip():
            self.jarvis.speak("No command provided")
            return False
            
        command = command.strip()
        level = self.classify(command)
        
        logging.info(f"Executing command '{command}' with safety level: {level}")
        
        if level == "safe":
            return self._run(command)
        elif level == "confirm":
            if not self._request_confirmation(command, "confirm"):
                return False
            return self._run(command)
        else:  # dangerous
            if not self._request_confirmation(command, "execute"):
                return False
            if not self._check_admin():
                self.jarvis.speak("Insufficient privileges to run this command. Please run Jarvis as administrator for this type of command.")
                return False
            return self._run(command)
