#!/bin/bash
# Start GreenRoute - Backend & Frontend

# Start backend in background
echo "Starting backend..."
bash "$(dirname "$0")/start_backend.sh" &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 3

# Start frontend
echo "Starting frontend..."
bash "$(dirname "$0")/start_frontend.sh"

# Cleanup
kill $BACKEND_PID 2>/dev/null
