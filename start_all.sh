#!/bin/bash
# Start GreenRoute - Backend & Frontend

echo ""
echo "🌿 GreenRoute Mesh - Full Stack Startup"
echo "========================================"
echo ""
echo "This will start both backend and frontend servers."
echo "Make sure you have configured backend/.env first!"
echo ""

# Start backend in background
echo "📡 Starting backend server..."
bash "$(dirname "$0")/start_backend.sh" &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to initialize..."
sleep 5

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo ""
    echo "❌ Backend failed to start. Check the error above."
    exit 1
fi

echo "✅ Backend running on http://localhost:5001"
echo ""

# Start frontend
echo "🖥️  Starting frontend server..."
bash "$(dirname "$0")/start_frontend.sh"

# Cleanup on exit
echo ""
echo "Shutting down backend..."
kill $BACKEND_PID 2>/dev/null
echo "Done."
