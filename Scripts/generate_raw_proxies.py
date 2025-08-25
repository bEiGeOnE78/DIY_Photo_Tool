#!/usr/bin/env python3
"""
Generate JPG proxies from RAW files using RawTherapee CLI.
Uses image ID from database as filename to avoid conflicts.
Handles orientation and color profiles correctly.
"""

import sqlite3
import os
import sys
import argparse
import tempfile
import shutil
from pathlib import Path
import subprocess

# Configuration - auto-detect paths based on current directory
if os.path.basename(os.getcwd()) == "Scripts":
    # Running from Scripts directory
    DB_FILE = "image_metadata.db"
    PROXY_DIR = "../RAW Proxies"
else:
    # Running from parent directory (via photo_manager.py)
    DB_FILE = "Scripts/image_metadata.db"
    PROXY_DIR = "RAW Proxies"

# RAW file extensions supported
RAW_EXTENSIONS = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw'}

# RawTherapee CLI settings for high quality
RAWTHERAPEE_QUALITY = 98  # Higher JPEG quality
RAWTHERAPEE_CHROMA_SUBSAMPLING = 3  # Best quality (4:4:4)
RAWTHERAPEE_TIMEOUT = 300  # 5 minutes per file (more time for quality processing)
DEFAULT_CAMERA_STANDARD = "RawTherapee Presets/Standard_A7C.pp3"  # Default camera standard
DEFAULT_STYLE_PRESET = None  # No default style preset - camera standard only

def setup_proxy_directory():
    """Create the RAW Proxies directory if it doesn't exist."""
    proxy_path = Path(PROXY_DIR)
    proxy_path.mkdir(exist_ok=True)
    return proxy_path

def get_raw_files_from_db(image_id=None):
    """Get RAW files from database that need proxies."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if image_id:
        # Get specific image by ID
        cursor.execute("""
            SELECT id, path, filename 
            FROM images 
            WHERE id = ?
            AND path IS NOT NULL
        """, (image_id,))
    else:
        # Find all RAW files by extension
        raw_extensions_sql = " OR ".join([f"UPPER(filename) LIKE '%.{ext[1:].upper()}'" for ext in RAW_EXTENSIONS])
        cursor.execute(f"""
            SELECT id, path, filename 
            FROM images 
            WHERE ({raw_extensions_sql})
            AND path IS NOT NULL
            ORDER BY id
        """)
    
    results = cursor.fetchall()
    conn.close()
    return results

def proxy_exists(image_id, proxy_dir):
    """Check if JPG proxy already exists for this image ID."""
    proxy_path = proxy_dir / f"{image_id}.jpg"
    return proxy_path.exists()

def has_adjacent_jpg(raw_path):
    """Check if there's an adjacent JPG file (same name, different extension)."""
    raw_path = Path(raw_path)
    jpg_path = raw_path.with_suffix('.jpg')
    jpeg_path = raw_path.with_suffix('.jpeg')
    JPG_path = raw_path.with_suffix('.JPG')
    JPEG_path = raw_path.with_suffix('.JPEG')
    
    for potential_jpg in [jpg_path, jpeg_path, JPG_path, JPEG_path]:
        if potential_jpg.exists():
            return potential_jpg
    return None

