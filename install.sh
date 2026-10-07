#!/bin/bash
# ========================================================
#  VICTOR Installation Script for Linux & macOS
#  Creator: Little-Sufi
#  VICTOR: Virtual Intelligence Created To Outsmart Reality
# ========================================================
set -e

echo "=========================================="
echo "  VICTOR AI Installation Script (Linux)   "
echo "=========================================="
echo ""

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3.10+ is required but was not found."
    echo "Please install python3 and python3-venv (e.g., sudo apt install python3 python3-venv)"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "[OK] Python detected: $PYTHON_VERSION"

# 2. Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version 2>&1)
    echo "[OK] Node.js detected: $NODE_VERSION"
else
    echo "[WARN] Node.js not detected. Some npm automation modules may be limited."
fi

# 3. Install system dependencies if apt/pacman/dnf available
echo ""
echo "Checking system audio & screen capture dependencies..."
if command -v apt-get &> /dev/null; then
    echo "Installing system packages via apt..."
    sudo apt-get update -qq || true
    sudo apt-get install -y -qq \
        portaudio19-dev \
        libasound2-dev \
        ffmpeg \
        wmctrl \
        xclip \
        libxcb-cursor0 \
        libgl1-mesa-glx || true
elif command -v pacman &> /dev/null; then
    echo "Installing system packages via pacman..."
    sudo pacman -S --noconfirm portaudio ffmpeg wmctrl xclip || true
elif command -v dnf &> /dev/null; then
    echo "Installing system packages via dnf..."
    sudo dnf install -y portaudio-devel ffmpeg wmctrl xclip || true
fi

# 4. Create Virtual Environment
echo ""
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment (.venv)..."
    python3 -m venv .venv
fi
echo "[OK] Virtual environment ready."

# 5. Install Python Dependencies
echo ""
echo "Installing Python dependencies from requirements.txt..."
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

# 6. Install Node.js Dependencies
if [ -f "package.json" ] && command -v npm &> /dev/null; then
    echo ""
    echo "Installing Node.js dependencies..."
    npm install --no-audit --prefer-offline 2>/dev/null || true
    echo "[OK] Node modules installed."
fi

# 7. Setup .env
echo ""
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[IMPORTANT] Created '.env' from '.env.example'!"
        echo "Please open '.env' and add your GEMINI_API_KEY from:"
        echo "  https://aistudio.google.com/app/apikey"
    fi
else
    echo "[OK] '.env' configuration file is already present."
fi

# 8. Create directories
mkdir -p notes tasks config

chmod +x main.py || true

echo ""
echo "=========================================="
echo "  Installation Completed Successfully!    "
echo "=========================================="
echo ""
echo "To launch VICTOR:"
echo "  ./.venv/bin/python main.py"
echo ""
