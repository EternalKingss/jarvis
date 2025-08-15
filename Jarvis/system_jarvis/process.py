"""
Process - Process management for Jarvis
"""

import os
import logging
import subprocess
import shutil
import psutil
from typing import Dict, List, Optional, Any, Tuple


def get_running_processes() -> List[Dict[str, Any]]:
    """
    Get list of running processes
    
    Returns:
        List of dictionaries with process information
    """
    processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'create_time', 'status']):
            try:
                # Get process info
                proc_info = proc.info
                
                # Skip processes with no name
                if not proc_info['name']:
                    continue
                    
                # Add process details
                process = {
                    'pid': proc_info['pid'],
                    'name': proc_info['name'],
                    'username': proc_info['username'],
                    'cpu_percent': proc_info['cpu_percent'] or 0,
                    'memory_percent': round(proc_info['memory_percent'] or 0, 2),
                    'create_time': proc_info['create_time'],
                    'status': proc_info['status']
                }
                
                # Try to get command line
                try:
                    process['cmdline'] = proc.cmdline()
                except:
                    process['cmdline'] = []
                
                # Try to get current working directory
                try:
                    process['cwd'] = proc.cwd()
                except:
                    process['cwd'] = None
                    
                processes.append(process)
            except:
                # Skip processes that disappear while iterating
                continue
                
        return processes
    except Exception as e:
        logging.error(f"Error getting running processes: {str(e)}")
        return []


def find_process_by_name(name: str) -> List[Dict[str, Any]]:
    """
    Find processes by name
    
    Args:
        name: Process name to search for
        
    Returns:
        List of dictionaries with process information
    """
    matching_processes = []
    
    try:
        # Get all running processes
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
            try:
                # Check if process name matches
                if name.lower() in proc.info['name'].lower():
                    # Add process details
                    process = {
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'username': proc.info['username'],
                        'cpu_percent': proc.info['cpu_percent'] or 0,
                        'memory_percent': round(proc.info['memory_percent'] or 0, 2)
                    }
                    
                    # Try to get command line
                    try:
                        process['cmdline'] = proc.cmdline()
                    except:
                        process['cmdline'] = []
                        
                    matching_processes.append(process)
            except:
                # Skip processes that disappear while iterating
                continue
                
        return matching_processes
    except Exception as e:
        logging.error(f"Error finding processes by name: {str(e)}")
        return []


