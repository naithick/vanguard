#!/bin/bash
# Start GreenRoute Frontend

cd "$(dirname "$0")/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing npm packages..."
    npm install
fi

echo "Starting frontend on http://localhost:5173"
npm run dev
