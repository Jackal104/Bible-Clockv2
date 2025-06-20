#!/usr/bin/env python3
"""
Test script to verify hostname configuration for Bible Clock web interface.
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def load_environment():
    """Load environment variables from .env file."""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value

def test_hostname_config():
    """Test hostname configuration."""
    print("📖 Bible Clock - Hostname Configuration Test")
    print("=" * 45)
    print()
    
    # Load configuration
    load_environment()
    
    # Get web interface configuration
    web_host = os.getenv('WEB_HOST', 'localhost')
    web_port = os.getenv('WEB_PORT', '5000')
    
    print(f"📋 Configuration:")
    print(f"   WEB_HOST: {web_host}")
    print(f"   WEB_PORT: {web_port}")
    print()
    
    print(f"🌐 Web interface will be accessible at:")
    print(f"   http://{web_host}:{web_port}")
    
    # Show additional access methods
    if web_host == 'bible-clock':
        print(f"   http://localhost:{web_port}")
        print(f"   http://127.0.0.1:{web_port}")
    
    print()
    
    # Test hostname resolution
    import socket
    print("🔍 Testing hostname resolution:")
    
    try:
        # Test if bible-clock resolves
        ip = socket.gethostbyname('bible-clock')
        print(f"   ✅ 'bible-clock' resolves to: {ip}")
        
        if ip == '127.0.0.1':
            print("   ✅ Correctly points to localhost")
        else:
            print(f"   ⚠️  Points to {ip} instead of localhost")
            
    except socket.gaierror:
        print("   ❌ 'bible-clock' hostname not configured")
        print("   💡 Run: sudo ./scripts/setup_hostname.sh")
    
    print()
    print("✅ Hostname configuration test completed!")

if __name__ == '__main__':
    test_hostname_config()