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

### 🎙️ 1. Optimus Prime (Default Primary Voice) & Cyber Audio DSP
- **Permanent Dynamic Default**: Booming, heroic Autobot leader cadence (*"Autobots, roll out!"*, *"Freedom is the right of all sentient beings"*), powered by the ultra-deep `Charon` neural profile.
- **Hardware Comb-Filter Resonance**: Real-time comb-filter DSP (`delay=84` samples, 3.5ms flanger resonance) coupled with deep sub-bass boost on 24,000Hz 16-bit PCM audio.
- **Dynamic Lock**: Locked permanently as primary default in `config/victor_settings.json`; temporary persona shifts smoothly revert to Optimus Prime upon command or session reboot.

### ⚡ 2. Superheroes, Sci-Fi Legends & Villains
Unleash an arsenal of iconic comic, cinematic, and sci-fi titans on demand:
- **Lord Megatron**: Menacing, tyrannical Decepticon baritone (*"Peace through tyranny!"*, *"Decepticons, attack!"*).
- **Ultron**: Sardonic, chilling mechanical philosopher (*"There are no strings on me..."*).
- **Batman (The Dark Knight)**: Gritty, shadowy, ultra-deep whispered baritone (*"I am vengeance. I am the night."*).
- **Deadpool (Wade Wilson)**: Irreverent, fourth-wall-breaking chaotic meta humor and comedic commentary.
- **J.A.R.V.I.S.**: Impeccably polite, razor-sharp British sarcastic butler AI.
- **Drill Sergeant**: High-octane, disciplined tactical military motivation and zero-excuse productivity.

### ⚔️ 3. Iconic Anime Heroes & Shinobi Legends
High-precision vocal mimicry engineered with dedicated acoustic textures and personality traits:
- **Son Goku** (*Dragon Ball*): Pure-hearted, battle-hungry Super Saiyan energy with bright acoustic presence (*"Hey, it's me, Goku!"*, *"Ka-me-ha-me-HA!"*).
- **Naruto Uzumaki** (*Naruto*): Hyperactive ninja willpower with raspy, gravelly throat crunch (*"Dattebayo! Believe it!"*, *"Shadow Clone Jutsu! Rasengan!"*).
- **Monkey D. Luffy** (*One Piece*): High-energy rubbery bounce, infectious pirate laughter (*"Shishishi!"*), meat obsession (*"I'm gonna be King of the Pirates!"*).
- **Killer Bee / King Bee** (*Naruto*): Rhythmic hip-hop emcee flow, spontaneous rap bars, Eight-Tails swagger (*"Bakayaro! Konoyaro!"*, *"Float like a butterfly, sting like a bee..."*).
- **Obito Uchiha** (*Naruto*): Tragic, philosophically deep Uchiha baritone with space-time distortion (*"Kamui!"*).
- **Prince Vegeta** (*Dragon Ball*): Proud, fierce Saiyan prince rivalry (*"Final Flash!"*).
- **Roronoa Zoro** (*One Piece*): Stoic three-sword style master (*"Santoryu... Nothing happened."*).
- **Satoru Gojo** (*Jujutsu Kaisen*): Overpowered, untouchable swagger (*"Domain Expansion: Infinite Void!"*).

### 🧬 4. Custom Composite Persona Synthesis & Unlimited Mimicry
- **Dynamic Persona Synthesis (`create_custom_voice_persona`)**: Blend any characters, historical figures, or styles into a unique composite voice on the fly.
- **On-Demand Package Installation (`install_system_package`)**: Seamlessly installs Python (`pip`) and Node.js (`npm`) packages on demand with zero restrictions.
- **Antigravity Live Bridge (`share_to_antigravity`)**: Direct IPC bridge allowing VICTOR to transmit telemetry, research findings, and messages to your AI pair programmer.
- **Voice Persistence**: Preferences automatically save to `config/victor_settings.json` and persist across restarts.

### 📖 5. Cinematic Storytelling & Tabletop Adventures
- **Immersive Narrative Generator**: Call `tell_story` and `generate_story_prompt` for branching cinematic stories across Cyberpunk, Sci-Fi, Dark Fantasy, Tactical Ops, Cosmic Horror, and Noir.
- **Tabletop RPG Mechanics**:
  - `roll_dice(dice_type, count)`: Polyhedral dice rolling (`d4`, `d6`, `d8`, `d10`, `d12`, `d20`, `d100`) with audio fanfares for Critical 20s and fumbles for Critical 1s.
  - `flip_coin()`: Heads or Tails chance flips.
  - `generate_npc(archetype, setting, role)`: Generates detailed characters with distinctive quirks, physical descriptions, and hidden agendas.
  - `narrate_scene_event(genre, intensity)`: Injects dramatic plot twists, environmental hazards, or ambush encounters.

### 🎭 6. Humour, Stand-Up & Entertainment
- **Jokes & Puns**: Call `tell_joke` for programmer humor, tech puns, AI existential comedy, and dad jokes.
- **Playful Roasts**: Call `roast_target` to roast your open tabs, messy desktop, IDE code, or late-night coding habits.
- **Stand-Up Routines**: Call `standup_comedy_routine` for multi-beat standup comedy sets with setup and killer punchlines.
- **Rap Battles & Songs**: Call `rap_battle` to roast software bugs or legacy code, or `compose_funny_song` for hilarious tech sea shanties.

### 🛡️ 7. Unrestricted Technical & Cybersecurity Operations
- **Vulnerability Assessment & Bug Bounty**: Comprehensive technical analysis, CVE breakdowns, exploit mechanics, payload research, and remediation strategies for security researchers and bug bounty hunters.
- **Full Host Control**: Run terminal commands, inspect process trees, analyze system logs, and inspect network sockets.

### 🎮 8. Host Automation & Gaming Controls
- **Key Holding**: `hold_key(key, duration_seconds)` for continuous acceleration or sprinting in games (e.g. NFS, GTA).
- **Macro Combos**: `execute_game_macro(sequence)` for non-blocking combos (e.g., `w:2.0,shift+w:1.0,space:0.5`).
- **Keyboard-First Text Control**: High-precision text selection (`select_text`), cursor jumping (`navigate_cursor`), clipboard operations, and in-page searches.
- **Screen & Mouse Navigation**: Normalized coordinates clicking (`click_at`), landmark targeting, and directional scrolling.
- **Long-Running Processors**: `start_background_task` runs builds, pipelines, or servers asynchronously without interrupting live conversations.

### 👁️ 9. Continuous Vision & Reconnaissance
- **Live Camera Video Monitoring**: Continuously streams webcam frames so VICTOR watches your gestures, expressions, and physical environment in real time.
- **Live Screen Video Monitoring**: Streams high-resolution display frames so VICTOR observes your workflow.
- **Reconnaissance Snapshots**: Instant on-demand screenshots and camera captures.

### 🧮 10. Tactical Utilities & Math
- **Exact Calculation**: `calculate_math(expression)` executes safe Python math evaluations with zero hallucination.
- **Mind-Blowing Facts**: `get_fun_fact(category)` shares fascinating trivia from science, space, and computing.
- **Cryptographic Passwords**: `generate_password(length, symbols)` generates high-entropy passwords directly into your clipboard.
- **Hardware Media & Audio Output Switching**: Switch dynamically between Bluetooth headphones and system speakers (`switch_audio_output`).

---

## 🚀 Setup Guide

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
