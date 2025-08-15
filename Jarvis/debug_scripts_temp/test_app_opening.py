"""
Test the improved fallback application opening
"""
import os
import subprocess

def test_epic_games_paths():
    \"\"\"Test Epic Games paths\"\"\"
    print("Testing Epic Games paths...")
    
    epic_paths = [
        'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe',
        'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe',
        'C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe',
        'C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe'
    ]
    
    for path in epic_paths:
        if os.path.exists(path):
            print(f"  ✓ Epic Games found at: {path}")
            return path
        else:
            print(f"  ✗ Epic Games not found at: {path}")
    
    return None

def test_chrome_paths():
    \"\"\"Test Chrome paths\"\"\"
    print("Testing Chrome paths...")
    
    chrome_paths = [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"  ✓ Chrome found at: {path}")
            return path
        else:
            print(f"  ✗ Chrome not found at: {path}")
    
    return None

def test_windows_start_command():
    \"\"\"Test Windows start command\"\"\"
    print("Testing Windows start command...")
    
    try:
        # Test if we can use the start command
        result = subprocess.run('start "" "notepad"', shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✓ Windows start command works")
            return True
        else:
            print(f"  ✗ Windows start command failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ✗ Windows start command error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("TESTING IMPROVED APP OPENING")
    print("=" * 50)
    
    epic_path = test_epic_games_paths()
    chrome_path = test_chrome_paths()
    start_works = test_windows_start_command()
    
    print("\\n" + "=" * 50)
    print("SUMMARY:")
    print("=" * 50)
    
    if epic_path:
        print("✓ Epic Games should work with improved fallback")
    else:
        print("? Epic Games not found - will try Windows start command")
    
    if chrome_path:
        print("✓ Chrome should work with improved fallback")
    else:
        print("? Chrome not found - will try Windows start command")
    
    if start_works:
        print("✓ Windows start command works as final fallback")
    else:
        print("✗ Windows start command doesn't work")
    
    print("\\nThe improved fallback should now handle these apps better!")
