#!/bin/bash

echo "💻 Starting servers for LOCAL access only..."
echo ""

# Start Face API server on localhost
echo "🚀 Starting Face API server on localhost:8001..."
python3 Scripts/face_api_server.py --bind 127.0.0.1 &
FACE_API_PID=$!

# Wait a moment for face API to start
sleep 2

# Start Gallery server on localhost
echo "📱 Starting Gallery server on localhost:8000..."
bash Scripts/start_gallery_server.sh --localhost

# When gallery server stops, also stop face API
kill $FACE_API_PID 2>/dev/null
echo ""
echo "🛑 All servers stopped"