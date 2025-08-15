"""
File Commands - File operations and search commands for Jarvis
"""

import os
import logging
import platform
from typing import Any, List, Optional, Tuple




class FileCommands:
    """File operations and search commands for Jarvis"""
    
    def __init__(self, jarvis_instance: Any, config: dict):
        """Initialize file commands with Jarvis instance and configuration"""
        self.jarvis = jarvis_instance
        self.config = config
    
    def search_files(self, query: str, file_type: Optional[str] = None, content_search: bool = False) -> bool:
        """
        Search for files on the system
        - query: Search term
        - file_type: Filter by extension (e.g., "pdf", "docx")
        - content_search: Whether to search file contents (slower)
        """
        try:
            self.jarvis.speak(f"Searching for {query}")

            # Determine search locations
            if platform.system() == "Windows":
                # Expanded locations on Windows
                locations = [
                    os.path.join(os.path.expanduser("~")),  # Entire user directory
                    # "C:\\",  # Entire C drive (commented out because it can be very slow)
                ]
            else:
                # Linux/Mac
                locations = [os.path.expanduser("~")]

            found_files = []
            query_lower = query.lower()

            # Search each location
            for current_location in locations:
                if not os.path.exists(current_location):
                    continue

                for root, dirs, files in os.walk(current_location):
                    for file in files:
                        # Filter by file type if specified
                        if file_type and not file.lower().endswith(f".{file_type.lower()}"):
                            continue

                        file_path = os.path.join(root, file)

                        # Check filename
                        if query_lower in file.lower():
                            found_files.append(file_path)

                        # Check content if requested
                        elif content_search:
                            try:
                                # Simple content search for text files
                                if os.path.getsize(file_path) < 10000000:  # Size limit
                                    with open(file_path, 'r', errors='ignore') as f:
                                        content = f.read()
                                        if query_lower in content.lower():
                                            found_files.append(file_path)
                            except:
                                pass

                        if len(found_files) >= 50:  # Limit results
                            break

                    if len(found_files) >= 50:
                        break

                if len(found_files) >= 50:
                    break

            # Report results
            if not found_files:
                self.jarvis.speak("I couldn't find any files matching your query.")
                return False

            self.jarvis.speak(f"I found {len(found_files)} files matching '{query}'.")

            # Group files by type for better reporting
            file_types = {}
            for found in found_files:
                ext = os.path.splitext(found)[1].lower()
                if ext not in file_types:
                    file_types[ext] = []
                file_types[ext].append(found)

            # Report by file type
            for ext, files in file_types.items():
                ext_name = ext[1:] if ext.startswith('.') else ext
                self.jarvis.speak(f"Found {len(files)} {ext_name} files.")

            # List some examples
            self.jarvis.speak("Here are some examples:")
            for i, found in enumerate(found_files[:5], 1):
                self.jarvis.speak(f"File {i}: {os.path.basename(found)} in {os.path.dirname(found)}")

            return True

        except Exception as e:
            logging.error(f"Error in file search: {str(e)}")
            self.jarvis.speak("I encountered an error while searching files.")
            return False
    
    def scan_directory(self, directory: Optional[str] = None) -> bool:
        """Scan a directory and report its contents"""
        try:
            # If no directory specified, use current directory
            if not directory:
                directory = os.getcwd()
                
            # Handle user home directory shorthand
            if directory.startswith('~'):
                directory = os.path.expanduser(directory)
                
            # Check if directory exists
            if not os.path.exists(directory):
                self.jarvis.speak(f"The directory {directory} does not exist.")
                return False
                
            # Get directory contents
            items = os.listdir(directory)
            
            # Count files and folders
            files = [item for item in items if os.path.isfile(os.path.join(directory, item))]
            folders = [item for item in items if os.path.isdir(os.path.join(directory, item))]
            
            # Group files by extension
            file_types = {}
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if not ext:
                    ext = '(no extension)'
                if ext not in file_types:
                    file_types[ext] = []
                file_types[ext].append(file)
                
            # Report results
            self.jarvis.speak(f"Directory {directory} contains {len(files)} files and {len(folders)} folders.")
            
            if file_types:
                self.jarvis.speak("File types include:")
                for ext, files_of_type in file_types.items():
                    ext_name = ext[1:] if ext.startswith('.') else ext
                    self.jarvis.speak(f"{len(files_of_type)} {ext_name} files")
                    
            if folders:
                self.jarvis.speak("Subdirectories include:")
                for i, folder in enumerate(folders[:5], 1):
                    if i <= 5:
                        self.jarvis.speak(f"{i}. {folder}")
                if len(folders) > 5:
                    self.jarvis.speak(f"And {len(folders) - 5} more folders.")
                    
            return True
            
        except Exception as e:
            logging.error(f"Error scanning directory: {str(e)}")
            self.jarvis.speak(f"I encountered an error while scanning the directory: {str(e)}")
            return False
    
    def create_directory(self, directory_name: str) -> bool:
        """Create a new directory"""
        try:
            # Handle user home directory shorthand
            if directory_name.startswith('~'):
                directory_name = os.path.expanduser(directory_name)
                
            # Check if directory already exists
            if os.path.exists(directory_name):
                self.jarvis.speak(f"The directory {directory_name} already exists.")
                return False
                
            # Create directory
            os.makedirs(directory_name)
            self.jarvis.speak(f"Created directory {directory_name}")
            logging.info(f"Created directory: {directory_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error creating directory: {str(e)}")
            self.jarvis.speak(f"I encountered an error while creating the directory: {str(e)}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file"""
        try:
            # Handle user home directory shorthand
            if file_path.startswith('~'):
                file_path = os.path.expanduser(file_path)
                
            # Check if file exists
            if not os.path.exists(file_path):
                self.jarvis.speak(f"The file {file_path} does not exist.")
                return False
                
            # Confirm deletion
            self.jarvis.speak(f"Are you sure you want to delete {file_path}? Say 'yes' to confirm.")
            
            # Wait for confirmation
            confirmation = self.jarvis.listen(timeout=5)
            if confirmation.lower() != "yes":
                self.jarvis.speak("Deletion canceled.")
                return False
                
            # Delete file
            os.remove(file_path)
            self.jarvis.speak(f"Deleted file {file_path}")
            logging.info(f"Deleted file: {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error deleting file: {str(e)}")
            self.jarvis.speak(f"I encountered an error while deleting the file: {str(e)}")
            return False
    
    def copy_file(self, source_path: str, destination_path: str) -> bool:
        """Copy a file from source to destination"""
        try:
            import shutil
            
            # Handle user home directory shorthand
            if source_path.startswith('~'):
                source_path = os.path.expanduser(source_path)
            if destination_path.startswith('~'):
                destination_path = os.path.expanduser(destination_path)
                
            # Check if source exists
            if not os.path.exists(source_path):
                self.jarvis.speak(f"The source file {source_path} does not exist.")
                return False
                
            # Copy file
            shutil.copy2(source_path, destination_path)
            self.jarvis.speak(f"Copied {source_path} to {destination_path}")
            logging.info(f"Copied file: {source_path} to {destination_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error copying file: {str(e)}")
            self.jarvis.speak(f"I encountered an error while copying the file: {str(e)}")
            return False
    
    def move_file(self, source_path: str, destination_path: str) -> bool:
        """Move a file from source to destination"""
        try:
            import shutil
            
            # Handle user home directory shorthand
            if source_path.startswith('~'):
                source_path = os.path.expanduser(source_path)
            if destination_path.startswith('~'):
                destination_path = os.path.expanduser(destination_path)
                
            # Check if source exists
            if not os.path.exists(source_path):
                self.jarvis.speak(f"The source file {source_path} does not exist.")
                return False
                
            # Move file
            shutil.move(source_path, destination_path)
            self.jarvis.speak(f"Moved {source_path} to {destination_path}")
            logging.info(f"Moved file: {source_path} to {destination_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error moving file: {str(e)}")
            self.jarvis.speak(f"I encountered an error while moving the file: {str(e)}")
            return False