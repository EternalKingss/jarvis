"""
Hardware - Hardware interactions for Jarvis
"""

import os
import logging
import datetime
from pathlib import Path
from typing import Optional

# Try to import optional dependencies
try:
    import pyautogui
    HAVE_PYAUTOGUI = True
except ImportError:
    HAVE_PYAUTOGUI = False
    logging.warning("PyAutoGUI not available - some features will be limited")

try:
    import vlc
    HAVE_VLC = True
except ImportError:
    HAVE_VLC = False
    logging.warning("VLC not available - video playback will be limited")


def adjust_volume(direction: str) -> bool:
    """
    Adjust system volume
    - direction: "up", "down", or "mute"
    """
    if not HAVE_PYAUTOGUI:
        logging.error("PyAutoGUI not available - cannot adjust volume")
        return False
        
    try:
        if direction == "up":
            for _ in range(5):  # Press 5 times for noticeable change
                pyautogui.press("volumeup")
            logging.info("Volume increased")
            return True
        elif direction == "down":
            for _ in range(5):  # Press 5 times for noticeable change
                pyautogui.press("volumedown")
            logging.info("Volume decreased")
            return True
        elif direction == "mute":
            pyautogui.press("volumemute")
            logging.info("Volume muted")
            return True
        else:
            logging.error(f"Unknown volume direction: {direction}")
            return False
    except Exception as e:
        logging.error(f"Error adjusting volume: {str(e)}")
        return False


def take_screenshot() -> Optional[str]:
    """
    Take a screenshot and save it to the desktop
    Returns the path to the screenshot if successful, None otherwise
    """
    if not HAVE_PYAUTOGUI:
        logging.error("PyAutoGUI not available - cannot take screenshot")
        return None
        
    try:
        # Create screenshot
        screenshot = pyautogui.screenshot()
        
        # Save to desktop
        desktop = Path.home() / "Desktop"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = desktop / f"Jarvis_Screenshot_{timestamp}.png"
        
        screenshot.save(str(file_path))
        logging.info(f"Screenshot saved: {file_path}")
        
        return str(file_path)
    except Exception as e:
        logging.error(f"Error taking screenshot: {str(e)}")
        return None


def play_video(video_path: str, fullscreen: bool = True) -> bool:
    """
    Play a video file using VLC or system default player
    """
    if not os.path.exists(video_path):
        logging.error(f"Video file not found: {video_path}")
        return False
        
    logging.info(f"Playing video: {video_path}")
    
    # Use VLC if available
    if HAVE_VLC:
        try:
            # Initialize VLC instance
            instance = vlc.Instance('--quiet')
            player = instance.media_player_new()
            media = instance.media_new(video_path)

            if media is None:
                logging.error("Failed to load media")
                raise Exception("Failed to load media")

            player.set_media(media)
            if fullscreen:
                player.set_fullscreen(True)

            # Start playing the video
            player.play()
            import time
            time.sleep(1)  # Delay to ensure the video starts playing

            # Wait until the video finishes playing
            while player.is_playing():
                time.sleep(0.9)

            # Stop the player and release resources
            player.stop()
            player.release()
            instance.release()
            
            return True
        except Exception as e:
            logging.error(f"VLC playback error: {str(e)}")
            # Continue to fallback method
    
    # Fallback to system default player
    try:
        if os.name == 'nt':  # Windows
            os.system(f'start /wait "" "{video_path}"')
        else:
            # For macOS or Linux
            import subprocess
            subprocess.call(['xdg-open', video_path])
            
        return True
    except Exception as e:
        logging.error(f"Error playing video with system player: {str(e)}")
        return False


def type_text(text: str) -> bool:
    """
    Type text using PyAutoGUI
    """
    if not HAVE_PYAUTOGUI:
        logging.error("PyAutoGUI not available - cannot type text")
        return False
        
    try:
        pyautogui.typewrite(text)
        logging.info(f"Typed text: {text}")
        return True
    except Exception as e:
        logging.error(f"Error typing text: {str(e)}")
        return False


def press_key(key: str, hold_time: float = 0) -> bool:
    """
    Press a keyboard key using PyAutoGUI
    """
    if not HAVE_PYAUTOGUI:
        logging.error("PyAutoGUI not available - cannot press key")
        return False
        
    try:
        if hold_time > 0:
            pyautogui.keyDown(key)
            import time
            time.sleep(hold_time)
            pyautogui.keyUp(key)
        else:
            pyautogui.press(key)
            
        logging.info(f"Pressed key: {key}")
        return True
    except Exception as e:
        logging.error(f"Error pressing key: {str(e)}")
        return False


def click_mouse(x: int = None, y: int = None, button: str = 'left') -> bool:
    """
    Click the mouse at specified coordinates
    If no coordinates are provided, click at current position
    """
    if not HAVE_PYAUTOGUI:
        logging.error("PyAutoGUI not available - cannot click mouse")
        return False
        
    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
            
        logging.info(f"Clicked {button} mouse button")
        return True
    except Exception as e:
        logging.error(f"Error clicking mouse: {str(e)}")
        return False


def move_mouse(x: int, y: int, duration: float = 0.25) -> bool:
    """
    Move the mouse to specified coordinates
    """
    if not HAVE_PYAUTOGUI:
        logging.error("PyAutoGUI not available - cannot move mouse")
        return False
        
    try:
        pyautogui.moveTo(x, y, duration=duration)
        logging.info(f"Moved mouse to ({x}, {y})")
        return True
    except Exception as e:
        logging.error(f"Error moving mouse: {str(e)}")
        return False


def get_screen_size() -> tuple:
    """
    Get the screen size
    Returns a tuple of (width, height)
    """
    if not HAVE_PYAUTOGUI:
        logging.error("PyAutoGUI not available - cannot get screen size")
        return (0, 0)
        
    try:
        width, height = pyautogui.size()
        logging.info(f"Screen size: {width}x{height}")
        return (width, height)
    except Exception as e:
        logging.error(f"Error getting screen size: {str(e)}")
        return (0, 0)