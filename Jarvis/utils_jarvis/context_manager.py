import os
import json
from typing import List, Dict

class ConversationContext:
    """Persist conversation history across Jarvis sessions."""

    def __init__(self, history_file: str = None):
        self.history_file = history_file or "conversation_history.json"
        self.history: List[Dict[str, str]] = self._load_history()

    def _load_history(self) -> List[Dict[str, str]]:
        if self.history_file and os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # Keep only the most recent 20 messages to avoid uncontrolled growth
        self.history = self.history[-20:]
        self._save()

    def _save(self) -> None:
        if not self.history_file:
            return
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f)
        except Exception:
            pass

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.history)
