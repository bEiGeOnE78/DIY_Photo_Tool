#!/usr/bin/env python3
"""
Regenerate RAW Picks with Custom Settings
Reads from picks.json and regenerates selected RAW files with custom RawTherapee settings.
"""

import sqlite3
import os
import sys
import json
import argparse
from pathlib import Path
import subprocess

# Configuration - auto-detect paths
if os.path.basename(os.getcwd()) == "Scripts":
    DB_FILE = "image_metadata.db"
    PICKS_FILE = "../JSON/picks.json"
    PROXY_DIR = "../RAW Proxies"
else:
    DB_FILE = "Scripts/image_metadata.db"
    PICKS_FILE = "JSON/picks.json"
    PROXY_DIR = "RAW Proxies"

# RawTherapee CLI settings for high quality custom processing
DEFAULT_QUALITY = 98  # Higher JPEG quality for picks
DEFAULT_CHROMA_SUBSAMPLING = 3  # Best quality (4:4:4)
DEFAULT_TIMEOUT = 600  # 10 minutes per file for custom processing
DEFAULT_CAMERA_STANDARD = "RawTherapee Presets/Standard_A7C.pp3"  # Default camera standard
DEFAULT_STYLE_PRESET = "RawTherapee Presets/Provia.pp3"  # Default style for picks - vibrant, punchy colors

