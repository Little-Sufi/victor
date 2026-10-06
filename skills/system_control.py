from .base_skill import BaseSkill
from datetime import datetime
import platform

class SystemControlSkill(BaseSkill):
    @property
    def skill_id(self):
        return "system_control"
    
    @property
    def description(self):
        return "System controls, time, and status info"
    
    @property
    def version(self):
        return "1.0.0"
    
    def can_handle(self, query: str):
        query_lower = query.lower()
        if any(t in query_lower for t in ["what time", "current time", "time now", "date", "system info", "status"]):
            return 1.0
        return 0.0
    
    def handle(self, query: str, params=None):
        query_lower = query.lower()
        if any(t in query_lower for t in ["what time", "current time", "time now", "date"]):
            now = datetime.now()
            return f"The time is {now.strftime('%I:%M %p')}, date is {now.strftime('%B %d, %Y')}"
        elif any(t in query_lower for t in ["system info", "status"]):
            return f"System: {platform.system()} {platform.release()}\nPython: {platform.python_version()}"
        return ""
