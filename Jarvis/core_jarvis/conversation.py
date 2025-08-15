"""
Conversation Engine - Handles AI conversation functionality
"""

import logging
import datetime
import os
from typing import List, Dict, Any, Optional

from config_jarvis.settings import DEFAULT_SYSTEM_MESSAGE, OFFLINE_RESPONSES
from utils_jarvis.api_helpers import get_openai_response
from utils_jarvis.context_manager import ConversationContext

# Try to import OpenAI
try:
    import openai
    HAVE_OPENAI = True
except ImportError:
    HAVE_OPENAI = False
    logging.warning("OpenAI package not available - using offline mode for conversation")


class ConversationEngine:
    """Handles AI conversation with GPT or offline responses"""

    def __init__(self, config_manager: dict):
        """Initialize conversation engine with configuration"""
        self.config_manager = config_manager
        context_file = self.config_manager.get(
            'context_file', 'conversation_history.json'
        ) or 'conversation_history.json'  # Ensure we always have a valid string
        self.context = ConversationContext(context_file)
        
        # Load API key
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        
        # Check if offline mode is enabled
        self.offline_mode = str(self.config_manager.get('offline_mode', 'False')).lower() == 'true'
        
        # Setup OpenAI if available
        if HAVE_OPENAI and self.OPENAI_API_KEY:
            openai.api_key = self.OPENAI_API_KEY
        
        # Initialize conversation history using persisted context if available
        self.conversation_history = self.context.get_history()
        if not self.conversation_history:
            self.conversation_history = [
                {
                    "role": "system",
                    "content": DEFAULT_SYSTEM_MESSAGE
                }
            ]
        elif self.conversation_history[0].get("role") != "system":
            self.conversation_history.insert(0, {"role": "system", "content": DEFAULT_SYSTEM_MESSAGE})

    def get_response(self, user_input: str) -> str:
        """Get response from GPT or offline mode based on settings"""
        if not user_input.strip():
            return "I didn't catch that. Can you please speak more clearly?"

        # Add user message to conversation history and persistent context
        self.conversation_history.append({"role": "user", "content": user_input})
        self.context.append("user", user_input)

        # Use offline mode if configured or if API key is missing or if OpenAI isn't available
        if self.offline_mode or not self.OPENAI_API_KEY or not HAVE_OPENAI:
            response = self.get_offline_response(user_input)
        else:
            try:
                # Get response from GPT
                response = self.get_gpt_response(user_input)
            except Exception as e:
                logging.error(f"Error with GPT API: {str(e)}")
                response = self.get_offline_response(user_input)

        # Add assistant response to conversation history and persistent context
        self.conversation_history.append({"role": "assistant", "content": response})
        self.context.append("assistant", response)

        # Keep conversation history manageable
        if len(self.conversation_history) > 10:
            self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-9:]

        return response

    def get_gpt_response(self, user_input: str) -> str:
        """Get response from GPT API"""
        if not HAVE_OPENAI or not self.OPENAI_API_KEY:
            return self.get_offline_response(user_input)

        try:
            response_text = get_openai_response(
                api_key=self.OPENAI_API_KEY,
                messages=self.conversation_history
            )
            if response_text is None:
                raise RuntimeError("No response")
            return response_text
        except Exception as e:
            logging.error(f"Error with GPT API: {str(e)}")
            return self.get_offline_response(user_input)

    def get_offline_response(self, user_input: str) -> str:
        """Generate simple responses when offline or API is unavailable"""
        # Make a copy of the responses dictionary
        responses = OFFLINE_RESPONSES.copy()
        
        # Update dynamic responses
        now = datetime.datetime.now()
        responses["time"] = now.strftime("The current time is %I:%M %p.")
        responses["date"] = now.strftime("Today is %A, %B %d, %Y.")

        # Look for keywords in user input
        user_input_lower = user_input.lower()
        for keyword, response in responses.items():
            if keyword in user_input_lower:
                return response

        # Default response
        return "I'm currently in offline mode with limited capabilities. I can still help with basic tasks like opening applications or checking the time."