# Photo Management System

A comprehensive photo management toolkit with AI-powered face recognition, web-based galleries, intelligent search, and automated processing workflows.

## Overview

This system provides a complete solution for:
1. **Automated photo processing** - Metadata extraction, face detection, thumbnail generation
2. **Intelligent search galleries** - Create collections using natural language queries
3. **Web-based photo management** - Browser interface with keyboard shortcuts and command palette
4. **AI face recognition** - Automatic people detection and clustering
5. **RAW file processing** - Custom proxy generation with RawTherapee
6. **Safe file operations** - Hard links, proxies, and trash-based deletion

## Quick Start

### Initial Setup
```bash
# 1. Create database and extract metadata
python photo_manager.py
# Choose option 2: Setup Database
# Choose option 1: Extract Metadata

# 2. Start servers
python photo_manager.py  
# Choose option 8: Start Gallery Server

# 3. Open web interface
# Navigate to: http://localhost:8000/index-display.html
```

### Create Your First Gallery
1. Press `/` to open command palette
2. Type "gallery" and press Enter
3. Enter search like: "2024 fuji" or "vacation photos"
4. View your new gallery in the web interface

## Core Components

### 1. Photo Manager (`photo_manager.py`)
Central command-line interface for all photo management operations.

**Main Options:**
- **Extract Metadata** - Process photos and populate database
- **Setup Database** - Initialize SQLite schema  
- **Create Virtual Gallery** - Make new photo collections
- **Gallery Management** - Rebuild, organize, and maintain galleries
- **Start Gallery Server** - Launch web interface
- **Process New Images** - Complete automated workflow for new photos
- **Face Recognition** - AI-powered people detection and labeling

### 2. Web Gallery Interface (`index-display.html`)
Modern browser-based photo viewer with advanced features and secure gallery management.

**Key Features:**
- **Command Palette** - Press `/` for spotlight-style commands
- **Thumbnail Grid** - Fast lazy-loading with selection support
- **Full-Screen Viewer** - Multiple zoom modes with smooth navigation
- **Face Detection Overlay** - See detected people with names
- **Metadata Sidebar** - Complete EXIF data and GPS links
- **Pick/Reject System** - Mark photos for organization
- **Gallery Management** - Secure web-based gallery deletion with automatic refresh
- **Touch Support** - Mobile-friendly interface
- **Multi-API Integration** - Seamlessly uses all three servers

**Keyboard Shortcuts:**
- `/` - Open command palette
- `Arrow keys` - Navigate images
- `Space` - Toggle zoom modes
- `M` - Toggle metadata sidebar
- `O` - Toggle face detection
- `P` - Mark as pick
- `X` - Mark as reject
- `G` - Gallery selector
- `L` - Toggle picks list
- `Q` - Exit/clear selection

### 3. Smart Gallery Creation (`Scripts/gallery_create_search.py`)
Create photo collections using intelligent search queries.

**Search Examples:**
```bash
# People and dates
"John 2024"          # Photos of John from 2024
"wedding guests"     # Wedding photos with multiple people
"family Christmas"   # Family photos from Christmas

# Camera and lens combinations  
"fuji 35mm"         # Photos taken with Fuji 35mm lens
"canon macro"       # Canon macro photography
"sony a7c"          # Photos from Sony A7C camera

# Dates and locations
"2024-06"           # June 2024 photos
"2023-12-25"        # Christmas Day 2023 photos
"vacation 2024"     # Vacation photos from 2024

# Technical specifications
"f2.8 iso800"       # Photos at f/2.8, ISO 800
"35mm f1.4"         # 35mm lens at f/1.4 aperture
```

**Word Boundary Matching:**
- `"john"` matches: "John", "John Smith", "Mary John"
- `"john"` excludes: "Johnson", "Jonathan" (partial matches)

### 4. Face Recognition System (`Scripts/face_recognizer_insightface.py`)
AI-powered face detection and people identification.

