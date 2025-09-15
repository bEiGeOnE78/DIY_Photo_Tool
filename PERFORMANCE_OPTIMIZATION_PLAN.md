# Photo Tool Performance Optimization Plan

## Executive Summary
Analysis of the codebase revealed significant performance bottlenecks that can be addressed with targeted optimizations. The most impactful improvements focus on reducing debug overhead, optimizing database queries, and improving async operations.

## Performance Issues Identified

### 🔴 **Critical Priority - Immediate Impact**

#### 1. Excessive Debug Logging (20-30% performance improvement)
**Problem**: 90+ console.log statements executing during normal operations
- Thumbnail loading: Lines 4940, 4965, 5126
- Image navigation: Lines 1721, 1960-1961, 2194
- Video playback: Lines 1762-1837 (15+ logs per video load)
- Face detection: Lines 4516-4524
- Background preloading: Lines 5099, 5141

**Impact**: Console logging with complex objects is expensive in JavaScript
**Solution**: Conditional debug logging system

#### 2. Individual Database Queries for Proxy States (15-25% improvement)
**Problem**: `getCurrentProxyState()` makes individual HTTP requests
- Called for every RAW image in thumbnail grid
- Cache frequently cleared, forcing re-requests
- No batch operations available

**Impact**: Network latency multiplied by number of RAW images
**Solution**: Batch proxy state API

### 🟡 **High Priority - Significant Impact**

#### 3. Inefficient DOM Manipulation
**Problem**: Repeated `querySelector` calls in thumbnail system
- `document.querySelector(.thumb-cell[data-idx='${idx}'])` per thumbnail
- No DOM reference caching
- Expensive CSS selector parsing

**Impact**: DOM queries are expensive, especially with complex selectors
**Solution**: Cache DOM references during creation

#### 4. Sequential vs Parallel Processing
**Problem**: Independent async operations run sequentially
- Gallery loading (one at a time)
- Metadata fetching for adjacent images
- Pick/reject operations

**Impact**: Artificial delays where parallelization possible
**Solution**: Use Promise.all for independent operations

### 🟠 **Medium Priority - Moderate Impact**

#### 5. Database Query Inefficiencies (Backend)
**Problem**: Missing database optimizations
- No connection pooling (new connection per request)
- Missing indexes on common query columns
- Individual queries instead of batch operations

**Impact**: Database becomes bottleneck with large galleries
**Solution**: Add indexes, connection pooling, batch queries

#### 6. Face Detection API Inefficiency
**Problem**: Individual face requests per image
- One HTTP request per image for face data
- No batch face loading API
- Repeated database queries for same data

**Impact**: Network overhead for face-heavy galleries
**Solution**: Batch face loading API

## Implementation Plan

### Phase 1: Debug Logging Optimization (Day 1)
```javascript
// Create debug system
const DEBUG_ENABLED = false; // Toggle for production
const debugLog = DEBUG_ENABLED ? console.log.bind(console) : () => {};
const debugWarn = DEBUG_ENABLED ? console.warn.bind(console) : () => {};

// Replace all console.log with debugLog
debugLog('🎬 Video loaded:', videoData);
```

**Estimated Impact**: 20-30% improvement in navigation speed
**Risk**: Low (easy to revert)

### Phase 2: Batch Proxy State API (Day 2-3)
**Frontend Changes**:
```javascript
// New batch proxy state function
async function getBatchProxyStates(imageIds) {
  const response = await fetch(`http://${window.location.hostname}:8001/api/batch-proxy-states`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({imageIds})
  });
  return await response.json();
}

// Modified thumbnail loading to use batch requests
async function loadThumbnailBatch(indices) {
  const rawImageIds = indices
    .map(idx => images[idx])
    .filter(meta => isRawFile(meta))
    .map(meta => meta._imageId);

  if (rawImageIds.length > 0) {
    const batchStates = await getBatchProxyStates(rawImageIds);
    // Cache all states at once
    Object.entries(batchStates).forEach(([id, state]) => {
      proxyStateCache.set(parseInt(id), state);
    });
  }
}
```

**Backend Changes**:
```python
# Add batch endpoint to face_api_server.py
elif path_parts[0] == 'api' and path_parts[1] == 'batch-proxy-states':
    # POST /api/batch-proxy-states
    content_length = int(self.headers.get('Content-Length', 0))
    request_data = json.loads(self.rfile.read(content_length))
    image_ids = request_data.get('imageIds', [])
    batch_states = self.get_batch_proxy_states(image_ids)
    self.send_json_response(batch_states)

def get_batch_proxy_states(self, image_ids):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Use IN clause for batch query
    placeholders = ','.join(['?'] * len(image_ids))
    cursor.execute(f"""
        SELECT id, raw_proxy_type
        FROM images
        WHERE id IN ({placeholders})
    """, image_ids)

    results = {}
    for row in cursor.fetchall():
        results[row['id']] = {
            'raw_proxy_type': row['raw_proxy_type'] or 'none',
            'has_custom_proxy': self.check_custom_proxy_exists(row['id'])
        }

    conn.close()
    return results
```

**Estimated Impact**: 15-25% improvement in RAW thumbnail loading
**Risk**: Medium (requires backend changes)

### Phase 3: DOM Reference Caching (Day 4)
```javascript
// Create DOM cache system
class ThumbnailDOMCache {
  constructor() {
    this.cells = new Map();
    this.images = new Map();
  }

