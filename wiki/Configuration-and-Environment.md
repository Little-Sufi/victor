# ⚙️ Configuration & Environment Guide

VICTOR relies on a streamlined configuration system managed via `.env` and `config/victor_settings.json`.

---

## 🔑 Environment Variables (`.env`)

Create a `.env` file in the root of the project by copying `.env.example`:

```bash
cp .env.example .env
```

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API Key (Tier 1 Live API) | `AIzaSy...` |
| `OPENAI_API_KEY` | OpenAI API Key (Tier 2 ChatGPT fallback) | `sk-...` |
| `VICTOR_PROVIDER`| Lock active provider (`gemini`, `openai`, `ollama`) | `gemini` |
| `OLLAMA_HOST` | Local Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Local offline model name | `deepseek-r1:7b` |
| `AUDIO_OUTPUT_DEVICE`| Default audio sink for speaker output | `default` |
| `AUDIO_INPUT_DEVICE` | Default microphone source | `default` |

---

## 🛠️ Persistent Settings (`config/victor_settings.json`)

User preferences, voice persona locks, and DSP options are saved automatically:

```json
{
  "active_persona": "optimus_prime",
  "comb_filter_enabled": true,
  "sub_bass_boost": true,
  "default_volume": 1.0,
  "screen_capture_fps": 1.0,
  "camera_capture_fps": 1.0
}
```