**Workflow:**
```bash
# 1. Extract faces from all photos
python Scripts/face_recognizer_insightface.py --extract

# 2. Cluster faces into people groups
python Scripts/face_recognizer_insightface.py --cluster

# 3. Label important people
python Scripts/face_recognizer_insightface.py --label 5 "John Smith"

# 4. View statistics
python Scripts/face_recognizer_insightface.py --stats
```

**Advanced Features:**
- **InsightFace AI** - High-accuracy face detection
- **DBSCAN Clustering** - Automatic people grouping
- **Iterative Improvement** - Re-cluster after labeling
- **Confidence Scoring** - Quality-based face filtering

### 5. Three-Server Architecture

The system now uses a clean three-server architecture for optimal separation of concerns:

#### Gallery Web Server (Port 8000)
- **Static File Serving** - HTML, CSS, JavaScript, and thumbnails
- **Main Interface** - Primary web gallery interface
- **Launch Command** - `Scripts/start_gallery_server.sh`

#### Face API Server (Port 8001) - `Scripts/face_api_server.py`
**Face Recognition and Core Operations:**
- `GET /api/faces/{image_id}` - Face detection data
- `GET /api/stats` - System statistics
- `GET /api/people` - All known people
- `POST /api/create-gallery` - Create new galleries
- `POST /api/process-new-images` - Automated processing workflow
- `POST /api/save-picks` - Save photo selections
- `POST /api/delete-rejects` - Safe file deletion
- `POST /api/assign-face` - Face labeling operations

#### Gallery API Server (Port 8002) - `Scripts/gallery_api_server.py`
**Gallery Management Operations:**
- `GET /api/load-picks` - Load saved picks
- `GET /api/load-rejects` - Load reject list
- `POST /api/delete-gallery` - Secure gallery deletion
- `POST /api/rebuild-galleries-list` - Refresh gallery index
- `POST /api/save-picks` - Save photo selections
- `POST /api/save-rejects` - Save reject list

**Shared Features:**
- **CORS Support** - Browser-compatible APIs
- **Real-time Progress** - Server-sent events for status updates
- **Security** - Path validation and whitelist protection
- **Auto-detection** - Database and JSON path resolution

### 6. RAW Processing (`Scripts/generate_raw_proxies.py`)
Advanced RAW file processing with custom presets.

**Features:**
- **RawTherapee Integration** - Professional RAW processing
- **Camera-Specific Presets** - Optimized for different cameras
- **Film Simulation** - Fuji film modes (Provia, Velvia, Acros, etc.)
- **Proxy Generation** - Web-optimized JPEG outputs
- **Batch Processing** - Handle large RAW collections

**Supported Cameras:**
- Fuji X-series (XE4, XT3, XT4, etc.)
- Sony A-series (A7C, A6500, etc.)
- Panasonic Lumix (LX100, etc.)

### 7. Command Palette System
Spotlight-style command interface accessible from web gallery.

**Available Commands:**
- **Create Gallery** - Smart search-based gallery creation
- **Process New Images** - Complete automated workflow
- **Regenerate RAW Picks** - Process selected RAW files
- **Delete Rejected Images** - Safe bulk deletion with preview
- **Stats Dashboard** - Comprehensive database analytics
- **Rebuild Gallery JSON** - Refresh current gallery data
- **Rebuild Galleries List** - Update main gallery index

**Usage:**
1. Press `/` in web gallery
2. Type command name or keyword
3. Follow prompts for parameters
4. Monitor progress in real-time

## Automated Workflows

### New Image Processing
Complete workflow for newly added photos:

```bash
# Via command line
python photo_manager.py
# Choose option 9: Process New Images

# Via web interface  
# Press `/` → "process new" → Enter
```

**Processing Steps:**
1. **Extract Metadata** - EXIF data, camera settings, GPS
2. **Generate Thumbnails** - Fast web-optimized previews  
3. **Create HEIC Proxies** - Browser-compatible versions
4. **Generate RAW Proxies** - Processed RAW file outputs
5. **Detect Faces** - AI-powered face recognition
6. **Cluster Faces** - Add to existing people groups

