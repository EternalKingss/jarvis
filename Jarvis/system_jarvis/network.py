"""
Network - Network operations for Jarvis
"""

import os
import socket
import logging
import subprocess
import requests
from typing import Dict, List, Optional, Any, Tuple


def get_ip_address() -> str:
    """
    Get the machine's current IP address
    
    Returns:
        IP address string
    """
    try:
        # Create a socket connection to get IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"  # Fallback to localhost


def check_internet_connection() -> bool:
    """
    Check if the internet connection is working
    
    Returns:
        True if connected, False otherwise
    """
    try:
        # Try connecting to Google's DNS server
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        pass
        
    # Fallback to checking a website
    try:
        response = requests.get("https://www.google.com", timeout=3)
        return response.status_code == 200
    except:
        return False


def get_hostname() -> str:
    """
    Get the machine's hostname
    
    Returns:
        Hostname string
    """
    return socket.gethostname()


def ping_host(host: str, count: int = 4, timeout: int = 2) -> Dict[str, Any]:
    """
    Ping a host and get response statistics
    
    Args:
        host: Hostname or IP address
        count: Number of pings to send
        timeout: Timeout in seconds
        
    Returns:
        Dictionary with ping results
    """
    results = {
        'host': host,
        'success': False,
        'packets_sent': count,
        'packets_received': 0,
        'packet_loss': 100.0,
        'min_time': None,
        'avg_time': None,
        'max_time': None,
        'error': None
    }
    
    try:
        # Determine platform-specific ping command
        if os.name == 'nt':  # Windows
            command = ['ping', '-n', str(count), '-w', str(timeout * 1000), host]
        else:  # Unix/Linux/Mac
            command = ['ping', '-c', str(count), '-W', str(timeout), host]
            
        # Execute ping command
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        # Check if ping was successful
        if process.returncode == 0:
            results['success'] = True
            
            # Parse ping statistics
            if os.name == 'nt':  # Windows output parsing
                # Parse packet loss
                for line in stdout.splitlines():
                    if "Lost = " in line:
                        loss_part = line.split("Lost = ")[1].split("(")[0].strip()
                        packets_received = count - int(loss_part)
                        results['packets_received'] = packets_received
                        results['packet_loss'] = (count - packets_received) / count * 100
                    elif "Minimum = " in line:
                        times = line.split("Minimum = ")[1].strip()
                        time_parts = times.split("ms")
                        if len(time_parts) >= 3:
                            results['min_time'] = float(time_parts[0].strip())
                            results['avg_time'] = float(time_parts[1].strip(",").strip())
                            results['max_time'] = float(time_parts[2].strip(",").strip())
            else:  # Unix/Linux/Mac output parsing
                for line in stdout.splitlines():
                    if "packets transmitted" in line:
                        parts = line.split(",")
                        if len(parts) >= 3:
                            # Parse received packets
                            received_part = parts[1].strip()
                            results['packets_received'] = int(received_part.split(" ")[0])
                            # Parse packet loss
                            loss_part = parts[2].strip()
                            results['packet_loss'] = float(loss_part.split("%")[0])
                    elif "min/avg/max" in line:
                        times_part = line.split("=")[1].strip()
                        time_values = times_part.split("/")
                        if len(time_values) >= 3:
                            results['min_time'] = float(time_values[0])
                            results['avg_time'] = float(time_values[1])
                            results['max_time'] = float(time_values[2].split(" ")[0])
        else:
            results['error'] = f"Ping failed: {stderr if stderr else 'Host unreachable'}"
            
        return results
    except Exception as e:
        results['error'] = f"Error pinging host: {str(e)}"
        return results


def scan_network(base_ip: Optional[str] = None, timeout: float = 0.5) -> List[Dict[str, Any]]:
    """
    Scan local network for active hosts
    
    Args:
        base_ip: Base IP address for scan (derived from current IP if None)
        timeout: Timeout for each host check
        
    Returns:
        List of dictionaries with active hosts information
    """
    active_hosts = []
    
    try:
        # Get base IP if not provided
        if not base_ip:
            current_ip = get_ip_address()
            base_ip = '.'.join(current_ip.split('.')[:3]) + '.'
            
        # Scan network (basic implementation)
        for i in range(1, 255):
            ip = base_ip + str(i)
            
            try:
                # Try to connect to the host
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, 80))
                if result == 0:
                    # Try to get hostname
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except:
                        hostname = ""
                        
                    active_hosts.append({
                        'ip': ip,
                        'hostname': hostname,
                        'port_80_open': True
                    })
                sock.close()
            except:
                pass
                
        return active_hosts
    except Exception as e:
        logging.error(f"Error scanning network: {str(e)}")
        return []


