"""
Enhanced Filesystem Intelligence Module for Jarvis
Provides deep system reconnaissance and file analysis capabilities
"""

import os
import sys
import time
import hashlib
import logging
import ctypes
import subprocess
import mimetypes
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class FileInfo:
    """Enhanced file information structure"""
    path: str
    name: str
    size: int
    size_mb: float
    created: datetime
    modified: datetime
    accessed: datetime
    extension: str
    mime_type: str
    is_hidden: bool
    is_system: bool
    attributes: str
    owner: str
    permissions: str
    hash_md5: Optional[str] = None

class SystemRecon:
    """Deep system reconnaissance capabilities"""
    
    def __init__(self, enable_admin_mode: bool = True):
        self.admin_mode = enable_admin_mode
        self.excluded_dirs = {
            '$Recycle.Bin', 'System Volume Information', 
            'Recovery', 'PerfLogs', 'hiberfil.sys', 'pagefile.sys'
        }
        
        if enable_admin_mode and os.name == 'nt':
            self._elevate_if_needed()
    
    def _elevate_if_needed(self):
        """Elevate to administrator if needed (Windows)"""
        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                logging.warning("Attempting to elevate to administrator...")
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
                sys.exit()
        except Exception as e:
            logging.error(f"Failed to elevate privileges: {e}")
    
    def deep_scan(self, root_path: str = None, max_depth: int = 5) -> Iterator[FileInfo]:
        """
        Perform deep filesystem scan with intelligent filtering
        
        Args:
            root_path: Starting directory (defaults to system root)
            max_depth: Maximum directory depth to scan
            
        Yields:
            FileInfo objects for discovered files
        """
        if root_path is None:
            root_path = "C:\\" if os.name == 'nt' else "/"
        
        current_depth = 0
        
        for root, dirs, files in os.walk(root_path):
            # Calculate current depth
            depth = root.replace(root_path, '').count(os.sep)
            if depth > max_depth:
                continue
            
            # Filter out system/hidden directories intelligently
            dirs[:] = [d for d in dirs if not self._should_skip_directory(
                os.path.join(root, d)
            )]
            
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    file_info = self._get_enhanced_file_info(file_path)
                    if file_info:
                        yield file_info
                except (PermissionError, OSError):
                    continue
    
    def _should_skip_directory(self, dir_path: str) -> bool:
        """Intelligent directory filtering"""
        dir_name = os.path.basename(dir_path)
        
        # Skip system directories
        if dir_name in self.excluded_dirs:
            return True
        
        # Skip hidden directories (unless specifically interesting)
        if dir_name.startswith('.') and dir_name not in {'.git', '.vscode', '.config'}:
            return True
        
        # Skip Windows system directories
        if os.name == 'nt':
            system_patterns = ['Windows', 'Program Files', 'ProgramData']
            if any(pattern in dir_path for pattern in system_patterns):
                # Allow some interesting subdirectories
                interesting = ['Logs', 'Temp', 'Downloads', 'Desktop']
                if not any(pattern in dir_path for pattern in interesting):
                    return True
        
        return False
    
    def _get_enhanced_file_info(self, file_path: str) -> Optional[FileInfo]:
        """Get comprehensive file information"""
        try:
            stat = os.stat(file_path)
            path_obj = Path(file_path)
            
            # Basic info
            name = path_obj.name
            size = stat.st_size
            size_mb = size / (1024 * 1024)
            
            # Timestamps
            created = datetime.fromtimestamp(stat.st_ctime)
            modified = datetime.fromtimestamp(stat.st_mtime)
            accessed = datetime.fromtimestamp(stat.st_atime)
            
            # File type info
            extension = path_obj.suffix.lower()
            mime_type, _ = mimetypes.guess_type(file_path)
            
            # System attributes
            is_hidden = self._is_hidden_file(file_path)
            is_system = self._is_system_file(file_path)
            attributes = self._get_file_attributes(file_path)
            
            # Ownership info
            owner = self._get_file_owner(file_path)
            permissions = self._get_file_permissions(file_path)
            
            return FileInfo(
                path=file_path,
                name=name,
                size=size,
                size_mb=size_mb,
                created=created,
                modified=modified,
                accessed=accessed,
                extension=extension,
                mime_type=mime_type or "unknown",
                is_hidden=is_hidden,
                is_system=is_system,
                attributes=attributes,
                owner=owner,
                permissions=permissions
            )
        
        except Exception as e:
            logging.debug(f"Failed to get info for {file_path}: {e}")
            return None
    
    def find_files_by_criteria(self, 
                             root_path: str = None,
                             extensions: List[str] = None,
                             min_size_mb: float = None,
                             max_size_mb: float = None,
                             modified_since: datetime = None,
                             name_pattern: str = None,
                             content_pattern: str = None) -> List[FileInfo]:
        """Advanced file search with multiple criteria"""
        
        results = []
        
        for file_info in self.deep_scan(root_path):
            # Extension filter
            if extensions and file_info.extension not in extensions:
                continue
            
            # Size filters
            if min_size_mb and file_info.size_mb < min_size_mb:
                continue
            if max_size_mb and file_info.size_mb > max_size_mb:
                continue
            
            # Date filter
            if modified_since and file_info.modified < modified_since:
                continue
            
            # Name pattern
            if name_pattern and name_pattern.lower() not in file_info.name.lower():
                continue
            
            # Content search (for text files)
            if content_pattern and self._search_file_content(file_info.path, content_pattern):
                continue
            
            results.append(file_info)
        
        return results
    
    def get_system_intelligence(self) -> Dict[str, any]:
        """Gather comprehensive system intelligence"""
        intel = {
            'timestamp': datetime.now().isoformat(),
            'disk_usage': self._get_disk_intelligence(),
            'process_intelligence': self._get_process_intelligence(),
            'network_intelligence': self._get_network_intelligence(),
            'file_hotspots': self._get_file_hotspots(),
            'security_indicators': self._get_security_indicators()
        }
        return intel
    
    def _get_disk_intelligence(self) -> Dict[str, any]:
        """Analyze disk usage patterns"""
        import psutil
        
        disk_info = {}
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info[partition.device] = {
                    'total_gb': usage.total / (1024**3),
                    'used_gb': usage.used / (1024**3),
                    'free_gb': usage.free / (1024**3),
                    'percent_used': (usage.used / usage.total) * 100,
                    'filesystem': partition.fstype
                }
            except PermissionError:
                continue
        
        return disk_info
    
    def _get_process_intelligence(self) -> Dict[str, any]:
        """Analyze running processes for intelligence"""
        import psutil
        
        processes = []
        suspicious_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                proc_info = proc.info
                
                # Flag suspicious processes
                if self._is_suspicious_process(proc_info['name']):
                    suspicious_processes.append(proc_info)
                
                processes.append({
                    'pid': proc_info['pid'],
                    'name': proc_info['name'],
                    'cpu_percent': proc_info['cpu_percent'] or 0,
                    'memory_mb': proc_info['memory_info'].rss / (1024**2) if proc_info['memory_info'] else 0,
                    'started': datetime.fromtimestamp(proc_info['create_time']).isoformat()
                })
            except:
                continue
        
        return {
            'total_processes': len(processes),
            'suspicious_count': len(suspicious_processes),
            'top_cpu': sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:5],
            'top_memory': sorted(processes, key=lambda x: x['memory_mb'], reverse=True)[:5],
            'suspicious_processes': suspicious_processes
        }
    
    def _get_network_intelligence(self) -> Dict[str, any]:
        """Network activity analysis"""
        import psutil
        
        connections = psutil.net_connections()
        
        # Analyze connection patterns
        foreign_ips = set()
        listening_ports = []
        
        for conn in connections:
            if conn.raddr:
                foreign_ips.add(conn.raddr.ip)
            if conn.status == 'LISTEN':
                listening_ports.append(conn.laddr.port)
        
        return {
            'active_connections': len(connections),
            'unique_foreign_ips': len(foreign_ips),
            'listening_ports': sorted(set(listening_ports)),
            'foreign_ips': list(foreign_ips)[:10]  # Limit for privacy
        }
    
    def _get_file_hotspots(self) -> Dict[str, any]:
        """Identify file activity hotspots"""
        hotspots = {}
        
        # Common directories to monitor
        if os.name == 'nt':
            monitor_dirs = [
                os.path.expanduser('~\\Downloads'),
                os.path.expanduser('~\\Documents'),
                os.path.expanduser('~\\Desktop'),
                'C:\\Temp',
                'C:\\Windows\\Temp'
            ]
        else:
            monitor_dirs = [
                os.path.expanduser('~/Downloads'),
                os.path.expanduser('~/Documents'),
                os.path.expanduser('~/Desktop'),
                '/tmp'
            ]
        
        for dir_path in monitor_dirs:
            if os.path.exists(dir_path):
                try:
                    files = list(os.listdir(dir_path))
                    recent_files = []
                    
                    for file in files[:10]:  # Limit check
                        file_path = os.path.join(dir_path, file)
                        if os.path.isfile(file_path):
                            mtime = os.path.getmtime(file_path)
                            if time.time() - mtime < 86400:  # Last 24 hours
                                recent_files.append(file)
                    
                    hotspots[dir_path] = {
                        'total_files': len(files),
                        'recent_files': len(recent_files),
                        'recent_file_names': recent_files
                    }
                except PermissionError:
                    continue
        
        return hotspots
    
    def _get_security_indicators(self) -> Dict[str, any]:
        """Basic security posture indicators"""
        indicators = {
            'admin_access': self._check_admin_access(),
            'antivirus_processes': self._detect_antivirus(),
            'firewall_status': self._check_firewall_status(),
            'suspicious_file_extensions': self._scan_suspicious_files()
        }
        return indicators
    
    # Utility methods
    def _is_hidden_file(self, file_path: str) -> bool:
        """Check if file is hidden"""
        if os.name == 'nt':
            try:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(file_path)
                return attrs != -1 and bool(attrs & 2)
            except:
                return False
        else:
            return os.path.basename(file_path).startswith('.')
    
    def _is_system_file(self, file_path: str) -> bool:
        """Check if file is a system file"""
        if os.name == 'nt':
            try:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(file_path)
                return attrs != -1 and bool(attrs & 4)
            except:
                return False
        return False
    
    def _get_file_attributes(self, file_path: str) -> str:
        """Get file attributes string"""
        if os.name == 'nt':
            try:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(file_path)
                if attrs == -1:
                    return "unknown"
                
                attr_strings = []
                if attrs & 1: attr_strings.append("readonly")
                if attrs & 2: attr_strings.append("hidden")
                if attrs & 4: attr_strings.append("system")
                if attrs & 16: attr_strings.append("directory")
                if attrs & 32: attr_strings.append("archive")
                
                return ",".join(attr_strings) if attr_strings else "normal"
            except:
                return "unknown"
        else:
            stat = os.stat(file_path)
            return oct(stat.st_mode)[-3:]
    
    def _get_file_owner(self, file_path: str) -> str:
        """Get file owner"""
        try:
            if os.name == 'nt':
                # Windows implementation would require additional libraries
                return "unknown"
            else:
                import pwd
                stat = os.stat(file_path)
                return pwd.getpwuid(stat.st_uid).pw_name
        except:
            return "unknown"
    
    def _get_file_permissions(self, file_path: str) -> str:
        """Get file permissions"""
        try:
            stat = os.stat(file_path)
            return oct(stat.st_mode)[-3:]
        except:
            return "unknown"
    
    def _search_file_content(self, file_path: str, pattern: str) -> bool:
        """Search for pattern in file content"""
        try:
            # Only search text files and limit size
            if os.path.getsize(file_path) > 10*1024*1024:  # 10MB limit
                return False
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return pattern.lower() in content.lower()
        except:
            return False
    
    def _is_suspicious_process(self, process_name: str) -> bool:
        """Basic suspicious process detection"""
        suspicious_patterns = [
            'keylog', 'backdoor', 'trojan', 'virus', 'malware',
            'rootkit', 'spyware', 'adware', 'hijack'
        ]
        return any(pattern in process_name.lower() for pattern in suspicious_patterns)
    
    def _check_admin_access(self) -> bool:
        """Check if running with admin privileges"""
        if os.name == 'nt':
            try:
                return ctypes.windll.shell32.IsUserAnAdmin()
            except:
                return False
        else:
            return os.geteuid() == 0
    
    def _detect_antivirus(self) -> List[str]:
        """Detect running antivirus software"""
        av_processes = []
        av_names = [
            'mcafee', 'norton', 'kaspersky', 'avast', 'avg', 'bitdefender',
            'eset', 'trend', 'sophos', 'webroot', 'malwarebytes', 'defender'
        ]
        
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                proc_name = proc.info['name'].lower()
                for av in av_names:
                    if av in proc_name:
                        av_processes.append(proc.info['name'])
        except:
            pass
        
        return list(set(av_processes))
    
    def _check_firewall_status(self) -> str:
        """Check firewall status"""
        if os.name == 'nt':
            try:
                result = subprocess.run(
                    ['netsh', 'advfirewall', 'show', 'allprofiles', 'state'],
                    capture_output=True, text=True, timeout=5
                )
                return "active" if "ON" in result.stdout else "unknown"
            except:
                return "unknown"
        return "unknown"
    
    def _scan_suspicious_files(self) -> Dict[str, int]:
        """Scan for files with suspicious extensions"""
        suspicious_extensions = ['.exe', '.scr', '.bat', '.cmd', '.pif', '.com']
        temp_dirs = []
        
        if os.name == 'nt':
            temp_dirs = ['C:\\Temp', 'C:\\Windows\\Temp', os.path.expanduser('~\\AppData\\Local\\Temp')]
        else:
            temp_dirs = ['/tmp', '/var/tmp']
        
        suspicious_counts = {}
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    for file in os.listdir(temp_dir):
                        ext = os.path.splitext(file)[1].lower()
                        if ext in suspicious_extensions:
                            suspicious_counts[ext] = suspicious_counts.get(ext, 0) + 1
                except PermissionError:
                    continue
        
        return suspicious_counts


