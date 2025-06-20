#!/bin/bash
# Bible Clock v3.0 - Startup Script
# Activates virtual environment and starts Bible Clock

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "📖 Starting Bible Clock v3.0..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run the setup script first: ./scripts/setup_bible_clock.sh"
    exit 1
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found!"
    echo "Please ensure you're in the Bible-Clockv2 directory"
    exit 1
fi

# Start Bible Clock
echo "🚀 Launching Bible Clock..."
python main.py