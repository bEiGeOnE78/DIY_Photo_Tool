#!/bin/bash

echo "🏠 Starting servers for HOME NETWORK access..."
echo ""

# Start Face API server on home network
echo "🚀 Starting Face API server on 192.168.68.120:8001..."
python3 Scripts/face_api_server.py --bind 192.168.68.120 &
FACE_API_PID=$!

# Wait a moment for face API to start
sleep 2

# Start Gallery server on home network  
echo "🌐 Starting Gallery server on 192.168.68.120:8000..."
bash Scripts/start_gallery_server.sh --home

# When gallery server stops, also stop face API
kill $FACE_API_PID 2>/dev/null
echo ""
echo "🛑 All servers stopped"