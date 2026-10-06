import requests
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class Thought:
    text: str
    model_used: str
    response_time: float

class Brain:
    def __init__(self, settings_path: str = "config/settings.yaml"):
        self.settings = self._load_settings(settings_path)
        # Use ONLY llama3.2:latest for EVERYTHING, MAX SPEED
        self.model_name = "llama3.2:latest"
        self.ollama_url = "http://localhost:11434/api/generate"
        self._check_connection()
        print(f"[OK] Brain initialized with model: {self.model_name} (MAX SPEED)")

    def _load_settings(self, settings_path: str) -> Dict:
        import yaml
        try:
            with open(settings_path, "r") as f:
                return yaml.safe_load(f)
        except Exception:
            return {}

    def _check_connection(self):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=1)
            response.raise_for_status()
        except Exception as e:
            print(f"[WARN] Ollama not responding: {e}")

    def think(self, prompt: str, system_prompt: Optional[str] = None) -> Thought:
        start_time = time.time()
        if not system_prompt:
            system_prompt = "You are Victor, a helpful, friendly, and CONCISE personal assistant. Keep responses SHORT and DIRECT."
        
        try:
            # MAX SPEED OPTIMIZATION: low temp, small num_predict, low context
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 150,
                    "num_ctx": 1024
                }
            }
            response = requests.post(
                self.ollama_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get("response", "").strip()
            elapsed = time.time() - start_time
            
            print(f"[OK] Brain response in {elapsed:.2f}s")
            
            return Thought(
                text=response_text,
                model_used=self.model_name,
                response_time=elapsed
            )
        except Exception as e:
            print(f"[ERR] Brain error: {e}")
            return Thought(
                text=f"Sorry, I couldn't process that right now. ({str(e)})",
                model_used=self.model_name,
                response_time=time.time() - start_time
            )

    def get_status(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "connected": True
        }
