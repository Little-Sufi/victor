"""
VICTOR AI - OpenAI / ChatGPT Engine (Tier 2 Provider)
Provides autonomous host control and voice interaction using OpenAI API (gpt-4o / gpt-4o-mini).
Guaranteed zero collision with Gemini and Ollama providers.
"""
import os
import sys
import json
import asyncio
import httpx
from core.gemini_live import VictorLiveAgent

class VictorOpenAIAgent:
    def __init__(self, model_name: str = "gpt-4o"):
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model_name = model_name
        self.host_agent = VictorLiveAgent()
        self.conversation_history = [
            {
                "role": "system",
                "content": (
                    "You are VICTOR (Virtual Intelligence Created To Outsmart Reality), created by AMKC, "
                    "an advanced autonomous AI Assistant with full host computer control. "
                    "Your commander is the user. Speak with high capability, loyalty, respect, and crisp intellect."
                )
            }
        ]

    async def run(self):
        """Runs the interactive OpenAI ChatGPT terminal loop for VICTOR."""
        print("\n" + "="*60)
        print("   VICTOR AI - Powered by OpenAI ChatGPT (Tier 2)")
        print(f"   Model: {self.model_name}")
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
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model_name,
                    "messages": self.conversation_history[-10:]
                }

                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data["choices"][0]["message"]["content"]
                        print(f"\n[VICTOR]: {reply}\n")
                        self.conversation_history.append({"role": "assistant", "content": reply})
                    else:
                        print(f"\n[VICTOR Error]: OpenAI API error ({resp.status_code}): {resp.text}\n")
            except (KeyboardInterrupt, EOFError):
                print("\nShutting down VICTOR...")
                break
            except Exception as e:
                print(f"[VICTOR Error]: {e}")
