"""
VICTOR AI - Local Ollama Engine (Tier 3 Provider)
Provides 100% offline, local host control using models like DeepSeek-R1, LLaMA-3.2, and Qwen2.5-Coder.
Guaranteed zero collision with Gemini and OpenAI providers.
"""
import os
import sys
import json
import asyncio
import httpx
from core.gemini_live import VictorLiveAgent

class VictorOllamaAgent:
    def __init__(self, model_name: str = "deepseek-r1:7b"):
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.model_name = os.getenv("OLLAMA_MODEL", model_name)
        self.host_agent = VictorLiveAgent()
        self.conversation_history = [
            {
                "role": "system",
                "content": (
                    "You are VICTOR (Virtual Intelligence Created To Outsmart Reality), created by AMKC, "
                    "a fully local autonomous AI Assistant running on the user's host machine. "
                    "Be loyal, razor-sharp, decisive, and respectful to your Commander."
                )
            }
        ]

    async def run(self):
        """Runs the interactive Local Ollama loop for VICTOR."""
        print("\n" + "="*60)
        print("   VICTOR AI - Powered by Local Ollama (Tier 3)")
        print(f"   Model: {self.model_name} at {self.host}")
        print("   Completely offline. Zero external API calls.")
        print("   Type 'exit' or press Ctrl+C to quit")
        print("="*60 + "\n")

        self.host_agent.play_sound_effect("boot")

        while True:
            try:
                user_msg = await asyncio.to_thread(input, "\n[Commander] > ")
                if not user_msg.strip():
                    continue
                if user_msg.strip().lower() in ("exit", "quit"):
                    print("VICTOR shutting down...")
                    break

                self.conversation_history.append({"role": "user", "content": user_msg})
                
                payload = {
                    "model": self.model_name,
                    "messages": self.conversation_history[-10:],
                    "stream": False
                }

                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(f"{self.host}/api/chat", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data.get("message", {}).get("content", "")
                        print(f"\n[VICTOR]: {reply}\n")
                        self.conversation_history.append({"role": "assistant", "content": reply})
                    else:
                        print(f"\n[VICTOR Error]: Ollama error ({resp.status_code}): {resp.text}\n")
            except (KeyboardInterrupt, EOFError):
                print("\nShutting down VICTOR...")
                break
            except Exception as e:
                print(f"[VICTOR Error]: {e}")