### Gallery Maintenance
Keep galleries updated and optimized:

```bash
# Rebuild main gallery list
python Scripts/rebuild_galleries_json.py

# Update specific gallery
bash Scripts/gallery_rebuild_json.sh "Hard Link Galleries/Gallery Name"

# Clean up orphaned files
python Scripts/cleanup_database.py --interactive
```

## File Organization

### Directory Structure
```
Ben Photos/
├── Master Photo Library/        # Original photos (never modify)
├── Hard Link Galleries/         # Virtual collections
├── RAW Proxies/                # Processed RAW outputs  
├── HEIC Proxies/               # Browser-compatible versions
├── thumbnails/                 # Fast preview images
├── JSON/                       # Gallery metadata
├── Scripts/                    # Processing tools
└── RawTherapee Presets/        # RAW processing presets
```

### File Types
**Input Formats:**
- **Photos:** JPG, HEIC, PNG, TIFF
- **RAW:** RAF (Fuji), ARW (Sony), CR2/CR3 (Canon), NEF (Nikon), RW2 (Panasonic)
- **Video:** MOV, MP4, AVI, MKV

**Generated Formats:**
- **Thumbnails:** WebP (fast loading)
- **Proxies:** JPG (web-compatible)
- **Metadata:** JSON (searchable)

## Advanced Features

### Smart Search Syntax
Create precise galleries with natural language:

**People Searches:**
- `"John"` - Exact name match
- `"John Smith"` - Full name
- `"wedding guests"` - Event-based grouping

**Date Formats:**
- `"2024"` - Entire year
- `"2024-06"` - Specific month  
- `"2024-06-15"` - Exact date
- `"2023-2024"` - Date range

**Camera/Lens Combinations:**
- `"fuji 35mm"` - Fuji camera + 35mm lens
- `"sony macro"` - Sony camera + macro lens
- `"canon f2.8"` - Canon camera + f/2.8 aperture

**Technical Parameters:**
- `"iso800"` - Specific ISO setting
- `"f1.4"` - Aperture value
- `"35mm f2.8 iso400"` - Multiple criteria

### RAW Workflow Integration
Seamless RAW file handling:

**Automatic Detection:**
- RAW files auto-detected during metadata extraction
- Adjacent JPEG companions identified
- Proxy generation prioritizes RAW sources

**Custom Processing:**
- Camera-specific presets applied automatically
- Film simulation modes for supported cameras
- Quality settings optimized for web viewing

**Web Interface:**
- Toggle between RAW proxy and original JPEG
- Generate custom RAW proxy with different settings
- Real-time preview of processing options

### Face Recognition Optimization
Maximize accuracy and performance:

**Initial Setup:**
```bash
# Process all images (one-time, may take hours)
python Scripts/face_recognizer_insightface.py --extract

# Initial clustering
python Scripts/face_recognizer_insightface.py --cluster --eps 0.38

# Create overview for labeling
python Scripts/gallery_create_search.py --face-samples --name "Face Samples"
```

**Iterative Improvement:**
```bash
# Label main people
python Scripts/face_recognizer_insightface.py --label 5 "John Smith"

# Clean up and re-cluster
python Scripts/face_recognizer_insightface.py --delete-unconfirmed
python Scripts/face_recognizer_insightface.py --cluster-new-loop
```

**Clustering Parameters:**
- `--eps 0.38` - Clustering sensitivity (lower = stricter)
- `--min-samples 16` - Minimum faces to form a person
- `--confidence 0.7` - Face detection confidence threshold

## Database Schema

### Core Tables
- **images** - Photo metadata, EXIF data, file paths
- **faces** - Detected face coordinates and embeddings  
- **persons** - People groups with names and confirmation
- **tags** - User-defined photo tags
- **collections** - Gallery definitions and metadata

