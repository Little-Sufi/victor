"""
VICTOR AI - Multi-Provider Manager
Orchestrates AI backend engines with strict zero-collision priority:
  Tier 1 (Primary):   Gemini Live API (GEMINI_API_KEY)
  Tier 2 (Secondary): ChatGPT / OpenAI API (OPENAI_API_KEY)
  Tier 3 (Tertiary):  Local LLM via Ollama (OLLAMA_HOST / deepseek-r1 / llama3.2)
"""
import os
import urllib.request
import json

def get_active_provider() -> str:
    """Resolves which AI backend engine should power VICTOR based on strict priority."""
    # 0. User explicit override
    override = os.environ.get("VICTOR_PROVIDER", "").strip().lower()
    if override in ("gemini", "openai", "chatgpt", "ollama", "local"):
        if override in ("openai", "chatgpt"):
            return "openai"
        elif override in ("ollama", "local"):
            return "ollama"
        return "gemini"

    # 1. Primary: Gemini API Key
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key and gemini_key not in ("paste_your_api_key_here", "your_gemini_api_key_here", ""):
        return "gemini"

    # 2. Secondary: OpenAI / ChatGPT API Key
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key and openai_key not in ("your_openai_api_key_here", ""):
        return "openai"

    # 3. Tertiary: Local Ollama
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{ollama_host}/api/tags", headers={"User-Agent": "VICTOR"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                if data.get("models"):
                    return "ollama"
    except Exception:
        pass

    # Default to Gemini (will trigger setup prompt if key missing)
    return "gemini"

def get_provider_status() -> dict:
    """Returns availability matrix across all three tiers."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    has_gemini = bool(gemini_key and gemini_key not in ("paste_your_api_key_here", "your_gemini_api_key_here"))

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    has_openai = bool(openai_key and openai_key not in ("your_openai_api_key_here", ""))

    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    has_ollama = False
    ollama_models = []
    try:
        req = urllib.request.Request(f"{ollama_host}/api/tags", headers={"User-Agent": "VICTOR"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                models = [m.get("name") for m in data.get("models", [])]
                if models:
                    has_ollama = True
                    ollama_models = models
    except Exception:
        pass

    active = get_active_provider()
    return {
        "active_provider": active,
        "tier1_gemini": {"configured": has_gemini, "priority": 1},
        "tier2_openai": {"configured": has_openai, "priority": 2},
        "tier3_ollama": {"configured": has_ollama, "models": ollama_models, "priority": 3}
    }
