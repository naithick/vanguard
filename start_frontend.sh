#!/bin/bash
# Start GreenRoute Frontend

set -e

echo "🌿 GreenRoute Frontend Setup"
echo "============================"

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found!"
    echo ""
    echo "Please install Node.js 18+ from:"
    echo "  https://nodejs.org/"
    echo ""
    echo "Or use a package manager:"
    echo "  macOS:   brew install node"
    echo "  Ubuntu:  sudo apt install nodejs npm"
    echo "  Windows: winget install OpenJS.NodeJS"
    exit 1
fi

echo "✓ Node.js $(node --version) found"

# Check for npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found! It usually comes with Node.js."
    exit 1
fi

echo "✓ npm $(npm --version) found"

cd "$(dirname "$0")/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo ""
    echo "📦 Installing npm packages (first time setup)..."
    npm install
fi

echo ""
echo "🚀 Starting frontend on http://localhost:5173"
echo "   Press Ctrl+C to stop"
echo ""
npx vite --host
