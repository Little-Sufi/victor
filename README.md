
# VICTOR AI - Just A Rather Very Intelligent System

**v2.0.0 | Fully Local | No API Keys Required | Cross-Platform (Windows + Linux)**

---

## 🚀 Overview

VICTOR is an advanced, fully local AI assistant that runs entirely on your computer. No internet required, no API keys needed, no data sent anywhere.

### Key Features

✅ **Cross-Platform**: Works perfectly on both Windows and Linux (Debian/Ubuntu)
✅ **Fully Local**: All processing happens on your machine - privacy first!
✅ **Voice First**: Wake word "Hey Victor", speech-to-text, text-to-speech
✅ **Cyber-Themed GUI**: Beautiful floating orb with cyberpunk aesthetics
✅ **Self-Adaptive Learning**: Learns from every task and gets better over time
✅ **Background Mode**: Hides to system tray, always listening for wake word
✅ **Windows Startup**: Auto-launches on system boot
✅ **10+ Skills**: System control, file management, browser, coding, cooking, storytelling, diagnostics, penetration testing, and more!

---

## 🛠️ Installation

### Prerequisites

- Python 3.10 or higher
- Git (optional, for cloning)

---

### 🪟 Windows Installation

1. **Clone or download the repository**
   ```powershell
   git clone https://github.com/your-username/victor-ai.git
   cd victor-ai
   ```

2. **Create and activate a virtual environment**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Download AI Models (optional but recommended)**
   - **LLaMA/LLaVA**: Install Ollama (https://ollama.com) and pull models
     ```powershell
     ollama pull llava
     ollama pull mistral
     ```
   - **YOLOv8 for vision**: Downloads automatically on first run
   - **Whisper for STT**: Downloads automatically on first run

5. **Run VICTOR**
   ```powershell
   python main.py
   ```

6. **Install as Windows Startup (optional)**
   ```powershell
   python install_startup_simple.py
   ```

---

### 🐧 Linux (Debian/Ubuntu) Installation

1. **Clone or download the repository**
   ```bash
   git clone https://github.com/your-username/victor-ai.git
   cd victor-ai
   ```

2. **Install system dependencies**
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv \
     portaudio19-dev scrot xdotool
   ```

3. **Create and activate a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Download AI Models (optional but recommended)**
   - **LLaMA/LLaVA**: Install Ollama (https://ollama.com) and pull models
     ```bash
     ollama pull llava
     ollama pull mistral
     ```
   - **YOLOv8/Whisper**: Download automatically on first run

6. **Run VICTOR**
   ```bash
   python3 main.py
   ```

---

## 🎯 Usage

### Basic Interaction

- **Wake Victor**: Say "Hey Victor"
- **Speak to Victor**: Click the orb or wake him up
- **Background Mode**: Say "Go to background" or use tray menu
- **Show Victor**: Say "Hey Victor" or use tray menu
- **Quit**: Right-click orb → Shutdown VICTOR

### Available Skills

1. **System Control**: Launch apps, control volume, media keys, shutdown/reboot/sleep, type text, press keys, click mouse
2. **File Manager**: Browse, read, write, copy, move, delete files and directories
3. **Browser**: Open URLs, search the web
4. **Code Executor**: Run Python code safely in sandbox
5. **Cooking**: Recipes, measurement conversions, kitchen timers, cooking tips
6. **Storytelling**: Tell stories, create characters, build worlds
7. **System Diagnostics**: Full system diagnostics, permission checks, process listing, network status
8. **Penetration Testing**: Ethical security testing tools (port scanning, network discovery, WHOIS, DNS, HTTP headers) - **ETHICAL USE ONLY**
9. **Vision**: Object detection, image analysis (with LLaVA)
10. **Memory**: Remembers your conversations, preferences, and tasks

---

## ⚙️ Configuration

Edit `config/settings.yaml` to customize:
- Agent name (default: VICTOR)
- Voice gender (male/female)
- Wake word (default: "Hey Victor")
- AI models
- And more!

---

## 🔒 Privacy & Security

- **100% Local**: All processing happens on your machine
- **No Data Sent**: Nothing is sent to any external servers
- **Sandboxed Code Execution**: Python code runs in a secure sandbox
- **Ethical Penetration Testing**: Tools include explicit warnings and require approval

---

## 📝 License

MIT License - see LICENSE file for details.

---

## 🤝 Contributing

Contributions are welcome! Feel free to fork the repo and submit pull requests.

---

## 🙏 Acknowledgments

- PySide6 for the GUI
- Ollama for local LLMs
- Whisper for speech-to-text
- YOLOv8 for computer vision
- All open-source contributors!

---

**VICTOR AI - Your Personal AI Assistant, Always Here!**

