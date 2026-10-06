from .base_skill import BaseSkill
import os

class FileManagerSkill(BaseSkill):
    @property
    def skill_id(self):
        return "file_manager"
    
    @property
    def description(self):
        return "File management operations like listing files"
    
    @property
    def version(self):
        return "1.0.0"
    
    def can_handle(self, query: str):
        query_lower = query.lower()
        if any(t in query_lower for t in ["list files", "what files", "files in", "show files"]):
            return 1.0
        return 0.0
    
    def handle(self, query: str, params=None):
        path = params.get("path", os.getcwd()) if params else os.getcwd()
        try:
            files = os.listdir(path)
            return "Files found:\n- " + "\n- ".join(files[:20])
        except Exception as e:
            return f"Error: {str(e)}"
