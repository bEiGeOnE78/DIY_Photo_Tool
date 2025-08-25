#!/usr/bin/env python3
"""
Video Proxy Generator
Creates compressed h.264 video proxies for fast gallery loading and playback.
Optimized for retina displays with good quality/size balance.
"""

import os
import sqlite3
import subprocess
import argparse
import tempfile
import json
from datetime import datetime
from pathlib import Path

class VideoProxyGenerator:
    def __init__(self, db_path=None, proxy_dir="Video Proxies"):
        if db_path is None:
            # Auto-detect database location
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                db_path = "image_metadata.db"  # Same directory
            else:
                db_path = "Scripts/image_metadata.db"  # Scripts subdirectory
        
        self.db_path = db_path
        self.proxy_dir = Path(proxy_dir)
        self.proxy_dir.mkdir(exist_ok=True)
        
        # FFmpeg settings for h.264 proxy generation
        # Keeps original resolution, optimized for good quality/size balance
        self.ffmpeg_path = "/usr/bin/ffmpeg"
        self.crf = 23  # Constant Rate Factor - 23 is good quality/size balance
        self.preset = "medium"  # Good compression/speed balance
        
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_proxy_path(self, video_id: int) -> Path:
        """Get proxy file path for a video ID."""
        return self.proxy_dir / f"{video_id}.mp4"
    
    def needs_proxy(self, video_id: int, original_path: str) -> bool:
        """Check if video needs proxy generation/update."""
        proxy_path = self.get_proxy_path(video_id)
        
        if not proxy_path.exists():
            return True
        
        # Check if original video is newer than proxy
        if not os.path.exists(original_path):
            return False
        
        original_mtime = os.path.getmtime(original_path)
        proxy_mtime = os.path.getmtime(proxy_path)
        
        return original_mtime > proxy_mtime
    
    def get_video_info(self, video_path: str) -> dict:
        """Get video information using ffprobe."""
        if not os.path.exists("/usr/bin/ffprobe"):
            return {}
        
        try:
            cmd = [
                "/usr/bin/ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-select_streams", "v:0", video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                import json
                data = json.loads(result.stdout)
                
                streams = data.get('streams', [])
                if streams:
                    video_stream = streams[0]
                    return {
                        'width': int(video_stream.get('width', 0)),
                        'height': int(video_stream.get('height', 0)),
                        'codec': video_stream.get('codec_name', ''),
                        'duration': float(video_stream.get('duration', 0))
                    }
        except Exception as e:
            print(f"Warning: Could not get video info for {video_path}: {e}")
        
        return {}
    
    def calculate_dimensions(self, original_width: int, original_height: int) -> tuple:
        """Keep original dimensions but ensure they are even (required for h.264)."""
        target_width = original_width
        target_height = original_height
        
        # Ensure dimensions are even (required for h.264)
        if target_width % 2 != 0:
            target_width -= 1
        if target_height % 2 != 0:
            target_height -= 1
        
        return target_width, target_height
    
    def generate_proxy(self, video_id: int, video_path: str, correction_lut: str = None, style_lut: str = None, force: bool = False) -> bool:
        """Generate h.264 proxy for a video."""
        if not os.path.exists(self.ffmpeg_path):
            print(f"❌ ffmpeg not found at {self.ffmpeg_path}")
            return False
        
        if not os.path.exists(video_path):
            print(f"❌ Original video not found: {video_path}")
            return False
        
        proxy_path = self.get_proxy_path(video_id)
        
        # Get original video info
        video_info = self.get_video_info(video_path)
        original_width = video_info.get('width', 1920)
        original_height = video_info.get('height', 1080)
        
        # Calculate target dimensions
        target_width, target_height = self.calculate_dimensions(original_width, original_height)
        
        print(f"🎬 Processing: {os.path.basename(video_path)} (ID: {video_id})")
        print(f"   📐 Original: {original_width}x{original_height} → Target: {target_width}x{target_height}")
        
        try:
            # Create temporary output file first (safer for concurrent access)
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False, dir=self.proxy_dir) as temp_file:
                temp_path = temp_file.name
            
            # Build FFmpeg command with proper LUT handling
            cmd = [self.ffmpeg_path, "-i", video_path]
            
            # Handle HALDCLUT PNG as separate input
            has_haldclut = (style_lut and os.path.exists(style_lut) and 
                           style_lut.lower().endswith('.png'))
            
            if has_haldclut:
                cmd.extend(["-i", style_lut])
                print(f"   🌈 Added HALDCLUT input: {os.path.basename(style_lut)}")
            
            # Build video filter chain - handle HALDCLUT specially
            if has_haldclut:
                # For HALDCLUT, we need to use filter_complex with proper syntax
                filter_parts = []
                
                # Start with video input and apply any correction LUT
                video_stream = "[0:v]"
                if correction_lut and os.path.exists(correction_lut) and correction_lut.lower().endswith('.cube'):
                    filter_parts.append(f"{video_stream}lut3d={correction_lut}[corrected]")
                    video_stream = "[corrected]"
                    print(f"   🎨 Applied correction LUT (.cube): {os.path.basename(correction_lut)}")
                
                # Apply HALDCLUT with the style LUT
                filter_parts.append(f"{video_stream}[1:v]haldclut[styled]")
                print(f"   🌈 Applied style LUT (HALDCLUT .png): {os.path.basename(style_lut)}")
                
                # Apply scaling
                filter_parts.append(f"[styled]scale={target_width}:{target_height}")
                
                filter_complex = ";".join(filter_parts)
            else:
                # Simple filter chain for non-HALDCLUT processing
                filters = []
                
                # Add correction LUT (cube files only)
                if correction_lut and os.path.exists(correction_lut):
                    if correction_lut.lower().endswith('.cube'):
                        filters.append(f"lut3d={correction_lut}")
                        print(f"   🎨 Applied correction LUT (.cube): {os.path.basename(correction_lut)}")
                    else:
                        print(f"   ⚠️ Correction LUT must be .cube format: {correction_lut}")
                
                # Add style LUT (cube only in this branch)
                if style_lut and os.path.exists(style_lut) and style_lut.lower().endswith('.cube'):
                    filters.append(f"lut3d={style_lut}")
                    print(f"   🌈 Applied style LUT (.cube): {os.path.basename(style_lut)}")
                
                # Add scaling filter
                filters.append(f"scale={target_width}:{target_height}")
                
                filter_complex = ",".join(filters)
            
            # Add filter and encoding options
            cmd.extend([
                "-vcodec", "libx264",  # h.264 codec
                "-preset", "ultrafast" if (correction_lut or style_lut) else self.preset,  # Use faster preset for LUT processing
                "-crf", str(self.crf),  # Quality setting (lower = better quality, bigger file)
            ])
            
            # Use filter_complex for multi-input filters (HALDCLUT), otherwise use vf
            if has_haldclut:
                cmd.extend(["-filter_complex", filter_complex])
            else:
                cmd.extend(["-vf", filter_complex])
            
            cmd.extend([
                "-threads", "0",  # Use all CPU cores
                "-pix_fmt", "yuv420p",  # Force compatible pixel format for web playback
                "-acodec", "aac",  # Audio codec
                "-ab", "128k",  # Audio bitrate (128k is good for most content)
                "-movflags", "faststart",  # Optimize for web streaming with progressive buffering
                "-avoid_negative_ts", "make_zero",  # Fix timing issues
                "-progress", "pipe:1",  # Show progress
                "-y",  # Overwrite output file
                temp_path
            ])
            
            lut_info = ""
            if correction_lut or style_lut:
                luts = []
                if correction_lut:
                    luts.append(f"correction: {os.path.basename(correction_lut)}")
                if style_lut:
                    luts.append(f"style: {os.path.basename(style_lut)}")
                lut_info = f" + LUTs ({', '.join(luts)})"
            
            print(f"   🔄 Encoding with h.264 (CRF {self.crf}, preset {self.preset}){lut_info}...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 60 minute timeout for LUT processing
            
            if result.returncode == 0 and os.path.exists(temp_path):
                # Move temporary file to final location
                os.rename(temp_path, proxy_path)
                
                # Get file size info
                original_size = os.path.getsize(video_path)
                proxy_size = os.path.getsize(proxy_path)
                compression_ratio = (1 - proxy_size / original_size) * 100
                
                print(f"   ✅ Generated: {proxy_path.name}")
                print(f"   📊 Size: {original_size/1024/1024:.1f}MB → {proxy_size/1024/1024:.1f}MB ({compression_ratio:.1f}% smaller)")
                return True
            else:
                # Clean up failed temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                print(f"   ❌ FFmpeg failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"   ⏰ Encoding timeout (>60 minutes)")
            return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    
    def batch_generate(self, limit: int = None, force: bool = False) -> dict:
        """Generate proxies for all videos in database."""
        cursor = self.conn.cursor()
        
        # Query for all video files
        if limit:
            cursor.execute("""
                SELECT id, path, filename FROM images 
                WHERE file_type = 'video'
                ORDER BY date_original DESC 
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT id, path, filename FROM images 
                WHERE file_type = 'video'
                ORDER BY date_original DESC
            """)
        
        videos = cursor.fetchall()
        
        if not videos:
            print("📹 No videos found in database")
            return {'total': 0, 'generated': 0, 'skipped': 0, 'errors': 0}
        
        stats = {
            'total': len(videos),
            'generated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        print(f"📹 Found {stats['total']} videos in database")
        print(f"🎯 Target: max {self.target_max_dimension}px longest edge, h.264, CRF {self.crf}")
        print(f"📁 Output: {self.proxy_dir}")
        print()
        
        for i, video in enumerate(videos):
            video_id = video['id']
            video_path = video['path']
            filename = video['filename']
            
            try:
                if not force and not self.needs_proxy(video_id, video_path):
                    print(f"⏭️ Skipping: {filename} (proxy up to date)")
                    stats['skipped'] += 1
                    continue
                
                if self.generate_proxy(video_id, video_path, force=force):
                    stats['generated'] += 1
                else:
                    stats['errors'] += 1
                
                # Progress update every 5 videos
                if (i + 1) % 5 == 0:
                    print(f"\n📈 Progress: {i + 1}/{stats['total']} videos processed")
                    print(f"   ✅ Generated: {stats['generated']}, ⏭️ Skipped: {stats['skipped']}, ❌ Errors: {stats['errors']}\n")
                
            except KeyboardInterrupt:
                print("\n⚠️ Generation interrupted by user")
                break
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def clean_orphaned(self) -> int:
        """Remove proxy files for videos no longer in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM images WHERE file_type = 'video'")
        valid_ids = {row[0] for row in cursor.fetchall()}
        
        removed = 0
        for proxy_file in self.proxy_dir.glob("*.mp4"):
            try:
                # Extract video ID from filename
                video_id = int(proxy_file.stem)
                if video_id not in valid_ids:
                    proxy_file.unlink()
                    print(f"🗑️ Removed orphaned proxy: {proxy_file.name}")
                    removed += 1
            except ValueError:
                # Invalid filename format, skip
                continue
        
        return removed
    
    def get_stats(self) -> dict:
        """Get proxy generation statistics."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images WHERE file_type = 'video'")
        total_videos = cursor.fetchone()[0]
        
        total_proxies = len(list(self.proxy_dir.glob("*.mp4")))
        cache_size = sum(f.stat().st_size for f in self.proxy_dir.glob("*.mp4"))
        
        return {
            'total_videos': total_videos,
            'total_proxies': total_proxies,
            'cache_size_mb': cache_size / (1024 * 1024),
            'cache_path': str(self.proxy_dir)
        }
    
    def process_picks_file(self, picks_file: str, correction_lut: str = None, style_lut: str = None, force: bool = False) -> dict:
        """Generate proxies for videos in a JSON picks file."""
        try:
            with open(picks_file, 'r') as f:
                picks = json.load(f)
        except Exception as e:
            print(f"❌ Error reading picks file: {e}")
            return {'total': 0, 'generated': 0, 'skipped': 0, 'errors': 1}
        
        cursor = self.conn.cursor()
        stats = {'total': 0, 'generated': 0, 'skipped': 0, 'errors': 0}
        
        for pick in picks:
            image_id = pick.get('id')
            if not image_id:
                continue
                
            # Get video info from database
            cursor.execute("SELECT id, path, filename FROM images WHERE id = ? AND file_type = 'video'", (image_id,))
            row = cursor.fetchone()
            
            if not row:
                print(f"❌ Video ID {image_id} not found in database or not a video")
                stats['errors'] += 1
                continue
            
            stats['total'] += 1
            video_path = row['path']
            
            if self.generate_proxy(row['id'], video_path, correction_lut, style_lut, force):
                stats['generated'] += 1
            else:
                if force or self.needs_proxy(row['id'], video_path):
                    stats['errors'] += 1
                else:
                    stats['skipped'] += 1
        
        return stats
    
    def process_single_video(self, video_path: str, correction_lut: str = None, style_lut: str = None, force: bool = False) -> dict:
        """Generate proxy for a single video file."""
        cursor = self.conn.cursor()
        
        # Get video info from database by path
        cursor.execute("SELECT id, path, filename FROM images WHERE path = ? AND file_type = 'video'", (video_path,))
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Video {video_path} not found in database")
            return {'total': 0, 'generated': 0, 'skipped': 0, 'errors': 1}
        
        stats = {'total': 1, 'generated': 0, 'skipped': 0, 'errors': 0}
        
        if self.generate_proxy(row['id'], video_path, correction_lut, style_lut, force):
            stats['generated'] = 1
        else:
            if force or self.needs_proxy(row['id'], video_path):
                stats['errors'] = 1
            else:
                stats['skipped'] = 1
        
        return stats
    
    def process_single_video_by_id(self, video_id: int, correction_lut: str = None, style_lut: str = None, force: bool = False) -> dict:
        """Generate proxy for a single video by database ID."""
        cursor = self.conn.cursor()
        
        # Get video info from database by ID
        cursor.execute("SELECT id, path, filename FROM images WHERE id = ? AND file_type = 'video'", (video_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Video ID {video_id} not found in database")
            return {'total': 0, 'generated': 0, 'skipped': 0, 'errors': 1}
        
        stats = {'total': 1, 'generated': 0, 'skipped': 0, 'errors': 0}
        
        if self.generate_proxy(row['id'], row['path'], correction_lut, style_lut, force):
            stats['generated'] = 1
        else:
            if force or self.needs_proxy(row['id'], row['path']):
                stats['errors'] = 1
            else:
                stats['skipped'] = 1
        
        return stats

def main():
    parser = argparse.ArgumentParser(description='Generate h.264 video proxies for fast gallery playback')
    parser.add_argument('--db', default=None, help='Database file path (auto-detected if not specified)')
    parser.add_argument('--proxy-dir', default='Video Proxies', help='Video proxy directory')
    parser.add_argument('--limit', type=int, help='Limit number of videos to process')
    parser.add_argument('--force', action='store_true', help='Regenerate existing proxies')
    parser.add_argument('--clean', action='store_true', help='Remove orphaned proxy files')
    parser.add_argument('--stats', action='store_true', help='Show proxy statistics')
    parser.add_argument('--crf', type=int, default=23, help='Quality setting (lower=better, 18-28 recommended)')
    parser.add_argument('--max-dimension', type=int, default=2732, help='Maximum dimension (longest edge) in pixels (default: 2732 for iPad Pro)')
    
    # New input options
    parser.add_argument('--picks-file', help='JSON picks file containing video IDs to process')
    parser.add_argument('--video-file', help='Single video file path to process')
    parser.add_argument('--video-id', type=int, help='Single video database ID to process')
    
    # LUT options
    parser.add_argument('--correction-lut', help='Path to correction LUT (.cube file)')
    parser.add_argument('--style-lut', help='Path to style LUT (.cube file)')
    
    args = parser.parse_args()
    
    generator = VideoProxyGenerator(args.db, args.proxy_dir)
    
    # Override default settings if specified
    if args.crf:
        generator.crf = args.crf
    if args.max_dimension:
        generator.target_max_dimension = args.max_dimension
    
    if args.stats:
        stats = generator.get_stats()
        print("\n📊 VIDEO PROXY STATISTICS")
        print("-" * 40)
        print(f"Total videos in database: {stats['total_videos']}")
        print(f"Proxy directory: {stats['cache_path']}")
        print(f"Cache size: {stats['cache_size_mb']:.1f} MB")
        print(f"Total proxies: {stats['total_proxies']}")
        coverage = (stats['total_proxies'] / stats['total_videos']) * 100 if stats['total_videos'] > 0 else 0
        print(f"Coverage: {coverage:.1f}%")
        return
    
    if args.clean:
        print("🧹 Cleaning orphaned video proxies...")
        removed = generator.clean_orphaned()
        print(f"✅ Removed {removed} orphaned proxy files")
        return
    
    # Determine processing mode and generate proxies
    print("🚀 Starting video proxy generation...")
    print(f"🎯 Settings: max {generator.target_max_dimension}px longest edge, CRF {generator.crf}, preset {generator.preset}")
    
    if args.correction_lut or args.style_lut:
        luts = []
        if args.correction_lut:
            luts.append(f"correction: {os.path.basename(args.correction_lut)}")
        if args.style_lut:
            luts.append(f"style: {os.path.basename(args.style_lut)}")
        print(f"🎨 LUTs: {', '.join(luts)}")
    print()
    
    # Choose processing mode
    if args.picks_file:
        print(f"📄 Processing videos from picks file: {args.picks_file}")
        stats = generator.process_picks_file(args.picks_file, args.correction_lut, args.style_lut, args.force)
    elif args.video_file:
        print(f"🎬 Processing single video file: {args.video_file}")
        stats = generator.process_single_video(args.video_file, args.correction_lut, args.style_lut, args.force)
    elif args.video_id:
        print(f"🆔 Processing single video ID: {args.video_id}")
        stats = generator.process_single_video_by_id(args.video_id, args.correction_lut, args.style_lut, args.force)
    else:
        print("📁 Processing all videos in database (batch mode)")
        stats = generator.batch_generate(args.limit, args.force)
    
    print(f"\n📊 GENERATION COMPLETE")
    print("-" * 40)
    print(f"Total videos: {stats['total']}")
    print(f"Generated: {stats['generated']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    
    if stats['generated'] > 0:
        print(f"\n💡 Video proxies stored in: {generator.proxy_dir}")
        print("💡 Proxies optimized for retina displays with h.264 compression")

if __name__ == "__main__":
    main()