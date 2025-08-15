"""
Log - Logging utilities for Jarvis
"""

import os
import logging
import datetime
from typing import Optional





def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None) -> None:
    """
    Set up logging for Jarvis
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file path, defaults to jarvis_log.txt
    """
    # Set default log file if not provided
    if not log_file:
        log_file = 'jarvis_log.txt'
    
    # Convert string log level to actual level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    # Configure logging
    logging.basicConfig(
        filename=log_file,
        level=numeric_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True
    )

    root_logger = logging.getLogger('')
    has_console = any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)
    if not has_console:
        console = logging.StreamHandler()
        console.setLevel(numeric_level)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        console.setFormatter(formatter)
        root_logger.addHandler(console)
    
    logging.info(f"Logging initialized at level {log_level}")


def rotate_log_file(log_file: str = 'jarvis_log.txt', max_size_mb: int = 10) -> None:
    """
    Rotate the log file if it exceeds the maximum size
    
    Args:
        log_file: Log file path
        max_size_mb: Maximum size in megabytes
    """
    try:
        # Check if file exists
        if not os.path.exists(log_file):
            return
            
        # Check file size
        file_size_mb = os.path.getsize(log_file) / (1024 * 1024)
        if file_size_mb < max_size_mb:
            return
            
        # Rotate log file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{log_file}.{timestamp}"
        
        # Temporarily shut down logging
        for handler in logging.root.handlers[:]:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(log_file):
                handler.close()
                logging.root.removeHandler(handler)
        
        # Rename current log file
        os.rename(log_file, backup_file)
        
        # Set up logging again
        logging.basicConfig(
            filename=log_file,
            level=logging.root.level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            force=True
        )
        
        logging.info(f"Log file rotated, previous log saved as {backup_file}")
    except Exception as e:
        print(f"Error rotating log file: {str(e)}")


def log_system_info(system_info: dict) -> None:
    """
    Log system information at startup
    
    Args:
        system_info: Dictionary containing system information
    """
    logging.info("=== SYSTEM INFORMATION ===")
    logging.info(f"OS: {system_info.get('os', 'Unknown')}")
    logging.info(f"Version: {system_info.get('version', 'Unknown')}")
    logging.info(f"Machine: {system_info.get('machine', 'Unknown')}")
    logging.info(f"Processor: {system_info.get('processor', 'Unknown')}")
    logging.info(f"Hostname: {system_info.get('hostname', 'Unknown')}")
    logging.info(f"IP Address: {system_info.get('ip', 'Unknown')}")
    
    # Log memory information
    memory = system_info.get('memory')
    if memory:
        logging.info(f"Total Memory: {memory.total / (1024**3):.2f} GB")
        logging.info(f"Available Memory: {memory.available / (1024**3):.2f} GB")
        logging.info(f"Memory Usage: {memory.percent}%")
    
    logging.info("=========================")


def log_conversation(role: str, message: str) -> None:
    """
    Log conversation between user and Jarvis
    
    Args:
        role: 'user' or 'jarvis'
        message: The message content
    """
    role_display = "User" if role.lower() == 'user' else "Jarvis"
    logging.info(f"Conversation - {role_display}: {message}")


def log_command(command: str, success: bool) -> None:
    """
    Log command execution
    
    Args:
        command: The command that was executed
        success: Whether the command was successful
    """
    status = "succeeded" if success else "failed"
    logging.info(f"Command '{command}' {status}")


def log_error(error_message: str, exception: Optional[Exception] = None) -> None:
    """
    Log an error with optional exception details
    
    Args:
        error_message: Error message
        exception: Optional exception object
    """
    if exception:
        logging.error(f"{error_message}: {str(exception)}")
        logging.debug(f"Exception details:", exc_info=exception)
    else:
        logging.error(error_message)


def get_log_contents(lines: int = 50) -> str:
    """
    Get the most recent lines from the log file
    
    Args:
        lines: Number of lines to retrieve
    
    Returns:
        String containing the requested log lines
    """
    log_file = 'jarvis_log.txt'
    try:
        if not os.path.exists(log_file):
            return "Log file does not exist."
            
        with open(log_file, 'r') as f:
            log_lines = f.readlines()
            
        # Get the last N lines
        if len(log_lines) <= lines:
            return ''.join(log_lines)
        else:
            return ''.join(log_lines[-lines:])
    except Exception as e:
        return f"Error reading log file: {str(e)}"


def clear_log() -> bool:
    """
    Clear the log file
    
    Returns:
        True if successful, False otherwise
    """
    log_file = 'jarvis_log.txt'
    try:
        # Temporarily shut down logging
        for handler in logging.root.handlers[:]:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(log_file):
                handler.close()
                logging.root.removeHandler(handler)
        
        # Clear log file
        with open(log_file, 'w') as f:
            f.write('')
        
        # Set up logging again
        logging.basicConfig(
            filename=log_file,
            level=logging.root.level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        logging.info("Log file cleared")
        return True
    except Exception as e:
        print(f"Error clearing log file: {str(e)}")
        return False