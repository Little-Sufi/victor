# VICTOR Setup Guide — Cross-Platform Installation

**Creator: [Little-Sufi](https://github.com/Little-Sufi)**  
**VICTOR: Virtual Intelligence Created To Outsmart Reality**

This guide provides complete, step-by-step instructions to configure, install, and execute VICTOR on **Windows 10/11** and **Linux (Ubuntu, Debian, Fedora, Arch)**.

---

## 📋 System Requirements

- **Python**: 3.10 to 3.13
- **Node.js**: v18.0.0 or newer
- **Microphone & Audio Output**: Any working microphone and speakers/headphones
- **Webcam**: Standard USB or integrated webcam (for live video vision)
- **API Key**: Free Gemini API Key from [Google AI Studio](https://aistudio.google.com/app/apikey)

---

## 🪟 Windows Setup Guide (One-Click)

### Step 1: Clone the Repository
Open PowerShell or Windows Terminal:
```powershell
git clone https://github.com/Little-Sufi/victor.git
cd victor
```

### Step 2: Run the Automated Installer
Execute the included Windows installer script:
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```
This script automatically:
1. Detects Python 3.10+ and Node.js.
2. Creates the Python virtual environment (`.venv`).
3. Installs all Python dependencies from `requirements.txt`.
4. Installs Node.js IPC automation dependencies from `package.json`.
5. Creates `.env` from `.env.example`.

### Step 3: Configure Your API Key
Open `.env` in Notepad:
```env
GEMINI_API_KEY=your_gemini_api_key_here
VICTOR_VOICE=Charon
```

### Step 4: Start VICTOR
Double-click `start.bat` or run:
```powershell
.\start.bat
```

---

## 🐧 Linux Setup Guide (Ubuntu / Debian / Fedora / Arch)

### Step 1: Clone and Run the Linux Installer
```bash
git clone https://github.com/Little-Sufi/victor.git
cd victor
chmod +x install.sh
./install.sh
```

The `install.sh` script installs all required audio drivers (`portaudio19-dev`, `libasound2-dev`), screen capture tools (`ffmpeg`, `xclip`, `wmctrl`), creates the `.venv` virtual environment, installs Python and Node.js requirements, and generates `.env`.

### Step 2: Configure Your API Key
```bash
nano .env
```
Add your `GEMINI_API_KEY`.

### Step 3: Audio Group Permissions
Ensure your user account can access audio hardware:
```bash
sudo usermod -aG audio $USER
```
*(Log out and back in if this is the first time adding yourself to the audio group).*

### Step 4: Start VICTOR
```bash
./.venv/bin/python main.py
```

---

## 🧠 Multi-Provider Configuration (Tier 1 -> Tier 2 -> Tier 3)

VICTOR automatically prioritizes providers without conflicts:

### Tier 1: Google Gemini Live API (Primary & Recommended)
Provides live streaming bidirectional audio and real-time vision:
```env
GEMINI_API_KEY=your_gemini_api_key_here
VICTOR_VOICE=Charon
```

### Tier 2: OpenAI ChatGPT (Secondary Fallback)
Used if `GEMINI_API_KEY` is not set or if `VICTOR_PROVIDER=openai`:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
```

### Tier 3: Local Ollama (100% Offline & Private)
Used if no external API keys are configured:
1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull your desired model:
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama pull deepseek-r1:7b
   ```
3. Configure `.env`:
   ```env
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=qwen2.5-coder:7b
   ```

---

## 🎙️ Character Voice Profiles & Audio DSP

You can command VICTOR by voice to switch character personas anytime:
- *"Switch to Optimus Prime"* — Heroic Autobot leader cadence.
- *"Switch to Megatron"* — Menacing Decepticon metallic baritone.
- *"Switch to Ultron"* — Cold, philosophical robotic cadence.
- *"Switch to J.A.R.V.I.S."* — British witty butler AI.
- *"Switch to Batman"* — Deep whispered baritone.

Persistent settings are stored in `config/victor_settings.json` and persist across restarts.

---

## ❓ Troubleshooting

1. **Microphone is silent**:
   Verify your default recording device in Windows Sound Settings or Linux PulseAudio/PipeWire.
2. **Audio device switching**:
   Say *"Switch audio output to headphones"* or *"Switch audio output to speakers"*.
3. **API Key errors**:
   Verify your key in `.env`. Ensure there are no surrounding quotes or trailing spaces.
