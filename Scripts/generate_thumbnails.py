#!/usr/bin/env python3
"""
Thumbnail Generator
Creates optimized thumbnails by database ID for fast gallery loading.
Stores thumbnails on main drive for maximum performance.
"""

import os
import sqlite3
import argparse
import subprocess
import tempfile
import json
from pathlib import Path
from PIL import Image, ImageOps
import hashlib

class ThumbnailGenerator:
    def __init__(self, db_path=None, thumb_dir="thumbnails"):
        if db_path is None:
            # Auto-detect database location
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                db_path = "image_metadata.db"  # Same directory
            else:
                db_path = "Scripts/image_metadata.db"  # Scripts subdirectory
        self.db_path = db_path
        
        # Handle thumbnail directory path
        if thumb_dir == "thumbnails":
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                thumb_dir = "../thumbnails"  # Up one level from Scripts
            # else use "thumbnails" as-is for main directory
        
        self.thumb_dir = Path(thumb_dir).expanduser()
        self.thumb_dir.mkdir(parents=True, exist_ok=True)
        
        # Single thumbnail size - 284px on longest edge
        self.thumb_size = 284
        
        # Video formats and ffmpeg path
        self.video_formats = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        self.ffmpeg_path = "/usr/bin/ffmpeg"
        
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def load_picks(self):
        """Load picks from JSON file."""
        # Auto-detect picks file location
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            picks_file = "../JSON/picks.json"
        else:
            picks_file = "JSON/picks.json"
            
        if not os.path.exists(picks_file):
            print(f"❌ Picks file not found: {picks_file}")
            return None
        
        try:
            with open(picks_file, 'r') as f:
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
                    return image_id
            
            return None
            
        except Exception as e:
            print(f"   ❌ Error reading gallery JSON: {e}")
            return None
    
    def get_image_ids_from_picks(self, picks):
        """Convert picks entries to image IDs."""
        if not picks:
            return []
        
        cursor = self.conn.cursor()
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
                image_id = self.get_image_id_from_gallery_json(gallery_name, filename)
                if image_id:
                    image_ids.append(image_id)
            
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
                    SELECT id FROM images 
                    WHERE filename = ? OR filename LIKE ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (original_filename, f"%{original_filename}"))
                
                result = cursor.fetchone()
                if result:
                    image_ids.append(result[0])
        
        return image_ids
    
    def get_thumbnail_path(self, image_id: int) -> Path:
        """Get thumbnail file path for an image ID."""
        return self.thumb_dir / f"{image_id}.webp"
    
    def get_thumbnail_url(self, image_id: int) -> str:
        """Get file:// URL for thumbnail."""
        thumb_path = self.get_thumbnail_path(image_id)
        return f"file://{thumb_path.absolute()}"
    
    def needs_thumbnail(self, image_id: int) -> bool:
        """Check if thumbnail needs to be generated/updated."""
        thumb_path = self.get_thumbnail_path(image_id)
        
        if not thumb_path.exists():
            return True
            
        # Check if source image is newer than thumbnail
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        
        if not row:
            return False
            
        # Get the correct source file (proxy, adjacent JPG, or original)
        source_file_path = self.get_hard_link_source(row)
        if not source_file_path:
            return False  # Can't generate thumbnail without valid source
            
        source_path = Path(source_file_path)
        if not source_path.exists():
            return False
            
        source_mtime = source_path.stat().st_mtime
        thumb_mtime = thumb_path.stat().st_mtime
        
        return source_mtime > thumb_mtime
    
    def get_hard_link_source(self, row):
        """Determine the correct hard link source for a file, handling RAW files and videos."""
        original_path = row['path']
        image_id = row['id']
        
        try:
            raw_proxy_type = row['raw_proxy_type']
        except (KeyError, IndexError):
            raw_proxy_type = None
        
        # For videos, always use the original master file (not proxies) for thumbnail generation
        
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
                # Regular file (JPG, PNG, HEIC, videos, etc.) - use original with path resolution
                return self._resolve_file_path(original_path)
    
    def _resolve_file_path(self, file_path):
        """Resolve file path, handling relative paths when running from Scripts directory."""
        if os.path.isabs(file_path):
            return file_path if os.path.exists(file_path) else None
        
        # For relative paths, try different locations
        potential_paths = [
            file_path,  # Try as-is first
            os.path.join('..', file_path),  # Try one level up (if running from Scripts)
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                return path
        
        # File not found in any location
        return None

    def generate_thumbnail(self, image_id: int) -> bool:
        """Generate thumbnail for an image (284px longest edge)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Image ID {image_id} not found in database")
            return False
            
        # Get the correct source file (proxy, adjacent JPG, or original)
        source_file_path = self.get_hard_link_source(row)
        if not source_file_path:
            print(f"⏭️ Skipping thumbnail generation for {row['filename']} - no valid source")
            return False
            
        source_path = Path(source_file_path)
        if not source_path.exists():
            print(f"❌ Source file not found: {source_path}")
            return False
            
        thumb_path = self.get_thumbnail_path(image_id)
        
        # Check if this is a video file
        try:
            file_type = row['file_type']
            if file_type == 'video':
                return self._generate_video_thumbnail(source_path, thumb_path, row, image_id)
        except (KeyError, IndexError):
            pass
        
        # Check by file extension if file_type is not available
        if source_path.suffix.lower() in self.video_formats:
            return self._generate_video_thumbnail(source_path, thumb_path, row, image_id)
        
        try:
            # Try PIL first for images
            return self._generate_with_pil(source_path, thumb_path, row, image_id)
            
        except Exception as pil_error:
            # If PIL fails (e.g., for HEIC files), try sips on macOS
            if source_path.suffix.lower() in ['.heic', '.heif']:
                print(f"⚠️ PIL failed for HEIC file, trying sips: {pil_error}")
                return self._generate_with_sips(source_path, thumb_path, row, image_id)
            else:
                print(f"❌ Failed to generate thumbnail for {row['filename']}: {pil_error}")
                return False
    
    def _generate_with_pil(self, source_path, thumb_path, row, image_id):
        """Generate thumbnail using PIL."""
        # Open and process image
        with Image.open(source_path) as img:
            # Handle EXIF orientation with robust fallback
            try:
                # Use ImageOps.exif_transpose for automatic orientation handling
                img = ImageOps.exif_transpose(img)
            except (AttributeError, TypeError, OSError):
                # Fallback to manual orientation handling for problematic files
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
            
            # Convert to RGB if necessary (for WebP)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Calculate size to make longest edge 284px
            width, height = img.size
            if width > height:
                new_width = self.thumb_size
                new_height = int(height * self.thumb_size / width)
            else:
                new_height = self.thumb_size
                new_width = int(width * self.thumb_size / height)
            
            # Resize image
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save as WebP for better compression
            img.save(thumb_path, 'WEBP', quality=85, optimize=True)
            
        print(f"✅ Generated thumbnail for {row['filename']} (ID: {image_id}) - {new_width}x{new_height}")
        return True
    
    def _generate_with_sips(self, source_path, thumb_path, row, image_id):
        """Generate thumbnail using macOS sips command for HEIC files."""
        try:
            # Use sips to convert HEIC to JPEG first, then process with PIL
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_jpg:
                temp_jpg_path = temp_jpg.name
            
            # Convert HEIC to JPEG using sips with max dimension
            cmd = [
                'sips', 
                '-s', 'format', 'jpeg',
                '-Z', str(self.thumb_size),  # Resize to fit within thumb_size
                str(source_path),
                '--out', temp_jpg_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"sips failed: {result.stderr}")
            
            # Now convert the JPEG to WebP using PIL with orientation handling
            with Image.open(temp_jpg_path) as img:
                # Handle EXIF orientation with robust fallback (in case sips didn't handle it)
                try:
                    img = ImageOps.exif_transpose(img)
                except (AttributeError, TypeError, OSError):
                    # Fallback to manual orientation handling for problematic files
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
                
                img.save(thumb_path, 'WEBP', quality=85, optimize=True)
                width, height = img.size
            
            # Clean up temp file
            os.unlink(temp_jpg_path)
            
            print(f"✅ Generated HEIC thumbnail for {row['filename']} (ID: {image_id}) - {width}x{height}")
            return True
            
        except Exception as e:
            # Clean up temp file if it exists
            if 'temp_jpg_path' in locals() and os.path.exists(temp_jpg_path):
                os.unlink(temp_jpg_path)
            raise e
    
    def _generate_video_thumbnail(self, source_path, thumb_path, row, image_id):
        """Generate thumbnail from video file using ffmpeg."""
        if not os.path.exists(self.ffmpeg_path):
            print(f"❌ ffmpeg not found at {self.ffmpeg_path}")
            return False
            
        try:
            # Create temporary file for video frame extraction
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_frame:
                temp_frame_path = temp_frame.name
            
            # Get video duration from database if available, otherwise use default
            try:
                duration_seconds = float(row['duration']) if row['duration'] else 1.0
            except (ValueError, KeyError):
                duration_seconds = 1.0
            
            # Use 50% of duration or 1 second, whichever is smaller
            seek_time = min(1.0, duration_seconds * 0.5)
            
            # Extract frame using calculated seek time
            cmd = [
                self.ffmpeg_path, "-i", str(source_path),
                "-ss", str(seek_time),  # Smart seek time
                "-vframes", "1",  # Extract 1 frame
                "-q:v", "2",  # High quality
                "-y",  # Overwrite output file
                temp_frame_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"ffmpeg failed: {result.stderr}")
            
            # Now process the extracted frame with PIL to create thumbnail
            with Image.open(temp_frame_path) as img:
                # Convert to RGB if necessary (for WebP)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Calculate size to make longest edge 284px
                width, height = img.size
                if width > height:
                    new_width = self.thumb_size
                    new_height = int(height * self.thumb_size / width)
                else:
                    new_height = self.thumb_size
                    new_width = int(width * self.thumb_size / height)
                
                # Resize image
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save as WebP for better compression
                img.save(thumb_path, 'WEBP', quality=85, optimize=True)
            
            # Clean up temp file
            os.unlink(temp_frame_path)
            
            print(f"✅ Generated video thumbnail for {row['filename']} (ID: {image_id}) - {new_width}x{new_height}")
            return True
            
        except Exception as e:
            # Clean up temp file if it exists
            if 'temp_frame_path' in locals() and os.path.exists(temp_frame_path):
                os.unlink(temp_frame_path)
            raise e
    
    def generate_thumbnail_if_needed(self, image_id: int) -> bool:
        """Generate thumbnail for an image if needed."""
        if self.needs_thumbnail(image_id):
            return self.generate_thumbnail(image_id)
        return True
    
    def batch_generate(self, limit: int = None, force: bool = False, heic_only: bool = False, video_only: bool = False, specific_ids: list = None) -> dict:
        """Generate thumbnails for multiple images."""
        
        if specific_ids:
            # Use the provided list of image IDs
            image_ids = specific_ids
        else:
            # Query database for image IDs
            cursor = self.conn.cursor()
            
            # Build query with optional filters
            if heic_only:
                if limit:
                    cursor.execute("""
                        SELECT id FROM images 
                        WHERE (file_format LIKE '%HEIC%' OR UPPER(filename) LIKE '%.HEIC')
                        ORDER BY date_original DESC 
                        LIMIT ?
                    """, (limit,))
                else:
                    cursor.execute("""
                        SELECT id FROM images 
                        WHERE (file_format LIKE '%HEIC%' OR UPPER(filename) LIKE '%.HEIC')
                        ORDER BY date_original DESC
                    """)
            elif video_only:
                if limit:
                    cursor.execute("""
                        SELECT id FROM images 
                        WHERE file_type = 'video'
                        ORDER BY date_original DESC 
                        LIMIT ?
                    """, (limit,))
                else:
                    cursor.execute("""
                        SELECT id FROM images 
                        WHERE file_type = 'video'
                        ORDER BY date_original DESC
                    """)
            else:
                if limit:
                    cursor.execute("SELECT id FROM images ORDER BY date_original DESC LIMIT ?", (limit,))
                else:
                    cursor.execute("SELECT id FROM images ORDER BY date_original DESC")
                
            image_ids = [row[0] for row in cursor.fetchall()]
        
        stats = {
            'total': len(image_ids),
            'generated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        if specific_ids:
            print(f"📊 Processing {stats['total']} picked images...")
        elif heic_only:
            print(f"📊 Processing {stats['total']} HEIC images...")
        elif video_only:
            print(f"📊 Processing {stats['total']} video files...")
        else:
            print(f"📊 Processing {stats['total']} images...")
        
        for i, image_id in enumerate(image_ids):
            try:
                if not force and not self.needs_thumbnail(image_id):
                    stats['skipped'] += 1
                    continue
                
                if self.generate_thumbnail(image_id):
                    stats['generated'] += 1
                else:
                    stats['errors'] += 1
                    
                # Progress update every 10 images
                if (i + 1) % 10 == 0:
                    print(f"📈 Progress: {i + 1}/{stats['total']} images processed")
                    
            except KeyboardInterrupt:
                print("\n⚠️ Generation interrupted by user")
                break
            except Exception as e:
                print(f"❌ Error processing image ID {image_id}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def clean_orphaned(self) -> int:
        """Remove thumbnails for images no longer in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM images")
        valid_ids = {row[0] for row in cursor.fetchall()}
        
        removed = 0
        for thumb_file in self.thumb_dir.glob("*.webp"):
            try:
                # Extract image ID from filename (no size suffix now)
                image_id = int(thumb_file.stem)
                if image_id not in valid_ids:
                    thumb_file.unlink()
                    removed += 1
            except ValueError:
                # Invalid filename format, skip
                continue
                
        return removed
    
    def get_stats(self) -> dict:
        """Get thumbnail generation statistics."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images")
        total_images = cursor.fetchone()[0]
        
        total_thumbs = len(list(self.thumb_dir.glob("*.webp")))
        cache_size = sum(f.stat().st_size for f in self.thumb_dir.glob("*.webp"))
        
        return {
            'total_images': total_images,
            'total_thumbnails': total_thumbs,
            'cache_size_mb': cache_size / (1024 * 1024),
            'cache_path': str(self.thumb_dir)
        }

def main():
    parser = argparse.ArgumentParser(description='Generate thumbnails for photo gallery')
    parser.add_argument('--db', default=None, help='Database file path (auto-detected if not specified)')
    parser.add_argument('--thumb-dir', default='thumbnails', 
                       help='Thumbnail cache directory')
    parser.add_argument('--limit', type=int, help='Limit number of images to process')
    parser.add_argument('--force', action='store_true', help='Regenerate existing thumbnails')
    parser.add_argument('--clean', action='store_true', help='Remove orphaned thumbnails')
    parser.add_argument('--stats', action='store_true', help='Show thumbnail statistics')
    parser.add_argument('--image-id', type=int, help='Generate thumbnails for specific image ID')
    parser.add_argument('--heic-only', action='store_true', help='Generate thumbnails only for HEIC files')
    parser.add_argument('--video-only', action='store_true', help='Generate thumbnails only for video files')
    parser.add_argument('--picks-only', action='store_true', help='Generate thumbnails only for images in picks.json')
    
    args = parser.parse_args()
    
    generator = ThumbnailGenerator(args.db, args.thumb_dir)
    
    if args.stats:
        stats = generator.get_stats()
        print("\n📊 THUMBNAIL STATISTICS")
        print("-" * 30)
        print(f"Total images in database: {stats['total_images']}")
        print(f"Cache directory: {stats['cache_path']}")
        print(f"Cache size: {stats['cache_size_mb']:.1f} MB")
        print(f"Total thumbnails: {stats['total_thumbnails']}")
        coverage = (stats['total_thumbnails'] / stats['total_images']) * 100 if stats['total_images'] > 0 else 0
        print(f"Coverage: {coverage:.1f}%")
        return
    
    if args.clean:
        print("🧹 Cleaning orphaned thumbnails...")
        removed = generator.clean_orphaned()
        print(f"✅ Removed {removed} orphaned thumbnails")
        return
    
    if args.image_id:
        print(f"🎯 Generating thumbnail for image ID {args.image_id}...")
        success = generator.generate_thumbnail(args.image_id)
        if success:
            print("✅ Thumbnail generated successfully")
        else:
            print("❌ Failed to generate thumbnail")
        return
    
    # Handle picks-only mode
    if args.picks_only:
        print("🚀 Starting thumbnail generation for picked images...")
        picks = generator.load_picks()
        if not picks:
            print("❌ No picks found or picks file error")
            return
        
        image_ids = generator.get_image_ids_from_picks(picks)
        if not image_ids:
            print("❌ No valid image IDs found in picks")
            return
        
        print(f"📋 Found {len(image_ids)} images in picks")
        stats = generator.batch_generate(force=args.force, specific_ids=image_ids)
    else:
        # Batch generation
        if args.heic_only:
            print("🚀 Starting HEIC thumbnail generation...")
        elif args.video_only:
            print("🚀 Starting video thumbnail generation...")
        else:
            print("🚀 Starting thumbnail generation...")
        stats = generator.batch_generate(args.limit, args.force, args.heic_only, args.video_only)
    
    print(f"\n📊 GENERATION COMPLETE")
    print("-" * 30)
    print(f"Total images: {stats['total']}")
    print(f"Generated: {stats['generated']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    
    if stats['generated'] > 0:
        print(f"\n💡 Thumbnails stored in: {generator.thumb_dir}")
        print("💡 Use file:// URLs in galleries for fast loading")

if __name__ == "__main__":
    main()
