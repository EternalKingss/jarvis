"""
Web Commands - Web browsing and search functions for Jarvis
"""

import logging
import webbrowser
import requests
from typing import Any, Optional




class WebCommands:
    """Web browsing and search commands for Jarvis"""
    
    def __init__(self, jarvis_instance: Any, config: dict):
        """Initialize web commands with Jarvis instance and configuration"""
        self.jarvis = jarvis_instance
        self.config = config
        
        # Import PyWhatKit if available
        try:
            import pywhatkit
            self.pywhatkit = pywhatkit
            self.HAVE_PYWHATKIT = True
        except ImportError:
            self.HAVE_PYWHATKIT = False
    
    def search_web(self, query: str, auto_read: bool = True) -> bool:
        """Perform a simple web search using default browser and optionally read results"""
        try:
            if not query:
                self.jarvis.speak("Please provide a search query.")
                return False
                
            # Use pywhatkit if available for better search
            if self.HAVE_PYWHATKIT:
                try:
                    self.pywhatkit.search(query)
                    self.jarvis.speak(f"Searching the web for {query}")
                    logging.info(f"Searched web for: {query} using PyWhatKit")
                    
                    # Auto-read results if requested
                    if auto_read:
                        # Wait for page to load (reduced time)
                        import time
                        self.jarvis.speak("Let me read the search results for you...")
                        time.sleep(2)  # Reduced from 3 to 2 seconds
                        self.read_current_page()
                    
                    return True
                except Exception as e:
                    logging.error(f"PyWhatKit search failed, using fallback: {str(e)}")
                    # Continue to fallback method
            
            # Fallback to simple URL search
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            import webbrowser
            webbrowser.open(url)
            self.jarvis.speak(f"Searching the web for {query}")
            logging.info(f"Searched web for: {query}")
            
            # Auto-read results if requested
            if auto_read:
                # Wait for page to load (reduced time)
                import time
                self.jarvis.speak("Let me read the search results for you...")
                time.sleep(2)  # Reduced from 3 to 2 seconds
                self.read_current_page()
            
            return True
            
        except Exception as e:
            logging.error(f"Error performing web search: {str(e)}")
            self.jarvis.speak("Web search failed. Please check your connection.")
            return False
    
    def read_current_page(self) -> bool:
        """Read the current page content using OCR"""
        try:
            # Import OCR functionality
            from ocr_reader import read_text_from_screen
            
            # Capture and read the screen
            text = read_text_from_screen()
            
            if text and text.strip():
                # Clean and filter the text using smart filtering
                cleaned_text = self._clean_search_results_text(text)
                
                if cleaned_text:
                    # Send to GPT for correction and improvement (silently)
                    corrected_text = self._correct_search_text_with_gpt(cleaned_text)
                    
                    if corrected_text:
                        words = corrected_text.split()
                        word_count = len(words)
                        
                        if word_count > 80:
                            # For long pages, read a substantial excerpt
                            excerpt = ' '.join(words[:70])
                            self.jarvis.speak(excerpt)
                            self.jarvis.speak("Would you like me to continue reading more results?")
                        else:
                            # For medium/short content, read it all
                            self.jarvis.speak(corrected_text)
                            
                        return True
                    else:
                        # Fallback to cleaned text if GPT fails
                        self.jarvis.speak(cleaned_text)
                        return True
                else:
                    self.jarvis.speak("I couldn't extract meaningful content from the current page. It might be mostly navigation elements or the page is still loading.")
                    return False
            else:
                self.jarvis.speak("I couldn't read any text from the current page. The page might still be loading or contain mostly images.")
                return False
                
        except Exception as e:
            logging.error(f"Error reading current page: {str(e)}")
            self.jarvis.speak("I had trouble reading the current page.")
            return False
    
    def _correct_search_text_with_gpt(self, search_text: str) -> str:
        """Use GPT to correct and clean search results text - balanced version"""
        try:
            import os
            import openai
            
            # Get OpenAI API key
            api_key = self.config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return search_text
                
            # Check OpenAI version
            OPENAI_V1 = hasattr(openai, 'OpenAI')
            
            prompt = f"""Fix this search results text and extract the useful information. Make it clear and informative. Remove website names and garbled content:

{search_text}

Cleaned results:"""
            
            if OPENAI_V1:
                # New v1.0+ API
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract useful information from search results. Be clear and informative but concise."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=180,
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
                        {"role": "system", "content": "Extract useful information from search results. Be clear and informative but concise."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=180,
                    temperature=0,
                    request_timeout=6
                )
                corrected = response["choices"][0]["message"]["content"].strip()
                
            # Clean up the response
            corrected = corrected.replace("Cleaned results:", "").strip()
            
            return corrected if corrected else search_text
            
        except Exception as e:
            return search_text  # Quickly return original text if correction fails
    
    def _clean_search_results_text(self, raw_text: str) -> str:
        """Clean OCR text specifically for search results pages"""
        if not raw_text:
            return ""
            
        # Split into lines and clean each line
        lines = raw_text.split('\n')
        cleaned_lines = []
        
        # Search page specific elements to filter out
        skip_patterns = [
            'google.com', 'search?q=', 'https://', 'http://', '.com', '.org', '.net',
            'chrome', 'firefox', 'edge', 'browser', 'tabs',
            'all', 'news', 'images', 'videos', 'shopping', 'maps',
            'tools', 'settings', 'feedback', 'privacy', 'terms',
            'about results', 'search tools', 'any time', 'past hour',
            'x', '©', '®', '™', '+', '-', '=', '<>', 
            'more', 'web', 'shortvideos'
        ]
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Skip lines that are too short (likely UI elements)
            if len(line) < 5:
                continue
                
            # Skip lines with mostly special characters
            if len([c for c in line if c.isalnum()]) < len(line) * 0.6:
                continue
                
            # Skip lines that match search UI patterns
            line_lower = line.lower()
            if any(pattern in line_lower for pattern in skip_patterns):
                continue
                
            # Skip lines that are likely OCR noise
            if self._is_likely_search_noise(line):
                continue
                
            # Skip very long lines without spaces (likely garbled)
            words = line.split()
            if len(words) == 1 and len(line) > 40:
                continue
                
            # Keep lines that seem like real search result content
            if len(words) >= 3 and len(line) >= 15:
                cleaned_lines.append(line)
        
        # Join the cleaned lines
        result = ' '.join(cleaned_lines)
        
        # Final cleanup - remove excessive whitespace
        result = ' '.join(result.split())
        
        # If the result is too short, it might be mostly UI elements
        if len(result.split()) < 10:
            return ""
            
        return result
    
    def _is_likely_search_noise(self, text: str) -> bool:
        """Check if text is likely search page noise/gibberish"""
        # Count special characters
        special_chars = sum(1 for c in text if not c.isalnum() and c != ' ')
        
        # If more than 40% special characters, likely noise
        if len(text) > 0 and special_chars / len(text) > 0.4:
            return True
            
        # Check for common search page OCR error patterns
        noise_indicators = ['¢', '°', 'vy', 'EH', '<>', 'oe', 'aa', 'baa', 'hittps', 'TSW', 'x |']
        if any(indicator in text for indicator in noise_indicators):
            return True
            
        # Skip weather widget coordinates and symbols
        if any(pattern in text for pattern in ['°¢|°F', 'TSW 1X2', '8pm tipm', 'aa.']):
            return True
            
        return False
    
    def open_website(self, url: str) -> bool:
        """Open a specific website"""
        try:
            # Check if URL has http:// or https:// prefix
            if not url.startswith(('http://', 'https://')):
                # Check if it's a common domain extension
                if any(url.endswith(ext) for ext in ['.com', '.org', '.net', '.edu', '.gov', '.io', '.co']):
                    url = 'https://' + url
                else:
                    # If no domain extension, assume .com
                    url = 'https://' + url + '.com'

            webbrowser.open(url)
            logging.info(f"Opened website: {url}")
            self.jarvis.speak(f"{url} opened")
            return True
        except Exception as e:
            logging.error(f"Error opening website: {str(e)}")
            self.jarvis.speak(f"Couldn't open {url}. Check the address or network.")
            return False
    
    def check_weather(self, location: str = "") -> bool:
        """Check weather for a location using Open-Meteo API"""
        try:
            # Clean up the location string to remove common prepositions
            location = location.lower().strip()
            for preposition in ["for", "in", "at", "near"]:
                location = location.replace(preposition + " ", "")
            
            # Default to Edmonton coordinates
            latitude = 53.5501
            longitude = -113.4687
            location_name = "Edmonton"
            
            # If a different location was specified, we would need geocoding 
            # (but for now we'll stick with Edmonton as that's the focus)
            
            # Direct API call using the format provided
            import requests
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": "temperature_2m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "America/Edmonton"
            }
            
            self.jarvis.speak(f"Checking current weather for {location_name}...")
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                
                # Extract weather data from the response
                hourly = data.get('hourly', {})
                daily = data.get('daily', {})
                
                # Get current temperature (first value in hourly data)
                current_temp = None
                if 'temperature_2m' in hourly and hourly['temperature_2m']:
                    current_temp = hourly['temperature_2m'][0]
                
                # Get daily high and low
                today_high = None
                today_low = None
                if 'temperature_2m_max' in daily and daily['temperature_2m_max']:
                    today_high = daily['temperature_2m_max'][0]
                if 'temperature_2m_min' in daily and daily['temperature_2m_min']:
                    today_low = daily['temperature_2m_min'][0]
                
                # Build weather report
                report = f"The current weather in {location_name} "
                if current_temp is not None:
                    report += f"has a temperature of {current_temp}°C. "
                else:
                    report += "temperature data is not available. "
                    
                if today_high is not None and today_low is not None:
                    report += f"Today's forecast shows a high of {today_high}°C and a low of {today_low}°C."
                
                # Check for precipitation
                if 'precipitation_sum' in daily and daily['precipitation_sum']:
                    precip = daily['precipitation_sum'][0]
                    if precip > 0:
                        report += f" Precipitation of {precip}mm expected today."
                
                self.jarvis.speak(report)
                return True
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                logging.error(f"Weather API error: {error_msg}")
                self.jarvis.speak("I couldn't retrieve the weather information at this time.")
                return False
                
        except Exception as e:
            logging.error(f"Error checking weather: {str(e)}")
            self.jarvis.speak("Unable to get weather data right now.")
            return False
    
    def search_wikipedia(self, query: str) -> bool:
        """Search for information on Wikipedia"""
        try:
            # Check if pywhatkit is available for Wikipedia search
            if self.HAVE_PYWHATKIT:
                try:
                    self.jarvis.speak(f"Searching Wikipedia for {query}...")
                    # Get 2 sentences from Wikipedia
                    result = self.pywhatkit.info(query, lines=2)
                    self.jarvis.speak(result)
                    return True
                except Exception as e:
                    logging.error(f"PyWhatKit Wikipedia search failed: {str(e)}")
                    # Continue to fallback method
            
            # Fallback to direct Wikipedia API
            import wikipedia
            
            self.jarvis.speak(f"Searching Wikipedia for {query}...")
            summary = wikipedia.summary(query, sentences=2)
            self.jarvis.speak(summary)
            
            return True
            
        except ImportError:
            # If Wikipedia module is not available
            logging.warning("Wikipedia module not available")
            self.jarvis.speak("I need the Wikipedia module to search Wikipedia. Please install it with 'pip install wikipedia'.")
            return False
        except Exception as e:
            logging.error(f"Error searching Wikipedia: {str(e)}")
            self.jarvis.speak(f"I couldn't find information about {query} on Wikipedia.")
            return False