def get_network_interfaces() -> List[Dict[str, Any]]:
    """
    Get information about network interfaces
    
    Returns:
        List of dictionaries with interface information
    """
    interfaces = []
    
    try:
        # Try using netifaces library if available
        try:
            import netifaces
            
            # Get all interface names
            for iface in netifaces.interfaces():
                interface_info = {
                    'name': iface,
                    'addresses': {}
                }
                
                # Get addresses for interface
                addrs = netifaces.ifaddresses(iface)
                
                # IPv4 addresses
                if netifaces.AF_INET in addrs:
                    interface_info['addresses']['ipv4'] = []
                    for addr in addrs[netifaces.AF_INET]:
                        if 'addr' in addr:
                            interface_info['addresses']['ipv4'].append({
                                'ip': addr.get('addr'),
                                'netmask': addr.get('netmask'),
                                'broadcast': addr.get('broadcast')
                            })
                
                # IPv6 addresses
                if netifaces.AF_INET6 in addrs:
                    interface_info['addresses']['ipv6'] = []
                    for addr in addrs[netifaces.AF_INET6]:
                        if 'addr' in addr:
                            interface_info['addresses']['ipv6'].append({
                                'ip': addr.get('addr'),
                                'netmask': addr.get('netmask'),
                                'scope': addr.get('scope')
                            })
                
                # MAC address
                if netifaces.AF_LINK in addrs:
                    interface_info['addresses']['mac'] = []
                    for addr in addrs[netifaces.AF_LINK]:
                        if 'addr' in addr:
                            interface_info['addresses']['mac'].append({
                                'addr': addr.get('addr')
                            })
                
                # Gateway
                try:
                    gws = netifaces.gateways()
                    if 'default' in gws and netifaces.AF_INET in gws['default']:
                        gw_addr, gw_iface = gws['default'][netifaces.AF_INET]
                        if gw_iface == iface:
                            interface_info['gateway'] = gw_addr
                except:
                    pass
                
                interfaces.append(interface_info)
                
        # Fallback to socket and subprocess
        except ImportError:
            # Get hostname and IP
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            
            interface_info = {
                'name': 'default',
                'addresses': {
                    'ipv4': [{'ip': ip}]
                }
            }
            
            interfaces.append(interface_info)
            
            # Try to get more info on Windows
            if os.name == 'nt':
                try:
                    output = subprocess.check_output(['ipconfig', '/all'], text=True)
                    
                    current_interface = None
                    for line in output.splitlines():
                        line = line.strip()
                        
                        # New interface
                        if line.endswith(":") and not line.startswith("   "):
                            current_interface = {
                                'name': line[:-1],
                                'addresses': {}
                            }
                            interfaces.append(current_interface)
                        
                        # IPv4 address
                        elif "IPv4 Address" in line and current_interface:
                            ip = line.split(":")[-1].strip()
                            if 'ipv4' not in current_interface['addresses']:
                                current_interface['addresses']['ipv4'] = []
                            current_interface['addresses']['ipv4'].append({'ip': ip})
                        
                        # MAC address
                        elif "Physical Address" in line and current_interface:
                            mac = line.split(":")[-1].strip()
                            if 'mac' not in current_interface['addresses']:
                                current_interface['addresses']['mac'] = []
                            current_interface['addresses']['mac'].append({'addr': mac})
                except:
                    pass
            
            # Try to get more info on Unix/Linux/Mac
            else:
                try:
                    output = subprocess.check_output(['ifconfig'], text=True)
                    
                    current_interface = None
                    for line in output.splitlines():
                        line = line.strip()
                        
                        # New interface
                        if line and not line.startswith(" "):
                            iface_name = line.split(":")[0].split(" ")[0]
                            current_interface = {
                                'name': iface_name,
                                'addresses': {}
                            }
                            interfaces.append(current_interface)
                        
                        # IPv4 address
                        elif "inet " in line and current_interface:
                            parts = line.split()
                            ip = None
                            for i, part in enumerate(parts):
                                if part == "inet":
                                    ip = parts[i + 1].split("/")[0]
                                    break
                            
                            if ip:
                                if 'ipv4' not in current_interface['addresses']:
                                    current_interface['addresses']['ipv4'] = []
                                current_interface['addresses']['ipv4'].append({'ip': ip})
                        
                        # MAC address
                        elif "ether " in line and current_interface:
                            mac = line.split("ether ")[1].split(" ")[0]
                            if 'mac' not in current_interface['addresses']:
                                current_interface['addresses']['mac'] = []
                            current_interface['addresses']['mac'].append({'addr': mac})
                except:
                    pass
        
        return interfaces
    except Exception as e:
        logging.error(f"Error getting network interfaces: {str(e)}")
        return []


