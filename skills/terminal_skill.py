from .base_skill import BaseSkill
import subprocess
import platform

class TerminalSkill(BaseSkill):
    @property
    def skill_id(self):
        return "terminal"
    
    @property
    def description(self):
        return "Terminal command execution (safe)"
    
    @property
    def version(self):
        return "1.0.0"
    
    def can_handle(self, query: str):
        query_lower = query.lower()
        terminal_keywords = ["run command", "execute", "terminal", "cmd", "powershell", "shell"]
        if any(k in query_lower for k in terminal_keywords):
            return 1.0
        return 0.0
    
    def handle(self, query: str, params=None):
        try:
            query_lower = query.lower()
            
            # Extract command (basic)
            command = None
            if "run command" in query_lower:
                command = query_lower.split("run command", 1)[-1].strip()
            elif "execute" in query_lower:
                command = query_lower.split("execute", 1)[-1].strip()
            
            if not command:
                return "Please specify a command to run"
            
            # Safe commands only
            safe_commands = ["dir", "ls", "echo", "pwd", "cd", "date", "time", "whoami", "hostname"]
            is_safe = any(cmd in command.lower().split() for cmd in safe_commands)
            
            if not is_safe:
                return f"Command '{command}' not allowed for safety"
            
            # Run command
            shell = True
            if platform.system() == "Windows":
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            
            output = result.stdout + result.stderr
            return f"Command executed:\n{output[:500]}"
            
        except subprocess.TimeoutExpired:
            return "Command timed out"
        except Exception as e:
            return f"Terminal error: {str(e)}"
