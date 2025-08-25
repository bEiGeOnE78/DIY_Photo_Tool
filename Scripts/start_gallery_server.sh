#!/bin/bash

echo "Starting Photo Gallery Server..."
echo "Open: http://localhost:8000/index-display.html"
echo "Press Ctrl+C to stop"

python3 -m http.server 8000 --bind 192.168.68.120
