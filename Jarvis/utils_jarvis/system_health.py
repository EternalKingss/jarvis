"""Comprehensive system health monitoring for Jarvis."""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import requests


class IssueType(Enum):
    """Types of issues that can be detected."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    FIXED = "fixed"


@dataclass
class Issue:
    """Represents a system issue."""

    id: str
    type: IssueType
    title: str
    description: str
    fix_suggestion: str
    auto_fixable: bool = False
    fixed: bool = False
    timestamp: float | None = None

    def __post_init__(self) -> None:  # pragma: no cover - init behaviour
        if self.timestamp is None:
            self.timestamp = time.time()


class JarvisSystemHealth:
    """System health monitoring and auto-fixing."""

    def __init__(self, config_manager: Any | None = None) -> None:
        self.config = config_manager
        self.issues: Dict[str, Issue] = {}
        self.health_metrics: Dict[str, Any] = {}
        self.auto_fix_enabled = True
        self.monitoring_active = False
        self.monitor_thread: threading.Thread | None = None
        self.logger = logging.getLogger("JarvisHealth")

    # ------------------------------------------------------------------
    # Diagnostic helpers
    # ------------------------------------------------------------------
    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run a comprehensive system diagnostic."""
        self.logger.info("Starting full system diagnostic...")
        diagnostics = {
            "system_info": self._get_system_info(),
            "python_environment": self._check_python_environment(),
            "dependencies": self._check_dependencies(),
            "configuration": self._validate_configuration(),
            "api_connectivity": self._test_api_connectivity(),
            "audio_system": self._check_audio_system(),
            "file_permissions": self._check_file_permissions(),
            "performance": self._check_performance(),
            "issues": self._detect_issues(),
        }
        if self.auto_fix_enabled:
            self._auto_fix_issues()
        return diagnostics

    def _get_system_info(self) -> Dict[str, Any]:
        """Return basic system information."""
        try:
            return {
                "platform": platform.platform(),
                "python_version": sys.version,
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "disk_usage": {
                    path: psutil.disk_usage(path)._asdict()
                    for path in ["/", "C:\\"]
                    if os.path.exists(path)
                },
            }
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"Failed to get system info: {exc}")
            return {"error": str(exc)}

    def _check_python_environment(self) -> Dict[str, Any]:
        """Check Python environment health."""
        issues: List[str] = []
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            issues.append("Python 3.8+ recommended for optimal performance")

        in_venv = hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        )
        if not in_venv:
            issues.append("Running outside virtual environment - may cause conflicts")

        try:
            import pip  # noqa: F401

            pip_version = pip.__version__
        except Exception:
            pip_version = "unknown"
            issues.append("pip not available")

        return {
            "version": f"{version.major}.{version.minor}.{version.micro}",
            "virtual_env": in_venv,
            "pip_version": pip_version,
            "executable": sys.executable,
            "issues": issues,
        }

    def _check_dependencies(self) -> Dict[str, Any]:
        """Verify required dependencies are installed."""
        required_packages = {
            "openai": "1.0.0",
            "speech_recognition": "3.8.1",
            "pyttsx3": "2.90",
            "requests": "2.25.0",
            "psutil": "5.8.0",
            "matplotlib": "3.5.0",
            "numpy": "1.21.0",
        }
        optional_packages = {
            "elevenlabs": "0.2.0",
            "pygame": "2.1.0",
            "pyaudio": "0.2.11",
        }

        installed: Dict[str, str] = {}
        missing: List[str] = []
        outdated: List[str] = []
        for package, min_version in required_packages.items():
            try:
                module = __import__(package)
                version = getattr(module, "__version__", "unknown")
                installed[package] = version
                if version != "unknown" and version < min_version:
                    outdated.append(f"{package} {version} < {min_version}")
            except ImportError:
                missing.append(package)

        optional_status: Dict[str, str] = {}
        for package, min_version in optional_packages.items():
            try:
                module = __import__(package)
                optional_status[package] = getattr(module, "__version__", "installed")
            except ImportError:
                optional_status[package] = "not installed"

        return {
            "installed": installed,
            "missing": missing,
            "outdated": outdated,
            "optional": optional_status,
        }

    def _validate_configuration(self) -> Dict[str, Any]:
        """Validate configuration files and API keys."""
        issues: List[str] = []
        warnings: List[str] = []
        if not self.config:
            issues.append("No configuration manager available")
            return {"issues": issues}

        config_file = getattr(self.config, "config_file", "jarvis_config.ini")
        if not os.path.exists(config_file):
            issues.append(f"Configuration file not found: {config_file}")

        api_keys = {
            "openai": self.config.get("API_KEYS", "openai", "", is_encrypted=True),
            "elevenlabs": self.config.get(
                "API_KEYS", "elevenlabs", "", is_encrypted=True
            ),
        }

        for service, key in api_keys.items():
            if not key:
                if service == "openai":
                    issues.append(f"Missing {service} API key (required)")
                else:
                    warnings.append(f"Missing {service} API key (optional)")

        required_dirs = ["logs", "temp", "config"]
        for name in required_dirs:
            dir_path = os.path.join(os.getcwd(), name)
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as exc:
                    issues.append(f"Cannot create directory {name}: {exc}")
            elif not os.access(dir_path, os.W_OK):
                issues.append(f"Directory not writable: {name}")

        return {
            "config_file": config_file,
            "api_keys": {k: bool(v) for k, v in api_keys.items()},
            "issues": issues,
            "warnings": warnings,
        }

    def _test_api_connectivity(self) -> Dict[str, Any]:
        """Test connectivity to external APIs."""
        results: Dict[str, Dict[str, Any] | str] = {}
        if not self.config:
            return {"error": "No configuration available"}

        openai_key = self.config.get("API_KEYS", "openai", "", is_encrypted=True)
        if openai_key:
            try:
                resp = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    timeout=10,
                )
                results["openai"] = {
                    "status": "connected" if resp.status_code == 200 else "error",
                    "response_time": resp.elapsed.total_seconds(),
                    "error": None if resp.status_code == 200 else f"HTTP {resp.status_code}",
                }
            except Exception as exc:
                results["openai"] = {
                    "status": "error",
                    "error": str(exc),
                    "response_time": None,
                }
        else:
            results["openai"] = {"status": "no_key"}

        eleven_key = self.config.get("API_KEYS", "elevenlabs", "", is_encrypted=True)
        if eleven_key:
            try:
                resp = requests.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": eleven_key},
                    timeout=10,
                )
                results["elevenlabs"] = {
                    "status": "connected" if resp.status_code == 200 else "error",
                    "response_time": resp.elapsed.total_seconds(),
                    "error": None if resp.status_code == 200 else f"HTTP {resp.status_code}",
                }
            except Exception as exc:
                results["elevenlabs"] = {
                    "status": "error",
                    "error": str(exc),
                    "response_time": None,
                }
        else:
            results["elevenlabs"] = {"status": "no_key"}

        return results

    def _check_audio_system(self) -> Dict[str, Any]:
        """Check availability of microphones and speakers."""
        results = {
            "microphone": {"available": False, "devices": []},
            "speakers": {"available": False, "devices": []},
            "issues": [],
        }
        try:
            import speech_recognition as sr

            mics = sr.Microphone.list_microphone_names()
            results["microphone"]["devices"] = mics
            results["microphone"]["available"] = bool(mics)
            if not mics:
                results["issues"].append("No microphones detected")
            else:
                try:
                    with sr.Microphone():
                        results["microphone"]["default_working"] = True
                except Exception as exc:
                    results["issues"].append(f"Default microphone error: {exc}")
                    results["microphone"]["default_working"] = False
        except ImportError:
            results["issues"].append("speech_recognition module not available")
        except Exception as exc:
            results["issues"].append(f"Audio system error: {exc}")

        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            results["speakers"]["available"] = bool(voices)
            results["speakers"]["voices"] = len(voices)
            engine.stop()
        except Exception as exc:
            results["issues"].append(f"TTS system error: {exc}")

        return results

    def _check_file_permissions(self) -> Dict[str, Any]:
        """Check read/write permissions for common directories."""
        issues: List[str] = []
        paths = [
            ("current_directory", os.getcwd()),
            ("temp_directory", os.path.join(os.getcwd(), "temp")),
            ("logs_directory", os.path.join(os.getcwd(), "logs")),
            ("config_directory", os.path.join(os.getcwd(), "config")),
        ]
        permissions: Dict[str, Dict[str, Any]] = {}
        for name, path in paths:
            if os.path.exists(path):
                permissions[name] = {
                    "readable": os.access(path, os.R_OK),
                    "writable": os.access(path, os.W_OK),
                    "executable": os.access(path, os.X_OK),
                }
                if not os.access(path, os.W_OK):
                    issues.append(f"Write permission denied: {path}")
            else:
                permissions[name] = {"exists": False}
                issues.append(f"Path does not exist: {path}")
        return {"permissions": permissions, "issues": issues}

    def _check_performance(self) -> Dict[str, Any]:
        """Gather system performance metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            issues: List[str] = []
            if cpu_percent > 90:
                issues.append("High CPU usage detected")
            if memory.percent > 90:
                issues.append("High memory usage detected")
            if disk.percent > 95:
                issues.append("Low disk space")
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "disk_percent": disk.percent,
                "disk_free": disk.free,
                "issues": issues,
            }
        except Exception as exc:  # pragma: no cover - psutil error
            return {"error": str(exc)}

    def _detect_issues(self) -> List[Issue]:
        """Detect and categorize system issues."""
        issues: List[Issue] = []
        if not self.config:
            issues.append(
                Issue(
                    id="no_config",
                    type=IssueType.CRITICAL,
                    title="No Configuration Manager",
                    description="Configuration manager not initialized",
                    fix_suggestion="Initialize configuration manager with proper config file",
                    auto_fixable=False,
                )
            )

        deps = self._check_dependencies()
        for package in deps.get("missing", []):
            issues.append(
                Issue(
                    id=f"missing_{package}",
                    type=IssueType.CRITICAL,
                    title=f"Missing Package: {package}",
                    description=f"Required package {package} is not installed",
                    fix_suggestion=f"Install with: pip install {package}",
                    auto_fixable=True,
                )
            )

        api_results = self._test_api_connectivity()
        for service, result in api_results.items():
            if isinstance(result, dict) and result.get("status") == "error":
                issues.append(
                    Issue(
                        id=f"api_{service}",
                        type=IssueType.WARNING,
                        title=f"API Connection Failed: {service}",
                        description=f"Cannot connect to {service} API: {result.get('error')}",
                        fix_suggestion="Check API key and internet connection",
                        auto_fixable=False,
                    )
                )

        audio = self._check_audio_system()
        if not audio["microphone"]["available"]:
            issues.append(
                Issue(
                    id="no_microphone",
                    type=IssueType.WARNING,
                    title="No Microphone Detected",
                    description="No audio input devices found",
                    fix_suggestion="Connect a microphone and check audio drivers",
                    auto_fixable=False,
                )
            )

        perf = self._check_performance()
        if isinstance(perf, dict) and "cpu_percent" in perf and perf["cpu_percent"] > 90:
            issues.append(
                Issue(
                    id="high_cpu",
                    type=IssueType.WARNING,
                    title="High CPU Usage",
                    description=f"CPU usage at {perf['cpu_percent']:.1f}%",
                    fix_suggestion="Close unnecessary applications",
                    auto_fixable=False,
                )
            )
        return issues

    # ------------------------------------------------------------------
    # Auto-fix
    # ------------------------------------------------------------------
    def _auto_fix_issues(self) -> int:
        """Automatically fix issues where possible."""
        fixed_count = 0
        for issue in self.issues.values():
            if issue.auto_fixable and not issue.fixed:
                try:
                    if issue.id.startswith("missing_"):
                        pkg = issue.id.replace("missing_", "")
                        self._install_package(pkg)
                        issue.fixed = True
                        issue.type = IssueType.FIXED
                        fixed_count += 1
                        self.logger.info(f"Auto-fixed: {issue.title}")
                except Exception as exc:
                    self.logger.error(f"Failed to auto-fix {issue.id}: {exc}")
        return fixed_count

    def _install_package(self, package: str) -> bool:
        """Install a Python package."""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            return True
        except subprocess.CalledProcessError as exc:
            self.logger.error(f"Failed to install {package}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_health_summary(self) -> Dict[str, Any]:
        """Return overall system health summary."""
        total_issues = len(self.issues)
        critical_issues = sum(
            1
            for i in self.issues.values()
            if i.type == IssueType.CRITICAL and not i.fixed
        )
        warning_issues = sum(
            1
            for i in self.issues.values()
            if i.type == IssueType.WARNING and not i.fixed
        )
        fixed_issues = sum(1 for i in self.issues.values() if i.fixed)

        if critical_issues > 0:
            status = "critical"
        elif warning_issues > 3:
            status = "poor"
        elif warning_issues > 0:
            status = "fair"
        else:
            status = "excellent"

        return {
            "status": status,
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "warning_issues": warning_issues,
            "fixed_issues": fixed_issues,
            "last_check": time.time(),
        }

    def start_monitoring(self, interval: int = 30) -> None:
        """Start background health monitoring."""
        if self.monitoring_active:
            return

        def monitor() -> None:
            while self.monitoring_active:
                try:
                    perf = self._check_performance()
                    self.health_metrics.update(perf)
                    if time.time() % 300 < interval:
                        new_issues = self._detect_issues()
                        for issue in new_issues:
                            if issue.id not in self.issues:
                                self.issues[issue.id] = issue
                                self.logger.warning(f"New issue detected: {issue.title}")
                    time.sleep(interval)
                except Exception as exc:
                    self.logger.error(f"Monitoring error: {exc}")
                    time.sleep(interval)

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Health monitoring started")

    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("Health monitoring stopped")

    def generate_report(self) -> str:
        """Generate a comprehensive health report."""
        report: List[str] = []
        report.append("\U0001F527 JARVIS SYSTEM HEALTH REPORT")
        report.append("=" * 50)
        summary = self.get_health_summary()
        status_emoji = {
            "excellent": "\U0001F7E2",
            "fair": "\U0001F7E1",
            "poor": "\U0001F7E0",
            "critical": "\U0001F534",
        }
        report.append(
            f"\n\U0001F4CA OVERALL HEALTH: {status_emoji.get(summary['status'], '❓')} {summary['status'].upper()}"
        )
        report.append(
            f"Issues: {summary['total_issues']} total, {summary['critical_issues']} critical, {summary['warning_issues']} warnings"
        )
        if summary["critical_issues"] > 0:
            report.append(f"\n\U0001F6A8 CRITICAL ISSUES ({summary['critical_issues']}):")
            for issue in self.issues.values():
                if issue.type == IssueType.CRITICAL and not issue.fixed:
                    report.append(f"  ❌ {issue.title}")
                    report.append(f"     {issue.description}")
                    report.append(f"     \U0001F4A1 {issue.fix_suggestion}")
        if summary["warning_issues"] > 0:
            report.append(f"\n⚠️  WARNINGS ({summary['warning_issues']}):")
            for issue in self.issues.values():
                if issue.type == IssueType.WARNING and not issue.fixed:
                    report.append(f"  ⚠️  {issue.title}")
                    report.append(f"     \U0001F4A1 {issue.fix_suggestion}")
        if summary["fixed_issues"] > 0:
            report.append(f"\n✅ FIXED ISSUES ({summary['fixed_issues']}):")
            for issue in self.issues.values():
                if issue.fixed:
                    report.append(f"  ✅ {issue.title}")
        if self.health_metrics:
            report.append("\n📈 PERFORMANCE METRICS:")
            if "cpu_percent" in self.health_metrics:
                report.append(f"  CPU Usage: {self.health_metrics['cpu_percent']:.1f}%")
            if "memory_percent" in self.health_metrics:
                report.append(f"  Memory Usage: {self.health_metrics['memory_percent']:.1f}%")
            if "disk_percent" in self.health_metrics:
                report.append(f"  Disk Usage: {self.health_metrics['disk_percent']:.1f}%")
        report.append(f"\n📅 Report generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 50)
        return "\n".join(report)


class JarvisHealthIntegration:
    """Integration layer for Jarvis health monitoring."""

    def __init__(self, jarvis_instance: Any | None = None, config_manager: Any | None = None) -> None:
        self.jarvis = jarvis_instance
        self.health_monitor = JarvisSystemHealth(config_manager)
        self.logger = logging.getLogger("JarvisHealthIntegration")

    def run_startup_check(self) -> bool:
        """Run startup health check and fix critical issues."""
        self.logger.info("Running startup health check...")
        diagnostics = self.health_monitor.run_full_diagnostic()
        summary = self.health_monitor.get_health_summary()
        if summary["critical_issues"] > 0:
            self.logger.error("Critical issues detected - cannot start safely")
            self.logger.error(self.health_monitor.generate_report())
            return False
        if summary["warning_issues"] > 0:
            self.logger.warning(f"{summary['warning_issues']} warnings detected")
            print(self.health_monitor.generate_report())
            response = input("\nContinue with warnings? (y/n): ")
            if response.lower() != "y":
                return False
        self.health_monitor.start_monitoring()
        self.logger.info("Startup health check passed")
        return True

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Return data for dashboard display."""
        return {
            "summary": self.health_monitor.get_health_summary(),
            "issues": list(self.health_monitor.issues.values()),
            "metrics": self.health_monitor.health_metrics,
            "report": self.health_monitor.generate_report(),
        }


def main() -> None:
    """CLI health check tool."""
    import argparse

    parser = argparse.ArgumentParser(description="Jarvis Health Check Tool")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--monitor", action="store_true", help="Start monitoring")
    parser.add_argument("--report", action="store_true", help="Generate report")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    health = JarvisSystemHealth()
    health.auto_fix_enabled = args.fix
    print("\U0001F50D Running system diagnostic...")
    _ = health.run_full_diagnostic()
    if args.report:
        print(health.generate_report())
    else:
        summary = health.get_health_summary()
        print(f"Health Status: {summary['status']}")
        print(f"Issues: {summary['total_issues']} total")
        if summary["critical_issues"] > 0:
            print(f"\U0001F6A8 {summary['critical_issues']} critical issues need attention!")
    if args.monitor:
        print("📊 Starting health monitoring... (Ctrl+C to stop)")
        health.start_monitoring(interval=10)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            health.stop_monitoring()
            print("\nMonitoring stopped.")


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
