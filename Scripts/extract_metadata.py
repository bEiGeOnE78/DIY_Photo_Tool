#!/usr/bin/env python3
"""
Image Metadata Extraction Script
Crawls photo directories and extracts EXIF metadata into SQLite database.
"""

import os
import sqlite3
import hashlib
import subprocess
import json
from datetime import datetime
from pathlib import Path
import argparse
from typing import Optional, Dict, Any

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    from PIL import ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True  # Handle truncated images
except ImportError:
    print("PIL/Pillow not found. Install with: pip install Pillow")
    exit(1)

class MetadataExtractor:
    
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp', '.heic', '.raw', '.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
    RAW_FORMATS = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw'}
    VIDEO_FORMATS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
    EXIFTOOL_PATH = "/usr/bin/vendor_perl/exiftool"
    FFMPEG_PATH = "/usr/bin/ffmpeg"
    FFPROBE_PATH = "/usr/bin/ffprobe"
    
    def __init__(self, db_path=None):
        if db_path is None:
            # Auto-detect database location
            from pathlib import Path
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                db_path = "image_metadata.db"  # Same directory
            else:
                db_path = "Scripts/image_metadata.db"  # Scripts subdirectory
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_file_hash(self, file_path: str, chunk_size: int = 8192) -> str:
        """Generate SHA-256 hash of file for duplicate detection."""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            print(f"Error hashing {file_path}: {e}")
            return ""
    
    def extract_gps_info(self, exif_dict: Dict[str, Any]) -> tuple:
        """Extract GPS coordinates from EXIF data."""
        gps_info = exif_dict.get('GPSInfo')
        if not gps_info or not isinstance(gps_info, dict):
            return None, None, None
            
        def convert_to_degrees(value):
            """Convert GPS coordinates to decimal degrees."""
            if not value or len(value) != 3:
                return None
            try:
                degrees, minutes, seconds = value
                return float(degrees) + float(minutes)/60 + float(seconds)/3600
            except (TypeError, ValueError):
                return None
        
        try:
            lat = gps_info.get(2)  # GPSLatitude
            lat_ref = gps_info.get(1)  # GPSLatitudeRef
            lon = gps_info.get(4)  # GPSLongitude
            lon_ref = gps_info.get(3)  # GPSLongitudeRef
            alt = gps_info.get(6)  # GPSAltitude
            
            latitude = convert_to_degrees(lat) if lat else None
            longitude = convert_to_degrees(lon) if lon else None
            altitude = float(alt) if alt and isinstance(alt, (int, float)) else None
            
            if latitude and lat_ref == 'S':
                latitude = -latitude
            if longitude and lon_ref == 'W':
                longitude = -longitude
                
            return latitude, longitude, altitude
        except Exception:
            return None, None, None
    
    def parse_datetime(self, date_string: str) -> Optional[datetime]:
        """Parse EXIF datetime string."""
        if not date_string:
            return None
        try:
            return datetime.strptime(date_string, '%Y:%m:%d %H:%M:%S')
        except ValueError:
            try:
                return datetime.strptime(date_string[:19], '%Y:%m:%d %H:%M:%S')
            except ValueError:
                return None
    
    def extract_exiftool_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata using exiftool for better accuracy."""
        exif_data = {}
        
        if not os.path.exists(self.EXIFTOOL_PATH):
            return exif_data
            
        try:
            # Use the same exiftool command as the bash script
            cmd = [
                self.EXIFTOOL_PATH, "-json",
                "-DateTimeOriginal", "-Make", "-Model", "-LensModel", "-LensMake",
                "-ExposureTime", "-FNumber", "-ISO", "-ExposureCompensation", 
                "-FocalLength", "-FocalLengthIn35mmFormat", "-FilmMode",
                "-GPSLatitude", "-GPSLongitude", "-GPSAltitude",
                "-FileName", "-FileType",
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                if data and len(data) > 0:
                    exif_data = data[0]
                    
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            # Fall back silently, we'll still have PIL data
            pass
            
        return exif_data
    
    def detect_raw_proxy_status(self, file_path: str) -> tuple:
        """Detect RAW proxy status and return (proxy_type, adjacent_jpg_path)."""
        file_path = Path(file_path)
        
        # Only process RAW files
        if file_path.suffix.lower() not in self.RAW_FORMATS:
            return 'none', None
        
        # Check for adjacent JPG file (same name, different extension)
        jpg_extensions = ['.jpg', '.jpeg', '.JPG', '.JPEG']
        for ext in jpg_extensions:
            adjacent_jpg = file_path.with_suffix(ext)
            if adjacent_jpg.exists():
                return 'original_jpg', str(adjacent_jpg)
        
        return 'none', None

    def parse_gps_coordinate(self, coord_str: str) -> Optional[float]:
        """Parse GPS coordinate from exiftool format like '50 deg 34' 26.36" N' to decimal degrees."""
        if not coord_str:
            return None
            
        try:
            # Remove direction indicator and split
            coord_clean = coord_str.replace('"', '').strip()
            direction = coord_clean[-1] if coord_clean[-1] in 'NSEW' else ''
            if direction:
                coord_clean = coord_clean[:-1].strip()
            
            # Parse degrees, minutes, seconds
            parts = coord_clean.replace('deg', ' ').replace("'", ' ').split()
            parts = [p for p in parts if p]  # Remove empty strings
            
            if len(parts) >= 1:
                degrees = float(parts[0])
                minutes = float(parts[1]) if len(parts) > 1 else 0
                seconds = float(parts[2]) if len(parts) > 2 else 0
                
                decimal = degrees + minutes/60 + seconds/3600
                
                # Apply direction
                if direction in 'SW':
                    decimal = -decimal
                    
                return decimal
        except (ValueError, IndexError):
            pass
            
        return None
    
    def extract_video_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from video files using ffprobe."""
        metadata = {}
        
        if not os.path.exists(self.FFPROBE_PATH):
            return metadata
            
        try:
            # Use ffprobe to extract video metadata
            cmd = [
                self.FFPROBE_PATH, "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                
                # Extract format information
                format_info = data.get('format', {})
                metadata['duration'] = float(format_info.get('duration', 0))
                metadata['file_format'] = format_info.get('format_name', '')
                metadata['bit_rate'] = int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None
                
                # Parse creation time from format tags
                format_tags = format_info.get('tags', {})
                creation_time = format_tags.get('creation_time') or format_tags.get('com.apple.quicktime.creationdate')
                if creation_time:
                    try:
                        # Handle different datetime formats
                        if 'T' in creation_time:
                            parsed_date = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
                        else:
                            parsed_date = datetime.strptime(creation_time, '%Y:%m:%d %H:%M:%S')
                        metadata['date_original'] = parsed_date
                    except (ValueError, TypeError):
                        pass
                
                # Extract video stream information
                video_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
                if video_streams:
                    video_stream = video_streams[0]  # Use first video stream
                    metadata['width'] = int(video_stream.get('width', 0))
                    metadata['height'] = int(video_stream.get('height', 0))
                    metadata['codec'] = video_stream.get('codec_name', '')
                    metadata['frame_rate'] = video_stream.get('r_frame_rate', '')
                    
                    # Extract rotation information
                    if 'tags' in video_stream and 'rotate' in video_stream['tags']:
                        metadata['rotation'] = int(video_stream['tags']['rotate'])
                
                # Extract audio stream information
                audio_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
                if audio_streams:
                    audio_stream = audio_streams[0]
                    metadata['audio_codec'] = audio_stream.get('codec_name', '')
                    metadata['audio_channels'] = int(audio_stream.get('channels', 0)) if audio_stream.get('channels') else None
                
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            print(f"Error extracting video metadata from {file_path}: {e}")
            
        return metadata
    
    def generate_video_thumbnail(self, file_path: str, output_path: str, timestamp: float = 1.0) -> bool:
        """Generate a thumbnail from video at specified timestamp."""
        if not os.path.exists(self.FFMPEG_PATH):
            return False
            
        try:
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            cmd = [
                self.FFMPEG_PATH, "-i", file_path,
                "-ss", str(timestamp),  # Seek to timestamp
                "-vframes", "1",  # Extract 1 frame
                "-q:v", "2",  # High quality
                "-y",  # Overwrite output file
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0 and os.path.exists(output_path)
            
        except Exception as e:
            print(f"Error generating thumbnail for {file_path}: {e}")
            return False
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract comprehensive metadata from image or video file."""
        metadata = {
            'path': file_path,
            'filename': os.path.basename(file_path),
            'file_size': 0,
            'last_modified': None,
        }
        
        # Check if this is a video file
        is_video = Path(file_path).suffix.lower() in self.VIDEO_FORMATS
        if is_video:
            metadata['file_type'] = 'video'
            return self._extract_video_file_metadata(file_path, metadata)
        else:
            metadata['file_type'] = 'image'
            return self._extract_image_file_metadata(file_path, metadata)
    
    def _extract_video_file_metadata(self, file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata specifically for video files."""
        try:
            # File system metadata
            stat = os.stat(file_path)
            metadata['file_size'] = stat.st_size
            metadata['last_modified'] = datetime.fromtimestamp(stat.st_mtime)
            
            # Extract video-specific metadata (duration, codecs, etc.)
            video_metadata = self.extract_video_metadata(file_path)
            metadata.update(video_metadata)
            
            # Extract camera/lens metadata using exiftool (same as for images)
            exiftool_data = self.extract_exiftool_metadata(file_path)
            if exiftool_data:
                # Map camera metadata
                metadata.update({
                    'camera_make': exiftool_data.get('Make'),
                    'camera_model': exiftool_data.get('Model'),
                    'lens_make': exiftool_data.get('LensMake'),
                    'lens_model': exiftool_data.get('LensModel'),
                    'iso': exiftool_data.get('ISO'),
                    'aperture': exiftool_data.get('FNumber'),
                    'shutter_speed': exiftool_data.get('ExposureTime'),
                    'focal_length': exiftool_data.get('FocalLength'),
                    'focal_length_35mm': exiftool_data.get('FocalLengthIn35mmFormat'),
                    'exposure_compensation': exiftool_data.get('ExposureCompensation'),
                    'film_mode': exiftool_data.get('FilmMode'),
                })
                
                # Handle date from exiftool if not already set from video metadata
                if exiftool_data.get('DateTimeOriginal') and not metadata.get('date_original'):
                    parsed_date = self.parse_datetime(exiftool_data['DateTimeOriginal'])
                    if parsed_date:
                        metadata['date_original'] = parsed_date
            
        except Exception as e:
            print(f"✗ Error processing video {file_path}: {e}")
            
        return metadata
    
    def _extract_image_file_metadata(self, file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata specifically for image files."""
        
        # Detect RAW proxy status
        proxy_type, adjacent_jpg_path = self.detect_raw_proxy_status(file_path)
        metadata['raw_proxy_type'] = proxy_type
        
        # For RAW files with adjacent JPGs, use the JPG for metadata extraction
        processing_file = adjacent_jpg_path if adjacent_jpg_path else file_path
        
        try:
            # File system metadata
            stat = os.stat(file_path)
            metadata['file_size'] = stat.st_size
            metadata['last_modified'] = datetime.fromtimestamp(stat.st_mtime)
            
            # Extract metadata using exiftool (more reliable for lens info)
            # For RAW files, use the RAW file for exiftool but adjacent JPG for PIL
            exiftool_data = self.extract_exiftool_metadata(file_path)
            
            # Try to open image and extract EXIF with PIL as fallback
            try:
                with Image.open(processing_file) as img:
                    metadata['width'] = img.width
                    metadata['height'] = img.height
                    metadata['file_format'] = img.format
                
                # Extract EXIF data with PIL
                exif = img.getexif()
                exif_dict = {}
                if exif:
                    for tag_id, value in exif.items():
                        try:
                            tag = TAGS.get(tag_id, tag_id)
                            exif_dict[tag] = value
                        except Exception:
                            continue  # Skip problematic EXIF tags
                    
                    # Map EXIF tags to our schema, preferring exiftool data
                    metadata.update({
                        'camera_make': exiftool_data.get('Make') or exif_dict.get('Make'),
                        'camera_model': exiftool_data.get('Model') or exif_dict.get('Model'),
                        'lens_make': exiftool_data.get('LensMake') or exif_dict.get('LensMake'),
                        'lens_model': exiftool_data.get('LensModel') or exif_dict.get('LensModel'),
                        'orientation': exif_dict.get('Orientation'),
                        'iso': exiftool_data.get('ISO') or exif_dict.get('ISOSpeedRatings'),
                        'aperture': exiftool_data.get('FNumber') or exif_dict.get('FNumber'),
                        'shutter_speed': exiftool_data.get('ExposureTime') or str(exif_dict.get('ExposureTime', '')),
                        'focal_length': exiftool_data.get('FocalLength') or exif_dict.get('FocalLength'),
                        'focal_length_35mm': exiftool_data.get('FocalLengthIn35mmFormat') or exif_dict.get('FocalLengthIn35mmFilm'),
                        'exposure_compensation': exiftool_data.get('ExposureCompensation'),
                        'film_mode': exiftool_data.get('FilmMode'),
                        'flash': str(exif_dict.get('Flash', '')),
                        'white_balance': str(exif_dict.get('WhiteBalance', '')),
                        'exposure_mode': str(exif_dict.get('ExposureMode', '')),
                        'metering_mode': str(exif_dict.get('MeteringMode', '')),
                        'color_space': str(exif_dict.get('ColorSpace', '')),
                    })
                    
                    # Parse dates (prefer exiftool for DateTimeOriginal)
                    if exiftool_data.get('DateTimeOriginal'):
                        parsed_date = self.parse_datetime(exiftool_data['DateTimeOriginal'])
                        if parsed_date:
                            metadata['date_original'] = parsed_date
                    
                    # Fill in other dates from PIL
                    for exif_date, db_field in [
                        ('DateTime', 'date_taken'),
                        ('DateTimeOriginal', 'date_original'),
                        ('DateTimeDigitized', 'date_digitized')
                    ]:
                        if db_field not in metadata and exif_date in exif_dict:
                            parsed_date = self.parse_datetime(str(exif_dict[exif_date]))
                            if parsed_date:
                                metadata[db_field] = parsed_date
                    
                    # Extract GPS coordinates (prefer exiftool)
                    if exiftool_data.get('GPSLatitude') and exiftool_data.get('GPSLongitude'):
                        try:
                            lat = self.parse_gps_coordinate(exiftool_data['GPSLatitude'])
                            lon = self.parse_gps_coordinate(exiftool_data['GPSLongitude'])
                            if lat is not None and lon is not None:
                                metadata['gps_latitude'] = lat
                                metadata['gps_longitude'] = lon
                        except Exception:
                            pass  # Fall back to PIL GPS extraction
                        
                        if exiftool_data.get('GPSAltitude'):
                            try:
                                metadata['gps_altitude'] = float(exiftool_data['GPSAltitude'].split()[0])
                            except Exception:
                                pass
                    else:
                        # Fall back to PIL GPS extraction
                        lat, lon, alt = self.extract_gps_info(exif_dict)
                        if lat is not None:
                            metadata['gps_latitude'] = lat
                        if lon is not None:
                            metadata['gps_longitude'] = lon
                        if alt is not None:
                            metadata['gps_altitude'] = alt
            
            except Exception as e:
                # Image couldn't be opened, but we still have file metadata
                # Try to get basic info from exiftool only
                if exiftool_data:
                    metadata.update({
                        'camera_make': exiftool_data.get('Make'),
                        'camera_model': exiftool_data.get('Model'),
                        'lens_make': exiftool_data.get('LensMake'),
                        'lens_model': exiftool_data.get('LensModel'),
                        'iso': exiftool_data.get('ISO'),
                        'aperture': exiftool_data.get('FNumber'),
                        'shutter_speed': exiftool_data.get('ExposureTime'),
                        'focal_length': exiftool_data.get('FocalLength'),
                        'focal_length_35mm': exiftool_data.get('FocalLengthIn35mmFormat'),
                        'exposure_compensation': exiftool_data.get('ExposureCompensation'),
                        'film_mode': exiftool_data.get('FilmMode'),
                    })
                    
                    if exiftool_data.get('DateTimeOriginal'):
                        parsed_date = self.parse_datetime(exiftool_data['DateTimeOriginal'])
                        if parsed_date:
                            metadata['date_original'] = parsed_date
                    
                    if exiftool_data.get('GPSLatitude') and exiftool_data.get('GPSLongitude'):
                        try:
                            lat = self.parse_gps_coordinate(exiftool_data['GPSLatitude'])
                            lon = self.parse_gps_coordinate(exiftool_data['GPSLongitude'])
                            if lat is not None and lon is not None:
                                metadata['gps_latitude'] = lat
                                metadata['gps_longitude'] = lon
                        except Exception:
                            pass
                    
                    # Extract image dimensions from exiftool as fallback
                    try:
                        width = exiftool_data.get('ImageWidth') or exiftool_data.get('ExifImageWidth')
                        height = exiftool_data.get('ImageHeight') or exiftool_data.get('ExifImageHeight')
                        if width and height:
                            metadata['width'] = int(width)
                            metadata['height'] = int(height)
                        
                        # Get file format from exiftool if available
                        if exiftool_data.get('FileType'):
                            metadata['file_format'] = exiftool_data['FileType']
                    except Exception:
                        pass
                        
                print(f"⚠ Could not read image data from {os.path.basename(processing_file)}: {type(e).__name__}")
                        
        except Exception as e:
            print(f"✗ Error processing {file_path}: {e}")
            
        return metadata
    
    def file_exists_in_db(self, file_path: str) -> Optional[datetime]:
        """Check if file exists in database and return its last_modified time."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT last_modified FROM images WHERE path = ?", (file_path,))
        result = cursor.fetchone()
        if result:
            return datetime.fromisoformat(result[0]) if result[0] else None
        return None
    
    def insert_or_update_metadata(self, metadata: Dict[str, Any], force_update: bool = False) -> int:
        """Insert or update image metadata in database."""
        cursor = self.conn.cursor()
        
        # Check if record exists
        existing_modified = self.file_exists_in_db(metadata['path'])
        
        if existing_modified is None:
            # Insert new record
            columns = ', '.join(metadata.keys())
            placeholders = ', '.join(['?' for _ in metadata])
            sql = f"INSERT INTO images ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, list(metadata.values()))
            image_id = cursor.lastrowid
            print(f"✓ Added: {metadata['filename']}")
        else:
            # Update existing record if file was modified OR force_update is True
            if force_update or metadata['last_modified'] > existing_modified:
                set_clause = ', '.join([f"{k} = ?" for k in metadata.keys() if k != 'path'])
                values = [v for k, v in metadata.items() if k != 'path']
                values.append(metadata['path'])
                
                sql = f"UPDATE images SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE path = ?"
                cursor.execute(sql, values)
                
                # Get image_id
                cursor.execute("SELECT id FROM images WHERE path = ?", (metadata['path'],))
                image_id = cursor.fetchone()[0]
                print(f"↻ Updated: {metadata['filename']}")
            else:
                # No update needed
                cursor.execute("SELECT id FROM images WHERE path = ?", (metadata['path'],))
                image_id = cursor.fetchone()[0]
                return image_id
        
        self.conn.commit()
        return image_id
    
    def cleanup_deleted_files(self, base_directory: str):
        """Remove database entries for files that no longer exist."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, path FROM images WHERE path LIKE ?", (f"{base_directory}%",))
        db_files = cursor.fetchall()
        
        deleted_count = 0
        for file_id, file_path in db_files:
            if not os.path.exists(file_path):
                cursor.execute("DELETE FROM images WHERE id = ?", (file_id,))
                print(f"🗑 Removed deleted file: {os.path.basename(file_path)}")
                deleted_count += 1
        
        if deleted_count > 0:
            self.conn.commit()
            print(f"Cleaned up {deleted_count} deleted files from database")
        else:
            print("No deleted files found in database")

    def crawl_directory(self, directory: str, include_hash: bool = False, recursive: bool = True, cleanup: bool = True, force_update: bool = False, videos_only: bool = False):
        """Crawl directory and extract metadata from all images or videos only."""
        directory = Path(directory)
        if not directory.exists():
            print(f"Directory not found: {directory}")
            return
        
        # Clean up deleted files first if requested
        if cleanup:
            print("Checking for deleted files...")
            self.cleanup_deleted_files(str(directory))
            print()
        
        print(f"Crawling: {directory}")
        if videos_only:
            print("Videos-only mode: Only processing video files")
        if force_update:
            print("Force update mode: Will re-extract metadata for all existing files")
        pattern = "**/*" if recursive else "*"
        
        processed = 0
        skipped = 0
        errors = 0
        
        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue
                
            if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
                continue
            
            # If videos_only mode, skip non-video files
            if videos_only and file_path.suffix.lower() not in self.VIDEO_FORMATS:
                continue
            
            # Skip JPG files that are adjacent to RAW files
            if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                # Check if there's an adjacent RAW file (case insensitive)
                has_adjacent_raw = False
                for raw_ext in ['.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw']:
                    adjacent_raw = file_path.with_suffix(raw_ext)
                    adjacent_raw_upper = file_path.with_suffix(raw_ext.upper())
                    if adjacent_raw.exists() or adjacent_raw_upper.exists():
                        raw_name = adjacent_raw.name if adjacent_raw.exists() else adjacent_raw_upper.name
                        print(f"⏭️ Skipping {file_path.name} - adjacent to RAW file {raw_name}")
                        skipped += 1
                        has_adjacent_raw = True
                        break
                if has_adjacent_raw:
                    continue
            
            try:
                metadata = self.extract_metadata(str(file_path))
                
                # Normalize path to always start with "Master Photo Library"
                path_str = str(file_path)
                if "Master Photo Library" in path_str:
                    # Extract everything from "Master Photo Library" onwards
                    master_lib_index = path_str.find("Master Photo Library")
                    normalized_path = path_str[master_lib_index:]
                    metadata['path'] = normalized_path
                
                if include_hash:
                    metadata['file_hash'] = self.get_file_hash(str(file_path))
                
                image_id = self.insert_or_update_metadata(metadata, force_update=force_update)
                processed += 1
                
                # Print additional info for RAW files
                if metadata.get('raw_proxy_type') == 'original_jpg':
                    print(f"   📄 RAW file with adjacent JPG - using JPG for processing")
                elif metadata.get('raw_proxy_type') == 'none' and file_path.suffix.lower() in self.RAW_FORMATS:
                    print(f"   🎞️ RAW file without adjacent JPG - will need proxy generation")
                
                if processed % 100 == 0:
                    print(f"Processed {processed} images...")
                    
            except KeyboardInterrupt:
                print("\nCrawl interrupted by user")
                break
            except Exception as e:
                print(f"✗ Error processing {file_path}: {e}")
                errors += 1
        
        print(f"\nCrawl complete:")
        print(f"  Processed: {processed}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")

