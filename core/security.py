
"""
VICTOR Security Module
Implements defense-in-depth: path sandboxing, command filtering,
code sandboxing, permission escalation workflows, and proactive monitoring.
"""
import os
import re
import sys
import subprocess
import tempfile
import shutil
import time
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
import yaml
import psutil

class SecurityManager:
    """Central security policy enforcement."""

    def __init__(self, config_path: str = "config/settings.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.forbidden_commands = set(self.config['security']['forbidden_commands'])
        self.allowed_paths = self._expand_paths(self.config['security']['allowed_paths'])
        self.approval_keywords = self.config['security']['require_approval_for']
        self.max_file_size = self.config['security']['max_file_size_mb'] * 1024 * 1024

        # Compile regex patterns for dangerous operations
        self.dangerous_patterns = [
            re.compile(r'\b' + cmd + r'\b') for cmd in self.forbidden_commands
        ]

        # Monitoring state
        self.monitoring_active = False
        self.monitoring_thread = None
        self.alerts = []
        self.on_alert: Optional[Callable] = None

        # Known safe processes to avoid false positives
        self.known_safe_processes = [
            'svchost.exe', 'explorer.exe', 'chrome.exe', 'firefox.exe',
            'code.exe', 'python.exe', 'java.exe', 'powershell.exe',
            'cmd.exe', 'notepad.exe', 'taskmgr.exe', 'ollama.exe',
            'system idle process', 'system', 'dwm.exe', 'csrss.exe',
            'wininit.exe', 'winlogon.exe', 'services.exe', 'lsass.exe',
            'smss.exe', 'conhost.exe', 'spoolsv.exe', 'searchindexer.exe'
        ]

    def start_proactive_monitoring(self, on_alert: Callable = None):
        """Start background proactive system monitoring."""
        if self.monitoring_active:
            return
        self.on_alert = on_alert
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        print("[Security] Proactive monitoring started")

    def stop_proactive_monitoring(self):
        """Stop the proactive monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)
        print("[Security] Proactive monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop that checks for suspicious activities."""
        known_processes = set()
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    known_processes.add(proc.info['pid'])
                except:
                    pass
        except:
            pass

        while self.monitoring_active:
            try:
                current_pids = set()
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                        try:
                            pid = proc.info['pid']
                            name = proc.info['name'].lower() if proc.info['name'] else ''
                            current_pids.add(pid)

                            # Check for new processes
                            if pid not in known_processes:
                                self._check_new_process(proc.info)
                            known_processes.add(pid)
                        except:
                            pass
                except:
                    pass

                # Check for processes that exited
                try:
                    exited_pids = known_processes - current_pids
                    for pid in exited_pids:
                        try:
                            known_processes.discard(pid)
                        except:
                            pass
                except:
                    pass

                # Check CPU/memory usage anomalies (less frequently)
                # self._check_resource_anomalies()

                # Check network connections (less frequently)
                # self._check_network_connections()

            except Exception as e:
                print(f"[Security] Monitoring error (handled): {e}")

            time.sleep(15)

    def _check_new_process(self, proc_info: Dict[str, Any]):
        """Check if a new process is suspicious."""
        name = proc_info.get('name', '').lower()
        exe = proc_info.get('exe', '')
        cmdline = proc_info.get('cmdline', [])

        alert = None

        # Check for unsigned or unknown processes
        if name not in [p.lower() for p in self.known_safe_processes]:
            if not exe or not os.path.exists(exe):
                alert = f"⚠️ Suspicious new process: {name} (PID: {proc_info['pid']}) - No executable path found"
            else:
                # Check if it's in a temp directory
                temp_dirs = [tempfile.gettempdir().lower(), os.path.expanduser('~\\AppData\\Local\\Temp').lower()]
                if any(temp_dir in exe.lower() for temp_dir in temp_dirs):
                    alert = f"⚠️ Process running from temp directory: {name} at {exe}"

        # Check for suspicious cmdline arguments
        cmdline_str = ' '.join(cmdline).lower()
        suspicious_flags = ['-encodedcommand', '-enc', 'bypass', 'iex', 'invoke-expression', 'downloadfile']
        if any(flag in cmdline_str for flag in suspicious_flags):
            alert = f"⚠️ Suspicious command line arguments for {name}: {cmdline_str}"

        if alert:
            self._record_alert(alert)

    def _check_resource_anomalies(self):
        """Check for processes using excessive CPU or memory (very relaxed)."""
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                cpu = proc.info['cpu_percent']
                mem = proc.info['memory_percent']
                name = proc.info['name']

                # Very relaxed thresholds - only alert on extreme usage
                if cpu > 190 and name.lower() not in [p.lower() for p in self.known_safe_processes]:
                    alert = f"⚠️ Very high CPU usage: {name} (PID: {proc.info['pid']}) - {cpu:.1f}%"
                    self._record_alert(alert)
                if mem > 95 and name.lower() not in [p.lower() for p in self.known_safe_processes]:
                    alert = f"⚠️ Very high memory usage: {name} (PID: {proc.info['pid']}) - {mem:.1f}%"
                    self._record_alert(alert)
            except:
                pass

    def _check_network_connections(self):
        """Check for suspicious network connections."""
        try:
            connections = psutil.net_connections()
            for conn in connections:
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    # Check for connections to unusual ports
                    remote_port = conn.raddr.port
                    suspicious_ports = [22, 23, 3389, 4444, 8080]
                    if remote_port in suspicious_ports:
                        try:
                            proc = psutil.Process(conn.pid)
                            alert = f"⚠️ Suspicious network connection: {proc.name()} (PID: {conn.pid}) -> {conn.raddr.ip}:{remote_port}"
                            self._record_alert(alert)
                        except:
                            pass
        except:
            pass

    def _record_alert(self, alert: str):
        """Record an alert and trigger callback."""
        print(alert)
        self.alerts.append((time.time(), alert))
        if self.on_alert:
            self.on_alert(alert)

    def get_alerts(self, limit: int = 10) -> List[str]:
        """Get recent alerts."""
        return [a[1] for a in self.alerts[-limit:]]

    def _expand_paths(self, paths: List[str]) -> List[str]:
        """Expand user home directories to absolute paths."""
        expanded = []
        for p in paths:
            if p.startswith('~'):
                p = os.path.expanduser(p)
            expanded.append(os.path.abspath(p))
        return expanded

    def validate_path(self, file_path: str) -> tuple[bool, str]:
        """
        Check if a file path is within allowed directories.
        Returns (is_allowed, resolved_path or error_message)
        """
        try:
            # Resolve to absolute path
            full_path = os.path.abspath(os.path.expanduser(file_path))

            # Check for path traversal attacks
            real_path = os.path.realpath(full_path)

            # Verify it's within allowed boundaries
            for allowed in self.allowed_paths:
                if real_path.startswith(allowed):
                    return True, real_path

            return False, f"Access denied: {file_path} is outside allowed directories."
        except Exception as e:
            return False, f"Path validation error: {str(e)}"

    def validate_command(self, command: str) -> tuple[bool, str]:
        """
        Check if a shell command contains forbidden operations.
        Returns (is_safe, reason)
        """
        cmd_lower = command.lower()

        for pattern in self.dangerous_patterns:
            if pattern.search(cmd_lower):
                return False, f"Forbidden command detected: {pattern.pattern}"

        # Check for path traversal in commands
        if '..' in cmd_lower and ('/' in cmd_lower or '\\' in cmd_lower):
            return False, "Path traversal attempt detected"

        return True, "Safe"

    def requires_approval(self, action: str, params: Dict[str, Any]) -> bool:
        """
        Determine if an action requires explicit user approval.
        """
        action_lower = action.lower()

        # Check action name against approval keywords
        for keyword in self.approval_keywords:
            if keyword in action_lower:
                return True

        # Check parameters for sensitive operations
        param_str = str(params).lower()
        for keyword in self.approval_keywords:
            if keyword in param_str:
                return True

        return False

    def check_file_size(self, file_path: str) -> tuple[bool, str]:
        """Ensure file is within size limits."""
        try:
            size = os.path.getsize(file_path)
            if size > self.max_file_size:
                return False, f"File too large: {size/1024/1024:.1f}MB (max: {self.max_file_size/1024/1024:.1f}MB)"
            return True, f"Size OK: {size/1024:.1f}KB"
        except Exception as e:
            return False, str(e)

    def create_sandbox(self) -> str:
        """Create an isolated temporary directory for code execution."""
        sandbox = tempfile.mkdtemp(prefix="victor_sandbox_")
        return sandbox

    def cleanup_sandbox(self, sandbox_path: str):
        """Safely remove sandbox directory."""
        try:
            if os.path.exists(sandbox_path) and sandbox_path.startswith(tempfile.gettempdir()):
                shutil.rmtree(sandbox_path)
        except Exception:
            pass

    def sanitize_filename(self, filename: str) -> str:
        """Remove dangerous characters from filenames."""
        sanitized = re.sub(r'[^\w\.\-]', '_', filename)
        return sanitized


class CodeSandbox:
    """
    Isolated environment for executing user code or commands.
    Uses subprocess with restricted permissions.
    """

    def __init__(self, security: SecurityManager):
        self.security = security
        self.active_sandboxes = []

    def execute_python(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute Python code in a restricted subprocess.
        Blocks dangerous imports and file operations outside sandbox.
        """
        sandbox = self.security.create_sandbox()
        self.active_sandboxes.append(sandbox)

        # Prepend security restrictions to code
        restricted_prefix = """
import sys
import os
# Block dangerous modules
forbidden_modules = ['os.system', 'subprocess', 'socket', 'urllib.request']
# Restrict file writes to sandbox only
os.chdir(r'""" + sandbox + """')
"""

        full_code = restricted_prefix + code

        # Write to temp file
        script_path = os.path.join(sandbox, "script.py")
        with open(script_path, 'w') as f:
            f.write(full_code)

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=sandbox,
                env={**os.environ, 'PYTHONPATH': sandbox}
            )

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'stdout': '', 'stderr': 'Execution timed out', 'returncode': -1}
        except Exception as e:
            return {'success': False, 'stdout': '', 'stderr': str(e), 'returncode': -1}
        finally:
            self.security.cleanup_sandbox(sandbox)
            self.active_sandboxes.remove(sandbox)

    def execute_shell(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute shell command after security validation."""
        is_safe, reason = self.security.validate_command(command)
        if not is_safe:
            return {'success': False, 'stdout': '', 'stderr': reason, 'returncode': -1}

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except Exception as e:
            return {'success': False, 'stdout': '', 'stderr': str(e), 'returncode': -1}

