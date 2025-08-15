"""
File Utils - File handling utilities for Jarvis
"""

import os
import shutil
import logging
import tempfile
import datetime
from typing import List, Optional, Tuple, Dict, Any


def get_file_info(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a file
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file information or None if file not found
    """
    try:
        if not os.path.exists(file_path):
            return None
            
        # Get file stats
        stats = os.stat(file_path)
        
        # Format timestamps
        creation_time = datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        modified_time = datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        access_time = datetime.datetime.fromtimestamp(stats.st_atime).strftime('%Y-%m-%d %H:%M:%S')
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()[1:] if ext else ""
        
        # Determine file type
        file_type = get_file_type(ext)
        
        # Calculate size in different units
        size_bytes = stats.st_size
        size_kb = size_bytes / 1024
        size_mb = size_kb / 1024
        size_gb = size_mb / 1024
        
        # Create info dictionary
        info = {
            'name': os.path.basename(file_path),
            'path': os.path.abspath(file_path),
            'directory': os.path.dirname(os.path.abspath(file_path)),
            'size_bytes': size_bytes,
            'size_kb': round(size_kb, 2),
            'size_mb': round(size_mb, 2),
            'size_gb': round(size_gb, 2),
            'extension': ext,
            'type': file_type,
            'created': creation_time,
            'modified': modified_time,
            'accessed': access_time,
            'is_file': os.path.isfile(file_path),
            'is_dir': os.path.isdir(file_path),
            'is_link': os.path.islink(file_path),
            'is_hidden': is_hidden_file(file_path)
        }
        
        return info
    except Exception as e:
        logging.error(f"Error getting file info: {str(e)}")
        return None


def get_file_type(extension: str) -> str:
    """
    Determine file type based on extension
    
    Args:
        extension: File extension (without dot)
        
    Returns:
        File type category
    """
    # File type mapping
    file_types = {
        # Documents
        'doc': 'Document',
        'docx': 'Document',
        'pdf': 'Document',
        'txt': 'Document',
        'rtf': 'Document',
        'odt': 'Document',
        'md': 'Document',
        
        # Spreadsheets
        'xls': 'Spreadsheet',
        'xlsx': 'Spreadsheet',
        'csv': 'Spreadsheet',
        'ods': 'Spreadsheet',
        
        # Presentations
        'ppt': 'Presentation',
        'pptx': 'Presentation',
        'odp': 'Presentation',
        
        # Images
        'jpg': 'Image',
        'jpeg': 'Image',
        'png': 'Image',
        'gif': 'Image',
        'bmp': 'Image',
        'tiff': 'Image',
        'svg': 'Image',
        'webp': 'Image',
        
        # Audio
        'mp3': 'Audio',
        'wav': 'Audio',
        'ogg': 'Audio',
        'flac': 'Audio',
        'aac': 'Audio',
        'wma': 'Audio',
        
        # Video
        'mp4': 'Video',
        'avi': 'Video',
        'mkv': 'Video',
        'mov': 'Video',
        'wmv': 'Video',
        'flv': 'Video',
        'webm': 'Video',
        
        # Archives
        'zip': 'Archive',
        'rar': 'Archive',
        '7z': 'Archive',
        'tar': 'Archive',
        'gz': 'Archive',
        
        # Code
        'py': 'Code',
        'js': 'Code',
        'html': 'Code',
        'css': 'Code',
        'java': 'Code',
        'cpp': 'Code',
        'c': 'Code',
        'h': 'Code',
        'php': 'Code',
        'rb': 'Code',
        'go': 'Code',
        'rs': 'Code',
        'swift': 'Code',
        'cs': 'Code',
        
        # Executables
        'exe': 'Executable',
        'msi': 'Executable',
        'app': 'Executable',
        'bat': 'Executable',
        'sh': 'Executable',
        
        # Databases
        'db': 'Database',
        'sqlite': 'Database',
        'sql': 'Database',
        
        # System
        'sys': 'System',
        'dll': 'System',
        'ini': 'System',
        'config': 'System',
        'log': 'System'
    }
    
    return file_types.get(extension.lower(), 'Other')


def is_hidden_file(file_path: str) -> bool:
    """
    Check if a file is hidden
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is hidden, False otherwise
    """
    # Get the file name without path
    file_name = os.path.basename(file_path)
    
    # Check if it's a hidden file (Unix-style dot files)
    if file_name.startswith('.'):
        return True
        
    # Check for Windows hidden attribute
    if os.name == 'nt':
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(file_path)
            return attrs != -1 and bool(attrs & 2)
        except:
            pass
            
    return False


def create_temp_file(content: str, prefix: str = "jarvis_", suffix: str = ".tmp") -> Optional[str]:
    """
    Create a temporary file with content
    
    Args:
        content: Content to write to the file
        prefix: File name prefix
        suffix: File name suffix
        
    Returns:
        Path to the temporary file or None if creation failed
    """
    try:
        fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        with os.fdopen(fd, 'w') as temp_file:
            temp_file.write(content)
        
        logging.info(f"Created temporary file: {temp_path}")
        return temp_path
    except Exception as e:
        logging.error(f"Error creating temporary file: {str(e)}")
        return None


def create_temp_directory(prefix: str = "jarvis_") -> Optional[str]:
    """
    Create a temporary directory
    
    Args:
        prefix: Directory name prefix
        
    Returns:
        Path to the temporary directory or None if creation failed
    """
    try:
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        logging.info(f"Created temporary directory: {temp_dir}")
        return temp_dir
    except Exception as e:
        logging.error(f"Error creating temporary directory: {str(e)}")
        return None


def get_writable_temp_dir(prefix: str = "jarvis_") -> str:
    """Return a user-writable temporary directory."""
    base = tempfile.gettempdir()
    try:
        test_dir = tempfile.mkdtemp(prefix=prefix, dir=base)
        return test_dir
    except Exception:
        alt_base = os.path.join(os.path.expanduser("~"), "JarvisTemp")
        os.makedirs(alt_base, exist_ok=True)
        return tempfile.mkdtemp(prefix=prefix, dir=alt_base)


def save_data_to_file(file_path: str, data: str, mode: str = 'w') -> bool:
    """
    Save data to a file
    
    Args:
        file_path: Path to the file
        data: Data to write
        mode: File open mode ('w' for write, 'a' for append)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        # Write data to file
        with open(file_path, mode) as f:
            f.write(data)
            
        logging.info(f"Saved data to file: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Error saving data to file: {str(e)}")
        return False


def read_file_data(file_path: str, encoding: str = 'utf-8') -> Optional[str]:
    """
    Read data from a file
    
    Args:
        file_path: Path to the file
        encoding: File encoding
        
    Returns:
        File contents or None if reading failed
    """
    try:
        if not os.path.exists(file_path):
            logging.error(f"File not found: {file_path}")
            return None
            
        with open(file_path, 'r', encoding=encoding) as f:
            data = f.read()
            
        return data
    except Exception as e:
        logging.error(f"Error reading file: {str(e)}")
        return None


def list_directory_contents(directory_path: str, include_hidden: bool = False) -> Optional[Dict[str, List[str]]]:
    """
    List contents of a directory
    
    Args:
        directory_path: Path to the directory
        include_hidden: Whether to include hidden files and directories
        
    Returns:
        Dictionary with 'files' and 'directories' lists or None if listing failed
    """
    try:
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            logging.error(f"Directory not found: {directory_path}")
            return None
            
        files = []
        directories = []
        
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            
            # Skip hidden items if not included
            if not include_hidden and is_hidden_file(item_path):
                continue
                
            if os.path.isfile(item_path):
                files.append(item)
            elif os.path.isdir(item_path):
                directories.append(item)
                
        return {
            'files': sorted(files),
            'directories': sorted(directories)
        }
    except Exception as e:
        logging.error(f"Error listing directory contents: {str(e)}")
        return None


def search_files(
    directory_path: str,
    name_pattern: Optional[str] = None,
    extension: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    recursive: bool = True,
    include_hidden: bool = False
) -> List[str]:
    """
    Search for files in a directory
    
    Args:
        directory_path: Path to the directory
        name_pattern: Pattern to match in file names
        extension: File extension to filter by
        min_size: Minimum file size in bytes
        max_size: Maximum file size in bytes
        recursive: Whether to search recursively
        include_hidden: Whether to include hidden files
        
    Returns:
        List of matching file paths
    """
    matching_files = []
    
    try:
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            logging.error(f"Directory not found: {directory_path}")
            return matching_files
            
        # Define walk function based on recursion setting
        if recursive:
            walk_func = os.walk
        else:
            def walk_func(path):
                yield path, [], [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            
        # Walk through directory
        for root, _, files in walk_func(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Skip hidden files if not included
                if not include_hidden and is_hidden_file(file_path):
                    continue
                    
                # Check name pattern
                if name_pattern and name_pattern.lower() not in file.lower():
                    continue
                    
                # Check extension
                if extension and not file.lower().endswith(f".{extension.lower()}"):
                    continue
                    
                # Check file size
                try:
                    file_size = os.path.getsize(file_path)
                    if min_size is not None and file_size < min_size:
                        continue
                    if max_size is not None and file_size > max_size:
                        continue
                except:
                    continue
                    
                matching_files.append(file_path)
                
        return matching_files
    except Exception as e:
        logging.error(f"Error searching files: {str(e)}")
        return matching_files


def copy_file(source_path: str, destination_path: str, overwrite: bool = True) -> bool:
    """
    Copy a file from source to destination
    
    Args:
        source_path: Path to the source file
        destination_path: Path to the destination file
        overwrite: Whether to overwrite existing destination
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(source_path):
            logging.error(f"Source file not found: {source_path}")
            return False
            
        # Check if destination exists and overwrite not allowed
        if os.path.exists(destination_path) and not overwrite:
            logging.error(f"Destination file already exists: {destination_path}")
            return False
            
        # Create destination directory if it doesn't exist
        destination_dir = os.path.dirname(destination_path)
        if destination_dir and not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
            
        # Copy the file
        shutil.copy2(source_path, destination_path)
        
        logging.info(f"Copied file from {source_path} to {destination_path}")
        return True
    except Exception as e:
        logging.error(f"Error copying file: {str(e)}")
        return False


def move_file(source_path: str, destination_path: str, overwrite: bool = True) -> bool:
    """
    Move a file from source to destination
    
    Args:
        source_path: Path to the source file
        destination_path: Path to the destination file
        overwrite: Whether to overwrite existing destination
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(source_path):
            logging.error(f"Source file not found: {source_path}")
            return False
            
        # Check if destination exists and overwrite not allowed
        if os.path.exists(destination_path) and not overwrite:
            logging.error(f"Destination file already exists: {destination_path}")
            return False
            
        # Create destination directory if it doesn't exist
        destination_dir = os.path.dirname(destination_path)
        if destination_dir and not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
            
        # Move the file
        shutil.move(source_path, destination_path)
        
        logging.info(f"Moved file from {source_path} to {destination_path}")
        return True
    except Exception as e:
        logging.error(f"Error moving file: {str(e)}")
        return False


def delete_file(file_path: str) -> bool:
    """
    Delete a file
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            logging.error(f"File not found: {file_path}")
            return False
            
        # Delete the file
        os.remove(file_path)
        
        logging.info(f"Deleted file: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Error deleting file: {str(e)}")
        return False


def create_directory(directory_path: str) -> bool:
    """
    Create a directory
    
    Args:
        directory_path: Path to the directory
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(directory_path):
            logging.info(f"Directory already exists: {directory_path}")
            return True
            
        # Create the directory and any parent directories
        os.makedirs(directory_path)
        
        logging.info(f"Created directory: {directory_path}")
        return True
    except Exception as e:
        logging.error(f"Error creating directory: {str(e)}")
        return False


def delete_directory(directory_path: str, recursive: bool = True) -> bool:
    """
    Delete a directory
    
    Args:
        directory_path: Path to the directory
        recursive: Whether to delete recursively
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(directory_path):
            logging.error(f"Directory not found: {directory_path}")
            return False
            
        if not os.path.isdir(directory_path):
            logging.error(f"Not a directory: {directory_path}")
            return False
            
        # Delete the directory
        if recursive:
            shutil.rmtree(directory_path)
        else:
            os.rmdir(directory_path)
            
        logging.info(f"Deleted directory: {directory_path}")
        return True
    except Exception as e:
        logging.error(f"Error deleting directory: {str(e)}")
        return False


def get_directory_size(directory_path: str) -> Optional[Dict[str, Any]]:
    """
    Calculate the size of a directory
    
    Args:
        directory_path: Path to the directory
        
    Returns:
        Dictionary with size information or None if calculation failed
    """
    try:
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            logging.error(f"Directory not found: {directory_path}")
            return None
            
        total_size = 0
        file_count = 0
        dir_count = 0
        
        for dirpath, dirnames, filenames in os.walk(directory_path):
            # Count directories
            dir_count += len(dirnames)
            
            # Count files and calculate size
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    file_count += 1
                except:
                    pass
                    
        # Calculate size in different units
        size_kb = total_size / 1024
        size_mb = size_kb / 1024
        size_gb = size_mb / 1024
        
        return {
            'total_bytes': total_size,
            'total_kb': round(size_kb, 2),
            'total_mb': round(size_mb, 2),
            'total_gb': round(size_gb, 2),
            'file_count': file_count,
            'directory_count': dir_count
        }
    except Exception as e:
        logging.error(f"Error calculating directory size: {str(e)}")
        return None


def clean_temp_files(directory: Optional[str] = None, prefix: str = "jarvis_", days_old: int = 7) -> int:
    """
    Clean up temporary files older than a certain number of days
    
    Args:
        directory: Directory to clean (default is system temp directory)
        prefix: File prefix to match
        days_old: Delete files older than this many days
        
    Returns:
        Number of files deleted
    """
    try:
        # Use system temp directory if none specified
        if not directory:
            directory = tempfile.gettempdir()
            
        if not os.path.exists(directory) or not os.path.isdir(directory):
            logging.error(f"Directory not found: {directory}")
            return 0
            
        # Calculate cutoff time
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days_old)
        cutoff_timestamp = cutoff_time.timestamp()
        
        # Track deleted files
        deleted_count = 0
        
        # Iterate through files in the directory
        for filename in os.listdir(directory):
            if filename.startswith(prefix):
                file_path = os.path.join(directory, filename)
                
                try:
                    # Check if it's a file
                    if not os.path.isfile(file_path):
                        continue
                        
                    # Check file age
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime < cutoff_timestamp:
                        # Delete the file
                        os.remove(file_path)
                        deleted_count += 1
                except:
                    pass
                    
        logging.info(f"Cleaned up {deleted_count} temporary files")
        return deleted_count
    except Exception as e:
        logging.error(f"Error cleaning temporary files: {str(e)}")
        return 0


def get_file_hash(file_path: str, algorithm: str = 'md5') -> Optional[str]:
    """
    Calculate the hash of a file
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (md5, sha1, sha256)
        
    Returns:
        File hash string or None if calculation failed
    """
    try:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            logging.error(f"File not found: {file_path}")
            return None
            
        import hashlib
        
        # Select hash algorithm
        if algorithm.lower() == 'md5':
            hash_func = hashlib.md5()
        elif algorithm.lower() == 'sha1':
            hash_func = hashlib.sha1()
        elif algorithm.lower() == 'sha256':
            hash_func = hashlib.sha256()
        else:
            logging.error(f"Unsupported hash algorithm: {algorithm}")
            return None
            
        # Calculate hash
        with open(file_path, 'rb') as f:
            # Read and update hash in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
                
        return hash_func.hexdigest()
    except Exception as e:
        logging.error(f"Error calculating file hash: {str(e)}")
        return None