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

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    build-essential \
    git \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7 \
    libtiff5

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install RPi.GPIO spidev numpy

# Clone and install IT8951 library
echo "📚 Installing IT8951 library..."
cd /tmp
if [ -d "IT8951" ]; then
    rm -rf IT8951
fi

git clone https://github.com/GregDMeyer/IT8951.git
cd IT8951
pip3 install .

# Verify installation
echo "✅ Verifying installation..."
python3 -c "
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
echo "4. Start Bible Clock: python3 main.py"
echo ""
echo "⚠️  Note: You may need to adjust the VCOM voltage in display_manager.py"
echo "   based on your specific display model (-2.06V is typical)"