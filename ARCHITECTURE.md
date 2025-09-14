# Photo Management Toolkit - Architecture Overview

## Current System Architecture (Three-Server Design)

The Photo Management Toolkit uses a clean three-server architecture that separates concerns for optimal performance and maintainability.

### Server Components

#### 1. Gallery Web Server (Port 8000)
**Purpose:** Static file serving and web interface hosting
- **Script:** `Scripts/start_gallery_server.sh`
- **Technology:** Python's built-in HTTP server
- **Serves:** HTML, CSS, JavaScript, thumbnails, and image files
- **Key Features:**
  - Fast static file delivery
  - Network configuration support (localhost, home network, custom)
  - No API endpoints - purely serves files

#### 2. Face API Server (Port 8001)
**Purpose:** Face recognition and core photo processing operations
- **Script:** `Scripts/face_api_server.py`
- **Technology:** Python HTTP server with custom BaseAPIHandler
- **Key Responsibilities:**
  - Face detection and recognition data
  - Photo metadata and statistics
  - Gallery creation via intelligent search
  - RAW and video proxy generation
  - Complete photo processing workflows
  - Pick/reject operations and safe file deletion

**Key Endpoints:**
```
GET  /api/faces/{image_id}      - Face detection data
GET  /api/stats                 - System statistics
GET  /api/people               - All known people
POST /api/create-gallery       - Create new galleries
POST /api/process-new-images   - Automated processing
POST /api/assign-face          - Face labeling
POST /api/generate-raw-proxy   - RAW processing
```

#### 3. Gallery API Server (Port 8002)
**Purpose:** Gallery management and file operations
- **Script:** `Scripts/gallery_api_server.py`
- **Technology:** Python HTTP server with BaseAPIHandler
- **Key Responsibilities:**
  - Secure gallery deletion with path validation
  - Gallery list maintenance and rebuilding
  - Pick/reject file management
  - Gallery-specific operations

**Key Endpoints:**
```
GET  /api/load-picks           - Load saved picks
GET  /api/load-rejects         - Load reject list
POST /api/delete-gallery       - Secure gallery deletion
POST /api/rebuild-galleries-list - Refresh gallery index
POST /api/save-picks           - Save photo selections
```

### Shared Infrastructure

#### Base API Handler (`Scripts/api_base.py`)
All API servers inherit from `BaseAPIHandler` which provides:
- **CORS Support** - Browser compatibility
- **Progress Broadcasting** - Real-time status updates via Server-Sent Events
- **JSON Response Handling** - Standardized API responses
- **Database Path Auto-detection** - Works from any directory
- **Security Features** - Path validation and whitelist protection

#### Launch Scripts
- **Local Development:** `Scripts/start_local_servers.sh` - All servers on localhost
- **Home Network:** `Scripts/start_home_servers.sh` - All servers on 192.168.68.120
- **CLI Integration:** `photo_manager.py` option 11 - Start servers with DEVNULL redirection

## Key Design Principles

### 1. Separation of Concerns
- **Web Server:** Pure static file serving
- **Face API:** Complex AI/ML operations and photo processing
- **Gallery API:** File system operations and gallery management

### 2. Security by Design
- **Path Validation:** All file operations validate paths against whitelists
- **Hard Link Galleries:** Virtual collections that don't modify originals
- **Safe Deletion:** Trash-based deletion with preview capabilities
- **Local-First:** No network exposure by default

### 3. Browser Integration
- **Dynamic API Detection:** Web interface automatically detects correct API endpoints
- **Real-Time Updates:** Server-Sent Events provide live progress feedback
- **CORS Enabled:** All APIs work seamlessly with modern browsers
- **Mobile Friendly:** Touch-optimized interface with responsive design

### 4. Development Flexibility
- **Auto-Detection:** Scripts work from main directory or Scripts subdirectory
- **Network Configuration:** Easy switching between localhost and network access
- **Database Location:** Automatic database path resolution
- **Incremental Processing:** Only process changed files

## Data Flow

### Gallery Creation Workflow
1. **User Input:** Web interface command palette or CLI menu
2. **API Call:** Browser sends request to Face API Server (port 8001)
3. **Processing:** Face API searches database and creates hard-link gallery
4. **Response:** Gallery creation status sent back to browser
5. **Refresh:** Gallery list automatically updated

### Gallery Deletion Workflow
1. **User Request:** Gallery deletion from web interface
2. **Security Check:** Gallery API Server validates path against Hard Link Galleries whitelist
3. **Deletion:** Safe removal of gallery directory
4. **Auto-Refresh:** Gallery list automatically rebuilt and updated
5. **Confirmation:** Success status sent to browser

### Face Recognition Workflow
1. **Extraction:** Face API Server processes images to detect faces
2. **Clustering:** AI groups similar faces into people clusters
3. **Labeling:** User assigns names to people via web interface or CLI
4. **Display:** Web interface shows face overlays with names in real-time

## File Organization

```
Ben Photos/
├── Master Photo Library/        # Original photos (never modified)
├── Hard Link Galleries/         # Virtual collections (hard links)
├── RAW Proxies/                # Processed RAW outputs
├── HEIC Proxies/               # Browser-compatible versions
├── thumbnails/                 # Fast preview images
├── JSON/                       # Gallery metadata and picks/rejects
├── Scripts/                    # All server and processing scripts
│   ├── start_local_servers.sh  # Launch all servers locally
│   ├── start_home_servers.sh   # Launch all servers on home network
│   ├── start_gallery_server.sh # Gallery web server
│   ├── face_api_server.py      # Face API server
│   ├── gallery_api_server.py   # Gallery API server
│   └── api_base.py            # Shared API utilities
└── image_metadata.db          # SQLite database (or Scripts/image_metadata.db)
```

## Performance Characteristics

### Scalability
- **Database:** SQLite with proper indexing handles 100k+ photos efficiently
- **Thumbnails:** WebP format provides fast loading with small file sizes
- **Hard Links:** Virtual galleries have zero storage overhead
- **Batch Processing:** All operations support bulk processing with progress updates

### Resource Usage
- **Gallery Web Server:** Minimal CPU, serves static files only
- **Face API Server:** CPU-intensive for face detection, memory for embeddings
- **Gallery API Server:** Minimal resources, handles file system operations
- **Total Memory:** ~500MB typical usage, scales with face database size

### Network Efficiency
- **Local First:** All servers can run localhost-only
- **API Separation:** Allows independent scaling and load balancing
- **Static Optimization:** Web assets served efficiently by dedicated server
- **Real-Time Updates:** Server-Sent Events minimize polling overhead

This architecture provides a robust, scalable, and maintainable foundation for the Photo Management Toolkit while preserving security and user experience.