def main():
    parser = argparse.ArgumentParser(description='Extract image metadata to SQLite database')
    parser.add_argument('directory', help='Directory to crawl for images')
    parser.add_argument('--db', default=None, help='Database file path (auto-detected if not specified)')
    parser.add_argument('--hash', action='store_true', help='Generate file hashes (slower)')
    parser.add_argument('--no-recursive', action='store_true', help='Don\'t crawl subdirectories')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup of deleted files')
    parser.add_argument('--force', action='store_true', help='Force re-extraction of metadata for existing files')
    parser.add_argument('--videos-only', action='store_true', help='Only process video files (useful for re-extracting camera metadata from videos)')
    
    args = parser.parse_args()
    
    # Auto-detect database path if not specified
    if args.db is None:
        from pathlib import Path
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            args.db = "image_metadata.db"  # Same directory
        else:
            args.db = "Scripts/image_metadata.db"  # Scripts subdirectory
    
    # Create database if it doesn't exist
    if not os.path.exists(args.db):
        print(f"Creating database: {args.db}")
        from create_db import create_database
        create_database(args.db)
    
    extractor = MetadataExtractor(args.db)
    extractor.crawl_directory(
        args.directory, 
        include_hash=args.hash,
        recursive=not args.no_recursive,
        cleanup=not args.no_cleanup,
        force_update=args.force,
        videos_only=args.videos_only
    )

if __name__ == "__main__":
    main()