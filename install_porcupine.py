#!/usr/bin/env python3
"""
Install and setup Porcupine for Bible Clock voice control.
"""

import subprocess
import sys
import os
import urllib.request
import json

def install_porcupine():
    """Install Porcupine package."""
    print("📦 Installing Porcupine...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pvporcupine"])
        print("✅ Porcupine installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Porcupine: {e}")
        return False

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'pvporcupine',
        'speech_recognition', 
        'pyttsx3',
        'pyaudio',
        'numpy'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - missing")
            missing_packages.append(package)
    
    return missing_packages

def install_missing_packages(packages):
    """Install missing packages."""
    if not packages:
        return True
    
    print(f"📦 Installing missing packages: {', '.join(packages)}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)
        print("✅ All packages installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install packages: {e}")
        return False

def test_porcupine():
    """Test Porcupine installation."""
    print("🧪 Testing Porcupine...")
    try:
        import pvporcupine
        import pyaudio
        
        # Try to create a Porcupine instance
        porcupine = pvporcupine.create(keywords=['picovoice'])
        
        print(f"✅ Porcupine test successful")
        print(f"   Sample rate: {porcupine.sample_rate}Hz")
        print(f"   Frame length: {porcupine.frame_length}")
        print(f"   Keywords: picovoice (built-in)")
        
        # Test PyAudio
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        print(f"   Audio devices available: {device_count}")
        
        # Clean up
        porcupine.delete()
        p.terminate()
        
        return True
        
    except Exception as e:
        print(f"❌ Porcupine test failed: {e}")
        return False

def create_env_template():
    """Create .env template with Porcupine settings."""
    env_template = """
# Porcupine Voice Control Settings
ENABLE_VOICE=true
PORCUPINE_ACCESS_KEY=
PORCUPINE_KEYWORD_PATH=
PORCUPINE_SENSITIVITY=0.5

# Wake Word Settings (for display purposes)
WAKE_WORD=picovoice
VOICE_RATE=150
VOICE_VOLUME=0.8
VOICE_TIMEOUT=5
VOICE_PHRASE_LIMIT=15

# USB Audio Settings
USB_AUDIO_ENABLED=true
USB_MIC_DEVICE_NAME="USB PnP Audio Device"
USB_SPEAKER_DEVICE_NAME="USB PnP Audio Device"
AUDIO_INPUT_ENABLED=true
AUDIO_OUTPUT_ENABLED=true
"""
    
    print("📝 Creating Porcupine .env template...")
    
    # Check if .env exists
    if os.path.exists('.env'):
        print("   .env file already exists")
        
        # Read existing .env
        with open('.env', 'r') as f:
            existing_env = f.read()
        
        # Add Porcupine settings if not present
        if 'PORCUPINE_ACCESS_KEY' not in existing_env:
            print("   Adding Porcupine settings to existing .env...")
            with open('.env', 'a') as f:
                f.write('\n' + env_template)
            print("✅ Porcupine settings added to .env")
        else:
            print("   Porcupine settings already in .env")
    else:
        # Create new .env with full template
        with open('.env', 'w') as f:
            # Read existing template if available
            try:
                with open('.env.template', 'r') as template:
                    existing_template = template.read()
                f.write(existing_template)
            except FileNotFoundError:
                pass
            
            f.write(env_template)
        print("✅ .env file created with Porcupine settings")

def show_usage_instructions():
    """Show usage instructions."""
    print("\n🎯 Porcupine Setup Complete!")
    print("=" * 50)
    
    print("\n📋 Usage Instructions:")
    print("1. **Start Bible Clock:**")
    print("   ./start_bible_clock.sh")
    print()
    print("2. **Default Wake Word:**")
    print("   Say 'Picovoice' to activate")
    print("   Then say your command: 'help', 'next verse', etc.")
    print()
    print("3. **Custom Wake Word (Optional):**")
    print("   - Visit: https://console.picovoice.ai/")
    print("   - Create custom keyword (e.g., 'Hey Bible Clock')")
    print("   - Download .ppn file")
    print("   - Set PORCUPINE_KEYWORD_PATH in .env")
    print("   - Set PORCUPINE_ACCESS_KEY in .env")
    print()
    print("4. **Test Voice Control:**")
    print("   python test_porcupine_voice.py")
    print()
    print("🔧 Configuration:")
    print("   Edit .env file to customize settings")
    print("   PORCUPINE_SENSITIVITY: 0.1 (less sensitive) to 1.0 (more sensitive)")

def main():
    print("🎙️ Bible Clock Porcupine Voice Control Setup")
    print("=" * 60)
    
    # Check and install dependencies
    missing = check_dependencies()
    if missing:
        if not install_missing_packages(missing):
            print("❌ Setup failed - could not install required packages")
            return False
    
    # Test Porcupine
    if not test_porcupine():
        print("❌ Setup failed - Porcupine test failed")
        return False
    
    # Create .env template
    create_env_template()
    
    # Show usage instructions
    show_usage_instructions()
    
    print("\n✅ Porcupine setup completed successfully!")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)