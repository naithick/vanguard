#!/bin/bash
# Start GreenRoute Backend

set -e

echo "🌿 GreenRoute Backend Setup"
echo "==========================="

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found!"
    echo ""
    echo "Please install Python 3.9+ from:"
    echo "  https://www.python.org/downloads/"
    echo ""
    echo "Or use a package manager:"
    echo "  macOS:   brew install python3"
    echo "  Ubuntu:  sudo apt install python3 python3-venv python3-pip"
    echo "  Windows: winget install Python.Python.3.11"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "✓ Python $PYTHON_VERSION found"

cd "$(dirname "$0")/backend"

# Create venv if needed
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creating virtual environment (first time setup)..."
    python3 -m venv venv
fi

# Activate venv
echo "✓ Activating virtual environment"
source venv/bin/activate

# Install dependencies
if [ ! -f "venv/.installed" ]; then
    echo "📦 Installing Python packages..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    touch venv/.installed
    echo "✓ Dependencies installed"
else
    echo "✓ Dependencies already installed"
fi

# Check for .env
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  Configuration needed!"
    echo ""
    echo "1. Copy the example config:"
    echo "   cp .env.example .env"
    echo ""
    echo "2. Edit .env and add your Supabase credentials:"
    echo "   SUPABASE_URL=https://your-project.supabase.co"
    echo "   SUPABASE_SERVICE_KEY=your-service-key"
    echo ""
    echo "Get credentials from: https://supabase.com/dashboard"
    exit 1
fi

echo ""
echo "🚀 Starting backend on http://localhost:5001"
echo "   Press Ctrl+C to stop"
echo ""
python app.py
