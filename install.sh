
#!/bin/bash
set -e

echo "=========================================="
echo "  V.I.C.T.O.R. Installation Script"
echo "=========================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama not found. Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "Ollama already installed"
fi

# Start Ollama service
echo "Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!
sleep 3

# Pull required models
echo ""
echo "Pulling required models (this may take a while)..."
ollama pull llama3.2
ollama pull llava
ollama pull codellama
ollama pull phi3
ollama pull mistral

# Install system dependencies
echo ""
echo "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y \
        tesseract-ocr \
        libtesseract-dev \
        portaudio19-dev \
        python3-pyaudio \
        libespeak1 \
        espeak \
        ffmpeg
elif command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm \
        tesseract \
        tesseract-data-eng \
        portaudio \
        espeak \
        ffmpeg
elif command -v dnf &> /dev/null; then
    sudo dnf install -y \
        tesseract \
        tesseract-langpack-eng \
        portaudio-devel \
        espeak \
        ffmpeg
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create data directories
echo ""
echo "Creating data directories..."
mkdir -p data/vector_store
mkdir -p ~/.victor/macros

# Make main.py executable
chmod +x main.py

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "To start VICTOR:"
echo "  python main.py"
echo ""
echo "To run diagnostics:"
echo "  python main.py --diagnose"
echo ""

# Kill Ollama background process
kill $OLLAMA_PID 2>/dev/null || true


