# ❓ Troubleshooting & Frequently Asked Questions (FAQ)

### Q1: Gemini Live API returns WebSocket connection error.
* **Resolution**: Verify that `GEMINI_API_KEY` is valid and has access to the Live API preview models (`gemini-3.1-flash-live-preview`). If cloud APIs are unreachable, VICTOR automatically fails over to Tier 2 (OpenAI) or Tier 3 (Ollama).

---

### Q2: How do I run VICTOR completely offline?
1. Install [Ollama](https://ollama.ai) on your system.
2. Pull your desired offline model:
   ```bash
   ollama pull deepseek-r1:7b
   ```
3. Start VICTOR in offline mode:
   ```bash
   python main.py --provider ollama
   ```

---

### Q3: Audio echo or loopback feedback during voice streaming.
* **Resolution**: Use headphones or enable hardware acoustic echo cancellation (AEC) in your system sound settings. VICTOR processes audio in full-duplex mode at 24kHz.
