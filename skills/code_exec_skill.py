from .base_skill import BaseSkill

class CodeExecSkill(BaseSkill):
    @property
    def skill_id(self):
        return "code_exec"
    
    @property
    def description(self):
        return "Execute Python code in a sandbox"
    
    @property
    def version(self):
        return "1.0.0"
    
    def can_handle(self, query: str):
        query_lower = query.lower()
        code_keywords = ["run python", "execute code", "code exec", "evaluate", "calculate"]
        if any(k in query_lower for k in code_keywords):
            return 1.0
        return 0.0
    
    def handle(self, query: str, params=None):
        try:
            query_lower = query.lower()
            
            # Extract code
            code = None
            if "```python" in query and "```" in query.split("```python", 1)[-1]:
                code = query.split("```python", 1)[-1].split("```", 1)[0].strip()
            elif "```" in query and "```" in query.split("```", 1)[-1]:
                code = query.split("```", 1)[-1].split("```", 1)[0].strip()
            elif "run python" in query_lower:
                code = query_lower.split("run python", 1)[-1].strip()
            
            if not code:
                return "Please provide Python code to execute"
            
            # Safe execution sandbox
            restricted_globals = {
                '__builtins__': {
                    'print': print,
                    'range': range,
                    'len': len,
                    'sum': sum,
                    'max': max,
                    'min': min
                }
            }
            
            # Capture output
            import io
            import sys
            old_stdout = sys.stdout
            redirected_output = io.StringIO()
            sys.stdout = redirected_output
            
            try:
                exec(code, restricted_globals, {})
                output = redirected_output.getvalue()
            finally:
                sys.stdout = old_stdout
            
            return f"Code output:\n{output}"
            
        except Exception as e:
            return f"Code execution error: {str(e)}"
