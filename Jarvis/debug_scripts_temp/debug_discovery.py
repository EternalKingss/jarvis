"""
Debug script to test program discovery
"""
import os
import sys

# Add the Jarvis directory to path
jarvis_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, jarvis_dir)

def test_program_discovery():
    """Test the program discovery function"""
    print("Testing program discovery...")
    
    search_dirs = [
        "C:\\Program Files",
        "C:\\Program Files (x86)",
    ]
    
    programs = []
    
    for directory in search_dirs:
        if os.path.exists(directory):
            print(f"\nScanning {directory}...")
            try:
                items = os.listdir(directory)
                print(f"Found {len(items)} items")
                
                for item in items[:20]:  # Just check first 20 for demo
                    item_path = os.path.join(directory, item)
                    if os.path.isdir(item_path):
                        # Look for .exe files in this directory
                        try:
                            files = os.listdir(item_path)
                            exe_files = [f for f in files if f.lower().endswith('.exe')]
                            if exe_files:
                                programs.append({
                                    'name': item,
                                    'path': os.path.join(item_path, exe_files[0]),
                                    'type': 'exe'
                                })
                                print(f"  ✓ {item} -> {exe_files[0]}")
                        except (PermissionError, FileNotFoundError) as e:
                            print(f"  ✗ {item} -> Access denied")
                            pass
            except (PermissionError, FileNotFoundError):
                print(f"Access denied to {directory}")
                pass
    
    print(f"\nTotal programs found: {len(programs)}")
    
    # Look for specific apps
    search_terms = ['chrome', 'epic', 'discord', 'steam']
    
    print("\nLooking for specific apps...")
    for term in search_terms:
        matches = []
        for prog in programs:
            if term in prog['name'].lower():
                matches.append(prog['name'])
        
        if matches:
            print(f"  {term}: Found {matches}")
        else:
            print(f"  {term}: Not found")
    
    return programs

def test_chrome_paths():
    """Test specific Chrome paths"""
    print("\nTesting Chrome paths...")
    
    chrome_paths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"  ✓ Chrome found at: {path}")
            return path
        else:
            print(f"  ✗ Chrome not found at: {path}")
    
    return None

def test_epic_paths():
    """Test Epic Games paths"""
    print("\nTesting Epic Games paths...")
    
    epic_paths = [
        "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe",
        "C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe",
        "C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win32\\EpicGamesLauncher.exe",
        "C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe",
    ]
    
    for path in epic_paths:
        if os.path.exists(path):
            print(f"  ✓ Epic Games found at: {path}")
            return path
        else:
            print(f"  ✗ Epic Games not found at: {path}")
    
    return None

if __name__ == "__main__":
    print("=" * 60)
    print("JARVIS PROGRAM DISCOVERY DEBUG")
    print("=" * 60)
    
    programs = test_program_discovery()
    chrome_path = test_chrome_paths()
    epic_path = test_epic_paths()
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    
    if chrome_path:
        print(f"✓ Chrome can be opened directly: {chrome_path}")
    else:
        print("✗ Chrome path needs to be found manually")
    
    if epic_path:
        print(f"✓ Epic Games can be opened directly: {epic_path}")
    else:
        print("✗ Epic Games path needs to be found manually")
    
    if len(programs) < 10:
        print("⚠ Very few programs discovered - discovery method may need improvement")
    else:
        print(f"✓ Discovery found {len(programs)} programs")
