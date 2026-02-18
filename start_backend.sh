#!/bin/bash
# Start GreenRoute Backend

cd "$(dirname "$0")/backend"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -q

# Check for .env
if [ ! -f ".env" ]; then
    echo "ERROR: .env file missing. Copy .env.example to .env and add your Supabase credentials."
    exit 1
fi

echo "Starting backend on http://localhost:5001"
python app.py
