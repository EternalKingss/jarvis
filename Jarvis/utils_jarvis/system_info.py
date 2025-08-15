"""
System Info - System information gathering for Jarvis
"""

import platform
import socket
import locale
import psutil
import logging
from typing import Dict, Any


def get_system_info() -> Dict[str, Any]:
    """Collect system information"""
    info = {
        'os': platform.system(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'hostname': platform.node(),
        'memory': psutil.virtual_memory(),
    }

    # Safely get locale
    try:
        info['language'] = locale.getdefaultlocale()[0]
    except:
        info['language'] = 'en_US'

    # Get IP address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info['ip'] = s.getsockname()[0]
        s.close()
    except:
        info['ip'] = '127.0.0.1'
        
    # Add platform details
    try:
        if info['os'] == 'Windows':
            info['windows_edition'] = platform.win32_edition()
            info['windows_version'] = platform.win32_ver()
        elif info['os'] == 'Linux':
            info['linux_distribution'] = platform.freedesktop_os_release()
        elif info['os'] == 'Darwin':  # macOS
            info['mac_version'] = platform.mac_ver()
    except:
        # These are optional details, so don't crash if they're not available
        pass
        
    # Get disk information
    try:
        info['disks'] = []
        for part in psutil.disk_partitions(all=False):
            if part.mountpoint and part.fstype:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    info['disks'].append({
                        'device': part.device,
                        'mountpoint': part.mountpoint,
                        'fstype': part.fstype,
                        'total_gb': usage.total / (1024**3),
                        'used_gb': usage.used / (1024**3),
                        'free_gb': usage.free / (1024**3),
                        'percent': usage.percent
                    })
                except:
                    pass
    except:
        info['disks'] = []

    logging.info(f"System info collected: {info['os']} on {info['machine']}")
    return info


def get_os_name() -> str:
    """Get formatted OS name"""
    os_name = platform.system()
    
    if os_name == 'Windows':
        try:
            version = platform.win32_ver()[0]
            edition = platform.win32_edition()
            return f"Windows {version} {edition}"
        except:
            return f"Windows {platform.version()}"
    elif os_name == 'Darwin':
        try:
            version = platform.mac_ver()[0]
            return f"macOS {version}"
        except:
            return "macOS"
    elif os_name == 'Linux':
        try:
            distro = platform.freedesktop_os_release()
            return f"{distro.get('NAME', 'Linux')} {distro.get('VERSION', '')}"
        except:
            return "Linux"
    else:
        return os_name


def get_memory_status() -> Dict[str, Any]:
    """Get current memory status"""
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    return {
        'total_gb': round(memory.total / (1024**3), 2),
        'available_gb': round(memory.available / (1024**3), 2),
        'used_gb': round(memory.used / (1024**3), 2),
        'percent': memory.percent,
        'swap_total_gb': round(swap.total / (1024**3), 2),
        'swap_used_gb': round(swap.used / (1024**3), 2),
        'swap_percent': swap.percent
    }


def get_network_info() -> Dict[str, Any]:
    """Get network information"""
    network_info = {
        'interfaces': {},
        'connections': {
            'established': 0,
            'listen': 0,
            'time_wait': 0,
            'close_wait': 0,
            'other': 0
        }
    }
    
    # Get network interfaces
    for interface_name, addresses in psutil.net_if_addrs().items():
        network_info['interfaces'][interface_name] = []
        for address in addresses:
            addr_info = {
                'family': str(address.family),
                'address': address.address
            }
            network_info['interfaces'][interface_name].append(addr_info)
    
    # Count connection states
    for conn in psutil.net_connections():
        status = conn.status.lower()
        if status in network_info['connections']:
            network_info['connections'][status] += 1
        else:
            network_info['connections']['other'] += 1
    
    # Get network statistics
    net_io = psutil.net_io_counters()
    network_info['stats'] = {
        'bytes_sent': net_io.bytes_sent,
        'bytes_recv': net_io.bytes_recv,
        'packets_sent': net_io.packets_sent,
        'packets_recv': net_io.packets_recv,
        'mb_sent': round(net_io.bytes_sent / (1024**2), 2),
        'mb_recv': round(net_io.bytes_recv / (1024**2), 2)
    }
    
    return network_info


def get_users() -> list:
    """Get information about users logged in"""
    users = []
    
    for user in psutil.users():
        users.append({
            'name': user.name,
            'terminal': user.terminal,
            'host': user.host,
            'started': user.started,
        })
    
    return users


def get_boot_time() -> str:
    """Get system boot time in readable format"""
    import datetime
    boot_time_timestamp = psutil.boot_time()
    boot_time = datetime.datetime.fromtimestamp(boot_time_timestamp)
    return boot_time.strftime("%Y-%m-%d %H:%M:%S")