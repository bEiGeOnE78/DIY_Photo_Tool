# Video Proxy Implementation Plan

## Overview
This document outlines the plan for implementing video proxy support in the Photo Tool, allowing users to select between original videos and proxy versions for both thumbnail display and playback modes.

## Current State Analysis

### Existing Video Infrastructure
- Videos are supported in galleries with thumbnail generation
- Video playback works in single view using HTML5 video elements
- Videos use proxy files in galleries (already converted/copied from master library)
- `isVideoFile()` function detects video extensions
- Thumbnail system can generate WebP thumbnails from video frames

### Current Limitations
- No user control over video proxy selection
- No database tracking of video proxy preferences
- Thumbnails always use generated WebP, not proxy-aware selection
- Single playback mode doesn't respect proxy preferences

## Implementation Plan

### Phase 1: Database Schema Extension

#### 1.1 Extend Image Metadata Table
```sql
-- Add video proxy columns to existing image metadata table
ALTER TABLE image_metadata ADD COLUMN video_proxy_type TEXT DEFAULT 'default';
ALTER TABLE image_metadata ADD COLUMN has_video_proxy BOOLEAN DEFAULT FALSE;
ALTER TABLE image_metadata ADD COLUMN video_proxy_path TEXT;
```

**Proxy Types for Videos:**
- `'default'` - Use the existing gallery video file
- `'compressed'` - Use a smaller, more compressed version
- `'high_quality'` - Use a higher quality proxy (if available)
- `'original'` - Use the original master library video file

#### 1.2 Video Proxy Detection Logic
```javascript
function isVideoProxy(meta) {
  const cleanSrc = (meta.SourceFile || meta.src || meta.FileName).replace(/^\.\//, "");
  return isVideoFile(cleanSrc) ||
         (meta._originalPath && isVideoFile(meta._originalPath));
}
```

### Phase 2: Backend API Extensions

#### 2.1 Video Proxy State API
**Endpoint:** `GET/POST /api/video-proxy-state/{image_id}`

Similar to RAW proxy API but for videos:
```python
def handle_video_proxy_state(self, image_id, method, body=None):
    if method == 'GET':
        # Return current video proxy state
        return {
            'video_proxy_type': row['video_proxy_type'],
            'has_video_proxy': bool(row['has_video_proxy']),
            'video_proxy_path': row['video_proxy_path'],
            'available_proxies': self.get_available_video_proxies(image_id)
        }
    elif method == 'POST':
        # Update video proxy preference
        # Similar to RAW proxy switching logic
```

#### 2.2 Video Thumbnail Generation API
**Endpoint:** `GET /api/video-thumbnail/{image_id}?source=default|compressed|high_quality|original`

Extend existing thumbnail system to generate thumbnails from selected video proxy:
```python
def get_video_proxy_thumbnail(self, image_id, source='default'):
    # Get video proxy path based on source preference
    video_path = self.get_video_proxy_path(image_id, source)
    # Generate thumbnail from video frame using ffmpeg or similar
    # Cache and return thumbnail
```

### Phase 3: Frontend Integration

#### 3.1 Video Proxy Detection in getDisplaySource()
```javascript
async function getDisplaySource(meta, forceTimestamp = false) {
    const originalSrc = meta.SourceFile || meta.src || meta.FileName;
    const cleanSrc = originalSrc.replace(/^\.\//, "");

    // Check for video proxy (similar to RAW proxy logic)
    if (meta._imageId && isVideoProxy(meta)) {
        const proxyState = await getCurrentVideoProxyState(meta._imageId);

        if (proxyState) {
            switch(proxyState.video_proxy_type) {
                case 'compressed':
                    return `Video Proxies/Compressed/${meta._imageId}.mp4`;
                case 'high_quality':
                    return `Video Proxies/HQ/${meta._imageId}.mp4`;
                case 'original':
                    return meta._originalPath;
                default:
                    return cleanSrc; // Use gallery default
            }
        }
    }

    // ... rest of existing logic
}
```

