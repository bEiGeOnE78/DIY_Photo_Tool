#!/usr/bin/env python3
"""
Generate JPG proxies from HEIC files for web viewing.
Uses image ID from database as filename to avoid conflicts.
Preserves orientation and full resolution.
"""

import sqlite3
import os
import sys
import argparse
from pathlib import Path
import subprocess
from PIL import Image
from PIL.ExifTags import TAGS

# Configuration - auto-detect paths based on current directory
if os.path.basename(os.getcwd()) == "Scripts":
    # Running from Scripts directory
    DB_FILE = "image_metadata.db"
    PROXY_DIR = "../HEIC Proxies"
else:
    # Running from parent directory (via photo_manager.py)
    DB_FILE = "Scripts/image_metadata.db"
    PROXY_DIR = "HEIC Proxies"
WEBP_QUALITY = 90

def setup_proxy_directory():
    """Create the HEIC Proxies directory if it doesn't exist."""
    proxy_path = Path(PROXY_DIR)
    proxy_path.mkdir(exist_ok=True)
    return proxy_path

def get_heic_files_from_db():
    """Get all HEIC files from database that need proxies."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Find HEIC files (either by format or filename extension)
    cursor.execute("""
        SELECT id, path, filename 
        FROM images 
        WHERE (file_format LIKE '%HEIC%' OR UPPER(filename) LIKE '%.HEIC')
        AND path IS NOT NULL
        ORDER BY id
    """)
    
    results = cursor.fetchall()
    conn.close()
    return results

def proxy_exists(image_id, proxy_dir):
    """Check if WebP proxy already exists for this image ID."""
    proxy_path = proxy_dir / f"{image_id}.webp"
    return proxy_path.exists()

def convert_heic_to_webp(source_path, output_path):
    """Convert HEIC file to WebP using ImageMagick (magick) or fallback to sips+PIL."""
    try:
        # Try ImageMagick first (better quality and EXIF handling)
        result = subprocess.run([
            'magick', str(source_path), 
            '-quality', str(WEBP_QUALITY),
            '-auto-orient',  # Handle orientation automatically
            str(output_path)
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            return True, "ImageMagick"
        else:
            print(f"   ⚠️ ImageMagick failed: {result.stderr}")
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"   ⚠️ ImageMagick not available or timeout")
    
    try:
        # Fallback to macOS sips command -> temp JPEG -> PIL -> WebP
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_jpg:
            temp_jpg_path = temp_jpg.name
        
        result = subprocess.run([
            'sips', '-s', 'format', 'jpeg',
            '-s', 'formatOptions', '90',
            str(source_path),
            '--out', temp_jpg_path
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            # Convert temp JPEG to WebP using PIL
            try:
                with Image.open(temp_jpg_path) as img:
                    # Handle orientation using newer PIL/Pillow method
                    try:
                        from PIL import ImageOps
                        img = ImageOps.exif_transpose(img)
                    except (ImportError, AttributeError):
                        # Fallback to manual orientation handling for older PIL versions
                        try:
                            exif = img.getexif()
                            orientation_key = 274  # EXIF orientation tag number
                            if orientation_key in exif:
                                orientation = exif[orientation_key]
                                if orientation == 3:
                                    img = img.rotate(180, expand=True)
                                elif orientation == 6:
                                    img = img.rotate(270, expand=True)
                                elif orientation == 8:
                                    img = img.rotate(90, expand=True)
                        except:
                            pass
                    
                    # Convert to RGB if necessary
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    img.save(output_path, 'WEBP', quality=WEBP_QUALITY, optimize=True)
                    
                # Clean up temp file
                os.unlink(temp_jpg_path)
                return True, "sips+PIL"
            except Exception as e:
                if os.path.exists(temp_jpg_path):
                    os.unlink(temp_jpg_path)
                raise e
        else:
            if os.path.exists(temp_jpg_path):
                os.unlink(temp_jpg_path)
            print(f"   ⚠️ sips failed: {result.stderr}")
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"   ⚠️ sips not available or timeout")
    
    try:
        # Final fallback to Python PIL (may have orientation issues)
        with Image.open(source_path) as img:
            # Handle orientation using newer PIL/Pillow method
            try:
                # Use ImageOps.exif_transpose for automatic orientation handling
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except (ImportError, AttributeError):
                # Fallback to manual orientation handling for older PIL versions
                try:
                    exif = img.getexif()
                    orientation_key = 274  # EXIF orientation tag number
                    if orientation_key in exif:
                        orientation = exif[orientation_key]
                        if orientation == 3:
                            img = img.rotate(180, expand=True)
                        elif orientation == 6:
                            img = img.rotate(270, expand=True)
                        elif orientation == 8:
                            img = img.rotate(90, expand=True)
                except:
                    # If all orientation handling fails, just use image as-is
                    pass
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            img.save(output_path, 'WEBP', quality=WEBP_QUALITY, optimize=True)
            return True, "PIL"
            
    except Exception as e:
        print(f"   ❌ PIL conversion failed: {e}")
        return False, str(e)
    
    return False, "All conversion methods failed"

def clean_orphaned_proxies():
    """Remove proxy files for images no longer in database."""
    proxy_dir = setup_proxy_directory()
    
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        return 0
    
    # Get all valid image IDs from database
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all HEIC image IDs that should have proxies
    cursor.execute("""
        SELECT id FROM images 
        WHERE (file_format LIKE '%HEIC%' OR UPPER(filename) LIKE '%.HEIC')
    """)
    valid_ids = {row['id'] for row in cursor.fetchall()}
    conn.close()
    
    # Find and remove orphaned proxy files
    removed = 0
    for proxy_file in proxy_dir.glob("*.webp"):
        try:
            # Extract image ID from filename
            image_id = int(proxy_file.stem)
            if image_id not in valid_ids:
                proxy_file.unlink()
                print(f"🗑️ Removed orphaned proxy: {proxy_file.name}")
                removed += 1
        except ValueError:
            # Skip files that don't have numeric names
            continue
    
    return removed

def main():
    parser = argparse.ArgumentParser(description='Generate WebP proxies from HEIC files')
    parser.add_argument('--clean', action='store_true', 
                        help='Clean up orphaned proxy files (remove proxies for images no longer in database)')
    args = parser.parse_args()
    
    if args.clean:
        print("🧹 Cleaning Orphaned HEIC Proxies")
        print("=" * 50)
        removed = clean_orphaned_proxies()
        if removed > 0:
            print(f"\n🗑️ Removed {removed} orphaned proxy files")
        else:
            print(f"\n✅ No orphaned proxy files found")
        return
    
    print("🖼️ HEIC to WebP Proxy Generator")
    print("=" * 50)
    
    # Setup
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        print(f"Current directory: {os.getcwd()}")
        print("Expected locations:")
        print("  • Scripts/image_metadata.db (from parent directory)")
        print("  • image_metadata.db (from Scripts directory)")
        print("\nPlease run metadata extraction first (option 1 in photo_manager.py)")
        sys.exit(1)
    
    proxy_dir = setup_proxy_directory()
    print(f"📁 Proxy directory: {proxy_dir.resolve()}")
    
    # Get HEIC files from database
    print("\n🔍 Finding HEIC files in database...")
    heic_files = get_heic_files_from_db()
    print(f"Found {len(heic_files)} HEIC files")
    
    if not heic_files:
        print("✅ No HEIC files found in database")
        return
    
    # Process each file
    converted_count = 0
    skipped_count = 0
    error_count = 0
    
    for row in heic_files:
        image_id = row['id']
        source_path = Path(row['path'])
        filename = row['filename']
        
        print(f"\n📷 Processing ID {image_id}: {filename}")
        
        # Check if source file exists
        if not source_path.exists():
            print(f"   ⚠️ Source file not found: {source_path}")
            error_count += 1
            continue
        
        # Check if proxy already exists
        if proxy_exists(image_id, proxy_dir):
            print(f"   ⏭️ Proxy already exists: {image_id}.webp")
            skipped_count += 1
            continue
        
        # Convert to WebP
        output_path = proxy_dir / f"{image_id}.webp"
        print(f"   🔄 Converting to {output_path.name}...")
        
        success, method = convert_heic_to_webp(source_path, output_path)
        
        if success:
            # Verify the output file was created and has reasonable size
            if output_path.exists() and output_path.stat().st_size > 1000:
                print(f"   ✅ Converted using {method} ({output_path.stat().st_size // 1024} KB)")
                converted_count += 1
            else:
                print(f"   ❌ Output file invalid or too small")
                if output_path.exists():
                    output_path.unlink()  # Remove invalid file
                error_count += 1
        else:
            print(f"   ❌ Conversion failed: {method}")
            error_count += 1
    
    # Summary
    print(f"\n🎉 Conversion complete!")
    print(f"   ✅ Converted: {converted_count} files")
    print(f"   ⏭️ Skipped: {skipped_count} files (already exist)")
    print(f"   ❌ Errors: {error_count} files")
    print(f"\n📁 Proxies stored in: {proxy_dir.resolve()}")
    
    if converted_count > 0:
        print(f"\n💡 Next steps:")
        print(f"   1. Update your gallery viewer to use WebP proxies for HEIC files")
        print(f"   2. Proxies are named by image ID: {{image_id}}.webp")

if __name__ == "__main__":
    main()