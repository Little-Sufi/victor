from .base_skill import BaseSkill
from .system_control import SystemControlSkill
from .file_manager import FileManagerSkill
from .vision_skill import VisionSkill
from .browser_skill import BrowserSkill
from .terminal_skill import TerminalSkill
from .code_exec_skill import CodeExecSkill
from .simple_chat import SimpleChatSkill

SKILLS = [
    SystemControlSkill,
    FileManagerSkill,
    VisionSkill,
    BrowserSkill,
    TerminalSkill,
    CodeExecSkill,
    SimpleChatSkill
]