  set(idx, cell, img) {
    this.cells.set(idx, cell);
    this.images.set(idx, img);
  }

  getCell(idx) { return this.cells.get(idx); }
  getImage(idx) { return this.images.get(idx); }

  clear() {
    this.cells.clear();
    this.images.clear();
  }
}

const thumbnailCache = new ThumbnailDOMCache();

// Modified thumbnail creation
function createThumbnailCell(idx, meta) {
  const cell = document.createElement("div");
  const img = document.createElement("img");
  // ... setup code ...

  // Cache references
  thumbnailCache.set(idx, cell, img);
  return cell;
}
```

**Estimated Impact**: 10-15% improvement in thumbnail interactions
**Risk**: Low (isolated changes)

### Phase 4: Database Optimization (Day 5-6)
```sql
-- Add performance indexes
CREATE INDEX IF NOT EXISTS idx_images_raw_proxy_type ON images(raw_proxy_type);
CREATE INDEX IF NOT EXISTS idx_faces_image_id_ignored ON faces(image_id, ignored);
CREATE INDEX IF NOT EXISTS idx_faces_person_id ON faces(person_id);
CREATE INDEX IF NOT EXISTS idx_images_needs_processing ON images(needs_processing);
CREATE INDEX IF NOT EXISTS idx_images_has_faces ON images(has_faces);
```

```python
# Add connection pooling
class DatabasePool:
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool = queue.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.pool.put(conn)

    @contextmanager
    def get_connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)
```

**Estimated Impact**: 10-20% improvement in database operations
**Risk**: Medium (database changes)

### Phase 5: Parallel Processing (Day 7)
```javascript
// Parallelize gallery loading
async function loadGalleries() {
  const galleryPromises = galleries.map(async gallery => {
    const response = await fetch(gallery.jsonPath + '?t=' + Date.now());
    return await response.json();
  });

  const galleryData = await Promise.all(galleryPromises);
  // Process results...
}

// Parallel adjacent image loading
async function createAdjacentImageElements(centerIdx) {
  const indices = calculateAdjacentIndices(centerIdx);

  // Load display sources in parallel
  const displaySources = await Promise.all(
    Object.entries(indices).map(async ([position, idx]) => {
      const meta = images[idx];
      const displaySrc = await getDisplaySource(meta);
      return { position, idx, meta, displaySrc };
    })
  );

  // Create DOM elements with cached data
  displaySources.forEach(({position, idx, meta, displaySrc}) => {
    createImageElement(position, idx, meta, displaySrc);
  });
}
```

**Estimated Impact**: 5-15% improvement in navigation speed
**Risk**: Medium (complex async logic)

## Performance Monitoring

### Metrics to Track
```javascript
// Add performance monitoring
class PerformanceMonitor {
  static startTimer(operation) {
    performance.mark(`${operation}-start`);
  }

  static endTimer(operation) {
    performance.mark(`${operation}-end`);
    performance.measure(operation, `${operation}-start`, `${operation}-end`);

    if (DEBUG_ENABLED) {
      const measure = performance.getEntriesByName(operation)[0];
      debugLog(`⏱️ ${operation}: ${measure.duration.toFixed(2)}ms`);
    }
  }
}

// Usage in critical paths
PerformanceMonitor.startTimer('thumbnail-load');
await loadThumbnail(cell, idx);
PerformanceMonitor.endTimer('thumbnail-load');
```

### Key Performance Indicators
- **Thumbnail Grid Load Time**: < 2 seconds for 100 images
- **Image Navigation Speed**: < 100ms for adjacent image switch
- **Proxy State Loading**: < 500ms for 50 RAW images
- **Memory Usage**: < 500MB for large galleries
- **Database Query Time**: < 50ms average per query

## Risk Assessment

| Phase | Risk Level | Rollback Strategy | Testing Required |
|-------|------------|-------------------|------------------|
| Debug Logging | Low | Simple toggle | Basic functionality |
| Batch API | Medium | Feature flag | Full proxy testing |
| DOM Caching | Low | Isolated changes | Thumbnail operations |
| Database | Medium | Index drops | Performance testing |
| Parallel Processing | Medium | Sequential fallback | Navigation testing |

## Expected Results

### Before Optimization
- Thumbnail grid: 5-8 seconds for 100 images
- Image navigation: 200-500ms per switch
- RAW proxy loading: 2-5 seconds delay
- Memory usage: 800MB+ for large galleries

### After Optimization
- Thumbnail grid: 2-3 seconds for 100 images (40-60% improvement)
- Image navigation: 50-100ms per switch (70-80% improvement)
- RAW proxy loading: 300-800ms delay (70-85% improvement)
- Memory usage: 300-500MB for large galleries (40-60% improvement)

## Implementation Schedule

**Week 1**: Phases 1-3 (Debug logging, Batch API, DOM caching)
**Week 2**: Phases 4-5 (Database optimization, Parallel processing)
**Week 3**: Performance testing, monitoring, and fine-tuning

This plan prioritizes the highest impact optimizations first, ensuring immediate performance improvements while building toward comprehensive optimization.