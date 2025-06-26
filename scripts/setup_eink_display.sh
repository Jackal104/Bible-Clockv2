#!/bin/bash
# Bible Clock v3.0 - E-ink Display Setup Script
# Installs IT8951 drivers for Waveshare e-ink displays

set -e

echo "🖥️  Setting up E-ink Display (IT8951) for Bible Clock..."

# Check if running on Raspberry Pi
if ! command -v raspi-config &> /dev/null; then
    echo "❌ This script must be run on a Raspberry Pi"
    exit 1
fi

# Enable SPI interface
echo "📡 Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# Check if SPI is properly configured
echo "🔍 Checking SPI configuration..."
if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
    echo "Adding SPI configuration to /boot/config.txt..."
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
    echo "⚠️  SPI enabled in config - reboot required before continuing"
    echo "Please run 'sudo reboot' and then re-run this script"
    exit 0
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    build-essential \
    git \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7 \
    libjpeg-dev \
    libtiff5-dev \
    libgpiod-dev \
    gpiod

# Get script directory and project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if virtual environment exists
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    echo "🐍 Using existing virtual environment..."
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo "🐍 Installing Python dependencies system-wide..."
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install RPi.GPIO spidev numpy

# Clone and install IT8951 library
echo "📚 Installing IT8951 library..."
DRIVER_DIR="$HOME/IT8951"
if [ ! -d "$DRIVER_DIR" ]; then
    git clone https://github.com/GregDMeyer/IT8951.git "$DRIVER_DIR"
fi
cd "$DRIVER_DIR"
pip install .[rpi]

# Verify installation
echo "✅ Verifying installation..."
python -c "
try:
    from IT8951.display import AutoEPDDisplay
    print('✅ IT8951 library installed successfully')
except ImportError as e:
    print(f'❌ IT8951 installation failed: {e}')
    exit(1)
except Exception as e:
    print(f'⚠️  IT8951 installed but display not connected: {e}')
"

# Test SPI interface
echo "🔍 Testing SPI interface..."
if [ -e /dev/spidev0.0 ]; then
    echo "✅ SPI interface available at /dev/spidev0.0"
else
    echo "❌ SPI interface not available. Please run 'sudo raspi-config' and enable SPI."
    exit 1
fi

echo ""
echo "🎉 E-ink display setup completed!"
echo ""
echo "📝 Next steps:"
echo "1. Connect your Waveshare IT8951 e-ink display"
echo "2. Default GPIO connections:"
echo "   - RST pin: GPIO 17"
echo "   - CS pin:  GPIO 8 (SPI0 CS0)"
echo "   - BUSY pin: GPIO 24"
echo "3. Set SIMULATION_MODE=false in your .env file"
echo "4. Start Bible Clock: ./start_bible_clock.sh"
echo ""
echo "⚠️  Note: VCOM voltage is set to -1.21V (from display ribbon)"
echo "   If display quality is poor, adjust DISPLAY_VCOM in .env file"