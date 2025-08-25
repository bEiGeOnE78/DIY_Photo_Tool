#!/usr/bin/env python3
"""
Flexible Gallery Creator with Search Functionality
Creates virtual galleries using search strings to filter by metadata like people, dates, cameras, or lenses.
"""

import sqlite3
import os
import sys
import json
import argparse
import re
import calendar
from datetime import datetime, date
from pathlib import Path

# Configuration - auto-detect paths
if os.path.basename(os.getcwd()) == "Scripts":
    DB_FILE = "image_metadata.db"
    GALLERY_ROOT = "../Hard Link Galleries"
else:
    DB_FILE = "Scripts/image_metadata.db"
    GALLERY_ROOT = "Hard Link Galleries"

class SearchGalleryCreator:
    def __init__(self):
        self.db_path = DB_FILE
        self.gallery_root = Path(GALLERY_ROOT)
        self.gallery_root.mkdir(exist_ok=True)
        
    def get_hard_link_source(self, row):
        """Determine the correct hard link source for a file, handling RAW files and videos."""
        original_path = row['path']
        image_id = row['id']
        
        try:
            raw_proxy_type = row['raw_proxy_type']
        except (KeyError, IndexError):
            raw_proxy_type = None
        
        # Check if this is a video file
        try:
            file_type = row['file_type']
            if file_type == 'video':
                # For video files, check if proxy exists
                video_proxy_path = f"Video Proxies/{image_id}.mp4"
                if os.path.exists(video_proxy_path):
                    return video_proxy_path
                else:
                    # Fall back to original video file
                    return original_path
        except (KeyError, IndexError):
            pass
        
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
            original_path_obj = Path(original_path)
            for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                adjacent_jpg = original_path_obj.with_suffix(ext)
                if adjacent_jpg.exists():
                    return str(adjacent_jpg)
            print(f"⚠️ Adjacent JPG not found for {row['filename']}")
            return None
        else:
            # Check if this is a RAW file that needs adjacent JPG detection
            original_path_obj = Path(original_path)
            file_ext = original_path_obj.suffix.lower()
            
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
    
    def parse_search_string(self, search_string):
        """Parse search string into structured search criteria."""
        if not search_string:
            return {}
        
        search_string = search_string.strip()
        criteria = {}
        
        # Default to only still images (backward compatibility)
        criteria['file_type'] = 'image_only'
        
        # Check for video-related keywords
        video_patterns = [
            r'\b(incl(?:ude)?\s+videos?)\b',
            r'\b(include\s+videos?)\b',
            r'\b(including\s+videos?)\b',
            r'\b(inc\s+videos?)\b',
            r'\b(with\s+videos?)\b',
            r'\b(\+\s*videos?)\b'
        ]
        
        video_only_patterns = [
            r'\b(only\s+videos?)\b',
            r'\b(videos?\s+only)\b',
            r'\b(just\s+videos?)\b'
        ]
        
        # Check for video inclusion patterns
        for pattern in video_patterns:
            if re.search(pattern, search_string, re.IGNORECASE):
                criteria['file_type'] = 'include_videos'
                # Remove the pattern from search string to avoid text search conflicts
                search_string = re.sub(pattern, '', search_string, flags=re.IGNORECASE)
                break
        
        # Check for video-only patterns (overrides include)
        for pattern in video_only_patterns:
            if re.search(pattern, search_string, re.IGNORECASE):
                criteria['file_type'] = 'video_only'
                # Remove the pattern from search string to avoid text search conflicts
                search_string = re.sub(pattern, '', search_string, flags=re.IGNORECASE)
                break
        
        # Month name to number mapping
        month_names = {
            'january': '01', 'jan': '01',
            'february': '02', 'feb': '02',
            'march': '03', 'mar': '03',
            'april': '04', 'apr': '04',
            'may': '05',
            'june': '06', 'jun': '06',
            'july': '07', 'jul': '07',
            'august': '08', 'aug': '08',
            'september': '09', 'sep': '09', 'sept': '09',
            'october': '10', 'oct': '10',
            'november': '11', 'nov': '11',
            'december': '12', 'dec': '12'
        }
        
        # First, convert month names to numeric format in the search string
        original_search = search_string
        
        # Handle month range patterns first (e.g., "June 2024 to August 2024")
        month_range_pattern = r'\b([a-zA-Z]+)\s+(\d{4})\s+to\s+([a-zA-Z]+)\s+(\d{4})\b'
        month_range_match = re.search(month_range_pattern, search_string, re.IGNORECASE)
        if month_range_match:
            start_month_name = month_range_match.group(1).lower()
            start_year = month_range_match.group(2)
            end_month_name = month_range_match.group(3).lower()
            end_year = month_range_match.group(4)
            
            if start_month_name in month_names and end_month_name in month_names:
                start_month_num = month_names[start_month_name]
                end_month_num = month_names[end_month_name]
                # Replace with numeric range format
                replacement = f"{start_year}-{start_month_num} to {end_year}-{end_month_num}"
                search_string = re.sub(month_range_pattern, replacement, search_string, flags=re.IGNORECASE)
        
        # Handle single month-year patterns
        for month_name, month_num in month_names.items():
            # Pattern for "Month YYYY" (e.g., "June 2025", "Dec 2023")
            month_year_pattern = rf'\b{re.escape(month_name)}\s+(\d{{4}})\b'
            match = re.search(month_year_pattern, search_string, re.IGNORECASE)
            if match:
                year = match.group(1)
                # Replace "Month YYYY" with "YYYY-MM"
                replacement = f"{year}-{month_num}"
                search_string = re.sub(month_year_pattern, replacement, search_string, flags=re.IGNORECASE)
                break
            
            # Pattern for "YYYY Month" (e.g., "2025 June", "2023 Dec")
            year_month_pattern = rf'\b(\d{{4}})\s+{re.escape(month_name)}\b'
            match = re.search(year_month_pattern, search_string, re.IGNORECASE)
            if match:
                year = match.group(1)
                # Replace "YYYY Month" with "YYYY-MM"
                replacement = f"{year}-{month_num}"
                search_string = re.sub(year_month_pattern, replacement, search_string, flags=re.IGNORECASE)
                break
        
        # Check for date range patterns first (YYYY-YYYY, YYYY-MM to YYYY-MM, etc.)
        date_range_patterns = [
            r'\b(\d{4})-(\d{1,2})-(\d{1,2})\s+to\s+(\d{4})-(\d{1,2})-(\d{1,2})\b',  # YYYY-MM-DD to YYYY-MM-DD
            r'\b(\d{4})-(\d{1,2})\s+to\s+(\d{4})-(\d{1,2})\b',                       # YYYY-MM to YYYY-MM
            r'\b(\d{4})\s+to\s+(\d{4})\b',                                            # YYYY to YYYY
            r'\b(\d{4})-(\d{4})\b'                                                    # YYYY-YYYY (shorthand)
        ]
        
        for pattern in date_range_patterns:
            match = re.search(pattern, search_string, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 6:  # Full date range YYYY-MM-DD to YYYY-MM-DD
                    start_date = f"{groups[0]}-{groups[1]:0>2}-{groups[2]:0>2}"
                    end_date = f"{groups[3]}-{groups[4]:0>2}-{groups[5]:0>2}"
                elif len(groups) == 4:  # Month range YYYY-MM to YYYY-MM
                    start_date = f"{groups[0]}-{groups[1]:0>2}"
                    end_date = f"{groups[2]}-{groups[3]:0>2}"
                elif len(groups) == 2:  # Year range
                    start_date = groups[0]
                    end_date = groups[1]
                
                criteria['date_range'] = {'start': start_date, 'end': end_date}
                break
        
        # If no date range found, check for single date patterns
        if 'date_range' not in criteria:
            date_patterns = [
                r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b',  # YYYY-MM-DD
                r'\b(\d{4})-(\d{1,2})\b',             # YYYY-MM
                r'\b(\d{4})\b'                        # YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, search_string)
                if match:
                    if len(match.groups()) == 3:  # YYYY-MM-DD
                        criteria['date'] = f"{match.group(1)}-{match.group(2):0>2}-{match.group(3):0>2}"
                    elif len(match.groups()) == 2:  # YYYY-MM
                        criteria['date'] = f"{match.group(1)}-{match.group(2):0>2}"
                    else:  # YYYY
                        criteria['date'] = match.group(1)
                    break
        
        # Check for lens patterns (common focal lengths)
        lens_patterns = [
            r'\b(\d+)mm\b',                    # e.g., "27mm", "85mm"
            r'\b(\d+)-(\d+)mm\b',              # e.g., "24-70mm"
            r'\b(\d+\.?\d*)mm\b'               # e.g., "2.8mm", "12.5mm"
        ]
        
        for pattern in lens_patterns:
            match = re.search(pattern, search_string, re.IGNORECASE)
            if match:
                criteria['lens'] = match.group(0)
                break
        
        # Check for camera brands
        camera_brands = ['canon', 'nikon', 'sony', 'fuji', 'fujifilm', 'panasonic', 'olympus', 'leica', 'pentax']
        for brand in camera_brands:
            if brand.lower() in search_string.lower():
                criteria['camera'] = brand
                break
        
        # Check for aperture patterns
        aperture_match = re.search(r'f/?(\d+\.?\d*)', search_string, re.IGNORECASE)
        if aperture_match:
            criteria['aperture'] = float(aperture_match.group(1))
        
        # Check for ISO patterns
        iso_match = re.search(r'iso\s*(\d+)', search_string, re.IGNORECASE)
        if iso_match:
            criteria['iso'] = int(iso_match.group(1))
        
        # Everything else is treated as a general text search (could be person name, location, etc.)
        # Remove recognized patterns to get the remaining text
        remaining_text = search_string
        for key, value in criteria.items():
            if key == 'date':
                remaining_text = re.sub(r'\b\d{4}(-\d{1,2})?(-\d{1,2})?\b', '', remaining_text)
            elif key == 'date_range':
                # Remove date range patterns
                remaining_text = re.sub(r'\b\d{4}(-\d{1,2})?(-\d{1,2})?\s+to\s+\d{4}(-\d{1,2})?(-\d{1,2})?\b', '', remaining_text, flags=re.IGNORECASE)
                remaining_text = re.sub(r'\b\d{4}-\d{4}\b', '', remaining_text)
            elif key == 'lens':
                remaining_text = re.sub(r'\b\d+(-\d+)?\.?\d*mm\b', '', remaining_text, flags=re.IGNORECASE)
            elif key == 'camera':
                remaining_text = re.sub(re.escape(value), '', remaining_text, flags=re.IGNORECASE)
            elif key == 'aperture':
                remaining_text = re.sub(r'f/?(\d+\.?\d*)', '', remaining_text, flags=re.IGNORECASE)
            elif key == 'iso':
                remaining_text = re.sub(r'iso\s*(\d+)', '', remaining_text, flags=re.IGNORECASE)
        
        # Clean up remaining text
        remaining_text = re.sub(r'\s+', ' ', remaining_text).strip()
        if remaining_text:
            criteria['text'] = remaining_text
        
        return criteria
    
    def build_search_query(self, criteria):
        """Build SQL query from search criteria."""
        base_query = """
            SELECT DISTINCT i.id, i.path, i.filename, i.date_original, i.camera_make, 
                   i.camera_model, i.lens_model, i.file_format, i.has_faces, i.raw_proxy_type, 
                   i.gps_latitude, i.gps_longitude, i.iso, i.aperture, i.shutter_speed, 
                   i.focal_length, i.focal_length_35mm, i.exposure_compensation, i.film_mode, 
                   i.width, i.height, i.file_type
            FROM images i
        """
        
        # Add person join if needed
        if 'text' in criteria:
            base_query += """
                LEFT JOIN faces f ON i.id = f.image_id
                LEFT JOIN persons p ON f.person_id = p.id
            """
        
        conditions = []
        params = []
        
        # File type filtering
        file_type_filter = criteria.get('file_type', 'image_only')
        if file_type_filter == 'image_only':
            # Default: only still images (exclude videos)
            conditions.append("(i.file_type IS NULL OR i.file_type = 'image')")
        elif file_type_filter == 'video_only':
            # Only videos
            conditions.append("i.file_type = 'video'")
        elif file_type_filter == 'include_videos':
            # Include both images and videos (no filter needed)
            pass
        
        # Date filtering (single date or range)
        if 'date_range' in criteria:
            start_date = criteria['date_range']['start']
            end_date = criteria['date_range']['end']
            
            # Handle different date formats for ranges
            if len(start_date) == 4:  # Year only
                start_condition = f"{start_date}-01-01 00:00:00"
                end_condition = f"{end_date}-12-31 23:59:59"
            elif len(start_date) == 7:  # Year-Month
                start_condition = f"{start_date}-01 00:00:00"
                # Calculate last day of end month
                year, month = map(int, end_date.split('-'))
                last_day = calendar.monthrange(year, month)[1]
                end_condition = f"{end_date}-{last_day:02d} 23:59:59"
            else:  # Full date
                start_condition = f"{start_date} 00:00:00"
                end_condition = f"{end_date} 23:59:59"
            
            conditions.append("date_original >= ? AND date_original <= ?")
            params.extend([start_condition, end_condition])
            
        elif 'date' in criteria:
            date_str = criteria['date']
            if len(date_str) == 4:  # Year only
                conditions.append("date_original LIKE ?")
                params.append(f"{date_str}%")
            elif len(date_str) == 7:  # Year-Month
                conditions.append("date_original LIKE ?")
                params.append(f"{date_str}%")
            else:  # Full date
                conditions.append("DATE(date_original) = ?")
                params.append(date_str)
        
        # Camera filtering
        if 'camera' in criteria:
            conditions.append("(UPPER(camera_make) LIKE UPPER(?) OR UPPER(camera_model) LIKE UPPER(?))")
            camera_term = f"%{criteria['camera']}%"
            params.extend([camera_term, camera_term])
        
        # Lens filtering - only search lens model name, not focal length
        # Use more precise matching to avoid confusion between focal lengths and apertures
        if 'lens' in criteria:
            lens_value = criteria['lens']
            # If it's a focal length pattern (e.g., "35mm", "24-70mm"), be more specific
            if 'mm' in lens_value:
                # For focal length searches, ensure we're matching focal length patterns not aperture
                focal_length_num = lens_value.replace('mm', '')
                if '-' in focal_length_num:
                    # Zoom lens pattern like "24-70mm"
                    conditions.append("UPPER(lens_model) LIKE UPPER(?)")
                    lens_term = f"%{lens_value}%"
                    params.append(lens_term)
                else:
                    # Prime lens pattern like "35mm" - match as focal length, not aperture
                    # Look for patterns like "35mm" or " 35mm" but not "3.5" or "F3.5"
                    conditions.append("(UPPER(lens_model) LIKE UPPER(?) AND UPPER(lens_model) NOT LIKE UPPER(?))")
                    lens_term = f"%{lens_value}%"
                    aperture_pattern = f"%F{focal_length_num}.%"  # Exclude aperture patterns like "F3.5"
                    params.extend([lens_term, aperture_pattern])
            else:
                # Non-focal length search, use simple pattern matching
                conditions.append("UPPER(lens_model) LIKE UPPER(?)")
                lens_term = f"%{lens_value}%"
                params.append(lens_term)
        
        # Aperture filtering
        if 'aperture' in criteria:
            conditions.append("aperture = ?")
            params.append(criteria['aperture'])
        
        # ISO filtering
        if 'iso' in criteria:
            conditions.append("iso = ?")
            params.append(criteria['iso'])
        
        # Text search (person names, locations, etc.)
        if 'text' in criteria:
            text_conditions = []
            text_term = f"%{criteria['text']}%"
            
            # Search in person names with word boundary matching
            # Check for exact word matches and beginning of names to avoid "ben" matching "Ruben"
            search_text = criteria['text'].strip()
            person_conditions = []
            
            # Exact match (case insensitive)
            person_conditions.append("UPPER(p.name) = UPPER(?)")
            params.append(search_text)
            
            # Word at beginning of name (e.g., "Ben Smith")
            person_conditions.append("UPPER(p.name) LIKE UPPER(?)")
            params.append(f"{search_text} %")
            
            # Word after space (e.g., "John Ben" or "Mary Ben Smith")
            person_conditions.append("UPPER(p.name) LIKE UPPER(?)")
            params.append(f"% {search_text} %")
            
            # Word at end of name (e.g., "Smith Ben")
            person_conditions.append("UPPER(p.name) LIKE UPPER(?)")
            params.append(f"% {search_text}")
            
            text_conditions.append(f"({' OR '.join(person_conditions)})")
            
            # Search in location names
            text_conditions.append("UPPER(location_name) LIKE UPPER(?)")
            params.append(text_term)
            
            # Search in camera/lens info
            text_conditions.append("UPPER(camera_make) LIKE UPPER(?)")
            params.append(text_term)
            
            text_conditions.append("UPPER(camera_model) LIKE UPPER(?)")
            params.append(text_term)
            
            text_conditions.append("UPPER(lens_model) LIKE UPPER(?)")
            params.append(text_term)
            
            # Search in filename
            text_conditions.append("UPPER(filename) LIKE UPPER(?)")
            params.append(text_term)
            
            conditions.append(f"({' OR '.join(text_conditions)})")
        
        # Add RAW file handling (exclude adjacent JPGs when RAW exists) - only for images
        if file_type_filter != 'video_only':
            raw_condition = """
                (
                    -- For videos, include all
                    i.file_type = 'video'
                    OR
                    -- For images: Include all non-JPG files (including RAW files)
                    (
                        (i.file_type IS NULL OR i.file_type = 'image')
                        AND (
                            UPPER(i.filename) NOT LIKE '%.JPG' AND UPPER(i.filename) NOT LIKE '%.JPEG'
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
                    )
                )
            """
            conditions.append(raw_condition)
        
        # Build final query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        final_query = f"{base_query} WHERE {where_clause} ORDER BY i.date_original DESC"
        
        return final_query, params
    
    def search_images(self, search_string):
        """Search for images based on search string."""
        if not search_string:
            return []
        
        criteria = self.parse_search_string(search_string)
        print(f"🔍 Search criteria: {criteria}")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query, params = self.build_search_query(criteria)
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            print(f"📊 Found {len(results)} matching images")
            return results
        except Exception as e:
            print(f"❌ Search query error: {e}")
            conn.close()
            return []
    
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
    
    def create_face_sample_gallery(self):
        """Create a special gallery with face samples for each person."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all people with their face samples
        sql = """
            SELECT p.id, p.name, 
                   GROUP_CONCAT(i.id || '|' || i.filename || '|' || f.confidence) as samples
            FROM persons p
            JOIN faces f ON p.id = f.person_id
            JOIN images i ON f.image_id = i.id
            WHERE p.name IS NOT NULL AND p.name != ''
            GROUP BY p.id, p.name
            ORDER BY p.name
        """
        
        cursor.execute(sql)
        people = cursor.fetchall()
        conn.close()
        
        if not people:
            print("❌ No people found for face sample gallery")
            return []
        
        # Create a sample gallery with one image per person
        sample_images = []
        for person in people:
            if person['samples']:
                # Get the first (highest confidence) sample
                samples = person['samples'].split(',')
                if samples:
                    image_id, filename, confidence = samples[0].split('|')
                    
                    # Get full image record
                    conn = sqlite3.connect(self.db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT * FROM images WHERE id = ?", (int(image_id),))
                    image = cursor.fetchone()
                    conn.close()
                    
                    if image:
                        sample_images.append(image)
        
        return sample_images
    
    def create_gallery(self, images, gallery_name, description=""):
        """Create gallery with hard links and JSON from selected images."""
        if not images:
            print("❌ No images provided for gallery creation")
            return False
        
        # Create gallery directory
        gallery_path = self.gallery_root / gallery_name
        gallery_exists = gallery_path.exists()
        gallery_path.mkdir(exist_ok=True)
        
        # Load existing gallery data if gallery already exists
        existing_gallery_data = []
        existing_image_ids = set()
        json_file = gallery_path / 'image_data.json'
        
        if gallery_exists and json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    existing_gallery_data = json.load(f)
                # Track existing image IDs to avoid duplicates
                for item in existing_gallery_data:
                    if '_imageId' in item:
                        existing_image_ids.add(item['_imageId'])
                print(f"📂 Found existing gallery with {len(existing_gallery_data)} images")
            except Exception as e:
                print(f"⚠️ Error reading existing gallery JSON: {e}")
                existing_gallery_data = []
        
        if gallery_exists:
            print(f"📁 Adding to existing gallery: {gallery_path}")
        else:
            print(f"📁 Creating new gallery: {gallery_path}")
        print(f"📊 Processing {len(images)} new images...")
        
        linked_count = 0
        skipped_count = 0
        error_count = 0
        new_gallery_data = []
        
        for row in images:
            filename = row['filename']
            image_id = row['id']
            
            # Skip if this image is already in the gallery
            if image_id in existing_image_ids:
                print(f"⏭️ Skipping existing image: {filename} (ID: {image_id})")
                skipped_count += 1
                continue
            
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
            
            new_gallery_data.append(obj)
            
            # Create hard link (we already checked for image ID duplicates above)
            if dest_path.exists():
                print(f"⏭️ File already exists: {dest_filename}")
                # Note: This can happen if same image has different filename due to date prefix
                linked_count += 1  # Count as successful since image is in gallery
            else:
                # Create hard link
                try:
                    os.link(source_path, dest_path)
                    print(f"✅ Linked: {dest_filename}")
                    linked_count += 1
                except OSError as e:
                    print(f"❌ Failed to link {filename}: {e}")
                    error_count += 1
        
        # Combine existing and new gallery data
        combined_gallery_data = existing_gallery_data + new_gallery_data
        
        # Generate gallery JSON file
        json_file = gallery_path / 'image_data.json'
        if existing_gallery_data:
            print(f"\n📄 Updating gallery JSON: {json_file}")
            print(f"   📂 Existing images: {len(existing_gallery_data)}")
            print(f"   ➕ New images: {len(new_gallery_data)}")
            print(f"   📊 Total images: {len(combined_gallery_data)}")
        else:
            print(f"\n📄 Creating gallery JSON: {json_file}")
        
        with open(json_file, 'w') as f:
            json.dump(combined_gallery_data, f, indent=2, default=str)
        
        # Create or update gallery info file
        info_file = gallery_path / 'gallery_info.json'
        
        # Load existing info if available
        existing_info = {}
        if info_file.exists():
            try:
                with open(info_file, 'r') as f:
                    existing_info = json.load(f)
            except Exception as e:
                print(f"⚠️ Error reading existing gallery info: {e}")
        
        # Update info data
        info_data = {
            'name': gallery_name,
            'description': description or existing_info.get('description', ''),
            'created': existing_info.get('created', datetime.now().isoformat()),
            'last_updated': datetime.now().isoformat(),
            'image_count': len(combined_gallery_data),
            'type': existing_info.get('type', 'search_gallery')
        }
        
        with open(info_file, 'w') as f:
            json.dump(info_data, f, indent=2)
        
        # Summary
        if existing_gallery_data:
            print(f"\n🎉 Gallery updated successfully!")
            print(f"   📁 Location: {gallery_path}")
            print(f"   ➕ Added: {linked_count} new files")
            print(f"   ⏭️ Skipped: {skipped_count} duplicates")
            print(f"   📊 Total: {len(combined_gallery_data)} images")
            print(f"   ❌ Errors: {error_count} files")
        else:
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

def interactive_mode():
    """Run interactive gallery creation with search functionality."""
    print("🔍 SEARCH-BASED GALLERY CREATOR")
    print("=" * 50)
    
    # Check if database exists
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        print("Please run metadata extraction first.")
        sys.exit(1)
    
    creator = SearchGalleryCreator()
    
    while True:
        print("\nSelect gallery type:")
        print("1. 🔍 Search-based gallery (flexible metadata search)")
        print("2. 📋 Picks-based gallery (from saved picks)")
        print("3. 👥 Face sample gallery (one image per person)")
        print("4. ❌ Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            print("\n🔍 SEARCH-BASED GALLERY")
            print("-" * 40)
            print("Enter search terms to filter images by:")
            print("• People: 'Ben', 'Sarah', etc.")
            print("• Dates: '2023', '2023-12', '2023-12-25'")
            print("• Date ranges: '2023 to 2024', '2023-01 to 2023-06', '2023-2024'")
            print("• Lenses: '27mm', '85mm', '24-70mm'")
            print("• Cameras: 'Fuji', 'Canon', 'Sony'")
            print("• Aperture: 'f/2.8', 'f/1.4'")
            print("• ISO: 'ISO400', 'ISO1600'")
            print("• File types: 'incl videos', 'include videos', 'only videos'")
            print("• Combinations: 'Ben 27mm fuji', '2023 to 2024 85mm incl videos'")
            print("• Note: By default, only still images are included")
            print()
            
            search_string = input("Search string: ").strip()
            if not search_string:
                continue
            
            gallery_name = get_gallery_name()
            
            print(f"🔍 Searching for: {search_string}")
            images = creator.search_images(search_string)
            
            if not images:
                print("❌ No matching images found")
                continue
            
            description = f"Search: {search_string}"
            success = creator.create_gallery(images, gallery_name, description)
            if success:
                print(f"\n💡 Gallery ready at: Hard Link Galleries/{gallery_name}")
        
        elif choice == "2":
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
                    continue
                if not os.path.exists(custom_picks):
                    print(f"❌ Custom picks file not found: {custom_picks}")
                    continue
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
                continue
            
            success = creator.create_gallery(images, gallery_name, description)
            if success:
                print(f"\n💡 Gallery ready at: Hard Link Galleries/{gallery_name}")
        
        elif choice == "3":
            print("\n👥 FACE SAMPLE GALLERY")
            print("-" * 30)
            
            gallery_name = get_gallery_name()
            
            print(f"👥 Creating face sample gallery: {gallery_name}")
            images = creator.create_face_sample_gallery()
            description = "Face sample gallery - one image per person"
            
            if not images:
                print("❌ No face samples found")
                continue
            
            success = creator.create_gallery(images, gallery_name, description)
            if success:
                print(f"\n💡 Gallery ready at: Hard Link Galleries/{gallery_name}")
        
        elif choice == "4":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")

def cli_mode():
    """Run command-line interface mode."""
    parser = argparse.ArgumentParser(description='Create virtual photo galleries with flexible search')
    parser.add_argument('search_string', nargs='?', help='Search string for filtering images')
    parser.add_argument('--name', required=True, help='Gallery name')
    parser.add_argument('--picks-file', help='Path to picks.json file for picks-based gallery')
    parser.add_argument('--face-samples', action='store_true', help='Create face sample gallery')
    
    args = parser.parse_args()
    
    # Check if database exists
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        print("Please run metadata extraction first.")
        sys.exit(1)
    
    creator = SearchGalleryCreator()
    
    if args.face_samples:
        print(f"👥 Creating face sample gallery: {args.name}")
        images = creator.create_face_sample_gallery()
        description = "Face sample gallery - one image per person"
    elif args.picks_file:
        print(f"📋 Creating picks-based gallery: {args.name}")
        images = creator.get_images_from_picks(args.picks_file)
        description = f"Gallery from picks: {args.picks_file}"
    elif args.search_string:
        print(f"🔍 Creating search-based gallery: {args.name}")
        print(f"🔍 Search string: {args.search_string}")
        images = creator.search_images(args.search_string)
        description = f"Search: {args.search_string}"
    else:
        print("❌ No search criteria provided. Use --help for usage information.")
        sys.exit(1)
    
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