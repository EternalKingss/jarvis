"""Enhanced error handling utilities for Jarvis."""

import logging
import functools
import traceback
from typing import Callable, Any, Optional


class JarvisError(Exception):
    """Base exception class for Jarvis errors."""
    pass

def handle_errors(default_return=False, speak_error=True, log_traceback=True):
    """
    Decorator to handle errors gracefully in Jarvis commands
    
    Args:
        default_return: Value to return on error
        speak_error: Whether to speak the error message
        log_traceback: Whether to log full traceback
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                # Log the error
                error_msg = f"Error in {func.__name__}: {str(e)}"
                logging.error(error_msg)
                
                # Log full traceback if requested
                if log_traceback:
                    logging.debug(f"Full traceback for {func.__name__}:\n{traceback.format_exc()}")
                
                # Speak error if requested and jarvis instance available
                if speak_error and hasattr(self, 'jarvis'):
                    # Make error message more user-friendly
                    user_error = (
                        f"I encountered an error executing your request. {str(e)}"
                    )
                    self.jarvis.speak(user_error)
                
                return default_return
        return wrapper
    return decorator


def safe_execute(func: Callable, default_return=None, *args, **kwargs) -> Any:
    """
    Safely execute a function with error handling
    
    Args:
        func: Function to execute
        default_return: Value to return on error
        *args, **kwargs: Arguments to pass to function
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"Error executing {func.__name__}: {str(e)}")
        return default_return


class ErrorContext:
    """Context manager for error handling in code blocks"""
    
    def __init__(self, operation_name: str, jarvis_instance=None, speak_errors=True):
        self.operation_name = operation_name
        self.jarvis = jarvis_instance
        self.speak_errors = speak_errors
        self.error_occurred = False
        self.error_message = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error_occurred = True
            self.error_message = str(exc_val)
            
            # Log the error
            logging.error(f"Error in {self.operation_name}: {self.error_message}")
            logging.debug(f"Full traceback:\n{traceback.format_exc()}")
            
            # Speak error if requested
            if self.speak_errors and self.jarvis:
                user_error = f"I encountered an error during {self.operation_name}"
                self.jarvis.speak(user_error)
            
            # Suppress the exception (return True)
            return True
        return False


# Specific error handlers for common Jarvis operations
def handle_speech_errors(func: Callable) -> Callable:
    """Decorator specifically for speech-related operations"""
    return handle_errors(
        default_return="",
        speak_error=False,  # Don't speak speech errors to avoid loops
        log_traceback=True
    )(func)


def handle_api_errors(func: Callable) -> Callable:
    """Decorator specifically for API operations"""
    return handle_errors(
        default_return=None,
        speak_error=True,
        log_traceback=False  # API errors usually don't need full traceback
    )(func)


def handle_system_errors(func: Callable) -> Callable:
    """Decorator specifically for system operations"""
    return handle_errors(
        default_return=False,
        speak_error=True,
        log_traceback=True,
    )(func)
