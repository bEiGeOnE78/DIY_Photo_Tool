#!/bin/bash

# Default to localhost, but allow override
BIND_ADDRESS="127.0.0.1"
PORT="8000"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --home)
      BIND_ADDRESS="192.168.68.120"
      shift
      ;;
    --localhost)
      BIND_ADDRESS="127.0.0.1"
      shift
      ;;
    --bind)
      BIND_ADDRESS="$2"
      shift
      shift
      ;;
    --port)
      PORT="$2"
      shift
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --home           Bind to 192.168.68.120 (home network)"
      echo "  --localhost      Bind to 127.0.0.1 (localhost only, default)"
      echo "  --bind ADDRESS   Bind to specific IP address"
      echo "  --port PORT      Use specific port (default: 8000)"
      echo "  -h, --help       Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

echo "Starting Photo Gallery Server..."
echo "Binding to: $BIND_ADDRESS:$PORT"

if [ "$BIND_ADDRESS" = "127.0.0.1" ]; then
  echo "📱 Local access: http://localhost:$PORT/index-display.html"
else
  echo "🌐 Network access: http://$BIND_ADDRESS:$PORT/index-display.html"
  echo "📱 Local access: http://localhost:$PORT/index-display.html"
fi

echo "Press Ctrl+C to stop"
echo ""

python3 -m http.server $PORT --bind $BIND_ADDRESS