# Integration class for Jarvis
class JarvisFilesystemIntelligence:
    """Main interface for Jarvis filesystem capabilities"""
    
    def __init__(self, jarvis_instance):
        self.jarvis = jarvis_instance
        self.recon = SystemRecon(enable_admin_mode=True)
        self.last_scan_time = None
        self.scan_cache = {}
    
    def handle_filesystem_command(self, command: str) -> str:
        """Process filesystem-related voice commands"""
        command = command.lower()
        
        if "scan system" in command or "deep scan" in command:
            return self._perform_deep_scan()
        
        elif "find large files" in command:
            size_mb = 100  # Default
            if "larger than" in command:
                # Extract size if specified
                import re
                match = re.search(r'(\d+)', command)
                if match:
                    size_mb = int(match.group(1))
            return self._find_large_files(size_mb)
        
        elif "recent files" in command:
            hours = 24  # Default to last 24 hours
            return self._find_recent_files(hours)
        
        elif "system intelligence" in command:
            return self._get_system_report()
        
        elif "security scan" in command:
            return self._security_scan()
        
        else:
            return "Filesystem command not recognized. Try 'scan system', 'find large files', 'recent files', or 'system intelligence'."
    
    def _perform_deep_scan(self) -> str:
        """Perform and report deep system scan"""
        self.jarvis.speak("Initiating deep system scan. This may take a moment.")
        
        start_time = time.time()
        file_count = 0
        total_size = 0
        
        for file_info in self.recon.deep_scan(max_depth=3):
            file_count += 1
            total_size += file_info.size
            
            # Progress update every 1000 files
            if file_count % 1000 == 0:
                self.jarvis.speak(f"Scanned {file_count} files so far...")
        
        elapsed = time.time() - start_time
        total_size_gb = total_size / (1024**3)
        
        result = f"Deep scan complete. Found {file_count} files totaling {total_size_gb:.2f} GB in {elapsed:.1f} seconds."
        self.jarvis.speak(result)
        return result
    
    def _find_large_files(self, min_size_mb: float) -> str:
        """Find and report large files"""
        self.jarvis.speak(f"Searching for files larger than {min_size_mb} megabytes...")
        
        large_files = self.recon.find_files_by_criteria(min_size_mb=min_size_mb)
        large_files.sort(key=lambda f: f.size_mb, reverse=True)
        
        if not large_files:
            result = f"No files larger than {min_size_mb}MB found."
        else:
            result = f"Found {len(large_files)} large files:\n"
            for file_info in large_files[:10]:  # Top 10
                result += f"- {file_info.name}: {file_info.size_mb:.1f}MB\n"
            
            if len(large_files) > 10:
                result += f"... and {len(large_files) - 10} more files."
        
        self.jarvis.speak(f"Found {len(large_files)} files larger than {min_size_mb}MB.")
        return result
    
    def _find_recent_files(self, hours: int) -> str:
        """Find recently modified files"""
        self.jarvis.speak(f"Searching for files modified in the last {hours} hours...")
        
        since_time = datetime.now() - timedelta(hours=hours)
        recent_files = self.recon.find_files_by_criteria(modified_since=since_time)
        recent_files.sort(key=lambda f: f.modified, reverse=True)
        
        if not recent_files:
            result = f"No files modified in the last {hours} hours."
        else:
            result = f"Found {len(recent_files)} recently modified files:\n"
            for file_info in recent_files[:10]:  # Top 10
                result += f"- {file_info.name}: {file_info.modified.strftime('%H:%M')}\n"
        
        self.jarvis.speak(f"Found {len(recent_files)} recently modified files.")
        return result
    
    def _get_system_report(self) -> str:
        """Generate comprehensive system intelligence report"""
        self.jarvis.speak("Generating system intelligence report...")
        
        intel = self.recon.get_system_intelligence()
        
        # Build report
        report = "=== SYSTEM INTELLIGENCE REPORT ===\n"
        report += f"Generated: {intel['timestamp']}\n\n"
        
        # Disk usage
        report += "DISK USAGE:\n"
        for device, info in intel['disk_usage'].items():
            report += f"- {device}: {info['used_gb']:.1f}GB used ({info['percent_used']:.1f}%)\n"
        
        # Process summary
        proc_intel = intel['process_intelligence']
        report += f"\nPROCESSES:\n"
        report += f"- Total processes: {proc_intel['total_processes']}\n"
        report += f"- Suspicious processes: {proc_intel['suspicious_count']}\n"
        
        # Network summary
        net_intel = intel['network_intelligence']
        report += f"\nNETWORK:\n"
        report += f"- Active connections: {net_intel['active_connections']}\n"
        report += f"- Unique foreign IPs: {net_intel['unique_foreign_ips']}\n"
        
        # Security indicators
        sec_intel = intel['security_indicators']
        report += f"\nSECURITY:\n"
        report += f"- Admin access: {sec_intel['admin_access']}\n"
        report += f"- Antivirus detected: {', '.join(sec_intel['antivirus_processes']) if sec_intel['antivirus_processes'] else 'None'}\n"
        
        self.jarvis.speak("System intelligence report generated.")
        return report
    
    def _security_scan(self) -> str:
        """Perform basic security scan"""
        self.jarvis.speak("Performing security scan...")
        
        intel = self.recon.get_system_intelligence()
        sec_intel = intel['security_indicators']
        
        findings = []
        
        if not sec_intel['admin_access']:
            findings.append("WARNING: Not running with administrator privileges")
        
        if not sec_intel['antivirus_processes']:
            findings.append("WARNING: No antivirus software detected")
        
        if sec_intel['suspicious_file_extensions']:
            total_suspicious = sum(sec_intel['suspicious_file_extensions'].values())
            findings.append(f"WARNING: Found {total_suspicious} potentially suspicious executable files in temp directories")
        
        if not findings:
            result = "Security scan complete. No immediate concerns detected."
        else:
            result = f"Security scan complete. Found {len(findings)} potential issues:\n"
            result += "\n".join(f"- {finding}" for finding in findings)
        
        self.jarvis.speak(f"Security scan complete. Found {len(findings)} potential issues.")
        return result