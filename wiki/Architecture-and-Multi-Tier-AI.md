# ⚡ Multi-Tier AI Architecture

VICTOR features a zero-collision, 3-tier fallback engine designed to guarantee continuous operation regardless of cloud network conditions or quota limits.

---

## 🏛️ The Three Execution Tiers

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                     User Input (Voice / Vision)              │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  Tier 1: Google Gemini Live API (Primary Default)           │
 │  • Model: gemini-3.1-flash-live-preview                     │
 │  • Sub-second bidirectional streaming WebSockets            │
 │  • Real-time video vision (Webcam & Desktop)                │
 └──────────────────────────────┬──────────────────────────────┘
                                │ (On Quota / Network Error)
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  Tier 2: OpenAI ChatGPT (Secondary Fallback)                │
 │  • Model: gpt-4o / gpt-4o-mini                              │
 │  • Conversational reasoning & tool execution                │
 └──────────────────────────────┬──────────────────────────────┘
                                │ (On Quota / Offline)
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  Tier 3: Local Ollama (Tertiary / Offline Air-Gapped)        │
 │  • Model: deepseek-r1:7b / qwen2.5-coder:7b                 │
 │  • 100% offline local LLM execution at localhost:11434      │
 └─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Dynamic Provider Overrides

You can lock the active provider at startup or during execution:
1. **Via Command Line**:
   ```bash
   python main.py --provider gemini
   python main.py --provider openai
   python main.py --provider ollama
   ```
2. **Via Environment Variable**:
   Set `VICTOR_PROVIDER=gemini` inside your `.env` file.
