"""
Monitor - System resource monitoring for Jarvis
"""

import os
import logging
import psutil
from typing import Optional, Dict, List, Tuple, Any


def monitor_system_resources():
    """
    Monitor system resources in real-time
    Returns tuple of (cpu_percent, memory_percent, disk_percent, top_processes)
    """
    try:
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # FIXED: Get disk usage with proper path for Windows
        import os
        if os.name == 'nt':  # Windows
            disk = psutil.disk_usage('C:')
        else:
            disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # Get running processes (top 5 by CPU)
        processes = []
        for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']),
                          key=lambda p: p.info['cpu_percent'] or 0,
                          reverse=True)[:5]:
            if proc.info['cpu_percent']:
                processes.append((proc.info['name'], proc.info['cpu_percent']))
        
        # FIXED: Use safe logging without problematic string formatting
        try:
            cpu_str = str(round(cpu_percent, 1))
            memory_str = str(round(memory_percent, 1))
            disk_str = str(round(disk_percent, 1))
            log_message = f"System monitoring - CPU: {cpu_str}%, Memory: {memory_str}%, Disk: {disk_str}%"
            logging.info(log_message)
        except Exception as log_error:
            # Fallback logging method if f-string fails
            logging.info(
                "System monitoring completed - CPU: %s%%, Memory: %s%%, Disk: %s%%",
                cpu_percent,
                memory_percent,
                disk_percent,
            )
        
        return (cpu_percent, memory_percent, disk_percent, processes)
    except Exception as e:
        logging.error(f"Error monitoring system: {e}")
        return None


def list_processes() -> Optional[List[Tuple[str, float, float]]]:
    """
    List running processes with CPU and memory usage
    Returns list of (name, cpu_percent, memory_percent) tuples
    """
    try:
        processes = []
        for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                          key=lambda p: p.info['cpu_percent'] or 0,
                          reverse=True)[:10]:
            name = proc.info['name']
            cpu = proc.info['cpu_percent'] or 0
            memory = proc.info['memory_percent'] or 0
            processes.append((name, cpu, round(memory, 1)))
        
        logging.info(f"Listed {len(processes)} top processes")
        return processes
    except Exception as e:
        logging.error(f"Error listing processes: {str(e)}")
        return None


def terminate_process(process_name: str) -> bool:
    """
    Terminate a process by name
    """
    try:
        killed = False
        for proc in psutil.process_iter(['pid', 'name']):
            if process_name.lower() in proc.info['name'].lower():
                try:
                    p = psutil.Process(proc.info['pid'])
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                    except Exception:
                        p.kill()
                    killed = True
                    logging.info(f"Terminated process: {proc.info['name']} (PID: {proc.info['pid']})")
                except psutil.AccessDenied:
                    logging.error(f"Access denied when terminating {proc.info['name']}")
                except Exception as e:
                    logging.error(f"Error terminating {proc.info['name']}: {e}")
        
        return killed
    except Exception as e:
        logging.error(f"Error terminating process: {str(e)}")
        return False


def monitor_network() -> Optional[Tuple[Dict[str, int], List[Tuple[str, str]]]]:
    """
    Monitor network connections
    Returns tuple of (status_counts, interfaces)
    """
    try:
        # Get network connections
        connections = psutil.net_connections()
        
        # Count connections by status
        status_counts = {}
        for conn in connections:
            status = conn.status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        # Get current network interfaces
        interfaces = []
        if_addrs = psutil.net_if_addrs()
        for interface_name, interface_addresses in if_addrs.items():
            for address in interface_addresses:
                if str(address.family) == 'AddressFamily.AF_INET':
                    interfaces.append((interface_name, address.address))
        
        logging.info(f"Network monitoring - {len(connections)} connections across {len(interfaces)} interfaces")
        
        return (status_counts, interfaces)
    except Exception as e:
        logging.error(f"Error monitoring network: {str(e)}")
        return None


def analyze_disk_usage(path: Optional[str] = None) -> Optional[Tuple[int, int, int, List[Tuple[str, int]]]]:
    """
    Analyze disk usage and find large files
    Returns tuple of (total_size, file_count, dir_count, large_files)
    """
    if not path:
        path = os.path.expanduser("~")
    
    try:
        # Get total disk usage
        total_size = 0
        file_count = 0
        dir_count = 0
        large_files = []  # (filename, size) tuples
        
        for dirpath, dirnames, filenames in os.walk(path):
            dir_count += len(dirnames)
            file_count += len(filenames)
            
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    size = os.path.getsize(fp)
                    total_size += size
                    
                    # Track files larger than 100MB
                    if size > 100 * 1024 * 1024:
                        large_files.append((os.path.basename(fp), size))
                except:
                    pass
        
        # Sort large files by size (largest first)
        large_files.sort(key=lambda x: x[1], reverse=True)
        
        logging.info(f"Disk analysis - {file_count} files, {dir_count} dirs, {total_size / (1024**3):.2f} GB total")
        
        return (total_size, file_count, dir_count, large_files)
    except Exception as e:
        logging.error(f"Error analyzing disk usage: {str(e)}")
        return None