def kill_process(pid: int) -> bool:
    """
    Kill a process by PID
    
    Args:
        pid: Process ID
        
    Returns:
        True if process was killed, False otherwise
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return False
            
        # Kill process
        process = psutil.Process(pid)
        process.terminate()
        
        # Wait for process to terminate
        gone, still_alive = psutil.wait_procs([process], timeout=3)
        
        # Force kill if still alive
        if still_alive:
            for p in still_alive:
                p.kill()
                
        logging.info(f"Killed process with PID {pid}")
        return True
    except Exception as e:
        logging.error(f"Error killing process: {str(e)}")
        return False


def kill_processes_by_name(name: str) -> int:
    """
    Kill all processes with a given name
    
    Args:
        name: Process name
        
    Returns:
        Number of processes killed
    """
    killed_count = 0
    
    try:
        # Find processes by name
        matching_processes = find_process_by_name(name)
        
        # Kill each matching process
        for process in matching_processes:
            pid = process['pid']
            if kill_process(pid):
                killed_count += 1
                
        logging.info(f"Killed {killed_count} processes with name '{name}'")
        return killed_count
    except Exception as e:
        logging.error(f"Error killing processes by name: {str(e)}")
        return 0


def get_process_details(pid: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a process
    
    Args:
        pid: Process ID
        
    Returns:
        Dictionary with process details or None if process not found
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return None
            
        # Get process
        process = psutil.Process(pid)
        
        # Collect process details
        details = {
            'pid': process.pid,
            'name': process.name(),
            'status': process.status(),
            'created': process.create_time(),
            'username': process.username(),
            'cpu_percent': process.cpu_percent(interval=0.1),
            'memory_percent': process.memory_percent(),
            'memory_info': dict(process.memory_info()._asdict()),
            'num_threads': process.num_threads(),
        }
        
        # Try to get additional details
        try:
            details['cmdline'] = process.cmdline()
        except:
            details['cmdline'] = []
            
        try:
            details['cwd'] = process.cwd()
        except:
            details['cwd'] = None
            
        try:
            details['exe'] = process.exe()
        except:
            details['exe'] = None
            
        try:
            details['parent'] = {
                'pid': process.parent().pid,
                'name': process.parent().name()
            } if process.parent() else None
        except:
            details['parent'] = None
            
        try:
            details['children'] = [
                {'pid': child.pid, 'name': child.name()}
                for child in process.children()
            ]
        except:
            details['children'] = []
            
        try:
            details['open_files'] = [
                {'path': f.path, 'fd': f.fd}
                for f in process.open_files()
            ]
        except:
            details['open_files'] = []
            
        try:
            details['connections'] = [
                {
                    'fd': c.fd,
                    'family': c.family,
                    'type': c.type,
                    'laddr': c.laddr._asdict() if c.laddr else None,
                    'raddr': c.raddr._asdict() if c.raddr else None,
                    'status': c.status
                }
                for c in process.connections()
            ]
        except:
            details['connections'] = []
            
        return details
    except Exception as e:
        logging.error(f"Error getting process details: {str(e)}")
        return None


def run_command(command: str, shell: bool = True, timeout: Optional[int] = None) -> Dict[str, Any]:
    """
    Run a system command
    
    Args:
        command: Command to run
        shell: Whether to use shell
        timeout: Command timeout in seconds
        
    Returns:
        Dictionary with command execution results
    """
    result = {
        'success': False,
        'returncode': None,
        'stdout': '',
        'stderr': '',
        'error': None
    }
    
    try:
        # Run command
        process = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # Collect results
        result['success'] = process.returncode == 0
        result['returncode'] = process.returncode
        result['stdout'] = process.stdout
        result['stderr'] = process.stderr
        
        logging.info(f"Command executed: {command}, Return code: {process.returncode}")
        return result
    except subprocess.TimeoutExpired:
        result['error'] = f"Command timed out after {timeout} seconds"
        logging.error(f"Command timed out: {command}")
        return result
    except Exception as e:
        result['error'] = str(e)
        logging.error(f"Error running command: {str(e)}")
        return result


def start_process(executable: str, args: List[str] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Start a new process
    
    Args:
        executable: Path to executable
        args: Command line arguments
        cwd: Working directory
        
    Returns:
        Dictionary with process information
    """
    result = {
        'success': False,
        'pid': None,
        'error': None
    }
    
    try:
        # Check if executable exists
        if not os.path.exists(executable) and not shutil.which(executable):
            result['error'] = f"Executable not found: {executable}"
            return result
            
        # Build command
        cmd = [executable]
        if args:
            cmd.extend(args)
            
        # Start process
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )
        
        # Collect results
        result['success'] = True
        result['pid'] = process.pid
        
        logging.info(f"Process started: {executable}, PID: {process.pid}")
        return result
    except Exception as e:
        result['error'] = str(e)
        logging.error(f"Error starting process: {str(e)}")
        return result


def get_top_processes(count: int = 5, sort_by: str = 'cpu') -> List[Dict[str, Any]]:
    """
    Get top processes by CPU or memory usage
    
    Args:
        count: Number of processes to return
        sort_by: Sort by 'cpu' or 'memory'
        
    Returns:
        List of dictionaries with process information
    """
    try:
        # Get all processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
            try:
                # Get process info
                proc_info = proc.info
                
                # Skip processes with no name
                if not proc_info['name']:
                    continue
                    
                # Get CPU percent (may be None)
                cpu_percent = proc_info['cpu_percent'] or 0
                
                # Get memory percent (may be None)
                memory_percent = proc_info['memory_percent'] or 0
                
                # Add process details
                process = {
                    'pid': proc_info['pid'],
                    'name': proc_info['name'],
                    'username': proc_info['username'],
                    'cpu_percent': cpu_percent,
                    'memory_percent': round(memory_percent, 2)
                }
                
                processes.append(process)
            except:
                # Skip processes that disappear while iterating
                continue
                
        # Sort processes
        if sort_by.lower() == 'memory':
            processes.sort(key=lambda x: x['memory_percent'], reverse=True)
        else:  # Default to CPU
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
        return processes[:count]
    except Exception as e:
        logging.error(f"Error getting top processes: {str(e)}")
        return []


def is_process_running(name: str) -> bool:
    """
    Check if a process with the given name is running
    
    Args:
        name: Process name
        
    Returns:
        True if process is running, False otherwise
    """
    try:
        # Find processes by name
        matching_processes = find_process_by_name(name)
        
        return len(matching_processes) > 0
    except Exception as e:
        logging.error(f"Error checking if process is running: {str(e)}")
        return False