def check_rawtherapee_cli():
    """Check if rawtherapee-cli is available."""
    try:
        result = subprocess.run(['rawtherapee-cli', '--help'], 
                              capture_output=True, text=True, timeout=10)
        # RawTherapee CLI returns exit code 2 with --help, but still outputs version info
        return 'RawTherapee' in result.stdout or 'command line' in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def get_camera_standard_from_exif(image_id, use_full_version=False):
    """Get appropriate camera standard based on EXIF data from database.
    
    Args:
        image_id: Database image ID
        use_full_version: If True, use Full version (with tone curve/look table for camera-only processing).
                         If False, use regular version (without tone curve/look table for film sim processing).
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT camera_make, camera_model FROM images WHERE id = ?", (image_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return DEFAULT_CAMERA_STANDARD
    
    make = (result['camera_make'] or '').upper()
    model = (result['camera_model'] or '').upper()
    
    # Map camera models to standard profiles
    # Regular versions: tone curve/look table disabled (for film sim use)
    # Full versions: tone curve/look table enabled (for camera-only use)
    camera_mappings = {
        'A7C': 'Standard_A7C_Full.pp3' if use_full_version else 'Standard_A7C.pp3',
        'LX100': 'Standard_LX100_Full.pp3' if use_full_version else 'Standard_LX100.pp3',
        'X-E4': 'Standard_XE4_Full.pp3' if use_full_version else 'Standard_XE4.pp3',
        'ILCE-6500': 'Standard_A6500_Full.pp3' if use_full_version else 'Standard_A6500.pp3',
        'ILCE-7C': 'Standard_A7C_Full.pp3' if use_full_version else 'Standard_A7C.pp3',  # Sony A7C full model name
        'DMC-LX100': 'Standard_LX100_Full.pp3' if use_full_version else 'Standard_LX100.pp3',  # Panasonic LX100 full model name
    }
    
    # Find matching standard
    for camera_key, standard_file in camera_mappings.items():
        if camera_key in model:
            standard_path = f"RawTherapee Presets/{standard_file}"
            if Path(standard_path).exists():
                return standard_path
    
    # Fallback to default
    return DEFAULT_CAMERA_STANDARD

def convert_raw_to_adjacent_jpg(source_path, image_id=None, camera_standard=None, style_preset=None, quality=None, exposure=0):
    """Convert RAW file to adjacent JPG using RawTherapee CLI with high quality settings and presets."""
    try:
        # Auto-detect camera standard if not provided
        # Use Full version if no style preset, regular version if style preset is used
        use_full_version = (style_preset is None or style_preset == "None")
        if camera_standard is None and image_id is not None:
            camera_standard = get_camera_standard_from_exif(image_id, use_full_version)
        elif camera_standard is None:
            camera_standard = DEFAULT_CAMERA_STANDARD
            
        # Use default style if not provided
        if style_preset is None:
            style_preset = DEFAULT_STYLE_PRESET
            
        # Use default quality if not provided
        if quality is None:
            quality = RAWTHERAPEE_QUALITY
        
        # Check if presets exist
        camera_path = Path(camera_standard)
        style_path = Path(style_preset)
        
        if not camera_path.exists():
            print(f"   ⚠️ Camera standard not found: {camera_standard}, using default settings")
        if not style_path.exists():
            print(f"   ⚠️ Style preset not found: {style_preset}, using default settings")
        
        # Get exposure preset path
        exposure_preset = f"RawTherapee Presets/Exposure_{exposure:+g}.pp3" if exposure != 0 else "RawTherapee Presets/Exposure_0.pp3"
        exposure_path = Path(exposure_preset)
        
        # Use RawTherapee CLI with optimized settings for best quality
        # Order: Camera Standard -> Exposure -> Film Simulation
        cmd = ['rawtherapee-cli']
        
        # Add camera standard first (base settings)
        if camera_path.exists():
            cmd.extend(['-p', str(camera_path.resolve())])
            print(f"   📷 Using camera standard: {camera_path.name}")
        
        # Add exposure adjustment second
        if exposure_path.exists():
            cmd.extend(['-p', str(exposure_path.resolve())])
            print(f"   ⚡ Using exposure: {exposure:+g} EV")
        
        # Add style preset third (stacked on top)
        if style_path.exists():
            cmd.extend(['-p', str(style_path.resolve())])
            print(f"   🎨 Using style preset: {style_path.name}")
        
        cmd.extend([
            f'-j{quality}',  # JPEG quality
            f'-js{RAWTHERAPEE_CHROMA_SUBSAMPLING}',  # Best chroma subsampling
            '-Y',  # Overwrite if exists
            '-s',  # Use sidecar files if available
            '-c', str(source_path)  # Convert (must be last)
        ])
        
        print(f"   🔧 RawTherapee command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=RAWTHERAPEE_TIMEOUT)
        
        # Check if adjacent JPG was created
        source_path_obj = Path(source_path)
        adjacent_jpg = source_path_obj.with_suffix('.jpg')
        
        if adjacent_jpg.exists():
            return True, str(adjacent_jpg), "RawTherapee CLI (adjacent JPG)"
        else:
            error_msg = result.stderr.strip() if result.stderr else "No adjacent JPG created"
            return False, None, f"RawTherapee CLI error: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, None, "RawTherapee CLI timeout"
    except FileNotFoundError:
        return False, None, "RawTherapee CLI not found"
    except Exception as e:
        return False, None, f"RawTherapee CLI exception: {e}"


def update_database_proxy_status(image_id, proxy_type, processing_settings=None):
    """Update database with RAW proxy information."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if columns exist, add them if they don't
    cursor.execute("PRAGMA table_info(images)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'raw_proxy_type' not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN raw_proxy_type TEXT")
    
    if 'raw_processing_settings' not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN raw_processing_settings TEXT")
    
    # Update the record
    cursor.execute("""
        UPDATE images 
        SET raw_proxy_type = ?, raw_processing_settings = ?
        WHERE id = ?
    """, (proxy_type, processing_settings, image_id))
    
    conn.commit()
    conn.close()