def get_open_ports(host: str, start_port: int = 1, end_port: int = 1024, timeout: float = 0.5) -> List[int]:
    """
    Scan a host for open ports
    
    Args:
        host: Hostname or IP address
        start_port: First port to scan
        end_port: Last port to scan
        timeout: Timeout for each port check
        
    Returns:
        List of open ports
    """
    open_ports = []
    
    try:
        # Limit scan range for safety
        if end_port > 10000:
            end_port = 10000
            
        # Scan ports
        for port in range(start_port, end_port + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                open_ports.append(port)
                
        return open_ports
    except Exception as e:
        logging.error(f"Error scanning ports: {str(e)}")
        return []


def get_public_ip() -> Optional[str]:
    """
    Get public IP address by querying an external service
    
    Returns:
        Public IP address string or None if unavailable
    """
    try:
        # Try multiple services
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
            "https://ident.me"
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=3)
                if response.status_code == 200:
                    ip = response.text.strip()
                    if ip and len(ip) <= 45:  # Max length for IPv6
                        return ip
            except:
                continue
                
        return None
    except Exception as e:
        logging.error(f"Error getting public IP: {str(e)}")
        return None


def trace_route(host: str, max_hops: int = 30, timeout: int = 2) -> List[Dict[str, Any]]:
    """
    Trace route to a host
    
    Args:
        host: Hostname or IP address
        max_hops: Maximum number of hops
        timeout: Timeout in seconds
        
    Returns:
        List of dictionaries with hop information
    """
    hops = []
    
    try:
        # Determine platform-specific traceroute command
        if os.name == 'nt':  # Windows
            command = ['tracert', '-d', '-h', str(max_hops), '-w', str(timeout * 1000), host]
        else:  # Unix/Linux/Mac
            command = ['traceroute', '-n', '-m', str(max_hops), '-w', str(timeout), host]
            
        # Execute traceroute command
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        # Parse traceroute output
        for line in stdout.splitlines():
            # Skip header lines
            if "Tracing route" in line or "traceroute to" in line:
                continue
                
            # Extract hop information
            parts = line.strip().split()
            
            if os.name == 'nt':  # Windows output parsing
                # Windows format: " 1    <1 ms    <1 ms    <1 ms  192.168.1.1"
                if len(parts) >= 4 and parts[0].isdigit():
                    hop_num = int(parts[0])
                    
                    # Extract IP address
                    ip = parts[-1]
                    
                    # Extract response times
                    times = []
                    for i in range(1, 4):
                        if i < len(parts) and "ms" in parts[i]:
                            try:
                                # Handle "<1 ms" format
                                if "<" in parts[i]:
                                    times.append(float(parts[i].replace("<", "")))
                                else:
                                    times.append(float(parts[i]))
                            except:
                                pass
                    
                    # Create hop entry
                    hop = {
                        'hop': hop_num,
                        'ip': ip,
                        'response_times': times,
                        'avg_time': sum(times) / len(times) if times else None
                    }
                    
                    hops.append(hop)
            else:  # Unix/Linux/Mac output parsing
                # Linux format: " 1  192.168.1.1  0.123 ms  0.456 ms  0.789 ms"
                if len(parts) >= 4 and parts[0].isdigit():
                    hop_num = int(parts[0])
                    
                    # Extract IP address
                    ip = parts[1]
                    
                    # Extract response times
                    times = []
                    for i in range(2, 5):
                        if i < len(parts) and "ms" in parts[i]:
                            try:
                                times.append(float(parts[i]))
                            except:
                                pass
                    
                    # Create hop entry
                    hop = {
                        'hop': hop_num,
                        'ip': ip,
                        'response_times': times,
                        'avg_time': sum(times) / len(times) if times else None
                    }
                    
                    hops.append(hop)
        
        return hops
    except Exception as e:
        logging.error(f"Error tracing route: {str(e)}")
        return []


def download_file(url: str, destination: str, timeout: int = 30) -> bool:
    """
    Download a file from a URL
    
    Args:
        url: URL to download from
        destination: Destination file path
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create destination directory if it doesn't exist
        destination_dir = os.path.dirname(destination)
        if destination_dir and not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
            
        # Download the file
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        
        # Get file size
        total_size = int(response.headers.get('content-length', 0))
        
        # Save the file
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logging.info(f"Downloaded file from {url} to {destination}")
        return True
    except Exception as e:
        logging.error(f"Error downloading file: {str(e)}")
        return False


def get_local_ip_range() -> str:
    """
    Get the local IP address range (e.g., 192.168.1)
    
    Returns:
        IP range string
    """
    ip = get_ip_address()
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    return "192.168.1"  # Default fallback