#!/bin/bash
# ReSpeaker HAT Setup Script for Bible Clock

echo "🎤 Setting up ReSpeaker HAT for Bible Clock..."

# Check if running on Raspberry Pi
if ! command -v raspi-config &> /dev/null; then
    echo "❌ This script is designed for Raspberry Pi"
    exit 1
fi

# Enable I2C and SPI
echo "⚡ Enabling I2C and SPI interfaces..."
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0

# Install ReSpeaker drivers
echo "📦 Installing ReSpeaker HAT drivers..."
cd /tmp
git clone https://github.com/respeaker/seeed-voicecard
cd seeed-voicecard
sudo ./install.sh

# Configure ALSA for ReSpeaker
echo "🔧 Configuring audio for ReSpeaker..."
sudo tee /home/pi/.asoundrc > /dev/null <<EOF
pcm.!default {
    type asym
    capture.pcm "mic"
    playback.pcm "speaker"
}
pcm.mic {
    type plug
    slave {
        pcm "hw:seeedvoicecard,0"
    }
}
pcm.speaker {
    type plug
    slave {
        pcm "hw:seeedvoicecard,0"
    }
}
EOF

# Test audio devices
echo "🔍 Available audio devices:"
arecord -l
aplay -l

# Test microphone
echo "🎤 Testing microphone (speak for 3 seconds)..."
timeout 3s arecord -f cd -t wav test_mic.wav
if [ -f test_mic.wav ]; then
    echo "✅ Microphone test file created"
    rm test_mic.wav
fi

# Update Bible Clock configuration
echo "📝 Updating Bible Clock configuration..."
if [ -f /home/pi/bible-clock/.env ]; then
    sed -i 's/RESPEAKER_ENABLED=false/RESPEAKER_ENABLED=true/' /home/pi/bible-clock/.env
    echo "✅ ReSpeaker enabled in Bible Clock configuration"
fi

echo ""
echo "🎉 ReSpeaker HAT setup complete!"
echo "Reboot your Raspberry Pi and then restart Bible Clock service:"
echo "sudo reboot"
echo "# After reboot:"
echo "sudo systemctl restart bible-clock"