### Performance Features
- **Indexed searches** - Fast queries on dates, cameras, people
- **Incremental updates** - Only process changed files
- **Batch operations** - Efficient bulk processing
- **Hard link resolution** - Automatic duplicate detection

## API Reference

### Three-Server API Architecture

#### Gallery Web Server (Port 8000)
Start server: `Scripts/start_gallery_server.sh`
- Static file serving (HTML, CSS, JS, thumbnails)
- No API endpoints - serves web interface files

#### Face API Server (Port 8001)
Start server: `python Scripts/face_api_server.py --port 8001`

**GET Endpoints:**
```
/api/faces/{image_id}     # Face detection data
/api/stats                # System statistics
/api/people              # All known people
/api/image-metadata/{id} # Complete image metadata
/api/presets             # Available RAW presets
/api/progress-log        # Real-time progress updates
```

**POST Endpoints:**
```
/api/create-gallery      # Create new gallery
/api/process-new-images  # Automated processing
/api/save-picks          # Save photo selections
/api/save-rejects        # Save rejection list
/api/delete-rejects      # Execute safe deletion
/api/assign-face         # Face labeling operations
/api/generate-raw-proxy  # RAW processing
```

#### Gallery API Server (Port 8002)
Start server: `python Scripts/gallery_api_server.py --port 8002`

**GET Endpoints:**
```
/api/load-picks          # Load saved picks
/api/load-rejects        # Load reject list
/api/progress-stream     # Server-sent events
```

**POST Endpoints:**
```
/api/delete-gallery      # Secure gallery deletion
/api/rebuild-galleries-list # Refresh gallery index
/api/save-picks          # Save photo selections
/api/save-rejects        # Save reject list
```

### Web Interface Integration
```javascript
// Create gallery via Face API Server (port 8001)
fetch(`http://${window.location.hostname}:8001/api/create-gallery`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    search_string: 'John 2024 fuji',
    gallery_name: 'John 2024 Fuji Photos'
  })
});

// Get face data for image from Face API Server
fetch(`http://${window.location.hostname}:8001/api/faces/${imageId}`)
  .then(r => r.json())
  .then(faces => {
    // Display face overlays
  });

// Delete gallery via Gallery API Server (port 8002)
fetch(`http://${window.location.hostname}:8002/api/delete-gallery`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    gallery_path: galleryPath
  })
});

// Load picks from Gallery API Server
fetch(`http://${window.location.hostname}:8002/api/load-picks`)
  .then(r => r.json())
  .then(picks => {
    // Process saved picks
  });
```

## Troubleshooting

### Common Issues

**Gallery creation fails:**
- Check database exists: `ls Scripts/image_metadata.db`
- Verify metadata extracted: `python Scripts/extract_metadata.py --help`
- Restart Face API server

**Face detection not working:**
- Install dependencies: `pip install insightface scikit-learn`
- Extract faces: `python Scripts/face_recognizer_insightface.py --extract`
- Start API server: `python Scripts/face_api_server.py --port 8001`

**RAW processing fails:**
- Install RawTherapee: Download from rawtherapee.com
- Check presets exist: `ls "RawTherapee Presets/"`
- Verify file permissions on RAW files

**Web interface not loading:**
- Check server running: `lsof -i :8000`
- Try different port: `python -m http.server 8080`
- Clear browser cache: Ctrl+F5 / Cmd+Shift+R

### Performance Optimization

**Large Libraries (>50k photos):**
- Use `--batch-size 1000` for metadata extraction
- Run face detection overnight
- Enable database query optimization
- Consider SSD storage for database

**Memory Management:**
- Monitor RAM usage during face processing
- Use `--max-workers 4` to limit concurrent processing
- Clear browser cache regularly for web interface

**Network Performance:**
- Use local servers only (avoid network drives)
- Enable HTTP/2 in server configuration
- Optimize thumbnail size for mobile devices

## Acknowledgments

- **InsightFace** - AI face recognition models
- **RawTherapee** - RAW photo processing engine
- **ExifTool** - Metadata extraction utility
- **SQLite** - Embedded database engine