#### 3.2 Video Thumbnail Integration
```javascript
async function getVideoThumbnailSource(meta) {
    if (!isVideoProxy(meta)) {
        return meta._thumbnail; // Use existing thumbnail
    }

    const proxyState = await getCurrentVideoProxyState(meta._imageId);
    if (proxyState) {
        // Request proxy-aware thumbnail from backend
        return `http://${window.location.hostname}:8001/api/video-thumbnail/${meta._imageId}?source=${proxyState.video_proxy_type}`;
    }

    return meta._thumbnail; // Fallback
}
```

#### 3.3 Video Proxy Control UI
Add video proxy controls to sidebar (similar to RAW proxy buttons):
```javascript
function addVideoProxyControls(meta) {
    if (!isVideoProxy(meta)) return;

    const controls = `
        <div class="video-proxy-controls">
            <h4>Video Quality</h4>
            <button onclick="switchVideoProxy(${meta._imageId}, 'original')">Original</button>
            <button onclick="switchVideoProxy(${meta._imageId}, 'high_quality')">High Quality</button>
            <button onclick="switchVideoProxy(${meta._imageId}, 'default')">Standard</button>
            <button onclick="switchVideoProxy(${meta._imageId}, 'compressed')">Compressed</button>
        </div>
    `;
    // Add to sidebar
}
```

### Phase 4: Performance Optimizations

#### 4.1 Caching Strategy
- Cache video proxy states similar to RAW proxy cache
- Pre-generate video thumbnails for common proxy types
- Implement lazy loading for video proxy detection

#### 4.2 Avoid Performance Issues (Lessons from RAW Proxy)
```javascript
// ❌ DON'T: Check video proxy state for every thumbnail
async function getThumbnailSource(meta) {
    if (isVideoFile(cleanSrc)) {
        // Only check by file extension, not original path
        // Keep fast path for non-proxy videos
    }
}

// ✅ DO: Only check video proxy state when needed for display
async function getDisplaySource(meta) {
    if (isVideoProxy(meta)) {
        // Full proxy state check only when displaying
    }
}
```

### Phase 5: Video Proxy Generation Pipeline

#### 5.1 Proxy Generation Scripts
Create background scripts to generate video proxies:
```bash
# scripts/generate_video_proxies.sh
ffmpeg -i "original.mov" -vcodec h264 -acodec aac -b:v 2M "compressed.mp4"
ffmpeg -i "original.mov" -vcodec h264 -acodec aac -b:v 8M "high_quality.mp4"
```

#### 5.2 Proxy Organization
```
Video Proxies/
├── Compressed/
│   ├── 123.mp4
│   └── 124.mp4
├── HQ/
│   ├── 123.mp4
│   └── 124.mp4
└── thumbnails/
    ├── 123_compressed.webp
    ├── 123_hq.webp
    └── 123_original.webp
```

## Key Considerations

### 1. Performance Priorities
- **Fast thumbnail loading:** Only check file extension for video detection in thumbnail grid
- **Accurate display:** Full proxy state checking only when entering single view or playback
- **Cache management:** Video proxy states with same cache invalidation as RAW proxies

### 2. User Experience
- **Seamless switching:** Video proxy changes should update thumbnails and playback immediately
- **Clear indicators:** Show current video quality in UI status
- **Progressive loading:** Load compressed proxy first, upgrade to higher quality if selected

### 3. Storage Management
- **Smart generation:** Only generate proxy types that are actually used
- **Cleanup scripts:** Remove unused video proxies
- **Size monitoring:** Track disk usage of video proxy directories

### 4. Error Handling
- **Fallback chain:** Original → Gallery Default → Error state
- **Network resilience:** Handle proxy file not found gracefully
- **Format compatibility:** Ensure proxy formats work across browsers

## Implementation Sequence

1. **Database schema updates** - Add video proxy columns
2. **Backend API implementation** - Video proxy state and thumbnail APIs
3. **Frontend detection logic** - Extend getDisplaySource() for videos
4. **UI controls** - Add video proxy switching buttons
5. **Thumbnail integration** - Proxy-aware video thumbnails
6. **Performance testing** - Ensure no regression in grid performance
7. **Proxy generation tools** - Scripts to create video proxies
8. **Documentation** - User guide for video proxy features

## Testing Strategy

### Performance Tests
- Grid loading time with mixed video/image galleries
- Proxy switching responsiveness
- Memory usage during video playback

### Functionality Tests
- Proxy state persistence across page reloads
- Thumbnail accuracy for different proxy types
- Playback quality matches selected proxy

### Edge Cases
- Videos without available proxies
- Network interruptions during proxy loading
- Very large video files with multiple proxy options

This plan provides a comprehensive roadmap for implementing video proxy support while avoiding the performance pitfalls encountered during RAW proxy implementation.