def get_process_cpu_times(pid: int) -> Optional[Dict[str, float]]:
    """
    Get CPU times for a process
    
    Args:
        pid: Process ID
        
    Returns:
        Dictionary with CPU times or None if process not found
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return None
            
        # Get process
        process = psutil.Process(pid)
        
        # Get CPU times
        cpu_times = process.cpu_times()
        
        return {
            'user': cpu_times.user,
            'system': cpu_times.system,
            'children_user': getattr(cpu_times, 'children_user', 0),
            'children_system': getattr(cpu_times, 'children_system', 0)
        }
    except Exception as e:
        logging.error(f"Error getting process CPU times: {str(e)}")
        return None


def get_process_memory_info(pid: int) -> Optional[Dict[str, int]]:
    """
    Get detailed memory info for a process
    
    Args:
        pid: Process ID
        
    Returns:
        Dictionary with memory info or None if process not found
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return None
            
        # Get process
        process = psutil.Process(pid)
        
        # Get memory info
        memory_info = process.memory_info()
        
        # Convert namedtuple to dictionary
        return dict(memory_info._asdict())
    except Exception as e:
        logging.error(f"Error getting process memory info: {str(e)}")
        return None


def get_process_io_counters(pid: int) -> Optional[Dict[str, int]]:
    """
    Get I/O counters for a process
    
    Args:
        pid: Process ID
        
    Returns:
        Dictionary with I/O counters or None if process not found
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return None
            
        # Get process
        process = psutil.Process(pid)
        
        # Get I/O counters
        io_counters = process.io_counters()
        
        return {
            'read_count': io_counters.read_count,
            'write_count': io_counters.write_count,
            'read_bytes': io_counters.read_bytes,
            'write_bytes': io_counters.write_bytes
        }
    except Exception as e:
        logging.error(f"Error getting process I/O counters: {str(e)}")
        return None


def suspend_process(pid: int) -> bool:
    """
    Suspend a process
    
    Args:
        pid: Process ID
        
    Returns:
        True if process was suspended, False otherwise
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return False
            
        # Get process
        process = psutil.Process(pid)
        
        # Suspend process
        process.suspend()
        
        logging.info(f"Suspended process with PID {pid}")
        return True
    except Exception as e:
        logging.error(f"Error suspending process: {str(e)}")
        return False


def resume_process(pid: int) -> bool:
    """
    Resume a suspended process
    
    Args:
        pid: Process ID
        
    Returns:
        True if process was resumed, False otherwise
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return False
            
        # Get process
        process = psutil.Process(pid)
        
        # Resume process
        process.resume()
        
        logging.info(f"Resumed process with PID {pid}")
        return True
    except Exception as e:
        logging.error(f"Error resuming process: {str(e)}")
        return False


def set_process_priority(pid: int, priority: str) -> bool:
    """
    Set process priority
    
    Args:
        pid: Process ID
        priority: Priority level (high, above_normal, normal, below_normal, idle)
        
    Returns:
        True if priority was set, False otherwise
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return False
            
        # Get process
        process = psutil.Process(pid)
        
        # Map priority names to values
        priority_map = {
            'high': psutil.HIGH_PRIORITY_CLASS,
            'above_normal': psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            'normal': psutil.NORMAL_PRIORITY_CLASS,
            'below_normal': psutil.BELOW_NORMAL_PRIORITY_CLASS,
            'idle': psutil.IDLE_PRIORITY_CLASS
        }
        
        # Set priority
        if priority.lower() in priority_map:
            process.nice(priority_map[priority.lower()])
            logging.info(f"Set priority of process with PID {pid} to {priority}")
            return True
        else:
            logging.error(f"Invalid priority: {priority}")
            return False
    except Exception as e:
        logging.error(f"Error setting process priority: {str(e)}")
        return False


def get_process_command_line(pid: int) -> Optional[List[str]]:
    """
    Get command line for a process
    
    Args:
        pid: Process ID
        
    Returns:
        List of command line arguments or None if process not found
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return None
            
        # Get process
        process = psutil.Process(pid)
        
        # Get command line
        return process.cmdline()
    except Exception as e:
        logging.error(f"Error getting process command line: {str(e)}")
        return None


def get_process_environment(pid: int) -> Optional[Dict[str, str]]:
    """
    Get environment variables for a process
    
    Args:
        pid: Process ID
        
    Returns:
        Dictionary with environment variables or None if process not found
    """
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            logging.error(f"Process with PID {pid} not found")
            return None
            
        # Get process
        process = psutil.Process(pid)
        
        # Get environment variables
        return process.environ()
    except Exception as e:
        logging.error(f"Error getting process environment: {str(e)}")
        return None