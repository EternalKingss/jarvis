#!/usr/bin/env python3
"""
Install missing packages for Jarvis
"""

import subprocess
import sys

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def main():
    """Install required packages"""
    packages = [
        "pywhatkit",
        "requests",  # Ensure requests is installed
        "urllib3"    # Sometimes needed for requests
    ]
    
    print("Installing missing packages for Jarvis...")
    print("=" * 50)
    
    success_count = 0
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print("=" * 50)
    print(f"Installation complete: {success_count}/{len(packages)} packages installed successfully")
    
    if success_count == len(packages):
        print("🎉 All packages installed! Your Jarvis should now be able to play music properly.")
        print("\nNow restart Jarvis and try saying 'play some jazz music'")
    else:
        print("⚠️  Some packages failed to install. Please check the errors above.")

if __name__ == "__main__":
    main()
