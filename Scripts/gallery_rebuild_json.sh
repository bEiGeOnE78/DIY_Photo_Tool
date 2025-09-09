#!/bin/bash
set -e

# Interactive folder selection (same as original)
if [[ -n "$1" ]]; then
  # Use command line argument if provided
  SRC_DIR="$1"
else
  # Interactive selection from Hard Link Galleries
  echo "Select a gallery folder:"
  
  # Check if Hard Link Galleries exists
  if [[ -d "Hard Link Galleries" ]]; then
    # Get list of folders in Hard Link Galleries
    folders=()
    while IFS= read -r -d '' folder; do
      folders+=("$(basename "$folder")")
    done < <(find "Hard Link Galleries" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
    
    # Add option for custom path
    folders+=("Other (specify path)")
    
    if [[ ${#folders[@]} -eq 0 ]]; then
      echo "No folders found in Hard Link Galleries"
      read -erp "Enter image directory path: " SRC_DIR
    else
      select folder in "${folders[@]}"; do
        if [[ -n "$folder" ]]; then
          if [[ "$folder" == "Other (specify path)" ]]; then
            read -erp "Enter image directory path: " SRC_DIR
          else
            SRC_DIR="Hard Link Galleries/$folder"
          fi
          break
        fi
      done
    fi
  else
    echo "Hard Link Galleries folder not found"
    read -erp "Enter image directory path: " SRC_DIR
  fi
fi

if [[ -z "$SRC_DIR" ]]; then
  echo "No directory specified"
  exit 1
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Directory not found: $SRC_DIR"
  exit 1
fi

SRC_DIR="$(cd "$SRC_DIR"; pwd)"
JSON_FILE="$SRC_DIR/image_data.json"

# Check if JSON already exists and notify user
if [[ -f "$JSON_FILE" ]]; then
  echo "Gallery JSON already exists: $JSON_FILE"
  echo "Overwriting existing file..."
fi

# Auto-detect database location
if [[ -f "image_metadata.db" ]]; then
  DB_FILE="image_metadata.db"
elif [[ -f "Scripts/image_metadata.db" ]]; then
  DB_FILE="Scripts/image_metadata.db"
else
  echo "❌ Database not found: tried image_metadata.db and Scripts/image_metadata.db"
  echo "Run: python3 extract_metadata.py \"Master Photo Library\" first"
  exit 1
fi

echo "🚀 Generating fast gallery for: $SRC_DIR"

# Get image files in directory
EXTS="-iname *.jpg -o -iname *.jpeg -o -iname *.heic -o -iname *.png -o -iname *.mp4 -o -iname *.mov -o -iname *.avi -o -iname *.mkv -o -iname *.webm -o -iname *.m4v"

# Create temporary file list
temp_files=$(mktemp)
find "$SRC_DIR" -type f \( $EXTS \) | sort > "$temp_files"

# Use Python to generate JSON from database with optimization
python3 << EOF
import sqlite3
import json
import os
from pathlib import Path

# Read file list
with open('$temp_files', 'r') as f:
    file_paths = [line.strip() for line in f.readlines()]

# Connect to database
conn = sqlite3.connect('$DB_FILE')
conn.row_factory = sqlite3.Row

def get_thumbnail_url(image_id):
    """Generate thumbnail URL for an image ID."""
    return f"thumbnails/{image_id}.webp"

# Try to load existing JSON to get image_id mappings for faster lookup
existing_image_ids = {}
json_file_path = '$JSON_FILE'

print("🚀 Optimized gallery rebuild: checking for existing JSON...")

if os.path.exists(json_file_path):
    try:
        with open(json_file_path, 'r') as f:
            existing_data = json.load(f)
        
        print(f"📄 Found existing JSON with {len(existing_data)} entries")
        
        # Build filename -> image_id mapping from existing JSON
        for entry in existing_data:
            if '_imageId' in entry and 'SourceFile' in entry:
                # Extract actual filename from SourceFile path
                source_file = entry['SourceFile']
                filename = os.path.basename(source_file)
                image_id = entry['_imageId']
                existing_image_ids[filename] = image_id
        
        print(f"📋 Mapped {len(existing_image_ids)} filenames to image IDs")
        
    except Exception as e:
        print(f"⚠️ Could not read existing JSON: {e}")
        existing_image_ids = {}
else:
    print("📄 No existing JSON found, will use slower method")

gallery_data = []

# Collect image IDs and filenames for batch processing
image_ids_to_fetch = []
filename_to_rel_path = {}

for i, file_path in enumerate(file_paths):
    # Get relative path for the gallery display
    rel_path = os.path.relpath(file_path, '.')
    filename = os.path.basename(file_path)
    filename_to_rel_path[filename] = rel_path
    
    # Try to find image_id from existing JSON first (fast path)
    if filename in existing_image_ids:
        image_id = existing_image_ids[filename]
        image_ids_to_fetch.append((image_id, filename, rel_path))
    else:
        # Mark for slow path processing
        image_ids_to_fetch.append((None, filename, rel_path))

print(f"⚡ Fast path: {len([x for x in image_ids_to_fetch if x[0] is not None])} files")
print(f"🐌 Slow path: {len([x for x in image_ids_to_fetch if x[0] is None])} files")

# Batch fetch metadata for images with known IDs (fast path)
if any(x[0] is not None for x in image_ids_to_fetch):
    known_ids = [x[0] for x in image_ids_to_fetch if x[0] is not None]
    placeholders = ','.join(['?' for _ in known_ids])
    
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT * FROM images WHERE id IN ({placeholders})
    """, known_ids)
    
    # Build image_id -> row mapping
    rows_by_id = {}
    for row in cursor.fetchall():
        rows_by_id[row['id']] = row
    
    print(f"📊 Retrieved {len(rows_by_id)} metadata records from database")

# Process all files
for image_id, filename, rel_path in image_ids_to_fetch:
    if image_id is not None and image_id in rows_by_id:
        # Fast path: use pre-fetched metadata
        row = rows_by_id[image_id]
    else:
        # Slow path: fallback to original samefile lookup
        file_path = os.path.join('$SRC_DIR', filename)
        
        # Use find -samefile to locate the original file
        try:
            import subprocess
            result = subprocess.run([
                'find', 'Master Photo Library', '-samefile', file_path
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                original_path = result.stdout.strip().split('\n')[0]
            else:
                original_path = file_path
        except:
            original_path = file_path
        
        # Query database for metadata using the original path
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM images WHERE path = ?", (original_path,))
        row = cursor.fetchone()
    
    if row:
        # Determine correct hard link source using same logic as gallery creation
        def get_hard_link_source(row):
            """Determine the correct hard link source for a file, handling RAW files."""
            original_path = row['path']
            try:
                raw_proxy_type = row['raw_proxy_type']
            except (KeyError, IndexError):
                raw_proxy_type = None
            image_id = row['id']
            
            # For RAW files, determine the correct source
            if raw_proxy_type == 'custom_generated':
                # Use the generated proxy from RAW Proxies folder
                proxy_path = f"RAW Proxies/{image_id}.jpg"
                if os.path.exists(proxy_path):
                    return proxy_path
                else:
                    print(f"   ⚠️ Custom proxy not found for {row['filename']}: {proxy_path}")
                    return None
            elif raw_proxy_type == 'original_jpg':
                # Use the adjacent JPG file
                original_path_obj = Path(original_path)
                for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                    adjacent_jpg = original_path_obj.with_suffix(ext)
                    if adjacent_jpg.exists():
                        return str(adjacent_jpg)
                print(f"   ⚠️ Adjacent JPG not found for {row['filename']}")
                return None
            else:
                # Check if this is a RAW file that needs adjacent JPG detection
                original_path_obj = Path(original_path)
                file_ext = original_path_obj.suffix.lower()
                
                # List of RAW file extensions
                raw_extensions = {'.cr2', '.nef', '.arw', '.dng', '.raf', '.rw2', '.orf', '.srw', '.x3f', '.3fr'}
                
                if file_ext in raw_extensions:
                    # Try to find adjacent JPG first
                    for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                        adjacent_jpg = original_path_obj.with_suffix(ext)
                        if adjacent_jpg.exists():
                            return str(adjacent_jpg)
                    
                    # If no adjacent JPG found, skip this RAW file
                    print(f"   ⏭️ Skipping RAW file without adjacent JPG: {row['filename']}")
                    return None
                else:
                    # Regular file (JPG, PNG, HEIC, etc.) - use original
                    return original_path
        
        # Get the correct source file path
        source_path = get_hard_link_source(row)
        
        if source_path:
            # Use the source filename for the gallery
            source_filename = os.path.basename(source_path)
            
            # Create JSON object matching exiftool format
            obj = {
                'SourceFile': rel_path,  # Use gallery path for display
                'FileName': filename,  # Use the gallery filename
                'FileType': row['file_format'] or Path(rel_path).suffix[1:].upper(),
                '_imageId': row['id'],  # Add image ID for face detection
                '_hasFaces': row['has_faces'] or 0,  # Add face count
                '_originalPath': row['path'],  # Store original path for reference
                '_thumbnail': get_thumbnail_url(row['id'])
            }
            
            # Add image dimensions if available
            if row['width'] and row['height']:
                obj['ImageWidth'] = row['width']
                obj['ImageHeight'] = row['height']
        else:
            # Skip files that don't have valid sources
            print(f"   ⏭️ Skipping {filename} - no valid source found")
            continue
        
        # Add EXIF data if available
        if row['date_original']:
            obj['DateTimeOriginal'] = row['date_original']
        if row['camera_make']:
            obj['Make'] = row['camera_make']
        if row['camera_model']:
            obj['Model'] = row['camera_model']
        if row['lens_model']:
            obj['LensModel'] = row['lens_model']
        if row['shutter_speed']:
            obj['ExposureTime'] = row['shutter_speed']
        if row['aperture']:
            obj['FNumber'] = row['aperture']
        if row['iso']:
            obj['ISO'] = row['iso']
        if row['exposure_compensation']:
            obj['ExposureCompensation'] = row['exposure_compensation']
        if row['focal_length']:
            obj['FocalLength'] = row['focal_length']
        if row['focal_length_35mm']:
            obj['FocalLengthIn35mmFormat'] = row['focal_length_35mm']
        if row['film_mode']:
            obj['FilmMode'] = row['film_mode']
        if row['gps_latitude'] and row['gps_longitude']:
            obj['GPSLatitude'] = row['gps_latitude']
            obj['GPSLongitude'] = row['gps_longitude']
            
        gallery_data.append(obj)
    else:
        # Fallback for files not in database
        obj = {
            'SourceFile': rel_path,
            'FileName': filename,
            'FileType': Path(rel_path).suffix[1:].upper(),
            '_note': f'No database entry found for {filename}'
        }
        gallery_data.append(obj)
        print(f"⚠️ Database lookup failed for {filename}")

conn.close()

# Sort gallery data by DateTimeOriginal (most recent first)
from datetime import datetime

def get_sort_date(item):
    date_str = item.get('DateTimeOriginal', '')
    if date_str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except:
            return datetime.min
    return datetime.min

gallery_data.sort(key=get_sort_date, reverse=False)
print(f"📅 Sorted by date (oldest first): {len(gallery_data)} images")

# Write JSON file
with open('$JSON_FILE', 'w') as f:
    json.dump(gallery_data, f, indent=2, default=str)

print(f"✅ Gallery JSON generated: $JSON_FILE")
print(f"📊 {len(gallery_data)} files processed")

# Show stats
db_files = sum(1 for item in gallery_data if '_note' not in item)
missing_files = len(gallery_data) - db_files
hardlink_matches = sum(1 for item in gallery_data if '_original_path' in item and item['_original_path'] != item['SourceFile'])

if missing_files > 0:
    print(f"⚠️  {missing_files} files not in database")
if hardlink_matches > 0:
    print(f"🔗 {hardlink_matches} hard links matched to originals")
if missing_files == 0:
    print("🎉 All files found in database!")

EOF

# Clean up
rm "$temp_files"