def generate_custom_raw_proxy(source_path, image_id, proxy_dir, camera_standard=None, style_preset=None, quality=None, exposure=0):
    """Generate custom RAW proxy in RAW Proxies directory using RawTherapee CLI."""
    try:
        # Auto-detect camera standard if not provided
        # Use Full version if no style preset, regular version if style preset is used
        use_full_version = (style_preset is None or style_preset == "None")
        if camera_standard is None:
            camera_standard = get_camera_standard_from_exif(image_id, use_full_version)
        
        # Use default style if not provided  
        if style_preset is None:
            style_preset = DEFAULT_STYLE_PRESET
            
        # Use default quality if not provided
        if quality is None:
            quality = RAWTHERAPEE_QUALITY
            
        # Setup output path
        output_path = proxy_dir / f"{image_id}.jpg"
        
        # Check if presets exist
        camera_path = Path(camera_standard)
        style_path = Path(style_preset) if style_preset and style_preset != "None" else None
        
        if not camera_path.exists():
            print(f"   ⚠️ Camera standard not found: {camera_standard}, using default settings")
        if style_path and not style_path.exists():
            print(f"   ⚠️ Style preset not found: {style_preset}, using default settings")
        
        # Get exposure preset path
        exposure_preset = f"RawTherapee Presets/Exposure_{exposure:+g}.pp3" if exposure != 0 else "RawTherapee Presets/Exposure_0.pp3"
        exposure_path = Path(exposure_preset)
        
        # Build RawTherapee command
        # Order: Camera Standard -> Exposure -> Film Simulation
        cmd = ['rawtherapee-cli']
        
        # Add camera standard first (base settings)
        if camera_path.exists():
            cmd.extend(['-p', str(camera_path.resolve())])
            print(f"   📷 Using camera standard: {camera_path.name}")
        
        # Add exposure adjustment second
        if exposure_path.exists():
            cmd.extend(['-p', str(exposure_path.resolve())])
            print(f"   ⚡ Using exposure: {exposure:+g} EV")
        
        # Add style preset third (stacked on top) - only if provided and exists
        if style_preset and style_preset != "None" and style_path and style_path.exists():
            cmd.extend(['-p', str(style_path.resolve())])
            print(f"   🎨 Using style preset: {style_path.name}")
        else:
            print(f"   🎨 No style preset - using camera standard only")
        
        cmd.extend([
            '-o', str(output_path),
            f'-j{quality}',  # JPEG quality
            f'-js{RAWTHERAPEE_CHROMA_SUBSAMPLING}',  # Best chroma subsampling
            '-Y',  # Overwrite if exists
            '-s',  # Use sidecar files if available
            '-c', str(source_path)  # Convert (must be last)
        ])
        
        print(f"   🔧 Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=RAWTHERAPEE_TIMEOUT)
        
        if result.returncode == 0 and output_path.exists():
            # Update database with custom proxy info
            import json
            processing_settings = json.dumps({
                "quality": quality,
                "chroma_subsampling": RAWTHERAPEE_CHROMA_SUBSAMPLING,
                "method": "rawtherapee-cli",
                "camera_standard": camera_path.name if camera_path.exists() else "auto-detected",
                "style_preset": style_path.name if style_path and style_path.exists() else "none",
                "generated_on_demand": True
            })
            update_database_proxy_status(image_id, "custom_generated", processing_settings)
            return True, "success"
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return False, f"conversion failed: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, f"error: {e}"

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
    
    # Get all RAW image IDs that should have proxies
    raw_extensions_sql = " OR ".join([f"UPPER(filename) LIKE '%.{ext[1:].upper()}'" for ext in RAW_EXTENSIONS])
    cursor.execute(f"""
        SELECT id FROM images 
        WHERE ({raw_extensions_sql})
    """)
    valid_ids = {row['id'] for row in cursor.fetchall()}
    conn.close()
    
    # Find and remove orphaned proxy files
    removed = 0
    for proxy_file in proxy_dir.glob("*.jpg"):
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

def get_available_presets():
    """Get lists of available camera standards and style presets."""
    preset_dir = Path("RawTherapee Presets")
    if not preset_dir.exists():
        return [], []
    
    all_presets = [p.name for p in preset_dir.glob("*.pp3")]
    camera_standards = [p for p in all_presets if p.startswith("Standard_")]
    style_presets = [p for p in all_presets if not p.startswith("Standard_") and not p.startswith("Exposure_") and "_Full" not in p]
    
    return camera_standards, style_presets

def main():
    camera_standards, style_presets = get_available_presets()
    
    parser = argparse.ArgumentParser(description='Generate JPG proxies from RAW files using RawTherapee')
    parser.add_argument('--clean', action='store_true', 
                        help='Clean up orphaned proxy files (remove proxies for images no longer in database)')
    parser.add_argument('--force', action='store_true',
                        help='Regenerate all proxies, even if they already exist')
    parser.add_argument('--camera-standard', choices=camera_standards,
                        help=f'Camera standard preset to use (auto-detected from EXIF if not specified). Available: {", ".join(camera_standards)}')
    parser.add_argument('--style-preset', choices=style_presets,
                        help=f'Style preset to apply on top of camera standard. Available: {", ".join(style_presets)}')
    parser.add_argument('--list-presets', action='store_true',
                        help='List available camera standards and style presets')
    parser.add_argument('--image-id', type=int,
                        help='Process only the specified image ID')
    parser.add_argument('--quality', type=int, default=RAWTHERAPEE_QUALITY,
                        help=f'JPEG quality (1-100, default: {RAWTHERAPEE_QUALITY})')
    parser.add_argument('--exposure', type=float, default=0.0, choices=[-1.0, -0.5, 0.0, 0.5, 1.0],
                        help='Exposure compensation in EV (-1, -0.5, 0, +0.5, +1, default: 0)')
    args = parser.parse_args()
    
    if args.list_presets:
        print("📷 Available Camera Standards:")
        for standard in camera_standards:
            print(f"   • {standard}")
        print("\n🎨 Available Style Presets:")
        for preset in style_presets:
            print(f"   • {preset}")
        return
    
    if args.clean:
        print("🧹 Cleaning Orphaned RAW Proxies")
        print("=" * 50)
        removed = clean_orphaned_proxies()
        if removed > 0:
            print(f"\n🗑️ Removed {removed} orphaned proxy files")
        else:
            print(f"\n✅ No orphaned proxy files found")
        return
    
    print("🎞️ RAW to JPG Proxy Generator")
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
    
    # Check RawTherapee CLI availability
    if not check_rawtherapee_cli():
        print("❌ RawTherapee CLI not found!")
        print("Please install RawTherapee CLI:")
        print("  • macOS: sudo port install rawtherapee")
        print("  • Linux: sudo apt install rawtherapee")
        print("  • Or download from: https://rawtherapee.com/")
        sys.exit(1)
    
    proxy_dir = setup_proxy_directory()
    print(f"📁 Proxy directory: {proxy_dir.resolve()}")
    print(f"✅ RawTherapee CLI available")
    
    # Get RAW files from database
    if args.image_id:
        print(f"\n🔍 Finding image {args.image_id} in database...")
        raw_files = get_raw_files_from_db(args.image_id)
        if raw_files:
            print(f"Found image {args.image_id}")
        else:
            print(f"❌ Image {args.image_id} not found in database")
            return
    else:
        print("\n🔍 Finding RAW files in database...")
        raw_files = get_raw_files_from_db()
        print(f"Found {len(raw_files)} RAW files")
    
    if not raw_files:
        print("✅ No RAW files found in database")
        return
    
    # Process each file
    converted_count = 0
    skipped_adjacent_count = 0
    skipped_count = 0
    error_count = 0
    
    for row in raw_files:
        image_id = row['id']
        source_path = Path(row['path'])
        filename = row['filename']
        
        print(f"\n📷 Processing ID {image_id}: {filename}")
        
        # Check if source file exists
        if not source_path.exists():
            print(f"   ⚠️ Source file not found: {source_path}")
            error_count += 1
            continue
        
        output_path = proxy_dir / f"{image_id}.jpg"
        
        # Check if proxy already exists (unless forcing regeneration)
        if not args.force and proxy_exists(image_id, proxy_dir):
            print(f"   ⏭️ Proxy already exists: {image_id}.jpg")
            skipped_count += 1
            continue
        
        # If processing a specific image ID, generate custom proxy
        if args.image_id:
            # Check if it's actually a RAW file
            if source_path.suffix.lower() not in RAW_EXTENSIONS:
                print(f"   ❌ Not a RAW file: {source_path.suffix}")
                error_count += 1
                continue
                
            print(f"   🔄 Generating custom proxy using RawTherapee...")
            
            # Determine presets to use
            camera_standard = f"RawTherapee Presets/{args.camera_standard}" if args.camera_standard else None
            style_preset = f"RawTherapee Presets/{args.style_preset}" if args.style_preset else None
            
            success, message = generate_custom_raw_proxy(
                source_path, 
                image_id,
                proxy_dir,
                camera_standard=camera_standard,
                style_preset=style_preset,
                quality=args.quality,
                exposure=args.exposure
            )
            
            if success:
                print(f"   ✅ Generated custom proxy: {image_id}.jpg")
                converted_count += 1
            else:
                print(f"   ❌ Failed to generate custom proxy: {message}")
                error_count += 1
        else:
            # Normal batch processing - check for adjacent JPG first
            adjacent_jpg = has_adjacent_jpg(source_path)
            if adjacent_jpg:
                print(f"   📄 Found adjacent JPG: {adjacent_jpg.name}")
                print(f"   ⏭️ Skipping - adjacent JPG will be used directly for galleries")
                update_database_proxy_status(image_id, "original_jpg")
                skipped_adjacent_count += 1
                continue
            
            # Generate adjacent JPG using RawTherapee CLI
            print(f"   🔄 Creating adjacent JPG using RawTherapee...")
            
            # Determine presets to use
            camera_standard = f"RawTherapee Presets/{args.camera_standard}" if args.camera_standard else None
            style_preset = f"RawTherapee Presets/{args.style_preset}" if args.style_preset else None
            
            success, adjacent_path, method = convert_raw_to_adjacent_jpg(
                source_path, 
                image_id=image_id,
                camera_standard=camera_standard,
                style_preset=style_preset,
                quality=args.quality,
                exposure=args.exposure
            )
            
            if success:
                # Verify the adjacent JPG was created and has reasonable size
                adjacent_jpg_path = Path(adjacent_path)
                if adjacent_jpg_path.exists() and adjacent_jpg_path.stat().st_size > 10000:  # At least 10KB
                    print(f"   ✅ Created adjacent JPG using {method} ({adjacent_jpg_path.stat().st_size // 1024} KB)")
                    print(f"   📄 Location: {adjacent_jpg_path.name}")
                    update_database_proxy_status(image_id, "original_jpg", 
                                               f'{{"quality": {RAWTHERAPEE_QUALITY}, "chroma_subsampling": {RAWTHERAPEE_CHROMA_SUBSAMPLING}, "method": "rawtherapee-cli-adjacent-hq", "lens_correction": true}}')
                    converted_count += 1
                else:
                    print(f"   ❌ Adjacent JPG invalid or too small")
                    if adjacent_jpg_path.exists():
                        adjacent_jpg_path.unlink()  # Remove invalid file
                    error_count += 1
            else:
                print(f"   ❌ Conversion failed: {method}")
                error_count += 1
    
    # Summary
    print(f"\n🎉 Processing complete!")
    print(f"   📄 Adjacent JPGs found: {skipped_adjacent_count} files (already existed)")
    print(f"   ✅ Adjacent JPGs created: {converted_count} files (RawTherapee)")
    print(f"   ⏭️ Skipped: {skipped_count} files (already processed)")
    print(f"   ❌ Errors: {error_count} files")
    
    if converted_count > 0:
        print(f"\n💡 Next steps:")
        print(f"   • Adjacent JPGs created alongside RAW files")
        print(f"   • Gallery creation will use adjacent JPGs automatically")
        print(f"   • Database tracks all files as 'original_jpg' type")
        print(f"   • Use 'Regenerate RAW Picks' for custom processing")

if __name__ == "__main__":
    main()