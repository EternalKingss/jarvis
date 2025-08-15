"""
Media Commands - YouTube, audio/video playback commands for Jarvis
"""

import os
import logging
import webbrowser
import random
from typing import Any, Optional, Dict, List




class MediaCommands:
    """YouTube, audio/video playback commands for Jarvis"""
    
    def __init__(self, jarvis_instance: Any, config: dict):
        """Initialize media commands with Jarvis instance and configuration"""
        self.jarvis = jarvis_instance
        self.config = config
        
        # Load YouTube API key
        self.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        
        # Import required modules (assume they're installed)
        try:
            from googleapiclient.discovery import build
            if self.YOUTUBE_API_KEY:
                self.youtube = build("youtube", "v3", developerKey=self.YOUTUBE_API_KEY)
                self.HAVE_YOUTUBE_API = True
            else:
                self.HAVE_YOUTUBE_API = False
        except ImportError:
            self.HAVE_YOUTUBE_API = False
            
        try:
            import pywhatkit
            self.pywhatkit = pywhatkit
            self.HAVE_PYWHATKIT = True
        except ImportError:
            self.HAVE_PYWHATKIT = False
            
        try:
            import vlc
            self.vlc = vlc
            self.HAVE_VLC = True
        except ImportError:
            self.HAVE_VLC = False
    
    def play_youtube(self, query: str, announce: bool = True) -> bool:
        """Play a YouTube video based on a search query"""
        try:
            if not query:
                if announce:
                    self.jarvis.speak("Please specify what you want to play on YouTube.")
                return False
                
            # Method 1: Use PyWhatKit if available (most reliable)
            if self.HAVE_PYWHATKIT:
                try:
                    if announce:
                        self.jarvis.speak(f"Playing {query} on YouTube")
                    # This will open the first video result and play it
                    self.pywhatkit.playonyt(query)
                    logging.info(f"Played '{query}' on YouTube using PyWhatKit")
                    return True
                except Exception as e:
                    logging.error(f"PyWhatKit YouTube play failed: {str(e)}")
                    # Continue to next method
            
            # Method 2: Use YouTube API if available to get direct video URL
            if self.HAVE_YOUTUBE_API and self.youtube:
                try:
                    # Use YouTube Data API to search for video IDs
                    request = self.youtube.search().list(
                        part="snippet",
                        q=query,
                        maxResults=1,
                        type="video"
                    )
                    response = request.execute()
                    
                    if response.get('items', []):
                        video_id = response['items'][0]['id']['videoId']
                        video_title = response['items'][0]['snippet']['title']
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        webbrowser.open(url)
                        if announce:
                            self.jarvis.speak(f"Now playing: {video_title}")
                        logging.info(f"Played '{query}' on YouTube using API")
                        return True
                    else:
                        logging.warning(f"No YouTube results found for '{query}'")
                        # Continue to fallback method
                except Exception as e:
                    logging.error(f"YouTube API error: {str(e)}")
                    # Continue to fallback method
            
            # Method 3: Enhanced fallback - try to get first video directly
            import requests
            from urllib.parse import quote_plus
            
            try:
                # Try to scrape first video ID from YouTube search
                search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(search_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    import re
                    # Look for video IDs in the page
                    video_id_pattern = r'"videoId":"([^"]+)"'
                    matches = re.findall(video_id_pattern, response.text)
                    
                    if matches:
                        # Open the first video directly
                        video_url = f"https://www.youtube.com/watch?v={matches[0]}"
                        webbrowser.open(video_url)
                        if announce:
                            self.jarvis.speak(f"Playing {query} on YouTube")
                        logging.info(f"Playing first result for '{query}' on YouTube")
                        return True
            except Exception as e:
                logging.warning(f"Enhanced fallback failed: {e}")
            
            # Final fallback - open search page
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            if announce:
                self.jarvis.speak(f"Opening YouTube search for {query}")
            logging.info(f"Opened YouTube search for '{query}'")
            return True
            
        except Exception as e:
            logging.error(f"Error playing YouTube: {str(e)}")
            self.jarvis.speak("I had trouble playing YouTube")
            return False
    
    def play_video(self, video_path: str) -> bool:
        """Play a video file using VLC or default player"""
        try:
            if not os.path.exists(video_path):
                self.jarvis.speak(f"The video file {video_path} does not exist.")
                return False
                
            self.jarvis.speak(f"Playing video: {os.path.basename(video_path)}")
            
            # Use VLC if available
            if self.HAVE_VLC:
                try:
                    # Initialize VLC instance
                    instance = self.vlc.Instance('--quiet')
                    player = instance.media_player_new()
                    media = instance.media_new(video_path)
                    
                    if media is None:
                        logging.error("Failed to load media")
                        raise Exception("Failed to load media")
                        
                    player.set_media(media)
                    
                    # Start playing the video
                    player.play()
                    
                    # Let the video play for a moment
                    import time
                    time.sleep(1)
                    
                    logging.info(f"Playing video using VLC: {video_path}")
                    return True
                    
                except Exception as vlc_e:
                    logging.error(f"VLC playback error: {str(vlc_e)}")
                    # Continue to fallback method
            
            # Fallback to system default player
            if os.name == 'nt':  # Windows
                os.system(f'start "" "{video_path}"')
            else:
                # For macOS or Linux
                import subprocess
                subprocess.call(['xdg-open', video_path])
                
            logging.info(f"Playing video using system player: {video_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error playing video: {str(e)}")
            self.jarvis.speak("I had trouble playing the video")
            return False
    
    def play_music(self, query: str = "", music_path: str = "") -> bool:
        """Play music from a file or search for music online"""
        try:
            # Case 1: Specified file or directory
            if music_path and os.path.exists(music_path):
                if os.path.isfile(music_path):
                    # Play single music file
                    return self.play_audio_file(music_path)
                elif os.path.isdir(music_path):
                    # Play from music directory
                    return self.play_from_directory(music_path)
            
            # Case 2: Query for online music
            if query:
                # Announce once and let play_youtube do the work silently
                self.jarvis.speak(f"Playing {query} on YouTube")
                return self.play_youtube(query + " music", announce=False)
            
            # Case 3: Default music directory
            default_music_dir = os.path.join(os.path.expanduser("~"), "Music")
            if os.path.exists(default_music_dir):
                self.jarvis.speak("Playing music from your Music folder")
                return self.play_from_directory(default_music_dir)
                
            # Case 4: No valid options found
            self.jarvis.speak("I couldn't find any music to play. Please specify a song or artist.")
            return False
            
        except Exception as e:
            logging.error(f"Error playing music: {str(e)}")
            self.jarvis.speak("I had trouble playing music")
            return False
    
    def play_audio_file(self, audio_path: str) -> bool:
        """Play a single audio file"""
        try:
            if not os.path.exists(audio_path):
                self.jarvis.speak(f"The audio file {audio_path} does not exist.")
                return False
                
            self.jarvis.speak(f"Playing audio: {os.path.basename(audio_path)}")
            
            # Use VLC if available
            if self.HAVE_VLC:
                try:
                    # Initialize VLC instance
                    instance = self.vlc.Instance('--quiet')
                    player = instance.media_player_new()
                    media = instance.media_new(audio_path)
                    
                    if media is None:
                        logging.error("Failed to load media")
                        raise Exception("Failed to load media")
                        
                    player.set_media(media)
                    
                    # Start playing
                    player.play()
                    
                    logging.info(f"Playing audio using VLC: {audio_path}")
                    return True
                    
                except Exception as vlc_e:
                    logging.error(f"VLC playback error: {str(vlc_e)}")
                    # Continue to fallback method
            
            # Fallback to system default player
            if os.name == 'nt':  # Windows
                os.system(f'start "" "{audio_path}"')
            else:
                # For macOS or Linux
                import subprocess
                subprocess.call(['xdg-open', audio_path])
                
            logging.info(f"Playing audio using system player: {audio_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error playing audio file: {str(e)}")
            self.jarvis.speak("I had trouble playing the audio file")
            return False
    
    def play_from_directory(self, directory_path: str) -> bool:
        """Play audio files from a directory"""
        try:
            if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                self.jarvis.speak(f"The directory {directory_path} does not exist.")
                return False
                
            # Find audio files in the directory
            audio_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.wma']
            audio_files = []
            
            for file in os.listdir(directory_path):
                if any(file.lower().endswith(ext) for ext in audio_extensions):
                    audio_files.append(os.path.join(directory_path, file))
            
            if not audio_files:
                self.jarvis.speak(f"No audio files found in {directory_path}")
                return False
                
            # Play the first audio file found
            first_file = audio_files[0]
            self.jarvis.speak(f"Playing music from {os.path.basename(directory_path)}")
            return self.play_audio_file(first_file)
            
        except Exception as e:
            logging.error(f"Error playing from directory: {str(e)}")
            self.jarvis.speak("I had trouble playing music from the directory")
            return False
    
    def play_random_music(self, directory_path: Optional[str] = None) -> bool:
        """Play a random music file from the specified directory or default music folder"""
        try:
            # If no directory specified, use default music directory
            if not directory_path:
                directory_path = os.path.join(os.path.expanduser("~"), "Music")
            
            if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                self.jarvis.speak(f"The directory {directory_path} does not exist.")
                return False
                
            # Find audio files in the directory and subdirectories
            audio_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.wma']
            audio_files = []
            
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in audio_extensions):
                        audio_files.append(os.path.join(root, file))
            
            if not audio_files:
                self.jarvis.speak(f"No audio files found in {directory_path}")
                return False
                
            # Select a random audio file
            random_file = random.choice(audio_files)
            self.jarvis.speak(f"Playing random music: {os.path.basename(random_file)}")
            return self.play_audio_file(random_file)
            
        except Exception as e:
            logging.error(f"Error playing random music: {str(e)}")
            self.jarvis.speak("I had trouble playing random music")
            return False
    
    def search_youtube_videos(self, query: str, max_results: int = 5) -> bool:
        """Search for videos on YouTube and list results"""
        try:
            if not query:
                self.jarvis.speak("Please specify what you want to search for on YouTube.")
                return False
                
            # Use YouTube API if available
            if self.HAVE_YOUTUBE_API and self.youtube:
                try:
                    # Use YouTube Data API to search for videos
                    request = self.youtube.search().list(
                        part="snippet",
                        q=query,
                        maxResults=max_results,
                        type="video"
                    )
                    response = request.execute()
                    
                    if response.get('items', []):
                        self.jarvis.speak(f"Here are the top {len(response['items'])} results for {query} on YouTube:")
                        
                        for i, item in enumerate(response['items'], 1):
                            title = item['snippet']['title']
                            channel = item['snippet']['channelTitle']
                            self.jarvis.speak(f"{i}. {title} by {channel}")
                        
                        self.jarvis.speak("Would you like me to play any of these videos? If so, say the number.")
                        
                        # Wait for user response
                        choice = self.jarvis.listen(timeout=5)
                        
                        try:
                            # Check if the response is a number
                            choice_num = int(choice)
                            
                            if 1 <= choice_num <= len(response['items']):
                                video_id = response['items'][choice_num-1]['id']['videoId']
                                url = f"https://www.youtube.com/watch?v={video_id}"
                                webbrowser.open(url)
                                self.jarvis.speak(f"Playing video {choice_num}")
                                return True
                            else:
                                self.jarvis.speak("Invalid selection. Please try again.")
                                return False
                        except (ValueError, TypeError):
                            # Not a number or empty response
                            self.jarvis.speak("No selection made. You can search again if you'd like.")
                            return True
                    else:
                        self.jarvis.speak(f"No results found for {query} on YouTube.")
                        return False
                except Exception as e:
                    logging.error(f"YouTube API error: {str(e)}")
                    # Continue to fallback method
            
            # Fallback to opening YouTube search
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            webbrowser.open(url)
            logging.info(f"Opened YouTube search for '{query}'")
            self.jarvis.speak("YouTube search opened")
            return True
            
        except Exception as e:
            logging.error(f"Error searching YouTube: {str(e)}")
            self.jarvis.speak("I had trouble searching YouTube")
            return False
