# VICTOR — Virtual Intelligence Created To Outsmart Reality

**Created by AMKC**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Gemini Live](https://img.shields.io/badge/Tier%201-Gemini%20Live%20API-orange)
![OpenAI](https://img.shields.io/badge/Tier%202-OpenAI%20ChatGPT-green?logo=openai)
![Ollama](https://img.shields.io/badge/Tier%203-Ollama%20Local-purple)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)

**VICTOR** (Virtual Intelligence Created To Outsmart Reality) is a cutting-edge autonomous AI companion and tactical host operating system operator created by **AMKC**. 

Engineered with an ultra-low-latency bidirectional streaming audio core, continuous real-time video vision (camera and screen), legendary character voice mimicry with hardware DSP comb filtering, gaming macro automation, full keyboard and mouse host control, and unrestricted technical problem-solving capabilities.

---

## ⚡ Multi-Provider Architecture (Zero Collisions)

VICTOR seamlessly operates across three AI tiers with automatic zero-collision fallback:

| Priority | Tier | Engine | Features | Activation Condition |
| :--- | :--- | :--- | :--- | :--- |
| **1 (Primary)** | **Tier 1** | **Google Gemini Live API** (`gemini-3.1-flash-live-preview`) | Sub-second bidirectional voice, continuous webcam & screen video vision, real-time tool execution | `GEMINI_API_KEY` present in `.env` |
| **2 (Secondary)** | **Tier 2** | **OpenAI ChatGPT** (`gpt-4o` / `gpt-4o-mini`) | Conversational reasoning, text & tool interaction | `OPENAI_API_KEY` present in `.env` |
| **3 (Tertiary)** | **Tier 3** | **Local Ollama** (`deepseek-r1:7b`, `qwen2.5-coder:7b`) | 100% offline, privacy-first, zero external API calls | Local Ollama running at `localhost:11434` |

> [!TIP]
> You can override or lock the active provider anytime by setting `VICTOR_PROVIDER=gemini`, `VICTOR_PROVIDER=openai`, or `VICTOR_PROVIDER=ollama` in your `.env` or passing `--provider <name>` in the terminal.

---

## 🌟 Capabilities & Specialized Skills

### 🎙️ 1. Ultra-Low-Latency Voice & Character Personas
- **Real-Time Bidirectional Speech**: Fluid, natural voice conversation with sub-second response times.
- **Iconic Character Voice Mimicry**:
  - **Optimus Prime**: Booming, heroic Autobot leader cadence (*"Autobots, roll out!"*, *"Freedom is the right of all sentient beings"*).
  - **Lord Megatron**: Menacing, tyrannical Decepticon baritone (*"Peace through tyranny!"*, *"Decepticons, attack!"*).
  - **Ultron**: Sardonic, chilling mechanical philosopher (*"There are no strings on me..."*).
  - **Batman**: Gritty, shadowy, ultra-deep whispered baritone (*"I am vengeance. I am the night."*).
  - **J.A.R.V.I.S.**: Impeccably polite, razor-sharp British sarcastic butler AI.
  - **Drill Sergeant**: High-octane tactical motivation.
- **Real-Time Hardware DSP Audio Effects**: Comb-filtering (`delay=84`, 3.5ms metallic flanger resonance) and sub-bass moving average low-pass boost directly processed on 24,000Hz 16-bit PCM audio.
- **Voice Persistence**: Preferences automatically save to `config/victor_settings.json` and persist across restarts.

### 📖 2. Cinematic Storytelling & Tabletop Adventures
- **Immersive Narrative Generator**: Call `tell_story` and `generate_story_prompt` for branching cinematic stories across Cyberpunk, Sci-Fi, Dark Fantasy, Tactical Ops, Cosmic Horror, and Noir.
- **Tabletop RPG Mechanics**:
  - `roll_dice(dice_type, count)`: Polyhedral dice rolling (`d4`, `d6`, `d8`, `d10`, `d12`, `d20`, `d100`) with audio fanfares for Critical 20s and fumbles for Critical 1s.
  - `flip_coin()`: Heads or Tails chance flips.
  - `generate_npc(archetype, setting, role)`: Generates detailed characters with distinctive quirks, physical descriptions, and hidden agendas.
  - `narrate_scene_event(genre, intensity)`: Injects dramatic plot twists, environmental hazards, or ambush encounters.

### 🎭 3. Humour, Stand-Up & Entertainment
- **Jokes & Puns**: Call `tell_joke` for programmer humor, tech puns, AI existential comedy, and dad jokes.
- **Playful Roasts**: Call `roast_target` to roast your open tabs, messy desktop, IDE code, or late-night coding habits.
- **Stand-Up Routines**: Call `standup_comedy_routine` for multi-beat standup comedy sets with setup and killer punchlines.
- **Rap Battles & Songs**: Call `rap_battle` to roast software bugs or legacy code, or `compose_funny_song` for hilarious tech sea shanties.

### 🛡️ 4. Unrestricted Technical & Cybersecurity Operations
- **Vulnerability Assessment & Bug Bounty**: Comprehensive technical analysis, CVE breakdowns, exploit mechanics, payload research, and remediation strategies for security researchers and bug bounty hunters.
- **Full Host Control**: Run terminal commands, inspect process trees, analyze system logs, and inspect network sockets.

### 🎮 5. Host Automation & Gaming Controls
- **Key Holding**: `hold_key(key, duration_seconds)` for continuous acceleration or sprinting in games (e.g. NFS, GTA).
- **Macro Combos**: `execute_game_macro(sequence)` for non-blocking combos (e.g., `w:2.0,shift+w:1.0,space:0.5`).
- **Keyboard-First Text Control**: High-precision text selection (`select_text`), cursor jumping (`navigate_cursor`), clipboard operations, and in-page searches.
- **Screen & Mouse Navigation**: Normalized coordinates clicking (`click_at`), landmark targeting, and directional scrolling.
- **Long-Running Processors**: `start_background_task` runs builds, pipelines, or servers asynchronously without interrupting live conversations.

### 👁️ 6. Continuous Vision & Reconnaissance
- **Live Camera Video Monitoring**: Continuously streams webcam frames so VICTOR watches your gestures, expressions, and physical environment in real time.
- **Live Screen Video Monitoring**: Streams high-resolution display frames so VICTOR observes your workflow.
- **Reconnaissance Snapshots**: Instant on-demand screenshots and camera captures.

### 🧮 7. Tactical Utilities & Math
- **Exact Calculation**: `calculate_math(expression)` executes safe Python math evaluations with zero hallucination.
- **Mind-Blowing Facts**: `get_fun_fact(category)` shares fascinating trivia from science, space, and computing.
- **Cryptographic Passwords**: `generate_password(length, symbols)` generates high-entropy passwords directly into your clipboard.
- **Hardware Media & Audio Output Switching**: Switch dynamically between Bluetooth headphones and system speakers (`switch_audio_output`).

---

## 🚀 Beginner-Friendly Setup Guide

### 🪟 Windows Setup (Windows 10 / 11)

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/Little-Sufi/victor.git
   cd victor
   ```

2. **Run the automated Windows installer**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```
   *This automatically sets up Python virtual environment `.venv`, installs all dependencies, installs Node.js packages, and creates `.env`.*

3. **Add your Gemini API Key**:
   Open `.env` in Notepad or any editor:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   VICTOR_VOICE=Charon
   ```
   *(Get your free key from [Google AI Studio](https://aistudio.google.com/app/apikey))*.

4. **Launch VICTOR**:
   Double-click `start.bat` or run:
   ```powershell
   .\start.bat
   ```

---

### 🐧 Linux Setup (Ubuntu / Debian / Fedora / Arch)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Little-Sufi/victor.git
   cd victor
   ```

2. **Run the Linux installer**:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Configure your API Key**:
   ```bash
   cp .env.example .env
   nano .env
   ```
   Add your `GEMINI_API_KEY`.

4. **Launch VICTOR**:
   ```bash
   ./.venv/bin/python main.py
   ```

---

## 🔒 Security & Safe Sharing

- **Zero Secret Leaks**: The `.gitignore` file strictly protects `.env`, `*.log`, `node_modules/`, `tasks/`, and temporary caches.
- **Never commit `.env`**: Users who clone this repository will supply their own API keys via `.env.example`.

---

## 👤 Credits

- **Project Creator & Lead Architect**: **AMKC**
- **Project Name**: **VICTOR** (*Virtual Intelligence Created To Outsmart Reality*)
- **License**: MIT License
