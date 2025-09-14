#!/usr/bin/env python3
"""
Gallery API server for photo management toolkit.
Handles gallery management, image processing, picks/rejects, and proxy generation.
"""

import sqlite3
import json
import os
from http.server import HTTPServer
from urllib.parse import urlparse, parse_qs
import argparse
from pathlib import Path
import glob
import shutil
import subprocess
import sys
from datetime import datetime

from api_base import BaseAPIHandler, create_server_factory


class GalleryAPIHandler(BaseAPIHandler):
    """Handler for gallery and image management API requests."""
    
    def do_GET(self):
        """Handle GET requests for gallery and image data."""
        parsed_path = urlparse(self.path)
        path_parts = parsed_path.path.strip('/').split('/')
        
        try:
            if len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'stats':
                # GET /api/stats
                stats = self.get_comprehensive_stats()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(stats)
            
            elif len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'image-metadata':
                # GET /api/image-metadata/{image_id}
                image_id = int(path_parts[2])
                metadata = self.get_image_metadata(image_id)
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(metadata)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'presets':
                # GET /api/presets
                presets = self.get_available_presets()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(presets)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'luts':
                # GET /api/luts
                luts = self.get_available_luts()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(luts)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'progress-log':
                # GET /api/progress-log?offset=N
                query_params = parse_qs(parsed_path.query)
                offset = int(query_params.get('offset', [0])[0])
                log_entries = self.get_progress_log(offset)
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response({'log': log_entries})
            
            elif len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'video-proxy-status':
                # GET /api/video-proxy-status/{image_id}
                image_id = int(path_parts[2])
                exists = self.check_video_proxy_exists(image_id)
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response({'exists': exists})
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'load-picks':
                # GET /api/load-picks
                picks = self.load_picks_from_file()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(picks)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'load-rejects':
                # GET /api/load-rejects
                rejects = self.load_rejects_from_file()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(rejects)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'progress-stream':
                # GET /api/progress-stream (Server-Sent Events)
                self.handle_progress_stream()
            
            else:
                self.send_error(404, "API endpoint not found")
                
        except ValueError as e:
            self.send_error(400, f"Invalid request: {str(e)}")
        except Exception as e:
            self.broadcast_progress(f"❌ GET Error: {e}", "error")
            self.send_error(500, "Internal server error")
    
    def do_POST(self):
        """Handle POST requests for gallery and image operations."""
        parsed_path = urlparse(self.path)
        path_parts = parsed_path.path.strip('/').split('/')
        
        try:
            if len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'save-picks':
                # POST /api/save-picks
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                success = self.save_picks_to_file(data.get('picks', []))
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True})
                else:
                    self.send_error(500, "Failed to save picks")
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'save-rejects':
                # POST /api/save-rejects
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                success = self.save_rejects_to_file(data.get('rejects', []))
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True})
                else:
                    self.send_error(500, "Failed to save rejects")
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'delete-gallery':
                # POST /api/delete-gallery
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                gallery_path = data.get('gallery_path', '').strip()
                
                if not gallery_path:
                    self.send_error(400, "Missing gallery_path")
                    return
                
                success, message = self.delete_gallery(gallery_path)
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'rebuild-galleries-list':
                # POST /api/rebuild-galleries-list
                success, message = self.rebuild_galleries_list()

                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)

            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'rename-gallery':
                # POST /api/rename-gallery
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                old_path = data.get('old_path', '').strip()
                new_name = data.get('new_name', '').strip()

                if not old_path or not new_name:
                    self.send_error(400, "Missing old_path or new_name")
                    return

                success, message = self.rename_gallery(old_path, new_name)

                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)
            
            else:
                self.send_error(404, "API endpoint not found")
                
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON data")
        except Exception as e:
            self.broadcast_progress(f"❌ POST Error: {e}", "error")
            self.send_error(500, "Internal server error")
    
    def delete_gallery(self, gallery_path):
        """Safely delete gallery with security whitelist check."""
        try:
            # Security validation: ensure path is within Hard Link Galleries directory
            gallery_path = gallery_path.strip()
            
            # Get absolute paths for security comparison
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                base_dir = current_dir.parent
            else:
                base_dir = current_dir
                
            # Expected gallery parent directory
            hardlinks_dir = base_dir / "Hard Link Galleries"
            
            # Convert to absolute paths
            gallery_abs_path = Path(gallery_path).resolve()
            hardlinks_abs_path = hardlinks_dir.resolve()
            
            # Security check: gallery must be within Hard Link Galleries directory
            if not str(gallery_abs_path).startswith(str(hardlinks_abs_path)):
                error_msg = f"Security violation: Gallery path must be within Hard Link Galleries directory"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg
            
            # Check if gallery exists
            if not gallery_abs_path.exists():
                error_msg = f"Gallery not found: {gallery_path}"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg
            
            # Check if it's actually a directory
            if not gallery_abs_path.is_dir():
                error_msg = f"Path is not a directory: {gallery_path}"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg
            
            gallery_name = gallery_abs_path.name
            self.broadcast_progress(f"🗑️ Deleting gallery: {gallery_name}", "info")
            
            # Perform the deletion
            shutil.rmtree(gallery_abs_path)
            
            self.broadcast_progress(f"✅ Gallery deleted successfully: {gallery_name}", "success")
            
            # Automatically rebuild galleries list after deletion
            rebuild_success, rebuild_message = self.rebuild_galleries_list()
            if rebuild_success:
                self.broadcast_progress("✅ Galleries list updated after deletion", "success")
                return True, f"Gallery '{gallery_name}' deleted successfully and galleries list updated"
            else:
                return True, f"Gallery '{gallery_name}' deleted successfully, but galleries list update failed: {rebuild_message}"
                
        except PermissionError as e:
            error_msg = f"Permission denied: {str(e)}"
            self.broadcast_progress(f"❌ {error_msg}", "error")
            return False, error_msg
        except Exception as e:
            error_msg = f"Error deleting gallery: {str(e)}"
            self.broadcast_progress(f"❌ {error_msg}", "error")
            return False, error_msg
    
    def rebuild_galleries_list(self):
        """Rebuild the main galleries.json list by calling the rebuild script."""
        try:
            # Get the script path
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                script_path = "rebuild_galleries_json.py"
                working_dir = "."
            else:
                script_path = "Scripts/rebuild_galleries_json.py"
                working_dir = "."
            
            # Call the rebuild script
            cmd = [sys.executable, script_path]
            
            self.broadcast_progress(f"🔨 Running galleries list rebuild: {' '.join(cmd)}", "info")
            
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.broadcast_progress("✅ Galleries list rebuild completed successfully", "success")
                
                # Extract summary from output
                lines = result.stdout.strip().split('\n')
                summary_lines = [line for line in lines if '✅' in line or 'galleries found' in line.lower()]
                summary = summary_lines[-1] if summary_lines else "Galleries list rebuilt successfully"
                
                return True, summary
            else:
                error_msg = result.stderr.strip() if result.stderr else "Galleries list rebuild failed"
                self.broadcast_progress(f"❌ Galleries list rebuild failed: {error_msg}", "error")
                return False, f"Galleries list rebuild failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            self.broadcast_progress("❌ Galleries list rebuild timed out", "error")
            return False, "Galleries list rebuild timed out"
        except Exception as e:
            self.broadcast_progress(f"❌ Error running galleries list rebuild: {e}", "error")
            return False, f"Error running galleries list rebuild: {str(e)}"

    def rename_gallery(self, old_path, new_name):
        """Safely rename gallery with security validation."""
        try:
            # Security validation: ensure path is within Hard Link Galleries directory
            old_path = old_path.strip()
            new_name = new_name.strip()

            # Validate new name (no path separators, reasonable length)
            if not new_name or '/' in new_name or '\\' in new_name or '..' in new_name:
                error_msg = "Invalid gallery name: must not contain path separators or be empty"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg

            if len(new_name) > 100:
                error_msg = "Gallery name too long (max 100 characters)"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg

            # Get absolute paths for security comparison
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                base_dir = current_dir.parent
            else:
                base_dir = current_dir

            # Expected gallery parent directory
            hardlinks_dir = base_dir / "Hard Link Galleries"

            # Convert to absolute paths
            old_abs_path = Path(old_path).resolve()
            hardlinks_abs_path = hardlinks_dir.resolve()

            # Security check: old gallery must be within Hard Link Galleries directory
            if not str(old_abs_path).startswith(str(hardlinks_abs_path)):
                error_msg = f"Security violation: Gallery path must be within Hard Link Galleries directory"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg

            # Check if old gallery exists
            if not old_abs_path.exists():
                error_msg = f"Gallery not found: {old_path}"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg

            # Check if it's actually a directory
            if not old_abs_path.is_dir():
                error_msg = f"Path is not a directory: {old_path}"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg

            # Create new path (same parent directory, new name)
            new_abs_path = old_abs_path.parent / new_name

            # Check if new name already exists
            if new_abs_path.exists():
                error_msg = f"Gallery name already exists: {new_name}"
                self.broadcast_progress(f"❌ {error_msg}", "error")
                return False, error_msg

            old_name = old_abs_path.name
            self.broadcast_progress(f"📝 Renaming gallery: {old_name} → {new_name}", "info")

            # Perform the rename
            old_abs_path.rename(new_abs_path)

            self.broadcast_progress(f"✅ Gallery renamed successfully: {old_name} → {new_name}", "success")

            # Update SourceFile paths in image_data.json
            self.broadcast_progress("🔄 Updating image paths in gallery JSON...", "info")
            success = self.update_gallery_json_paths(new_abs_path, old_name, new_name)
            if success:
                self.broadcast_progress("✅ Gallery JSON paths updated", "success")
            else:
                self.broadcast_progress("⚠️ Warning: Could not update gallery JSON paths", "warning")

            # Automatically rebuild galleries list after rename
            rebuild_success, rebuild_message = self.rebuild_galleries_list()
            if rebuild_success:
                self.broadcast_progress("✅ Galleries list updated after rename", "success")
                return True, f"Gallery '{old_name}' renamed to '{new_name}' successfully and galleries list updated"
            else:
                return True, f"Gallery '{old_name}' renamed to '{new_name}' successfully, but galleries list update failed: {rebuild_message}"

        except PermissionError as e:
            error_msg = f"Permission denied: {str(e)}"
            self.broadcast_progress(f"❌ {error_msg}", "error")
            return False, error_msg
        except Exception as e:
            error_msg = f"Error renaming gallery: {str(e)}"
            self.broadcast_progress(f"❌ {error_msg}", "error")
            return False, error_msg

    def update_gallery_json_paths(self, gallery_path, old_name, new_name):
        """Update SourceFile paths in gallery JSON after rename."""
        try:
            import json

            json_file = gallery_path / "image_data.json"
            if not json_file.exists():
                return True  # No JSON file, nothing to update

            # Read the JSON file
            with open(json_file, 'r') as f:
                gallery_data = json.load(f)

            # Update SourceFile paths
            updated_count = 0
            old_path_prefix = f"Hard Link Galleries/{old_name}/"
            new_path_prefix = f"Hard Link Galleries/{new_name}/"

            for image in gallery_data:
                if 'SourceFile' in image and image['SourceFile'].startswith(old_path_prefix):
                    # Update the path
                    old_source = image['SourceFile']
                    image['SourceFile'] = old_source.replace(old_path_prefix, new_path_prefix, 1)
                    updated_count += 1

            # Write back the updated JSON
            with open(json_file, 'w') as f:
                json.dump(gallery_data, f, indent=2)

            self.broadcast_progress(f"📝 Updated {updated_count} image paths in gallery JSON", "info")
            return True

        except Exception as e:
            self.broadcast_progress(f"❌ Error updating gallery JSON: {str(e)}", "error")
            return False

    # Placeholder methods - these would need to be implemented with the full functionality
    def get_comprehensive_stats(self):
        """Get comprehensive database statistics."""
        return {"message": "Stats endpoint placeholder"}
    
    def get_image_metadata(self, image_id):
        """Get complete metadata for an image."""
        return {"message": f"Image metadata for {image_id}"}
    
    def get_available_presets(self):
        """Get available RAW processing presets."""
        return {"presets": []}
    
    def get_available_luts(self):
        """Get available LUT files for video processing."""
        return {"luts": []}
    
    def get_progress_log(self, offset):
        """Get progress log entries."""
        return []
    
    def check_video_proxy_exists(self, image_id):
        """Check if video proxy exists."""
        return False
    
    def load_picks_from_file(self):
        """Load picks from JSON file."""
        try:
            picks_path = self.get_json_path("picks.json")
            if os.path.exists(picks_path):
                with open(picks_path, 'r') as f:
                    return json.load(f)
            return []
        except Exception:
            return []
    
    def load_rejects_from_file(self):
        """Load rejects from JSON file."""
        try:
            rejects_path = self.get_json_path("delete_list.json")
            if os.path.exists(rejects_path):
                with open(rejects_path, 'r') as f:
                    return json.load(f)
            return []
        except Exception:
            return []
    
    def save_picks_to_file(self, picks):
        """Save picks to JSON file."""
        try:
            picks_path = self.get_json_path("picks.json")
            with open(picks_path, 'w') as f:
                json.dump(picks, f, indent=2)
            return True
        except Exception as e:
            self.broadcast_progress(f"❌ Error saving picks: {e}", "error")
            return False
    
    def save_rejects_to_file(self, rejects):
        """Save rejects to JSON file."""
        try:
            rejects_path = self.get_json_path("delete_list.json")
            with open(rejects_path, 'w') as f:
                json.dump(rejects, f, indent=2)
            return True
        except Exception as e:
            self.broadcast_progress(f"❌ Error saving rejects: {e}", "error")
            return False


def main():
    parser = argparse.ArgumentParser(description='Gallery API Server')
    parser.add_argument('--bind', default='127.0.0.1', help='Bind address (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8002, help='Port number (default: 8002)')
    parser.add_argument('--db', help='Database path (auto-detected if not specified)')
    
    args = parser.parse_args()
    
    # Create server
    server_address = (args.bind, args.port)
    handler_factory = create_server_factory(GalleryAPIHandler)
    httpd = HTTPServer(server_address, handler_factory)
    
    print(f"Gallery API Server starting on {args.bind}:{args.port}")
    print(f"Database: {args.db or 'auto-detected'}")
    print("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Gallery API Server...")
        httpd.shutdown()


if __name__ == '__main__':
    main()