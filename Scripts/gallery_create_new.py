#!/usr/bin/env python3
"""
Simplified Gallery Creator
Creates virtual galleries using hard links with unified logic for RAW file handling.
"""

import sqlite3
import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# Configuration - auto-detect paths
if os.path.basename(os.getcwd()) == "Scripts":
    DB_FILE = "image_metadata.db"
    GALLERY_ROOT = "../Hard Link Galleries"
else:
    DB_FILE = "Scripts/image_metadata.db"
    GALLERY_ROOT = "Hard Link Galleries"

class GalleryCreator:
    def __init__(self):
        self.db_path = DB_FILE
        self.gallery_root = Path(GALLERY_ROOT)
        self.gallery_root.mkdir(exist_ok=True)
        
    def get_hard_link_source(self, row):
        """Determine the correct hard link source for a file, handling RAW files and videos."""
        original_path = row['path']
        try:
            raw_proxy_type = row['raw_proxy_type']
        except (KeyError, IndexError):
            raw_proxy_type = None
        
        image_id = row['id']
        original_path_obj = Path(original_path)
        file_ext = original_path_obj.suffix.lower()
        
        # Video file extensions
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        
        # Handle video files - check if proxy exists on disk
        if file_ext in video_extensions:
            proxy_path = f"Video Proxies/{image_id}.mp4"
            if os.path.exists(proxy_path):
                print(f"📹 Using video proxy for {row['filename']}: {proxy_path}")
                return proxy_path
            else:
                # Use original video file
                return original_path
        
        # For RAW files, determine the correct source
        if raw_proxy_type == 'custom_generated':
            # Use the generated proxy from RAW Proxies folder
            proxy_path = f"RAW Proxies/{image_id}.jpg"
            if os.path.exists(proxy_path):
                return proxy_path
            else:
                print(f"⚠️ Custom proxy not found for {row['filename']}: {proxy_path}")
                return None
        elif raw_proxy_type == 'original_jpg':
            # Use the adjacent JPG file
            for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                adjacent_jpg = original_path_obj.with_suffix(ext)
                if adjacent_jpg.exists():
                    return str(adjacent_jpg)
            print(f"⚠️ Adjacent JPG not found for {row['filename']}")
            return None
        else:
            # Check if this is a RAW file that needs adjacent JPG detection
            # List of RAW file extensions
            raw_extensions = {'.cr2', '.nef', '.arw', '.dng', '.raf', '.rw2', '.orf', '.srw', '.x3f', '.3fr'}
            
            if file_ext in raw_extensions:
                # Try to find adjacent JPG
                for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                    adjacent_jpg = original_path_obj.with_suffix(ext)
                    if adjacent_jpg.exists():
                        return str(adjacent_jpg)
                
                # If no adjacent JPG found, skip this RAW file
                print(f"⏭️ Skipping RAW file without adjacent JPG: {row['filename']}")
                return None
            else:
                # Regular file (JPG, PNG, HEIC, etc.) - use original
                return original_path
    
    def get_images_by_date_range(self, start_date=None, end_date=None, camera_make=None):
        """Get images from database filtered by date range and optional camera make."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build query
        conditions = []
        params = []
        
        if start_date:
            conditions.append("date_original >= ?")
            # Add time component for start of day
            start_with_time = start_date + " 00:00:00" if len(start_date) == 10 else start_date
            params.append(start_with_time)
        if end_date:
            conditions.append("date_original <= ?")
            # Add time component for end of day
            end_with_time = end_date + " 23:59:59" if len(end_date) == 10 else end_date
            params.append(end_with_time)
        if camera_make:
            conditions.append("UPPER(camera_make) LIKE UPPER(?)")
            params.append(f"%{camera_make}%")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Modified query to include videos and exclude adjacent JPG files when corresponding RAW exists
        sql = f"""
            SELECT id, path, filename, date_original, camera_make, camera_model, 
                   lens_model, file_format, has_faces, raw_proxy_type,
                   gps_latitude, gps_longitude, iso, aperture, shutter_speed, 
                   focal_length, focal_length_35mm, exposure_compensation, film_mode,
                   width, height
            FROM images i
            WHERE ({where_clause})
            AND (
                -- Include all video files
                (UPPER(filename) LIKE '%.MP4' OR UPPER(filename) LIKE '%.MOV' OR 
                 UPPER(filename) LIKE '%.AVI' OR UPPER(filename) LIKE '%.MKV' OR 
                 UPPER(filename) LIKE '%.WEBM' OR UPPER(filename) LIKE '%.M4V')
                OR
                -- Include all non-JPG/non-video files (including RAW files)
                (UPPER(filename) NOT LIKE '%.JPG' AND UPPER(filename) NOT LIKE '%.JPEG' AND
                 UPPER(filename) NOT LIKE '%.MP4' AND UPPER(filename) NOT LIKE '%.MOV' AND
                 UPPER(filename) NOT LIKE '%.AVI' AND UPPER(filename) NOT LIKE '%.MKV' AND
                 UPPER(filename) NOT LIKE '%.WEBM' AND UPPER(filename) NOT LIKE '%.M4V')
                OR
                -- Include JPG files only if no corresponding RAW file exists
                (
                    (UPPER(filename) LIKE '%.JPG' OR UPPER(filename) LIKE '%.JPEG')
                    AND NOT EXISTS (
                        SELECT 1 FROM images r 
                        WHERE SUBSTR(r.path, 1, LENGTH(r.path) - LENGTH(r.filename)) = SUBSTR(i.path, 1, LENGTH(i.path) - LENGTH(i.filename))
                        AND SUBSTR(r.filename, 1, INSTR(r.filename, '.') - 1) = SUBSTR(i.filename, 1, INSTR(i.filename, '.') - 1)
                        AND (
                            UPPER(r.filename) LIKE '%.RW2' OR UPPER(r.filename) LIKE '%.CR2' OR 
                            UPPER(r.filename) LIKE '%.NEF' OR UPPER(r.filename) LIKE '%.ARW' OR 
                            UPPER(r.filename) LIKE '%.DNG' OR UPPER(r.filename) LIKE '%.RAF' OR 
                            UPPER(r.filename) LIKE '%.ORF' OR UPPER(r.filename) LIKE '%.SRW' OR
                            UPPER(r.filename) LIKE '%.X3F' OR UPPER(r.filename) LIKE '%.3FR' OR
                            UPPER(r.filename) LIKE '%.CR3'
                        )
                    )
                )
            )
            ORDER BY date_original DESC
        """
        
        cursor.execute(sql, params)
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_images_by_person(self, person_name):
        """Get images containing a specific person."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = """
            SELECT DISTINCT i.id, i.path, i.filename, i.date_original, i.camera_make, 
                   i.camera_model, i.lens_model, i.file_format, i.has_faces, i.raw_proxy_type,
                   i.gps_latitude, i.gps_longitude, i.iso, i.aperture, i.shutter_speed, 
                   i.focal_length, i.focal_length_35mm, i.exposure_compensation, i.film_mode, 
                   i.width, i.height, f.confidence
            FROM images i
            JOIN faces f ON i.id = f.image_id
            JOIN persons p ON f.person_id = p.id
            WHERE p.name = ?
            AND (
                -- Include all video files
                (UPPER(i.filename) LIKE '%.MP4' OR UPPER(i.filename) LIKE '%.MOV' OR 
                 UPPER(i.filename) LIKE '%.AVI' OR UPPER(i.filename) LIKE '%.MKV' OR 
                 UPPER(i.filename) LIKE '%.WEBM' OR UPPER(i.filename) LIKE '%.M4V')
                OR
                -- Include all non-JPG/non-video files (including RAW files)
                (UPPER(i.filename) NOT LIKE '%.JPG' AND UPPER(i.filename) NOT LIKE '%.JPEG' AND
                 UPPER(i.filename) NOT LIKE '%.MP4' AND UPPER(i.filename) NOT LIKE '%.MOV' AND
                 UPPER(i.filename) NOT LIKE '%.AVI' AND UPPER(i.filename) NOT LIKE '%.MKV' AND
                 UPPER(i.filename) NOT LIKE '%.WEBM' AND UPPER(i.filename) NOT LIKE '%.M4V')
                OR
                -- Include JPG files only if no corresponding RAW file exists
                (
                    (UPPER(i.filename) LIKE '%.JPG' OR UPPER(i.filename) LIKE '%.JPEG')
                    AND NOT EXISTS (
                        SELECT 1 FROM images r 
                        WHERE SUBSTR(r.path, 1, LENGTH(r.path) - LENGTH(r.filename)) = SUBSTR(i.path, 1, LENGTH(i.path) - LENGTH(i.filename))
                        AND SUBSTR(r.filename, 1, INSTR(r.filename, '.') - 1) = SUBSTR(i.filename, 1, INSTR(i.filename, '.') - 1)
                        AND (
                            UPPER(r.filename) LIKE '%.RW2' OR UPPER(r.filename) LIKE '%.CR2' OR 
                            UPPER(r.filename) LIKE '%.NEF' OR UPPER(r.filename) LIKE '%.ARW' OR 
                            UPPER(r.filename) LIKE '%.DNG' OR UPPER(r.filename) LIKE '%.RAF' OR 
                            UPPER(r.filename) LIKE '%.ORF' OR UPPER(r.filename) LIKE '%.SRW' OR
                            UPPER(r.filename) LIKE '%.X3F' OR UPPER(r.filename) LIKE '%.3FR' OR
                            UPPER(r.filename) LIKE '%.CR3'
                        )
                    )
                )
            )
            ORDER BY i.date_original DESC
        """
        
        cursor.execute(sql, (person_name,))
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_available_people(self):
        """Get list of available people for face galleries."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = """
            SELECT p.name, COUNT(f.id) as face_count
            FROM persons p
            JOIN faces f ON p.id = f.person_id
            WHERE p.name IS NOT NULL AND p.name != ''
            GROUP BY p.id, p.name
            ORDER BY face_count DESC
        """
        
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_images_from_picks(self, picks_file=None):
        """Get images from picks JSON file."""
        if picks_file is None:
            # Auto-detect picks file location
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                picks_file = '../JSON/picks.json'
            else:
                picks_file = 'JSON/picks.json'
        
        if not os.path.exists(picks_file):
            print(f"❌ Picks file not found: {picks_file}")
            return []
        
        try:
            with open(picks_file, 'r') as f:
                picks = json.load(f)
        except Exception as e:
            print(f"❌ Error reading picks file: {e}")
            return []
        
        if not isinstance(picks, list):
            print("❌ Picks file must contain an array")
            return []
        
        print(f"📋 Loaded {len(picks)} picks from {picks_file}")
        
        # Convert picks to image IDs and fetch from database
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        image_ids = []
        
        for pick_entry in picks:
            if not pick_entry:
                continue
            
            # Check if it's a numeric ID (new format)
            if isinstance(pick_entry, int) or (isinstance(pick_entry, str) and pick_entry.isdigit()):
                image_ids.append(int(pick_entry))
            
            # Legacy support: Parse gallery_name/filename format
            elif isinstance(pick_entry, str) and '/' in pick_entry:
                gallery_name, filename = pick_entry.split('/', 1)
                
                # Try to get image ID from gallery JSON first
                gallery_path = self.gallery_root / gallery_name / 'image_data.json'
                if gallery_path.exists():
                    try:
                        with open(gallery_path, 'r') as f:
                            gallery_data = json.load(f)
                        
                        for entry in gallery_data:
                            entry_filename = os.path.basename(entry.get('SourceFile', ''))
                            if entry_filename == filename and '_imageId' in entry:
                                image_ids.append(entry['_imageId'])
                                break
                    except Exception as e:
                        print(f"⚠️ Error reading gallery JSON {gallery_path}: {e}")
                        continue
            
            # Legacy fallback: direct filename lookup
            elif isinstance(pick_entry, str):
                filename = pick_entry
                
                # Remove any date prefix (YYYYMMDD_) if present
                if len(filename) > 9 and filename[8] == '_':
                    original_filename = filename[9:]
                else:
                    original_filename = filename
                
                # Look up in database
                cursor.execute("""
                    SELECT id FROM images 
                    WHERE filename = ? OR filename LIKE ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (original_filename, f"%{original_filename}"))
                
                result = cursor.fetchone()
                if result:
                    image_ids.append(result['id'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for image_id in image_ids:
            if image_id not in seen:
                seen.add(image_id)
                unique_ids.append(image_id)
        
        if not unique_ids:
            print("❌ No valid image IDs found from picks")
            conn.close()
            return []
        
        # Fetch image records
        placeholders = ','.join(['?'] * len(unique_ids))
        sql = f"""
            SELECT * FROM images 
            WHERE id IN ({placeholders})
            ORDER BY CASE id {' '.join([f'WHEN {id} THEN {i}' for i, id in enumerate(unique_ids)])} END
        """
        
        cursor.execute(sql, unique_ids)
        results = cursor.fetchall()
        conn.close()
        
        print(f"📊 Found {len(results)} images from picks")
        return results
    
    def create_gallery(self, images, gallery_name, description=""):
        """Create gallery with hard links and JSON from selected images."""
        if not images:
            print("❌ No images provided for gallery creation")
            return False
        
        # Create gallery directory
        gallery_path = self.gallery_root / gallery_name
        gallery_path.mkdir(exist_ok=True)
        
        print(f"📁 Creating gallery: {gallery_path}")
        print(f"📊 Processing {len(images)} images...")
        
        linked_count = 0
        skipped_count = 0
        error_count = 0
        gallery_data = []
        
        for row in images:
            filename = row['filename']
            image_id = row['id']
            
            # Get the correct hard link source (handles RAW files)
            source_path = self.get_hard_link_source(row)
            
            # Check if source file exists
            if not source_path or not os.path.exists(source_path):
                if source_path:
                    print(f"⚠️ Source file not found: {source_path}")
                else:
                    print(f"⚠️ No valid source found for: {filename}")
                error_count += 1
                continue
            
            # Create destination filename with date prefix if available
            # Use the actual source file's name, not the original filename
            source_filename = os.path.basename(source_path)
            if row['date_original']:
                try:
                    date_obj = datetime.fromisoformat(row['date_original'].replace(' ', 'T'))
                    date_prefix = date_obj.strftime('%Y%m%d_')
                    dest_filename = f"{date_prefix}{source_filename}"
                except:
                    dest_filename = source_filename
            else:
                dest_filename = source_filename
            
            dest_path = gallery_path / dest_filename
            
            # Create JSON object (regardless of whether file already exists)
            rel_path = os.path.relpath(dest_path, '.')
            obj = {
                'SourceFile': rel_path,
                'FileName': dest_filename,
                'FileType': row['file_format'] or os.path.splitext(filename)[1][1:].upper(),
                '_imageId': image_id,
                '_originalPath': row['path'],
                '_thumbnail': f"thumbnails/{image_id}.webp"
            }
            
            # Add optional metadata with safe access
            try:
                obj['_hasFaces'] = row['has_faces'] or 0
            except (KeyError, IndexError):
                obj['_hasFaces'] = 0
            
            # Add image dimensions if available
            try:
                if row['width'] and row['height']:
                    obj['ImageWidth'] = row['width']
                    obj['ImageHeight'] = row['height']
            except (KeyError, IndexError):
                pass
            
            # Add comprehensive EXIF metadata
            metadata_fields = [
                ('date_original', 'DateTimeOriginal'),
                ('camera_make', 'Make'),
                ('camera_model', 'Model'),
                ('lens_model', 'LensModel'),
                ('shutter_speed', 'ExposureTime'),
                ('aperture', 'FNumber'),
                ('iso', 'ISO'),
                ('exposure_compensation', 'ExposureCompensation'),
                ('focal_length', 'FocalLength'),
                ('focal_length_35mm', 'FocalLengthIn35mmFormat'),
                ('film_mode', 'FilmMode')
            ]
            
            for db_field, json_field in metadata_fields:
                try:
                    value = row[db_field]
                    if value is not None:
                        obj[json_field] = value
                except (KeyError, IndexError):
                    pass
            
            # Add GPS coordinates if available
            try:
                if row['gps_latitude'] and row['gps_longitude']:
                    obj['GPSLatitude'] = row['gps_latitude']
                    obj['GPSLongitude'] = row['gps_longitude']
            except (KeyError, IndexError):
                pass
            
            try:
                if row['confidence']:
                    obj['_faceConfidence'] = row['confidence']
            except (KeyError, IndexError):
                pass
            
            gallery_data.append(obj)
            
            # Check for duplicates and create hard link if needed
            if dest_path.exists():
                print(f"⏭️ Skipping duplicate: {dest_filename}")
                skipped_count += 1
            else:
                # Create hard link
                try:
                    os.link(source_path, dest_path)
                    print(f"✅ Linked: {dest_filename}")
                    linked_count += 1
                except OSError as e:
                    print(f"❌ Failed to link {filename}: {e}")
                    error_count += 1
        
        # Generate gallery JSON file
        json_file = gallery_path / 'image_data.json'
        print(f"\n📄 Generating gallery JSON: {json_file}")
        
        with open(json_file, 'w') as f:
            json.dump(gallery_data, f, indent=2, default=str)
        
        # Create gallery info file
        info_file = gallery_path / 'gallery_info.json'
        info_data = {
            'name': gallery_name,
            'description': description,
            'created': datetime.now().isoformat(),
            'image_count': linked_count,
            'type': 'virtual_gallery'
        }
        
        with open(info_file, 'w') as f:
            json.dump(info_data, f, indent=2)
        
        # Summary
        print(f"\n🎉 Gallery created successfully!")
        print(f"   📁 Location: {gallery_path}")
        print(f"   ✅ Linked: {linked_count} files")
        print(f"   ⏭️ Skipped: {skipped_count} duplicates")
        print(f"   ❌ Errors: {error_count} files")
        
        return True

def get_gallery_name():
    """Get gallery name from user."""
    while True:
        name = input("Gallery name: ").strip()
        if name:
            # Remove special characters but preserve spaces
            clean_name = "".join(c if c.isalnum() or c in " -_" else "" for c in name)
            return clean_name
        print("❌ Gallery name cannot be empty")

def create_date_gallery_interactive(creator):
    """Interactive date-based gallery creation."""
    print("\n📅 DATE-BASED GALLERY")
    print("-" * 30)
    
    gallery_name = get_gallery_name()
    
    print("\nDate range (leave blank for all):")
    start_date = input("Start date (YYYY-MM-DD): ").strip() or None
    end_date = input("End date (YYYY-MM-DD): ").strip() or None
    
    camera = input("Camera make filter (blank for all): ").strip() or None
    
    print(f"🗓️ Creating date-based gallery: {gallery_name}")
    if start_date or end_date or camera:
        print(f"   Date range: {start_date or 'start'} to {end_date or 'end'}")
        if camera:
            print(f"   Camera filter: {camera}")
    
    images = creator.get_images_by_date_range(start_date, end_date, camera)
    description = f"Date range: {start_date or 'all'} to {end_date or 'all'}"
    if camera:
        description += f", Camera: {camera}"
    
    if not images:
        print("❌ No matching images found")
        return
    
    success = creator.create_gallery(images, gallery_name, description)
    if success:
        print(f"\n💡 Gallery ready at: Hard Link Galleries/{gallery_name}")
    else:
        print("❌ Gallery creation failed")

def create_person_gallery_interactive(creator):
    """Interactive person-based gallery creation."""
    print("\n👤 PERSON-BASED GALLERY")
    print("-" * 30)
    
    # First, show available people
    people = creator.get_available_people()
    
    if not people:
        print("❌ No people found in database. Run face recognition first.")
        return
    
    print("Available people:")
    for i, person in enumerate(people, 1):
        print(f"  {i:2d}. {person['name']} ({person['face_count']} faces)")
    
    # Get selection
    while True:
        try:
            choice = input(f"\nSelect person (1-{len(people)}) or enter name: ").strip()
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(people):
                    person_name = people[idx]['name']
                    break
                else:
                    print(f"❌ Please enter a number between 1 and {len(people)}")
            else:
                # Check if entered name exists
                matching = [p for p in people if p['name'].lower() == choice.lower()]
                if matching:
                    person_name = matching[0]['name']
                    break
                else:
                    print(f"❌ Person '{choice}' not found")
        except ValueError:
            print("❌ Invalid input")
    
    gallery_name = get_gallery_name()
    
    print(f"👤 Creating person gallery: {gallery_name} for {person_name}")
    images = creator.get_images_by_person(person_name)
    description = f"Images containing: {person_name}"
    
    if not images:
        print("❌ No matching images found")
        return
    
    success = creator.create_gallery(images, gallery_name, description)
    if success:
        print(f"\n💡 Gallery ready at: Hard Link Galleries/{gallery_name}")
    else:
        print("❌ Gallery creation failed")

def create_picks_gallery_interactive(creator):
    """Interactive picks-based gallery creation."""
    print("\n📋 PICKS-BASED GALLERY")
    print("-" * 30)
    
    # Check if picks.json exists
    current_dir = Path.cwd()
    if current_dir.name == "Scripts":
        default_picks = '../JSON/picks.json'
    else:
        default_picks = 'JSON/picks.json'
    
    picks_file = default_picks
    
    if not os.path.exists(default_picks):
        print(f"❌ Default picks file not found: {default_picks}")
        print("Please create picks using the gallery interface first.")
        
        # Allow user to specify custom picks file
        custom_picks = input("Enter path to custom picks file (or press Enter to cancel): ").strip()
        if not custom_picks:
            return
        if not os.path.exists(custom_picks):
            print(f"❌ Custom picks file not found: {custom_picks}")
            return
        picks_file = custom_picks
    else:
        print(f"✅ Found picks file: {default_picks}")
        
        # Show option to use custom file
        use_custom = input("Use custom picks file? (y/N): ").strip().lower()
        if use_custom in ['y', 'yes']:
            custom_picks = input("Enter path to custom picks file: ").strip()
            if custom_picks and os.path.exists(custom_picks):
                picks_file = custom_picks
                print(f"✅ Using custom picks file: {custom_picks}")
            else:
                print(f"❌ Custom picks file not found, using default: {default_picks}")
                picks_file = default_picks
    
    gallery_name = get_gallery_name()
    
    print(f"📋 Creating picks-based gallery: {gallery_name}")
    images = creator.get_images_from_picks(picks_file)
    description = f"Gallery from picks: {picks_file}"
    
    if not images:
        print("❌ No matching images found")
        return
    
    success = creator.create_gallery(images, gallery_name, description)
    if success:
        print(f"\n💡 Gallery ready at: Hard Link Galleries/{gallery_name}")
    else:
        print("❌ Gallery creation failed")

def interactive_mode():
    """Run interactive gallery creation menu."""
    print("🖼️ VIRTUAL GALLERY CREATOR")
    print("=" * 40)
    
    # Check if database exists
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        print("Please run metadata extraction first.")
        sys.exit(1)
    
    creator = GalleryCreator()
    
    while True:
        print("\nSelect gallery type:")
        print("1. 📅 Date-based gallery (filter by date range and camera)")
        print("2. 👤 Person-based gallery (filter by face recognition)")
        print("3. 📋 Picks-based gallery (from saved picks)")
        print("4. ❌ Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            create_date_gallery_interactive(creator)
        elif choice == "2":
            create_person_gallery_interactive(creator)
        elif choice == "3":
            create_picks_gallery_interactive(creator)
        elif choice == "4":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")

def cli_mode():
    """Run command-line interface mode."""
    parser = argparse.ArgumentParser(description='Create virtual photo galleries')
    parser.add_argument('--type', choices=['date', 'person', 'picks'], required=True,
                        help='Gallery type: date-based, person-based, or from picks')
    parser.add_argument('--name', required=True, help='Gallery name')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--camera', help='Camera make filter')
    parser.add_argument('--person', help='Person name for face galleries')
    parser.add_argument('--picks-file', help='Path to picks.json file (auto-detected if not specified)')
    
    args = parser.parse_args()
    
    # Check if database exists
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        print("Please run metadata extraction first.")
        sys.exit(1)
    
    creator = GalleryCreator()
    
    if args.type == 'date':
        print(f"🗓️ Creating date-based gallery: {args.name}")
        if args.start_date or args.end_date or args.camera:
            print(f"   Date range: {args.start_date or 'start'} to {args.end_date or 'end'}")
            if args.camera:
                print(f"   Camera filter: {args.camera}")
        
        images = creator.get_images_by_date_range(args.start_date, args.end_date, args.camera)
        description = f"Date range: {args.start_date or 'all'} to {args.end_date or 'all'}"
        if args.camera:
            description += f", Camera: {args.camera}"
        
    elif args.type == 'person':
        if not args.person:
            # Show available people
            people = creator.get_available_people()
            if not people:
                print("❌ No people found in database. Run face recognition first.")
                sys.exit(1)
            
            print("👥 Available people:")
            for person in people:
                print(f"   • {person['name']} ({person['face_count']} faces)")
            sys.exit(0)
        
        print(f"👤 Creating person gallery: {args.name} for {args.person}")
        images = creator.get_images_by_person(args.person)
        description = f"Images containing: {args.person}"
    
    elif args.type == 'picks':
        print(f"📋 Creating picks-based gallery: {args.name}")
        images = creator.get_images_from_picks(args.picks_file)
        description = f"Gallery from picks: {args.picks_file or 'auto-detected picks.json'}"
    
    if not images:
        print("❌ No matching images found")
        sys.exit(1)
    
    # Create the gallery
    success = creator.create_gallery(images, args.name, description)
    
    if success:
        print(f"\n💡 Gallery ready at: Hard Link Galleries/{args.name}")
    else:
        print("❌ Gallery creation failed")
        sys.exit(1)

def main():
    """Main entry point - detect CLI args or run interactive mode."""
    if len(sys.argv) > 1:
        # CLI mode - arguments provided
        cli_mode()
    else:
        # Interactive mode - no arguments
        interactive_mode()

if __name__ == "__main__":
    main()