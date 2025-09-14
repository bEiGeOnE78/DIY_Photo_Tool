# Photo Gallery Network Configuration Guide

## Server Address Configuration

The photo gallery now uses a three-server architecture with flexible network configuration for both home and away usage:

1. **Gallery Web Server** (Port 8000) - Serves static files and web interface
2. **Face API Server** (Port 8001) - Handles face recognition and core photo operations
3. **Gallery API Server** (Port 8002) - Manages gallery operations and file management

## Quick Start Scripts

### 🏠 Home Network (192.168.68.120)
```bash
bash Scripts/start_home_servers.sh
```
- Gallery Web Interface: http://192.168.68.120:8000/index-display.html
- Face API Server: http://192.168.68.120:8001
- Gallery API Server: http://192.168.68.120:8002

### 💻 Local Only (localhost)
```bash
bash Scripts/start_local_servers.sh
```
- Gallery Web Interface: http://localhost:8000/index-display.html
- Face API Server: http://localhost:8001
- Gallery API Server: http://localhost:8002

## Manual Server Control

### Gallery Server Options
```bash
# Default (localhost only)
bash Scripts/start_gallery_server.sh

# Home network
bash Scripts/start_gallery_server.sh --home

# Localhost explicitly
bash Scripts/start_gallery_server.sh --localhost

# Custom address
bash Scripts/start_gallery_server.sh --bind 192.168.1.100

# Custom port
bash Scripts/start_gallery_server.sh --port 9000

# Help
bash Scripts/start_gallery_server.sh --help
```

### API Server Options

#### Face API Server (Port 8001)
```bash
# Default (localhost only)
python3 Scripts/face_api_server.py

# Home network
python3 Scripts/face_api_server.py --bind 192.168.68.120

# Custom port
python3 Scripts/face_api_server.py --port 9001
```

#### Gallery API Server (Port 8002)
```bash
# Default (localhost only)
python3 Scripts/gallery_api_server.py

# Home network
python3 Scripts/gallery_api_server.py --bind 192.168.68.120

# Custom port
python3 Scripts/gallery_api_server.py --port 9002
```

## How It Works

### Automatic API Detection
The gallery web interface automatically detects the correct API servers based on how you access it:

- Access via `localhost` → API calls go to `localhost:8001` (Face API) and `localhost:8002` (Gallery API)
- Access via `192.168.68.120` → API calls go to `192.168.68.120:8001` (Face API) and `192.168.68.120:8002` (Gallery API)
- Access via any other IP → API calls go to that same IP on ports 8001 and 8002

### Configuration Changes Made
- ✅ Removed hardcoded IP addresses from HTML/JavaScript
- ✅ Added dynamic API URL detection
- ✅ Made gallery server configurable with command line options
- ✅ Made face API server configurable with --bind option
- ✅ Created convenience scripts for common use cases

## Usage Scenarios

### At Home (on home network)
```bash
bash Scripts/start_home_servers.sh
```
Access from any device on your network: `http://192.168.68.120:8000/index-display.html`

### Away from Home (laptop only)
```bash
bash Scripts/start_local_servers.sh
```
Access only on your laptop: `http://localhost:8000/index-display.html`

### Custom Network
```bash
# Start with your specific IP
bash Scripts/start_gallery_server.sh --bind YOUR_IP
python3 Scripts/face_api_server.py --bind YOUR_IP
python3 Scripts/gallery_api_server.py --bind YOUR_IP
```

The gallery will automatically adapt to whatever network configuration you use!