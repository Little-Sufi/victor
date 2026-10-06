
"""
VICTOR Skill System - Plugin Architecture
Skills are modular capabilities that can be dynamically loaded.
Each skill declares its tools, triggers, and handlers.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass


@dataclass
class SkillTool:
    """A tool exposed by a skill."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema
    handler: Callable
    requires_approval: bool = False


@dataclass
class SkillTrigger:
    """A trigger pattern that activates this skill."""
    patterns: List[str]  # Regex patterns or keywords
    intent: str
    confidence_threshold: float = 0.6


class BaseSkill(ABC):
    """
    Base class for all VICTOR skills.
    Skills are self-contained modules that add capabilities.
    """

    def __init__(self, victor_core=None):
        self.victor = victor_core
        self.name = self.__class__.__name__
        self.enabled = True
        self.tools: List[SkillTool] = []
        self.triggers: List[SkillTrigger] = []
        self._register_tools()
        self._register_triggers()

    @property
    @abstractmethod
    def skill_id(self) -> str:
        """Unique identifier for this skill."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Skill version."""
        pass

    def _register_tools(self):
        """Override to register tools."""
        pass

    def _register_triggers(self):
        """Override to register trigger patterns."""
        pass

    def register_tool(self, name: str, description: str, 
                     parameters: Dict, handler: Callable, 
                     requires_approval: bool = False):
        """Register a tool with VICTOR."""
        tool = SkillTool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            requires_approval=requires_approval
        )
        self.tools.append(tool)

        # Register with brain if available
        if self.victor and hasattr(self.victor, 'brain'):
            self.victor.brain.register_tool(
                name, handler,
                {
                    'name': name,
                    'description': description,
                    'parameters': parameters
                }
            )

    def register_trigger(self, patterns: List[str], intent: str, 
                        confidence: float = 0.6):
        """Register intent trigger patterns."""
        trigger = SkillTrigger(
            patterns=patterns,
            intent=intent,
            confidence_threshold=confidence
        )
        self.triggers.append(trigger)

    @abstractmethod
    def can_handle(self, query: str) -> float:
        """
        Return confidence (0.0-1.0) that this skill can handle the query.
        """
        pass

    @abstractmethod
    def handle(self, query: str, params: Dict = None) -> str:
        """
        Execute the skill's primary function.
        Returns response text.
        """
        pass

    def on_load(self):
        """Called when skill is loaded."""
        pass

    def on_unload(self):
        """Called when skill is unloaded."""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Return skill status information."""
        return {
            'id': self.skill_id,
            'name': self.name,
            'version': self.version,
            'enabled': self.enabled,
            'tools_count': len(self.tools),
            'triggers_count': len(self.triggers)
        }