class RawPicksRegenerator:
    def __init__(self):
        self.db_path = DB_FILE
        self.picks_file = PICKS_FILE
        self.proxy_dir = Path(PROXY_DIR)
        self.proxy_dir.mkdir(exist_ok=True)
        
    def check_rawtherapee_cli(self):
        """Check if rawtherapee-cli is available."""
        try:
            result = subprocess.run(['rawtherapee-cli', '--help'], 
                                  capture_output=True, text=True, timeout=10)
            # RawTherapee CLI returns exit code 2 with --help, but still outputs version info
            return 'RawTherapee' in result.stdout or 'command line' in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def get_camera_standard_from_exif(self, image_id):
        """Get appropriate camera standard based on EXIF data from database."""
        conn = sqlite3.connect(self.db_path)
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
        camera_mappings = {
            'A7C': 'Standard_A7C.pp3',
            'LX100': 'Standard_LX100.pp3',
            'X-E4': 'Standard_XE4.pp3',
            'ILCE-6500': 'Standard_A6500.pp3',
            'ILCE-7C': 'Standard_A7C.pp3',  # Sony A7C full model name
            'DMC-LX100': 'Standard_LX100.pp3',  # Panasonic LX100 full model name
        }
        
        # Find matching standard
        for camera_key, standard_file in camera_mappings.items():
            if camera_key in model:
                standard_path = f"RawTherapee Presets/{standard_file}"
                if Path(standard_path).exists():
                    return standard_path
        
        # Fallback to default
        return DEFAULT_CAMERA_STANDARD
    
    def load_picks(self):
        """Load picks from JSON file."""
        if not os.path.exists(self.picks_file):
            print(f"❌ Picks file not found: {self.picks_file}")
            return None
        
        try:
            with open(self.picks_file, 'r') as f:
                picks = json.load(f)
            
            if not isinstance(picks, list):
                print("❌ Picks file must contain an array")
                return None
                
            return picks
        except Exception as e:
            print(f"❌ Error reading picks file: {e}")
            return None
    
    def get_image_id_from_gallery_json(self, gallery_name, filename):
        """Get image ID from gallery JSON file by looking up filename."""
        gallery_json_path = Path("Hard Link Galleries") / gallery_name / "image_data.json"
        
        if not gallery_json_path.exists():
            print(f"   ⚠️ Gallery JSON not found: {gallery_json_path}")
            return None
        
        try:
            with open(gallery_json_path, 'r') as f:
                gallery_data = json.load(f)
            
            # Look for the filename in gallery data
            for item in gallery_data:
                if item.get('FileName') == filename:
                    image_id = item.get('_imageId')
                    original_path = item.get('_originalPath')
                    print(f"   🔍 Found in gallery: ID {image_id}, original: {original_path}")
                    return image_id
            
            print(f"   ⚠️ File not found in gallery JSON: {filename}")
            return None
            
        except Exception as e:
            print(f"   ❌ Error reading gallery JSON: {e}")
            return None
    
    def get_raw_files_from_picks(self, picks):
        """Get RAW files from database that match the picks."""
        if not picks:
            return []
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        raw_files = []
        for pick_entry in picks:
            if not pick_entry:
                continue
            
            print(f"\n📷 Processing pick: {pick_entry}")
            
            # Check if it's a numeric ID (new format)
            if isinstance(pick_entry, int) or (isinstance(pick_entry, str) and pick_entry.isdigit()):
                image_id = int(pick_entry)
                
                # Look up the original file by image ID
                cursor.execute("""
                    SELECT id, path, filename, raw_proxy_type
                    FROM images 
                    WHERE id = ?
                """, (image_id,))
                
                result = cursor.fetchone()
                if result:
                    # Check if it's a RAW file by extension
                    file_ext = Path(result['filename']).suffix.lower()
                    raw_extensions = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw'}
                    
                    if file_ext in raw_extensions:
                        raw_files.append(result)
                        print(f"   ✅ Found RAW file: {result['filename']} (ID: {result['id']})")
                    else:
                        print(f"   ⏭️ Original file is not RAW: {result['filename']}")
                else:
                    print(f"   ❌ Image ID {image_id} not found in database")
            
            # Legacy support: Parse gallery_name/filename format or just filename
            elif isinstance(pick_entry, str) and '/' in pick_entry:
                gallery_name, filename = pick_entry.split('/', 1)
                
                # Try to get image ID from gallery JSON first
                image_id = self.get_image_id_from_gallery_json(gallery_name, filename)
                
                if image_id:
                    # Look up the original file by image ID
                    cursor.execute("""
                        SELECT id, path, filename, raw_proxy_type
                        FROM images 
                        WHERE id = ?
                    """, (image_id,))
                    
                    result = cursor.fetchone()
                    if result:
                        # Check if it's a RAW file by extension
                        file_ext = Path(result['filename']).suffix.lower()
                        raw_extensions = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw'}
                        
                        if file_ext in raw_extensions:
                            raw_files.append(result)
                            print(f"   ✅ Found RAW file: {result['filename']} (ID: {result['id']})")
                        else:
                            print(f"   ⏭️ Original file is not RAW: {result['filename']}")
                    else:
                        print(f"   ❌ Image ID {image_id} not found in database")
                else:
                    print(f"   ❌ Could not find image ID for: {pick_entry}")
            elif isinstance(pick_entry, str):
                # Legacy fallback: direct filename lookup
                filename = pick_entry
                
                # Remove any date prefix (YYYYMMDD_) if present
                if len(filename) > 9 and filename[8] == '_':
                    original_filename = filename[9:]
                else:
                    original_filename = filename
                
                # Look up in database
                cursor.execute("""
                    SELECT id, path, filename, raw_proxy_type
                    FROM images 
                    WHERE filename = ? OR filename LIKE ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (original_filename, f"%{original_filename}"))
                
                result = cursor.fetchone()
                if result:
                    # Check if it's a RAW file by extension
                    file_ext = Path(result['filename']).suffix.lower()
                    raw_extensions = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw'}
                    
                    if file_ext in raw_extensions:
                        raw_files.append(result)
                        print(f"   ✅ Found RAW file (legacy): {original_filename} (ID: {result['id']})")
                    else:
                        print(f"   ⏭️ Skipping non-RAW file (legacy): {original_filename}")
                else:
                    print(f"   ⚠️ Pick not found in database (legacy): {original_filename}")
        
        conn.close()
        return raw_files
    
    def get_camera_standard_from_exif(self, image_id):
        """Get appropriate camera standard based on EXIF data from database."""
        conn = sqlite3.connect(self.db_path)
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
        camera_mappings = {
            'A7C': 'Standard_A7C.pp3',
            'LX100': 'Standard_LX100.pp3', 
            'ILCE-7C': 'Standard_A7C.pp3',  # Sony A7C full model name
            'DMC-LX100': 'Standard_LX100.pp3',  # Panasonic LX100 full model name
        }
        
        # Find matching standard
        for camera_key, standard_file in camera_mappings.items():
            if camera_key in model:
                standard_path = f"RawTherapee Presets/{standard_file}"
                if Path(standard_path).exists():
                    return standard_path
        
        # Fallback to default
        return DEFAULT_CAMERA_STANDARD

    def convert_raw_with_custom_settings(self, source_path, output_path, image_id=None, quality=DEFAULT_QUALITY, camera_standard=None, style_preset=None):
        """Convert RAW file to JPG using RawTherapee CLI with high quality custom settings and two-stage processing."""
        try:
            # Auto-detect camera standard if not provided
            if camera_standard is None and image_id is not None:
                camera_standard = self.get_camera_standard_from_exif(image_id)
            elif camera_standard is None:
                camera_standard = DEFAULT_CAMERA_STANDARD
                
            # Use default style if not provided, or skip if "None"
            if style_preset is None:
                style_preset = DEFAULT_STYLE_PRESET
            elif style_preset == "None":
                style_preset = None  # No style preset - just camera standard
            
            # Check if presets exist
            camera_path = Path(camera_standard)
            style_path = Path(style_preset) if style_preset else None
            
            if not camera_path.exists():
                print(f"   ⚠️ Camera standard not found: {camera_standard}, using default settings")
            if style_preset and style_path and not style_path.exists():
                print(f"   ⚠️ Style preset not found: {style_preset}, using default settings")
            
            cmd = ['rawtherapee-cli']
            
            # Add camera standard first (base settings)
            if camera_path.exists():
                cmd.extend(['-p', str(camera_path.resolve())])
                print(f"   📷 Using camera standard: {camera_path.name}")
            
            # Add style preset second (stacked on top) - only if specified
            if style_preset and style_path and style_path.exists():
                cmd.extend(['-p', str(style_path.resolve())])
                print(f"   🎨 Using style preset: {style_path.name}")
            elif style_preset is None:
                print(f"   🎨 No style preset - using camera standard only")
            
            cmd.extend([
                '-o', str(output_path),
                f'-j{quality}',  # JPEG output with quality
                f'-js{DEFAULT_CHROMA_SUBSAMPLING}',  # Best chroma subsampling (4:4:4)
                '-Y',  # Overwrite if exists
                '-s',  # Use sidecar files if available
                '-c', str(source_path)  # Convert (must be last)
            ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=DEFAULT_TIMEOUT)
            
            if result.returncode == 0:
                return True, "RawTherapee CLI (custom)"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return False, f"RawTherapee CLI error: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, "RawTherapee CLI timeout"
        except FileNotFoundError:
            return False, "RawTherapee CLI not found"
        except Exception as e:
            return False, f"RawTherapee CLI exception: {e}"
    
    def update_database_proxy_status(self, image_id, processing_settings):
        """Update database to mark as custom_generated with new settings."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Ensure columns exist
        try:
            cursor.execute("SELECT raw_proxy_type FROM images LIMIT 1")
        except:
            cursor.execute("ALTER TABLE images ADD COLUMN raw_proxy_type TEXT")
            cursor.execute("ALTER TABLE images ADD COLUMN raw_processing_settings TEXT")
        
        # Update the record
        cursor.execute("""
            UPDATE images 
            SET raw_proxy_type = 'custom_generated', raw_processing_settings = ?
            WHERE id = ?
        """, (processing_settings, image_id))
        
        conn.commit()
        conn.close()
    
    def regenerate_picks(self, quality=DEFAULT_QUALITY, camera_standard=None, style_preset=None, force=False):
        """Regenerate RAW picks with custom settings."""
        print("🎞️ RAW PICKS REGENERATION")
        print("=" * 50)
        
        # Check RawTherapee CLI
        if not self.check_rawtherapee_cli():
            print("❌ RawTherapee CLI not found!")
            print("Please install RawTherapee CLI:")
            print("  • macOS: sudo port install rawtherapee")
            print("  • Linux: sudo apt install rawtherapee")
            return False
        
        # Load picks
        print(f"📋 Loading picks from: {self.picks_file}")
        picks = self.load_picks()
        if not picks:
            return False
        
        print(f"Found {len(picks)} picks")
        
        # Get RAW files from picks
        print("\n🔍 Finding RAW files from picks...")
        raw_files = self.get_raw_files_from_picks(picks)
        
        if not raw_files:
            print("❌ No RAW files found in picks")
            return False
        
        print(f"📷 Found {len(raw_files)} RAW files to process")
        
        # Show settings
        print(f"\n⚙️ Processing settings:")
        print(f"   Quality: {quality}%")
        if camera_standard:
            print(f"   Camera Standard: {camera_standard}")
        else:
            print(f"   Camera Standard: Auto-detected from EXIF")
        if style_preset:
            print(f"   Style Preset: {style_preset}")
        else:
            print(f"   Style Preset: Default ({DEFAULT_STYLE_PRESET})")
        print(f"   Force regenerate: {force}")
        
        # Process each RAW file
        regenerated_count = 0
        skipped_count = 0
        error_count = 0
        regenerated_image_ids = []  # Track which images were regenerated for gallery updates
        
        print(f"\n🔄 Processing {len(raw_files)} RAW files...")
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
            
            output_path = self.proxy_dir / f"{image_id}.jpg"
            
            # Check if proxy already exists
            if not force and output_path.exists():
                print(f"   ⏭️ Proxy already exists: {output_path.name}")
                skipped_count += 1
                continue
            
            # Convert with custom settings
            print(f"   🔄 Converting with custom settings...")
            success, method = self.convert_raw_with_custom_settings(
                source_path, output_path, image_id, quality, camera_standard, style_preset
            )
            
            if success:
                # Verify output file
                if output_path.exists() and output_path.stat().st_size > 10000:
                    print(f"   ✅ Regenerated using {method} ({output_path.stat().st_size // 1024} KB)")
                    
                    # Update database
                    processing_settings = json.dumps({
                        "quality": quality,
                        "chroma_subsampling": DEFAULT_CHROMA_SUBSAMPLING,
                        "method": "rawtherapee-cli-two-stage",
                        "camera_standard": Path(camera_standard).name if camera_standard else "auto-detected",
                        "style_preset": Path(style_preset).name if style_preset else "none",
                        "regenerated_from_picks": True
                    })
                    self.update_database_proxy_status(image_id, processing_settings)
                    regenerated_count += 1
                    regenerated_image_ids.append(image_id)  # Track for gallery updates
                else:
                    print(f"   ❌ Output file invalid or too small")
                    if output_path.exists():
                        output_path.unlink()
                    error_count += 1
            else:
                print(f"   ❌ Conversion failed: {method}")
                error_count += 1
        
        # Update gallery hard links for regenerated images
        if regenerated_image_ids:
            self.update_gallery_hard_links_for_regenerated_picks(regenerated_image_ids)
        
        # Summary
        print(f"\n🎉 RAW picks regeneration complete!")
        print(f"   ✅ Regenerated: {regenerated_count} files")
        print(f"   ⏭️ Skipped: {skipped_count} files (already exist)")
        print(f"   ❌ Errors: {error_count} files")
        print(f"\n📁 Custom proxies stored in: {self.proxy_dir.resolve()}")
        
        if regenerated_count > 0:
            print(f"\n💡 Next steps:")
            print(f"   • Gallery creation will now use custom proxies for these images")
            print(f"   • Database marked files as 'custom_generated'")
            print(f"   • Original RAW files remain untouched")
        
        return regenerated_count > 0
    
    def regenerate_thumbnails_for_picks(self):
        """Regenerate thumbnails for all picks using the new proxies."""
        try:
            print(f"\n🖼️ Regenerating thumbnails for picked images...")
            print("-" * 50)
            
            # Call generate_thumbnails.py with --picks-only and --force
            cmd = [sys.executable, "Scripts/generate_thumbnails.py", "--picks-only", "--force"]
            
            # If we're running from Scripts directory, adjust the path
            if os.path.basename(os.getcwd()) == "Scripts":
                cmd = [sys.executable, "generate_thumbnails.py", "--picks-only", "--force"]
            
            result = subprocess.run(cmd, capture_output=False, text=True)
            
            if result.returncode == 0:
                print(f"✅ Thumbnail regeneration completed successfully")
                return True
            else:
                print(f"⚠️ Thumbnail regeneration completed with warnings")
                return True  # Still return True as it's not critical
                
        except Exception as e:
            print(f"⚠️ Error regenerating thumbnails: {e}")
            print(f"💡 You can manually run: python3 Scripts/generate_thumbnails.py --picks-only --force")
            return False
    
    def update_hard_link_in_gallery(self, gallery_path, image_id, new_source_path):
        """Update hard link for a specific image in a gallery."""
        try:
            # Load gallery JSON
            json_file = gallery_path / 'image_data.json'
            if not json_file.exists():
                return False, f"Gallery JSON not found: {json_file}"
            
            with open(json_file, 'r') as f:
                gallery_data = json.load(f)
            
            # Find the image in gallery data
            updated = False
            for item in gallery_data:
                if item.get('_imageId') == image_id:
                    old_gallery_file = gallery_path / item['FileName']
                    
                    if old_gallery_file.exists():
                        # Remove old hard link
                        old_gallery_file.unlink()
                        print(f"   🗑️ Removed old hard link: {item['FileName']}")
                    
                    # Create new hard link with same filename
                    try:
                        os.link(new_source_path, old_gallery_file)
                        print(f"   🔗 Created new hard link: {item['FileName']} -> {new_source_path}")
                        updated = True
                        break
                    except OSError as e:
                        return False, f"Failed to create hard link: {e}"
            
            if updated:
                return True, "Hard link updated successfully"
            else:
                return False, f"Image ID {image_id} not found in gallery"
                
        except Exception as e:
            return False, f"Error updating gallery: {e}"
    
    def update_gallery_hard_links_for_regenerated_picks(self, regenerated_image_ids):
        """Update hard links in all galleries for regenerated images."""
        if not regenerated_image_ids:
            return
            
        print(f"\n🔗 Updating gallery hard links for {len(regenerated_image_ids)} regenerated images...")
        print("-" * 50)
        
        # Auto-detect gallery root
        if os.path.basename(os.getcwd()) == "Scripts":
            gallery_root = Path("../Hard Link Galleries")
        else:
            gallery_root = Path("Hard Link Galleries")
            
        if not gallery_root.exists():
            print(f"⚠️ Gallery root not found: {gallery_root}")
            return
        
        galleries_updated = 0
        links_updated = 0
        errors = 0
        
        # Iterate through all galleries
        for gallery_dir in gallery_root.iterdir():
            if not gallery_dir.is_dir():
                continue
                
            print(f"\n📁 Checking gallery: {gallery_dir.name}")
            gallery_updated = False
            
            # Check each regenerated image
            for image_id in regenerated_image_ids:
                proxy_path = self.proxy_dir / f"{image_id}.jpg"
                
                if not proxy_path.exists():
                    print(f"   ⚠️ Proxy not found for ID {image_id}: {proxy_path}")
                    continue
                
                # Update hard link in this gallery
                success, message = self.update_hard_link_in_gallery(gallery_dir, image_id, str(proxy_path))
                
                if success:
                    if not gallery_updated:
                        galleries_updated += 1
                        gallery_updated = True
                    links_updated += 1
                elif "not found in gallery" not in message:
                    # Only count as error if it's not just "image not in this gallery"
                    print(f"   ❌ {message}")
                    errors += 1
        
        # Summary
        print(f"\n🔗 Gallery hard link update complete!")
        print(f"   📁 Galleries updated: {galleries_updated}")
        print(f"   🔗 Hard links updated: {links_updated}")
        if errors > 0:
            print(f"   ❌ Errors: {errors}")
        
        if links_updated > 0:
            print(f"\n💡 Galleries now use custom RAW proxies for regenerated images")
        else:
            print(f"\n💡 No gallery hard links needed updating")
        
        return links_updated > 0
    
    def get_available_presets(self):
        """Get lists of available camera standards and style presets."""
        presets_dir = Path("RawTherapee Presets")
        if not presets_dir.exists():
            return [], []
        
        all_presets = [p.name for p in presets_dir.glob("*.pp3")]
        camera_standards = [p for p in all_presets if p.startswith("Standard_")]
        style_presets = [p for p in all_presets if not p.startswith("Standard_")]
        style_presets.insert(0, "None")  # Add "None" option to use no style preset
        
        return camera_standards, style_presets
    
    def interactive_preset_selection(self):
        """Show interactive menu for two-stage preset selection."""
        camera_standards, style_presets = self.get_available_presets()
        
        # Camera standard selection
        print("\n📷 AVAILABLE CAMERA STANDARDS:")
        print("=" * 40)
        for i, standard in enumerate(camera_standards, 1):
            print(f"  {i:2d}. {standard}")
        print(f"  {len(camera_standards)+1:2d}. Auto-detect from EXIF")
        print(f"   0. Cancel")
        
        while True:
            try:
                choice = input(f"\nSelect camera standard (0-{len(camera_standards)+1}): ").strip()
                
                if choice == "0":
                    return "CANCELLED", "CANCELLED"
                elif choice == str(len(camera_standards)+1):
                    selected_camera = None  # Auto-detect
                    break
                else:
                    idx = int(choice) - 1
                    if 0 <= idx < len(camera_standards):
                        selected_camera = f"RawTherapee Presets/{camera_standards[idx]}"
                        print(f"✅ Selected camera standard: {camera_standards[idx]}")
                        break
                    else:
                        print(f"❌ Please enter a number between 0 and {len(camera_standards)+1}")
            except ValueError:
                print("❌ Please enter a valid number")
        
        # Style preset selection
        print("\n🎨 AVAILABLE STYLE PRESETS:")
        print("=" * 40)
        for i, preset in enumerate(style_presets, 1):
            display_name = preset.replace("_", " ").replace(".pp3", "")
            print(f"  {i:2d}. {display_name}")
        print(f"  {len(style_presets)+1:2d}. Default (Provia)")
        print(f"   0. Cancel")
        
        while True:
            try:
                choice = input(f"\nSelect style preset (0-{len(style_presets)+1}): ").strip()
                
                if choice == "0":
                    return "CANCELLED", "CANCELLED"
                elif choice == str(len(style_presets)+1):
                    selected_style = None  # Default
                    break
                else:
                    idx = int(choice) - 1
                    if 0 <= idx < len(style_presets):
                        if style_presets[idx] == "None":
                            selected_style = "None"
                            print(f"✅ Selected style preset: None (camera standard only)")
                        else:
                            selected_style = f"RawTherapee Presets/{style_presets[idx]}"
                            display_name = style_presets[idx].replace("_", " ").replace(".pp3", "")
                            print(f"✅ Selected style preset: {display_name}")
                        break
                    else:
                        print(f"❌ Please enter a number between 0 and {len(style_presets)+1}")
            except ValueError:
                print("❌ Please enter a valid number")
        
        return selected_camera, selected_style

def main():
    # Get available presets for help text
    regenerator = RawPicksRegenerator()
    camera_standards, style_presets = regenerator.get_available_presets()
    
    parser = argparse.ArgumentParser(description='Regenerate RAW picks with custom RawTherapee settings using two-stage processing')
    parser.add_argument('--quality', type=int, default=DEFAULT_QUALITY,
                        help=f'JPEG quality (1-100, default: {DEFAULT_QUALITY})')
    parser.add_argument('--camera-standard', choices=camera_standards,
                        help=f'Camera standard preset (auto-detected from EXIF if not specified). Available: {", ".join(camera_standards)}')
    parser.add_argument('--style-preset', choices=style_presets,
                        help=f'Style preset to apply on top of camera standard. Available: {", ".join(style_presets)}')
    parser.add_argument('--force', action='store_true',
                        help='Force regeneration even if proxy already exists')
    parser.add_argument('--regenerate-thumbnails', action='store_true',
                        help='Automatically regenerate thumbnails after creating proxies')
    parser.add_argument('--list-presets', action='store_true',
                        help='List available camera standards and style presets')
    
    args = parser.parse_args()
    
    if args.list_presets:
        print("📷 Available Camera Standards:")
        for standard in camera_standards:
            print(f"   • {standard}")
        print("\n🎨 Available Style Presets:")
        for preset in style_presets:
            print(f"   • {preset}")
        return
    
    # Check if database exists
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        print("Please run metadata extraction first.")
        sys.exit(1)
    
    # Validate quality
    if not 1 <= args.quality <= 100:
        print("❌ Quality must be between 1 and 100")
        sys.exit(1)
    
    # Handle preset selection
    camera_standard = f"RawTherapee Presets/{args.camera_standard}" if args.camera_standard else None
    style_preset = args.style_preset if args.style_preset == "None" else f"RawTherapee Presets/{args.style_preset}" if args.style_preset else None
    
    if not camera_standard and not style_preset:
        # Show interactive preset selection
        camera_standard, style_preset = regenerator.interactive_preset_selection()
        if camera_standard == "CANCELLED":
            print("❌ Operation cancelled")
            sys.exit(0)
    
    # Check preset files if specified
    if camera_standard and not os.path.exists(camera_standard):
        print(f"❌ Camera standard file not found: {camera_standard}")
        sys.exit(1)
    if style_preset and style_preset != "None" and not os.path.exists(style_preset):
        print(f"❌ Style preset file not found: {style_preset}")
        sys.exit(1)
    
    success = regenerator.regenerate_picks(args.quality, camera_standard, style_preset, args.force)
    
    if not success:
        sys.exit(1)
    
    # Regenerate thumbnails if requested and if proxy regeneration was successful
    if args.regenerate_thumbnails and success:
        regenerator.regenerate_thumbnails_for_picks()

if __name__ == "__main__":
    main()