from .base_skill import BaseSkill

class SimpleChatSkill(BaseSkill):
    @property
    def skill_id(self):
        return "simple_chat"
    
    @property
    def description(self):
        return "Simple general conversation skill"
    
    @property
    def version(self):
        return "1.0.0"
    
    def can_handle(self, query: str):
        return 0.1  # Low priority, always a fallback
    
    def handle(self, query: str, params=None):
        return ""  # Pass to brain