def get_battery_status() -> Optional[Dict[str, Any]]:
    """
    Get battery status information
    Returns dictionary with battery info or None if no battery
    """
    try:
        battery = psutil.sensors_battery()
        if battery:
            status = {
                'percent': battery.percent,
                'power_plugged': battery.power_plugged,
                'secsleft': battery.secsleft
            }
            
            # Convert seconds left to more readable format
            if status['secsleft'] == psutil.POWER_TIME_UNLIMITED:
                status['time_left'] = 'Unlimited'
            elif status['secsleft'] == psutil.POWER_TIME_UNKNOWN:
                status['time_left'] = 'Unknown'
            else:
                hours, remainder = divmod(status['secsleft'], 3600)
                minutes, seconds = divmod(remainder, 60)
                status['time_left'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            logging.info(f"Battery status: {status['percent']}%, {'Plugged in' if status['power_plugged'] else 'Not plugged in'}")
            return status
        else:
            logging.info("No battery detected")
            return None
    except Exception as e:
        logging.error(f"Error getting battery status: {str(e)}")
        return None


def get_disk_partitions() -> Optional[List[Dict[str, Any]]]:
    """
    Get information about disk partitions
    Returns list of partition dictionaries
    """
    try:
        partitions = []
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt' and 'cdrom' in part.opts or part.fstype == '':
                # Skip CD-ROMs and empty partitions on Windows
                continue
                
            usage = psutil.disk_usage(part.mountpoint)
            
            partition_info = {
                'device': part.device,
                'mountpoint': part.mountpoint,
                'fstype': part.fstype,
                'opts': part.opts,
                'total_gb': usage.total / (1024**3),
                'used_gb': usage.used / (1024**3),
                'free_gb': usage.free / (1024**3),
                'percent': usage.percent
            }
            partitions.append(partition_info)
        
        logging.info(f"Disk partitions - Found {len(partitions)} partitions")
        return partitions
    except Exception as e:
        logging.error(f"Error getting disk partitions: {str(e)}")
        return None


def get_network_usage() -> Optional[Dict[str, float]]:
    """
    Get network usage statistics
    Returns dictionary with network usage info
    """
    try:
        # Get network IO counters
        net_io = psutil.net_io_counters()
        
        # Convert to MB for readability
        sent_mb = net_io.bytes_sent / (1024**2)
        recv_mb = net_io.bytes_recv / (1024**2)
        
        # Get network stats
        network_stats = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'errin': net_io.errin,
            'errout': net_io.errout,
            'dropin': net_io.dropin,
            'dropout': net_io.dropout,
            'sent_mb': sent_mb,
            'recv_mb': recv_mb
        }
        
        logging.info(f"Network usage - Sent: {sent_mb:.2f} MB, Received: {recv_mb:.2f} MB")
        return network_stats
    except Exception as e:
        logging.error(f"Error getting network usage: {str(e)}")
        return None


def get_cpu_info() -> Optional[Dict[str, Any]]:
    """
    Get detailed CPU information
    Returns dictionary with CPU info
    """
    try:
        # CPU count and usage
        cpu_count_physical = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        
        # CPU frequency
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            current_freq = cpu_freq.current
            min_freq = cpu_freq.min
            max_freq = cpu_freq.max
        else:
            current_freq = min_freq = max_freq = None
        
        # CPU temperature (if available)
        try:
            temperature = psutil.sensors_temperatures()
        except:
            temperature = None
        
        cpu_info = {
            'physical_cores': cpu_count_physical,
            'logical_cores': cpu_count_logical,
            'usage_per_core': cpu_percent,
            'current_freq': current_freq,
            'min_freq': min_freq,
            'max_freq': max_freq,
            'temperature': temperature
        }
        
        logging.info(f"CPU info - {cpu_count_physical} physical cores, {cpu_count_logical} logical cores")
        return cpu_info
    except Exception as e:
        logging.error(f"Error getting CPU info: {str(e)}")
        return None


def get_memory_info() -> Optional[Dict[str, Any]]:
    """
    Get detailed memory information
    Returns dictionary with memory info
    """
    try:
        # Virtual memory
        virtual_memory = psutil.virtual_memory()
        
        # Swap memory
        swap_memory = psutil.swap_memory()
        
        memory_info = {
            'total': virtual_memory.total,
            'available': virtual_memory.available,
            'used': virtual_memory.used,
            'free': virtual_memory.free,
            'percent': virtual_memory.percent,
            'swap_total': swap_memory.total,
            'swap_used': swap_memory.used,
            'swap_free': swap_memory.free,
            'swap_percent': swap_memory.percent,
            # Convert to GB for readability
            'total_gb': virtual_memory.total / (1024**3),
            'available_gb': virtual_memory.available / (1024**3),
            'used_gb': virtual_memory.used / (1024**3),
            'free_gb': virtual_memory.free / (1024**3),
            'swap_total_gb': swap_memory.total / (1024**3),
            'swap_used_gb': swap_memory.used / (1024**3),
            'swap_free_gb': swap_memory.free / (1024**3),
        }
        
        logging.info(f"Memory info - Total: {memory_info['total_gb']:.2f} GB, Used: {virtual_memory.percent}%")
        return memory_info
    except Exception as e:
        logging.error(f"Error getting memory info: {str(e)}")
        return None