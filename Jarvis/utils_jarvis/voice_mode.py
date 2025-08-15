class MessageType:
    USER_RESPONSE = "user_response"
    SYSTEM_STATUS = "system_status"
    ERROR_MESSAGE = "error_message"


class VoiceModeController:
    """Determine whether Jarvis should speak based on message type and config."""

    def __init__(self, config: dict):
        self.config = config
        self.silent_background_mode = (
            str(self.config.get("silent_background_mode", "False")).lower() == "true"
        )

    def should_speak(self, message_type: str, critical: bool = False) -> bool:
        """Return True if Jarvis should speak the given message."""
        if not self.silent_background_mode:
            return True
        if message_type == MessageType.USER_RESPONSE:
            return True
        if message_type == MessageType.ERROR_MESSAGE and critical:
            return True
        return False
