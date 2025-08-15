"""
Default settings and constants for Jarvis
"""

# Default Jarvis system configuration
DEFAULT_SLEEP_TIMEOUT = 120
DEFAULT_LANGUAGE = "en-US"
DEFAULT_VOICE = "alloy"
DEFAULT_WAKE_WORD = "jarvis"

# Speech recognition settings
DEFAULT_ENERGY_THRESHOLD = 3000
DEFAULT_PAUSE_THRESHOLD = 0.5
DEFAULT_TTS_RATE = 180

# ElevenLabs default voice IDs
ELEVENLABS_VOICE_IDS = {
    "adam": "pNInz6obpgDQGcFmaJgB",
    "antoni": "ErXwobaYiN019PkySvjV",
    "arnold": "VR6AewLTigWG4xSOukaG",
    "bella": "EXAVITQu4vr4xnSDxMaL",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "domi": "AZnzlk1XvdvUeBnXmlld",
    "elli": "MF3mGyEYCl7XYWbV9V6O",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "patrick": "ODq5zmih8GrVes37Dizd",
    "sam": "yoZ06aMxZJJ28mfd3POQ"
}

# OpenAI voice options
OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

# Default system message for GPT conversations
DEFAULT_SYSTEM_MESSAGE = (
    "You are Jarvis, an AI assistant modeled after Tony Stark's AI in Iron Man. "
    "You are helpful, knowledgeable, and have a bit of wit. Keep responses concise but informative."
)

# Application paths mapping
DEFAULT_APP_PATHS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "youtube": "https://www.youtube.com",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "steam": "steam.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "cmd.exe",
    "powershell": "powershell.exe",
    "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:",
    "mail": "outlook.exe",
    "outlook": "outlook.exe",
    "maps": "explorer.exe shell:AppsFolder\\Microsoft.WindowsMaps_8wekyb3d8bbwe!App",
    "weather": "explorer.exe shell:AppsFolder\\Microsoft.BingWeather_8wekyb3d8bbwe!App",
    "calendar": "outlookcal:",
    "music": "mswindowsmusic:",
    "movies": "mswindowsvideo:",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
    "twitter": "https://www.twitter.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "github": "https://www.github.com",
    "brave": "brave.exe",
    "zoom": "zoom.exe",
    "teams": "teams.exe",
    "skype": "skype.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "visual studio": "devenv.exe",
    "adobe reader": "AcroRd32.exe",
    "adobe photoshop": "photoshop.exe",
    "photoshop": "photoshop.exe",
    "adobe illustrator": "illustrator.exe",
    "illustrator": "illustrator.exe",
    "vlc": "vlc.exe",
    "vlc player": "vlc.exe",
    "media player": "wmplayer.exe",
    "windows media player": "wmplayer.exe",
}

# Process name mapping for close operations
PROCESS_NAME_MAP = {
    "chrome": ["chrome.exe"],
    "firefox": ["firefox.exe"],
    "edge": ["msedge.exe"],
    "brave": ["brave.exe"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "file explorer": ["explorer.exe"],
    "files": ["explorer.exe"],
    "spotify": ["spotify.exe"],
    "discord": ["discord.exe", "Update.exe"],
    "steam": ["steam.exe", "steamwebhelper.exe"],
    "vlc": ["vlc.exe"],
    "zoom": ["zoom.exe", "Zoom.exe"],
    "teams": ["Teams.exe"],
    "skype": ["Skype.exe"],
    "vscode": ["Code.exe"],
    "visual studio code": ["Code.exe"],
    "visual studio": ["devenv.exe"],
    "adobe reader": ["AcroRd32.exe"],
    "photoshop": ["Photoshop.exe"],
    "illustrator": ["Illustrator.exe"],
    "media player": ["wmplayer.exe"],
}

# Additional aliases for fuzzy matching
PROCESS_ALIASES = {
    "wordpad": "wordpad.exe",
    "notes": "notepad.exe",
    "editor": "notepad.exe",
    "excel spreadsheet": "EXCEL.EXE",
    "power point": "POWERPNT.EXE",
}

# Offline response templates
OFFLINE_RESPONSES = {
    "hello": "Hello! How can I help you today?",
    "hi": "Hi there! What can I do for you?",
    "how are you": "I'm functioning normally. Thank you for asking.",
    "thank": "You're welcome. Is there anything else you need?",
    "time": "Current time placeholder - will be filled dynamically",
    "date": "Current date placeholder - will be filled dynamically",
    "weather": "I'm in offline mode and can't check the weather right now.",
    "help": "I can help with opening applications, searching the web, and answering questions. What would you like to do?",
    "joke": "Why don't scientists trust atoms? Because they make up everything!",
    "name": "I'm Jarvis, your personal AI assistant.",
    "bye": "Goodbye! Have a great day.",
    "shutdown": "Initiating shutdown sequence.",
    "music": "I can play music for you, just tell me what you'd like to hear.",
}

# Default log file name
LOG_FILENAME = "jarvis_log.txt"

# Default reminders file
REMINDERS_FILE = "jarvis_reminders.txt"