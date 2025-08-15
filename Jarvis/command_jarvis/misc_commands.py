"""Miscellaneous commands formerly provided by plugins."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import pyperclip


class MiscCommands:
    """Commands covering clipboard utilities and script execution."""

    def __init__(self, jarvis_instance: Any, config: dict) -> None:
        self.jarvis = jarvis_instance
        self.config = config
        self.history: List[str] = []
        self.snippets: Dict[str, str] = {}
        self.last_clip: Optional[str] = None
        self.script_dir = os.path.join(os.getcwd(), "scripts")
        os.makedirs(self.script_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Clipboard helpers
    # ------------------------------------------------------------------
    def _poll_clipboard(self) -> None:
        try:
            current = pyperclip.paste()
            if current and current != self.last_clip:
                self.last_clip = current
                self.history.insert(0, current)
                if len(self.history) > 20:
                    self.history.pop()
        except Exception as exc:
            logging.debug("Clipboard access failed: %s", exc)

    def show_clipboard_history(self) -> bool:
        """Speak a summary of clipboard history."""
        self._poll_clipboard()
        if not self.history:
            self.jarvis.speak("Clipboard history is empty")
            return True
        for i, item in enumerate(self.history, 1):
            print(f"{i}: {item[:40]}")
        self.jarvis.speak(f"{len(self.history)} items in clipboard history")
        return True

    def save_clipboard_snippet(self, name: str) -> bool:
        """Save current clipboard contents under a name."""
        self._poll_clipboard()
        if not name:
            self.jarvis.speak("Provide a name for the snippet")
            return False
        if not self.last_clip:
            self.jarvis.speak("Clipboard is empty")
            return False
        self.snippets[name] = self.last_clip
        self.jarvis.speak(f"Snippet {name} saved")
        return True

    def paste_clipboard_snippet(self, name: str) -> bool:
        """Copy a saved snippet back to the clipboard."""
        content = self.snippets.get(name)
        if not content:
            self.jarvis.speak(f"Snippet {name} not found")
            return False
        pyperclip.copy(content)
        self.jarvis.speak(f"Snippet {name} copied to clipboard")
        return True

    # ------------------------------------------------------------------
    # Script execution helpers
    # ------------------------------------------------------------------
    def _build_command(self, path: str) -> List[str]:
        if path.endswith(".py"):
            return [sys.executable, path]
        if path.endswith(".ps1"):
            return ["powershell", "-ExecutionPolicy", "Bypass", "-File", path]
        if path.endswith(".cmd") or path.endswith(".bat"):
            return ["cmd", "/c", path]
        if path.endswith(".sh"):
            return ["bash", path]
        return [path]

    def list_scripts(self) -> bool:
        """List available scripts in the scripts directory."""
        try:
            files = sorted(os.listdir(self.script_dir))
            if files:
                for f in files:
                    print(f)
                self.jarvis.speak(f"Found {len(files)} scripts")
            else:
                self.jarvis.speak("No scripts available")
            return True
        except Exception as exc:
            logging.error("Listing scripts failed: %s", exc)
            return False

    def run_script(self, script_name: str) -> bool:
        """Run a script by name from the scripts directory."""
        if not script_name:
            self.jarvis.speak("Specify which script to run")
            return False
        path = script_name
        if not os.path.isabs(path):
            path = os.path.join(self.script_dir, script_name)
        if not os.path.exists(path):
            self.jarvis.speak(f"Script {script_name} not found")
            return False
        try:
            cmd = self._build_command(path)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.stdout:
                logging.info("Script output: %s", result.stdout.strip())
            if result.stderr:
                logging.error("Script error: %s", result.stderr.strip())
            self.jarvis.speak("Script completed")
            return True
        except Exception as exc:
            logging.error("Running script failed: %s", exc)
            self.jarvis.speak("Failed to run script")
            return False

    def read_screen(self) -> bool:
        """Read and extract text from the current screen using OCR."""
        try:
            # Import OCR functionality
            from ocr_reader import read_text_from_screen
            
            self.jarvis.speak("Reading your screen, please wait...")
            
            # Capture and read the screen - focus on main content for stories
            text = read_text_from_screen(focus_main_content=True)
            
            if text and text.strip():
                # Clean and filter the text
                cleaned_text = self._clean_screen_text(text)
                
                if cleaned_text:
                    # Detect what type of content this is
                    content_type = self._detect_content_type(cleaned_text)
                    
                    # Send to GPT for correction and improvement (silently)
                    corrected_text = self._correct_ocr_with_gpt(cleaned_text, content_type)
                    
                    if corrected_text:
                        word_count = len(corrected_text.split())
                        
                        if word_count > 100:
                            # For long content, read first portion
                            excerpt = ' '.join(corrected_text.split()[:80])
                            self.jarvis.speak(excerpt)
                            
                            # Store the remaining text for continuation
                            remaining_text = ' '.join(corrected_text.split()[80:])
                            self.jarvis.pending_reading = remaining_text
                            self.jarvis.auto_continue_reading = False  # Start with asking first time
                            
                            self.jarvis.speak("Would you like me to continue reading? Say 'yes' to continue or 'stop reading' to stop.")
                        else:
                            # For shorter content, read it all
                            self.jarvis.speak(corrected_text)
                            
                        # Log the results for debugging
                        logging.info(f"Content type: {content_type}")
                        logging.info(f"Original: {cleaned_text[:100]}...")
                        logging.info(f"Corrected: {corrected_text[:100]}...")
                        return True
                    else:
                        # Fallback to original cleaned text if GPT fails
                        self.jarvis.speak(cleaned_text)
                        return True
                else:
                    self.jarvis.speak("I found text on your screen, but it appears to be mostly navigation elements or unclear content. Try focusing on a specific area with clear text.")
                    return False
            else:
                self.jarvis.speak("I couldn't detect any readable text on your screen. Make sure there's clear, visible text and try again.")
                return False
                
        except ImportError:
            self.jarvis.speak("Screen reading requires pytesseract and Pillow. Please install them with: pip install pytesseract pillow")
            return False
        except Exception as e:
            logging.error(f"Error reading screen: {str(e)}")
            self.jarvis.speak("I encountered an error while trying to read your screen. Make sure Tesseract OCR is properly installed.")
            return False
    
    def continue_reading(self) -> bool:
        """Continue reading the stored text"""
        if hasattr(self.jarvis, 'pending_reading') and self.jarvis.pending_reading:
            remaining_text = self.jarvis.pending_reading
            words = remaining_text.split()
            
            if len(words) > 80:
                # Read next chunk
                excerpt = ' '.join(words[:80])
                self.jarvis.speak(excerpt)
                
                # Store remaining text
                self.jarvis.pending_reading = ' '.join(words[80:])
                
                # Set auto-continue mode
                self.jarvis.auto_continue_reading = True
                
                # Don't ask, just continue automatically after a brief pause
                import time
                time.sleep(1.5)  # Brief pause between chunks
                return self.continue_reading()  # Automatically continue
            else:
                # Read the rest
                self.jarvis.speak(remaining_text)
                self.jarvis.pending_reading = None
                self.jarvis.auto_continue_reading = False
                self.jarvis.speak("That's the end of the text.")
            
            return True
        else:
            self.jarvis.speak("There's no more text to read.")
            return False
    
    def stop_reading(self) -> bool:
        """Stop the current reading session"""
        if hasattr(self.jarvis, 'pending_reading'):
            self.jarvis.pending_reading = None
            self.jarvis.auto_continue_reading = False
            self.jarvis.speak("Reading stopped.")
            return True
        else:
            self.jarvis.speak("No reading session is currently active.")
            return False
    
    def _detect_content_type(self, text: str) -> str:
        """Detect what type of content this is"""
        text_lower = text.lower()
        
        # Check for story/novel indicators
        story_indicators = [
            'said', 'asked', 'replied', 'whispered', 'shouted',
            'he said', 'she said', 'chapter', 'once upon',
            'dialogue', 'character', 'protagonist',
            'transmigration', 'cultivation', 'system',
            'fantasy', 'magic', 'adventure'
        ]
        
        # Check for web page indicators
        web_indicators = [
            'click', 'website', 'login', 'sign up', 'home',
            'menu', 'search', 'results', 'price', 'buy now',
            'contact', 'about us', 'privacy policy'
        ]
        
        # Check for article indicators
        article_indicators = [
            'according to', 'research shows', 'study',
            'published', 'author', 'article', 'news',
            'reported', 'source', 'analysis'
        ]
        
        story_count = sum(1 for indicator in story_indicators if indicator in text_lower)
        web_count = sum(1 for indicator in web_indicators if indicator in text_lower)
        article_count = sum(1 for indicator in article_indicators if indicator in text_lower)
        
        if story_count >= 2:
            return "story"
        elif web_count >= 2:
            return "webpage"
        elif article_count >= 1:
            return "article"
        else:
            return "general"
    
    def _correct_ocr_with_gpt(self, ocr_text: str, content_type: str = "general") -> str:
        """Use GPT to correct and clean OCR text based on content type"""
        try:
            # Get OpenAI API key
            api_key = self.config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return ocr_text
                
            import openai
            
            # Check OpenAI version
            OPENAI_V1 = hasattr(openai, 'OpenAI')
            
            # Customize prompt based on content type
            if content_type == "story":
                system_msg = "Fix OCR text from a story/novel. Preserve dialogue, narrative flow, and character interactions. Make it read naturally like a book."
                user_prompt = f"Fix this story text and make it read naturally:\n\n{ocr_text}\n\nFixed story:"
            elif content_type == "webpage":
                system_msg = "Fix OCR text from a webpage. Extract useful information, ignore navigation elements, focus on main content."
                user_prompt = f"Extract the main information from this webpage text:\n\n{ocr_text}\n\nMain content:"
            elif content_type == "article":
                system_msg = "Fix OCR text from an article. Preserve factual information, make it clear and informative."
                user_prompt = f"Fix this article text and make it clear:\n\n{ocr_text}\n\nFixed article:"
            else:
                system_msg = "Fix OCR text. Make it clear and natural. Be concise but informative."
                user_prompt = f"Fix this OCR text and make it clear and readable:\n\n{ocr_text}\n\nFixed version:"
            
            if OPENAI_V1:
                # New v1.0+ API
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=200,  # Increased for stories
                    temperature=0,
                    timeout=6
                )
                corrected = response.choices[0].message.content.strip()
            else:
                # Old API
                openai.api_key = api_key
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=200,
                    temperature=0,
                    request_timeout=6
                )
                corrected = response["choices"][0]["message"]["content"].strip()
                
            # Clean up the response
            corrected = corrected.replace("Fixed version:", "").strip()
            corrected = corrected.replace("Fixed story:", "").strip()
            corrected = corrected.replace("Main content:", "").strip()
            corrected = corrected.replace("Fixed article:", "").strip()
            
            return corrected if corrected else ocr_text
            
        except Exception as e:
            return ocr_text  # Quickly return original text if correction fails
    
    def _clean_screen_text(self, raw_text: str) -> str:
        """Clean and filter OCR text to extract meaningful content"""
        if not raw_text:
            return ""
            
        # Split into lines and clean each line
        lines = raw_text.split('\n')
        cleaned_lines = []
        
        # System messages and interface elements to filter out
        skip_patterns = [
            'processing command', 'jarvis:', 'user:', 'info:', 'root:', 'config',
            'audio system', 'initialized', 'all systems', 'online', 'ready',
            'hello. i am jarvis', 'personal ai assistant', 'how can i assist',
            'listening...', 'processing...', 'error:', 'warning:', 'debug:',
            'pip install', 'package versions', 'dependency conflict',
            'remove package', 'loosen the range', 'attempt to solve',
            'google.com', 'https://', 'http://', '.com', '.org', '.net',
            'chrome', 'firefox', 'edge', 'browser', 'tabs',
            'close', 'minimize', 'maximize', 'back', 'forward', 'refresh',
            'x', '©', '®', '™', '+', '-', '=', '<>', 
            'more tools', 'feedback', 'privacy', 'terms'
        ]
        
        # Novel/story indicators that should be kept
        story_indicators = [
            'said', 'asked', 'replied', 'whispered', 'shouted',
            'chapter', 'dialogue', 'character', 'protagonist'
        ]
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Skip lines that are too short (likely UI elements)
            if len(line) < 8:
                continue
                
            # Skip lines with mostly special characters or numbers only
            if len([c for c in line if c.isalnum()]) < len(line) * 0.6:
                continue
                
            # Skip lines that match system/UI patterns
            line_lower = line.lower()
            
            # Always skip system messages
            if any(pattern in line_lower for pattern in skip_patterns):
                continue
                
            # Skip lines that are likely OCR noise
            if self._is_likely_ocr_noise(line):
                continue
                
            # Skip very long lines without spaces (likely garbled)
            words = line.split()
            if len(words) == 1 and len(line) > 50:
                continue
            
            # Prioritize story content
            is_story_line = any(indicator in line_lower for indicator in story_indicators)
            
            # Keep lines that seem like real content
            if len(words) >= 3 and len(line) >= 15:
                # If it's a story line, definitely keep it
                if is_story_line:
                    cleaned_lines.append(line)
                # For other lines, be more selective
                elif not any(skip in line_lower for skip in ['command', 'system', 'error', 'info']):
                    cleaned_lines.append(line)
        
        # Join the cleaned lines
        result = ' '.join(cleaned_lines)
        
        # Final cleanup - remove excessive whitespace
        result = ' '.join(result.split())
        
        # If the result is too short, it might be mostly UI elements
        if len(result.split()) < 8:
            return ""
            
        return result
    
    def _is_likely_ocr_noise(self, text: str) -> bool:
        """Check if text is likely OCR noise/gibberish"""
        # Count special characters
        special_chars = sum(1 for c in text if not c.isalnum() and c != ' ')
        
        # If more than 30% special characters, likely noise
        if len(text) > 0 and special_chars / len(text) > 0.3:
            return True
            
        # Check for common OCR error patterns
        noise_indicators = ['¢', '°', 'vy', 'EH', '<>', 'oe', 'aa', 'baa', 'hittps']
        if any(indicator in text for indicator in noise_indicators):
            return True
        
        # Check for system/technical messages that shouldn't be in stories
        system_patterns = [
            'processing command', 'user:', 'jarvis:', 'info:', 'root:',
            'audio system', 'config file', 'initialized', 'pip install',
            'package versions', 'dependency conflict', 'remove package'
        ]
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in system_patterns):
            return True
            
        return False
