import json
import os
import logging
from typing import Any, Callable, Dict, List

# Check OpenAI version
try:
    import openai
    OPENAI_V1 = hasattr(openai, 'OpenAI')
except ImportError:
    openai = None
    OPENAI_V1 = False

from command_jarvis.app_commands import AppCommands
from command_jarvis.intelligent_app_commands import IntelligentAppCommands
from command_jarvis.system_commands import SystemCommands
from command_jarvis.file_commands import FileCommands
from command_jarvis.web_commands import WebCommands
from command_jarvis.media_commands import MediaCommands
from command_jarvis.misc_commands import MiscCommands


class GPTCommandHandler:
    """Handle commands using OpenAI function calling with comprehensive system command support."""

    def __init__(self, jarvis: Any, config: dict) -> None:
        self.jarvis = jarvis
        self.config = config

        # Initialize underlying command modules
        self.app_commands = AppCommands(jarvis, config)
        self.intelligent_apps = IntelligentAppCommands(jarvis, config)
        self.system_commands = SystemCommands(jarvis, config)
        self.file_commands = FileCommands(jarvis, config)
        self.web_commands = WebCommands(jarvis, config)
        self.media_commands = MediaCommands(jarvis, config)
        self.misc_commands = MiscCommands(jarvis, config)

        # Map of function name to metadata and callable
        self.functions: Dict[str, Dict[str, Any]] = {}
        self._register_functions()

    def _register_functions(self) -> None:
        """Register ALL command functions for GPT including comprehensive system commands."""
        self.functions = {
            # Intelligent Application Commands
            "open_application": {
                "callable": self.intelligent_apps.intelligent_open_application,
                "description": "Intelligently find and open any application on the computer by searching the system and using AI to match the request. Works with partial names, common names, or descriptions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_request": {
                            "type": "string",
                            "description": "Name or description of the application to open (e.g., 'chrome', 'browser', 'text editor', 'music player', 'steam', 'discord', 'photoshop', etc.)",
                        }
                    },
                    "required": ["app_request"],
                },
            },
            "close_application": {
                "callable": self.intelligent_apps.close_application,
                "description": "Close a running application",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Name of the application to close",
                        }
                    },
                    "required": ["app_name"],
                },
            },
            "list_available_programs": {
                "callable": self.intelligent_apps.list_available_programs,
                "description": "List available programs that can be opened on the system",
                "parameters": {"type": "object", "properties": {}},
            },
            "list_running_applications": {
                "callable": self.app_commands.list_running_applications,
                "description": "List currently running applications",
                "parameters": {"type": "object", "properties": {}},
            },
            "switch_to_application": {
                "callable": self.app_commands.switch_to_application,
                "description": "Switch focus to a running application",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Name of the application to switch to",
                        }
                    },
                    "required": ["app_name"],
                },
            },

            # System Commands
            "execute_command": {
                "callable": self.system_commands.execute_command,
                "description": "Execute a system command or shell script with safety checks. Use this for any CMD, PowerShell, or terminal commands.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The system command to execute (e.g., 'dir', 'ipconfig', 'tasklist', 'systeminfo', etc.)",
                        }
                    },
                    "required": ["command"],
                },
            },
            "get_system_info": {
                "callable": lambda: self.system_commands.execute_command("systeminfo"),
                "description": "Get complete detailed system information",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_simple_system_overview": {
                "callable": lambda: self.system_commands.execute_command('systeminfo'),
                "description": "Get system overview information",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_detailed_system_specs": {
                "callable": lambda: self.system_commands.execute_command('systeminfo'),
                "description": "Get comprehensive system specifications including all hardware and software details",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_quick_system_summary": {
                "callable": lambda: self.system_commands.execute_command('echo Computer: %COMPUTERNAME% & echo User: %USERNAME% & echo Current Time: %DATE% %TIME%'),
                "description": "Get a quick system summary with basic info",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_network_config": {
                "callable": lambda: self.system_commands.execute_command("ipconfig /all"),
                "description": "Check network configuration and IP addresses",
                "parameters": {"type": "object", "properties": {}},
            },
            "list_running_processes": {
                "callable": lambda: self.system_commands.execute_command("tasklist"),
                "description": "List all running processes with details",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_disk_space": {
                "callable": lambda: self.system_commands.execute_command('dir C:\\ /-c'),
                "description": "Check disk space usage for C drive",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_all_drives": {
                "callable": lambda: self.system_commands.execute_command('dir C:\\ /-c & echo. & dir D:\\ /-c 2>nul & echo. & dir E:\\ /-c 2>nul'),
                "description": "Check disk space for all drives",
                "parameters": {"type": "object", "properties": {}},
            },
            "ping_host": {
                "callable": lambda host: self.system_commands.execute_command(f"ping {host}"),
                "description": "Ping a host to test connectivity",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Host or IP address to ping",
                        }
                    },
                    "required": ["host"],
                },
            },
            "check_wifi_status": {
                "callable": lambda: self.system_commands.execute_command("netsh wlan show interfaces"),
                "description": "Check Wi-Fi connection status and details",
                "parameters": {"type": "object", "properties": {}},
            },
            "list_installed_programs": {
                "callable": lambda: self.system_commands.execute_command('dir "C:\\Program Files" /b'),
                "description": "List installed programs from Program Files",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_windows_version": {
                "callable": lambda: self.system_commands.execute_command('ver & echo. & systeminfo'),
                "description": "Check Windows version and details",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_environment_variables": {
                "callable": lambda: self.system_commands.execute_command("set"),
                "description": "List all environment variables",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_services": {
                "callable": lambda service: self.system_commands.execute_command(f"sc query {service}" if service else "sc query state= all"),
                "description": "Check status of Windows services",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Specific service name to check (optional)",
                        }
                    },
                },
            },
            "check_startup_programs": {
                "callable": lambda: self.system_commands.execute_command("reg query HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"),
                "description": "List programs that start with Windows",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_hardware_info": {
                "callable": lambda: self.system_commands.execute_command('systeminfo'),
                "description": "Get complete computer hardware information",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_memory_usage": {
                "callable": lambda: self.system_commands.execute_command('echo === MEMORY USAGE === & echo Total Physical Memory: & wmic computersystem get TotalPhysicalMemory /value & echo. & echo Memory Usage: & wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /value'),
                "description": "Check specific memory usage and statistics",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_memory_details": {
                "callable": lambda: self.system_commands.execute_command('echo === DETAILED MEMORY INFORMATION === & wmic memorychip get Capacity,Speed,Manufacturer /format:table & echo. & wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /value'),
                "description": "Get detailed memory information including RAM modules",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_cpu_details": {
                "callable": lambda: self.system_commands.execute_command('echo === CPU INFORMATION === & wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed /value'),
                "description": "Get detailed CPU information",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_gpu_details": {
                "callable": lambda: self.system_commands.execute_command('echo === GPU INFORMATION === & wmic path win32_VideoController get Name,AdapterRAM,DriverVersion /value'),
                "description": "Get detailed graphics card information",
                "parameters": {"type": "object", "properties": {}},
            },
            "list_network_connections": {
                "callable": lambda: self.system_commands.execute_command("netstat -an"),
                "description": "List active network connections",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_firewall_status": {
                "callable": lambda: self.system_commands.execute_command("netsh advfirewall show allprofiles"),
                "description": "Check Windows Firewall status",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_user_accounts": {
                "callable": lambda: self.system_commands.execute_command("net user"),
                "description": "List user accounts on the system",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_event_logs": {
                "callable": lambda log_type: self.system_commands.execute_command(f"wevtutil qe {log_type or 'System'} /c:10 /rd:true /f:text"),
                "description": "Check recent Windows event logs",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "log_type": {
                            "type": "string",
                            "description": "Type of log to check (System, Application, Security)",
                            "enum": ["System", "Application", "Security"]
                        }
                    },
                },
            },
            "get_cpu_info": {
                "callable": lambda: self.system_commands.execute_command('systeminfo'),
                "description": "Get detailed CPU information",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_complete_hardware_report": {
                "callable": lambda: self.system_commands.execute_command('systeminfo'),
                "description": "Get a complete hardware and system report with all details",
                "parameters": {"type": "object", "properties": {}},
            },
            "shutdown_computer": {
                "callable": self.system_commands.shutdown_computer,
                "description": "Shutdown the computer",
                "parameters": {"type": "object", "properties": {}},
            },
            "restart_computer": {
                "callable": self.system_commands.restart_computer,
                "description": "Restart the computer",
                "parameters": {"type": "object", "properties": {}},
            },
            "cancel_shutdown": {
                "callable": self.system_commands.cancel_shutdown,
                "description": "Cancel a pending shutdown or restart",
                "parameters": {"type": "object", "properties": {}},
            },
            "lock_computer": {
                "callable": self.system_commands.lock_computer,
                "description": "Lock the computer",
                "parameters": {"type": "object", "properties": {}},
            },
            "adjust_volume": {
                "callable": self.system_commands.adjust_volume,
                "description": "Adjust system volume",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["up", "down", "mute"],
                            "description": "Direction to adjust volume",
                        }
                    },
                    "required": ["direction"],
                },
            },
            "take_screenshot": {
                "callable": self.system_commands.take_screenshot,
                "description": "Take a screenshot",
                "parameters": {"type": "object", "properties": {}},
            },
            "check_system_status": {
                "callable": self.system_commands.check_system_status,
                "description": "Check overall system resource usage",
                "parameters": {"type": "object", "properties": {}},
            },
            "monitor_system_resources": {
                "callable": self.system_commands.monitor_system_resources,
                "description": "Monitor CPU, memory, and disk usage",
                "parameters": {"type": "object", "properties": {}},
            },
            "terminate_process": {
                "callable": self.system_commands.terminate_process,
                "description": "Terminate a process by name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Name of the process to terminate",
                        }
                    },
                    "required": ["process_name"],
                },
            },
            "empty_recycle_bin": {
                "callable": self.system_commands.empty_recycle_bin,
                "description": "Empty the Windows Recycle Bin",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_current_time": {
                "callable": self.system_commands.get_current_time,
                "description": "Get the current time",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_current_date": {
                "callable": self.system_commands.get_current_date,
                "description": "Get the current date",
                "parameters": {"type": "object", "properties": {}},
            },

            # File Commands
            "create_directory": {
                "callable": self.file_commands.create_directory,
                "description": "Create a new directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory_name": {
                            "type": "string",
                            "description": "Path of the directory to create",
                        }
                    },
                    "required": ["directory_name"],
                },
            },
            "move_file": {
                "callable": self.file_commands.move_file,
                "description": "Move a file to a new location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_path": {
                            "type": "string",
                            "description": "Path of the file to move",
                        },
                        "destination_path": {
                            "type": "string",
                            "description": "Destination path",
                        },
                    },
                    "required": ["source_path", "destination_path"],
                },
            },
            "search_files": {
                "callable": self.file_commands.search_files,
                "description": "Search for files on the system",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term",
                        },
                        "file_type": {
                            "type": "string",
                            "description": "Optional file extension filter",
                        },
                    },
                    "required": ["query"],
                },
            },

            # Web Commands
            "search_web": {
                "callable": self.web_commands.search_web,
                "description": "Perform a web search",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        }
                    },
                    "required": ["query"],
                },
            },
            "open_website": {
                "callable": self.web_commands.open_website,
                "description": "Open a specific website",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to open",
                        }
                    },
                    "required": ["url"],
                },
            },

            # Media Commands
            "play_music": {
                "callable": self.media_commands.play_music,
                "description": "Play music from the library or YouTube",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Song or artist to play",
                        }
                    },
                    "required": ["query"],
                },
            },

            # Misc Commands
            "show_clipboard_history": {
                "callable": self.misc_commands.show_clipboard_history,
                "description": "Show recent clipboard contents",
                "parameters": {"type": "object", "properties": {}},
            },
            "save_clipboard_snippet": {
                "callable": self.misc_commands.save_clipboard_snippet,
                "description": "Save current clipboard text as a snippet",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the snippet",
                        }
                    },
                    "required": ["name"],
                },
            },
            "paste_clipboard_snippet": {
                "callable": self.misc_commands.paste_clipboard_snippet,
                "description": "Copy a saved snippet back to the clipboard",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Snippet name",
                        }
                    },
                    "required": ["name"],
                },
            },
            "read_screen": {
                "callable": self.misc_commands.read_screen,
                "description": "Read and extract text from the current screen",
                "parameters": {"type": "object", "properties": {}},
            },
            "continue_reading": {
                "callable": self.misc_commands.continue_reading,
                "description": "Continue reading the current text",
                "parameters": {"type": "object", "properties": {}},
            },
            "stop_reading": {
                "callable": self.misc_commands.stop_reading,
                "description": "Stop the current reading session",
                "parameters": {"type": "object", "properties": {}},
            },
            "list_scripts": {
                "callable": self.misc_commands.list_scripts,
                "description": "List scripts available for execution",
                "parameters": {"type": "object", "properties": {}},
            },
            "run_script": {
                "callable": self.misc_commands.run_script,
                "description": "Run a script from the scripts directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script_name": {
                            "type": "string",
                            "description": "Name of the script file",
                        }
                    },
                    "required": ["script_name"],
                },
            },
        }

    def _get_function_specs(self) -> List[Dict[str, Any]]:
        """Return function specs for OpenAI."""
        specs = []
        for name, meta in self.functions.items():
            specs.append(
                {
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["parameters"],
                }
            )
        return specs

    def handle_input(self, user_input: str) -> Any:
        """Send input to GPT-4 and execute returned function."""
        try:
            from utils_jarvis import sanitize_text
        except ImportError:
            # If sanitize_text isn't available, just use the input as is
            pass
        else:
            user_input = sanitize_text(user_input)

        # Handle simple continuation commands directly
        user_lower = user_input.lower().strip()
        if user_lower in ['yes', 'continue', 'keep reading', 'go on', 'more']:
            return self.misc_commands.continue_reading()
        elif user_lower in ['no', 'stop', 'stop reading', 'enough', 'that\'s enough']:
            return self.misc_commands.stop_reading()
        
        messages = [
            {
                "role": "system", 
                "content": """You are Jarvis, an intelligent AI assistant with comprehensive system command capabilities and intelligent application discovery. 
                You can execute various system commands, manage applications, control hardware, and perform file operations.
                
                When a user asks to open applications, use the intelligent open_application function which can:
                - Find programs by partial names (e.g., "chrome" finds "Google Chrome")
                - Match common aliases (e.g., "browser" finds web browsers)
                - Search the entire system for installed programs
                - Use AI to match user requests to available software
                
                Examples for applications:
                - "Open Chrome" -> use open_application with "chrome"
                - "Open a browser" -> use open_application with "browser"  
                - "Open text editor" -> use open_application with "text editor"
                - "Open Steam" -> use open_application with "steam"
                - "Open Discord" -> use open_application with "discord"
                - "Open music player" -> use open_application with "music player"
                
                For system information:
                - "What's my IP address?" -> use check_network_config
                - "List running processes" -> use list_running_processes  
                - "Check disk space" -> use check_disk_space or check_all_drives
                - "What's my CPU info?" -> use get_cpu_details
                - "Check memory usage" -> use check_memory_usage
                - "Show available programs" -> use list_available_programs
                
                Always be helpful and execute the most appropriate function for the user's request."""
            },
            {"role": "user", "content": user_input}
        ]
        
        try:
            # Get API key from config
            api_key = self.config.get("API_KEYS", "openai", "", is_encrypted=True) or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logging.warning("OpenAI API key not configured; continuing without it")
            else:
                openai.api_key = api_key
            
            if OPENAI_V1 and api_key:
                # New v1.0+ API
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-4-0613",
                    messages=messages,
                    functions=self._get_function_specs(),
                    function_call="auto"
                )
                message = response.choices[0].message
                if not hasattr(message, 'function_call') or not message.function_call:
                    if message.content:
                        self.jarvis.speak(message.content)
                    return None
                name = message.function_call.name
                args_json = message.function_call.arguments
            else:
                # Old API or testing without API key
                if api_key:
                    openai.api_key = api_key
                response = openai.ChatCompletion.create(
                    model="gpt-4-0613",
                    messages=messages,
                    functions=self._get_function_specs(),
                )
                message = response["choices"][0]["message"]
                if "function_call" not in message:
                    if message.get("content"):
                        self.jarvis.speak(message["content"])
                    return None
                name = message["function_call"]["name"]
                args_json = message["function_call"].get("arguments", "{}")
            
            args = json.loads(args_json)
            
            if name in self.functions:
                func: Callable[..., Any] = self.functions[name]["callable"]
                
                # Handle lambda functions with parameters
                if name in ["ping_host", "check_services", "check_event_logs"]:
                    if name == "ping_host":
                        return self.system_commands.execute_command(f"ping {args.get('host', 'google.com')}")
                    elif name == "check_services":
                        service = args.get('service', '')
                        if service:
                            return self.system_commands.execute_command(f"sc query {service}")
                        else:
                            return self.system_commands.execute_command("sc query state= all")
                    elif name == "check_event_logs":
                        log_type = args.get('log_type', 'System')
                        return self.system_commands.execute_command(f"wevtutil qe {log_type} /c:10 /rd:true /f:text")
                
                return func(**args)
            return None
        except Exception as exc:
            logging.error(f"Error calling GPT: {exc}")
            # Instead of returning an error string, speak the error and return None
            self.jarvis.speak(f"I encountered an error processing your request. {str(exc)[:100]}")
            return None
