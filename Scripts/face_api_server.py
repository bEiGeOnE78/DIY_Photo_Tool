#!/usr/bin/env python3
"""
Simple API server to serve face detection data to the gallery interface.
"""

import sqlite3
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import argparse
from pathlib import Path
import glob

class FaceAPIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, db_path=None, **kwargs):
        if db_path is None:
            # Auto-detect database location
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                db_path = "image_metadata.db"  # Same directory
            else:
                db_path = "Scripts/image_metadata.db"  # Scripts subdirectory
        self.db_path = db_path
        super().__init__(*args, **kwargs)
    
    def get_json_path(self, filename):
        """Get correct path to JSON file, works from Scripts/ or main directory."""
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            return f"../JSON/{filename}"
        else:
            return f"JSON/{filename}"
    
    def do_GET(self):
        """Handle GET requests for face data."""
        parsed_path = urlparse(self.path)
        path_parts = parsed_path.path.strip('/').split('/')
        
        try:
            if len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'faces':
                # GET /api/faces/{image_id}
                image_id = int(path_parts[2])
                faces = self.get_faces_for_image(image_id)
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(faces)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'stats':
                # GET /api/stats
                stats = self.get_comprehensive_stats()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(stats)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'people':
                # GET /api/people
                people = self.get_all_people()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(people)
            
            elif len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'image-metadata':
                # GET /api/image-metadata/{image_id}
                image_id = int(path_parts[2])
                metadata = self.get_image_metadata(image_id)
                if metadata:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response(metadata)
                else:
                    self.send_error(404, "Image not found")
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'presets':
                # GET /api/presets
                presets = self.get_available_presets()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(presets)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'progress-log':
                # GET /api/progress-log?offset=N - Get progress log entries from offset
                query_params = parse_qs(parsed_path.query)
                offset = int(query_params.get('offset', ['0'])[0])
                
                progress_data = self.get_progress_log(offset)
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(progress_data)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'luts':
                # GET /api/luts
                luts = self.get_available_luts()
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response(luts)
            
            elif len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'video-proxy-status':
                # GET /api/video-proxy-status/{image_id}
                image_id = path_parts[2]
                proxy_exists = self.check_video_proxy_exists(image_id)
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response({'exists': proxy_exists})
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'load-picks':
                # GET /api/load-picks
                picks_list = self.load_picks_from_file()
                if picks_list is not None:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'picks': picks_list})
                else:
                    self.send_error(500, "Failed to load picks")
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'load-rejects':
                # GET /api/load-rejects
                rejects_list = self.load_rejects_from_file()
                if rejects_list is not None:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'rejects': rejects_list})
                else:
                    self.send_error(500, "Failed to load rejects")
            
            else:
                self.send_error(404, "API endpoint not found")
                
        except ValueError:
            self.broadcast_progress("❌ Invalid image ID in GET request", "error")
            self.send_error(400, "Invalid image ID")
        except Exception as e:
            import traceback
            self.broadcast_progress(f"❌ GET Error: {e}", "error")
            traceback.print_exc()
            self.send_error(500, "Internal server error")
    
    def do_POST(self):
        """Handle POST requests for saving data."""
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
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.write(b'OK')
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
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.write(b'OK')
                else:
                    self.send_error(500, "Failed to save rejects")
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'assign-face':
                # POST /api/assign-face
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                success = self.assign_face_to_person(data.get('face_id'), data.get('person_id'))
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': 'Face assigned successfully'})
                else:
                    self.send_error(400, "Failed to assign face")
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'ignore-face':
                # POST /api/ignore-face
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                success = self.ignore_face(data.get('face_id'))
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': 'Face ignored successfully'})
                else:
                    self.send_error(400, "Failed to ignore face")
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'rename-person':
                # POST /api/rename-person
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                person_id = data.get('person_id')
                new_name = data.get('new_name', '').strip()
                
                if not person_id or not new_name:
                    self.send_error(400, "Missing person_id or new_name")
                    return
                
                success, message = self.rename_person_with_label_mode(person_id, new_name)
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'switch-proxy':
                # POST /api/switch-proxy
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                image_id = data.get('image_id')
                use_custom_proxy = data.get('use_custom_proxy', False)
                
                if not image_id:
                    self.send_error(400, "Missing image_id")
                    return
                
                success, message = self.switch_proxy_mode(image_id, use_custom_proxy)
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'generate-raw-proxy':
                # POST /api/generate-raw-proxy
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                image_id = data.get('image_id')
                camera_standard = data.get('camera_standard')
                style_preset = data.get('style_preset')
                quality = data.get('quality', 95)
                exposure = data.get('exposure', 0.0)
                
                if not image_id:
                    self.send_error(400, "Missing image_id")
                    return
                
                success, message = self.generate_raw_proxy_with_preset(image_id, camera_standard, style_preset, quality, exposure)
                
                if success:
                    # Switch to the new custom proxy
                    switch_success, switch_message = self.switch_proxy_mode(image_id, True)
                    
                    if switch_success:
                        full_message = f"{message}. {switch_message}"
                    else:
                        full_message = f"{message}. Warning: {switch_message}"
                    
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': full_message})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'generate-video-proxy':
                # POST /api/generate-video-proxy
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                image_id = data.get('image_id')
                correction_lut = data.get('correction_lut')
                style_lut = data.get('style_lut')
                
                if not image_id:
                    self.send_error(400, "Missing image_id")
                    return
                
                success, message = self.generate_video_proxy_with_luts(image_id, correction_lut, style_lut)
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'switch-video-proxy':
                # POST /api/switch-video-proxy
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                image_id = data.get('image_id')
                use_custom_proxy = data.get('use_custom_proxy', False)
                
                if not image_id:
                    self.send_error(400, "Missing image_id")
                    return
                
                success, message = self.switch_video_proxy_mode(image_id, use_custom_proxy)
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'delete-rejects-preview':
                # POST /api/delete-rejects-preview
                success, result = self.preview_rejected_files()
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'preview': result})
                else:
                    self.send_error(400, result)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'delete-rejects':
                # POST /api/delete-rejects
                success, message = self.delete_rejected_files()
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'create-gallery':
                # POST /api/create-gallery
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                search_string = data.get('search_string', '').strip()
                gallery_name = data.get('gallery_name', '').strip()
                
                if not search_string and not data.get('face_samples', False) and not data.get('picks_file'):
                    self.send_error(400, "Missing search_string, face_samples flag, or picks_file")
                    return
                
                if not gallery_name:
                    self.send_error(400, "Missing gallery_name")
                    return
                
                success, message = self.create_gallery_from_search(search_string, gallery_name, data.get('face_samples', False), data.get('picks_file'))
                
                if success:
                    self.send_response(200)
                    self.send_cors_headers()
                    self.send_json_response({'success': True, 'message': message, 'gallery_name': gallery_name})
                else:
                    self.send_error(400, message)
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'rebuild-gallery-json':
                # POST /api/rebuild-gallery-json
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                gallery_path = data.get('gallery_path', '').strip()
                
                if not gallery_path:
                    self.send_error(400, "Missing gallery_path")
                    return
                
                success, message = self.rebuild_gallery_json(gallery_path)
                
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
            
            elif len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1] == 'process-new-images':
                # POST /api/process-new-images
                content_length = int(self.headers.get('Content-Length', 0))
                
                # Handle empty request body
                if content_length > 0:
                    post_data = self.rfile.read(content_length)
                    try:
                        data = json.loads(post_data.decode('utf-8'))
                    except json.JSONDecodeError:
                        data = {}
                else:
                    data = {}
                
                directory = data.get('directory', 'Master Photo Library')
                
                # Start processing in background thread
                import threading
                thread = threading.Thread(target=self.process_new_images, args=(directory,))
                thread.daemon = True
                thread.start()
                
                # Return immediately
                self.send_response(200)
                self.send_cors_headers()
                self.send_json_response({
                    'success': True, 
                    'message': f'Started processing new images from {directory} in background. Check the console for progress updates.'
                })
            
            else:
                self.send_error(404, "API endpoint not found")
                
        except Exception as e:
            self.broadcast_progress(f"❌ POST Error: {e}", "error")
            self.send_error(500, "Internal server error")
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def send_error(self, code, message=None):
        """Override send_error to include CORS headers."""
        self.send_response(code)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Type', 'application/json')
        
        if message:
            error_response = json.dumps({'error': message})
            self.send_header('Content-Length', str(len(error_response)))
            self.end_headers()
            self.wfile.write(error_response.encode())
        else:
            self.send_header('Content-Length', '0')
            self.end_headers()
    
    def send_cors_headers(self):
        """Send CORS headers for browser requests."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Type', 'application/json')
    
    def send_json_response(self, data):
        """Send JSON response."""
        json_data = json.dumps(data, default=str)
        self.send_header('Content-Length', str(len(json_data)))
        self.end_headers()
        self.wfile.write(json_data.encode())
    
    def get_faces_for_image(self, image_id):
        """Get face detection data for a specific image."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT f.id, f.x, f.y, f.width, f.height, f.confidence, f.person_id,
                   p.name as person_name, p.confirmed, f.ignored
            FROM faces f
            LEFT JOIN persons p ON f.person_id = p.id
            WHERE f.image_id = ? AND (f.ignored IS NULL OR f.ignored = 0)
            ORDER BY f.confidence DESC
        """, (image_id,))
        
        faces = []
        for row in cursor.fetchall():
            faces.append({
                'id': row['id'],
                'x': row['x'],
                'y': row['y'],
                'width': row['width'],
                'height': row['height'],
                'confidence': row['confidence'],
                'person_id': row['person_id'],
                'person_name': row['person_name'],
                'confirmed': bool(row['confirmed']) if row['confirmed'] is not None else False,
                'ignored': bool(row['ignored']) if row['ignored'] is not None else False
            })
        
        conn.close()
        return faces
    
    def get_all_people(self):
        """Get list of all people for dropdown menu."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.id, p.name, p.confirmed, COUNT(f.id) as face_count
            FROM persons p
            LEFT JOIN faces f ON p.id = f.person_id AND (f.ignored IS NULL OR f.ignored = 0)
            WHERE p.name IS NOT NULL AND p.name != ''
            GROUP BY p.id, p.name, p.confirmed
            ORDER BY p.name ASC
        """)
        
        people = []
        for row in cursor.fetchall():
            people.append({
                'id': row['id'],
                'name': row['name'],
                'confirmed': bool(row['confirmed']) if row['confirmed'] is not None else False,
                'face_count': row['face_count']
            })
        
        conn.close()
        return people
    
    def get_image_metadata(self, image_id):
        """Get image metadata including proxy information."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, path, filename, raw_proxy_type, raw_processing_settings,
                   file_format, camera_make, camera_model, date_taken, video_proxy_type
            FROM images 
            WHERE id = ?
        """, (image_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        # Check if custom proxy exists
        proxy_path = f"RAW Proxies/{image_id}.jpg"
        has_custom_proxy = os.path.exists(proxy_path)
        
        # Check if adjacent JPG exists (for RAW files)
        original_path = Path(row['path'])
        has_adjacent_jpg = False
        if original_path.suffix.lower() in {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw'}:
            for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                adjacent_jpg = original_path.with_suffix(ext)
                if adjacent_jpg.exists():
                    has_adjacent_jpg = True
                    break
        
        metadata = {
            'id': row['id'],
            'filename': row['filename'],
            'path': row['path'],
            'raw_proxy_type': row['raw_proxy_type'],
            'raw_processing_settings': row['raw_processing_settings'],
            'file_format': row['file_format'],
            'camera_make': row['camera_make'],
            'camera_model': row['camera_model'],
            'date_taken': row['date_taken'],
            'video_proxy_type': row['video_proxy_type'],
            'has_custom_proxy': has_custom_proxy,
            'has_adjacent_jpg': has_adjacent_jpg
        }
        
        conn.close()
        return metadata
    
    def get_hard_link_source(self, row):
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
                self.broadcast_progress(f"⚠️ Custom proxy not found for image {image_id}: {proxy_path}", "warning")
                return None
        elif raw_proxy_type == 'original_jpg':
            # Use the adjacent JPG file
            original_path_obj = Path(original_path)
            for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                adjacent_jpg = original_path_obj.with_suffix(ext)
                if adjacent_jpg.exists():
                    return str(adjacent_jpg)
            self.broadcast_progress(f"⚠️ Adjacent JPG not found for image {image_id}", "warning")
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
                self.broadcast_progress(f"⏭️ Skipping RAW file without adjacent JPG: image {image_id}", "info")
                return None
            else:
                # Check if it's a HEIC file and if we have a proxy
                if file_ext.lower() == '.heic':
                    heic_proxy_path = f"HEIC Proxies/{image_id}.jpg"
                    if os.path.exists(heic_proxy_path):
                        return heic_proxy_path
                
                # Regular file (JPG, PNG, etc.) or HEIC without proxy - use original
                return original_path
    
    def find_gallery_hard_links(self, image_id):
        """Find all gallery hard links for a specific image ID by checking gallery JSON files."""
        gallery_links = []
        
        # Search for the image in all gallery JSON files
        gallery_root = Path("Hard Link Galleries")
        if not gallery_root.exists():
            return gallery_links
        
        for gallery_dir in gallery_root.iterdir():
            if not gallery_dir.is_dir():
                continue
                
            # Check if this gallery has the image
            json_file = gallery_dir / 'image_data.json'
            if not json_file.exists():
                continue
                
            try:
                with open(json_file, 'r') as f:
                    gallery_data = json.load(f)
                
                # Look for the image ID in gallery data
                for item in gallery_data:
                    if item.get('_imageId') == image_id:
                        gallery_file_path = gallery_dir / item['FileName']
                        if gallery_file_path.exists():
                            gallery_links.append({
                                'gallery': gallery_dir.name,
                                'path': str(gallery_file_path),
                                'filename': item['FileName']
                            })
                        break  # Found the image in this gallery
                        
            except Exception as e:
                self.broadcast_progress(f"⚠️ Error reading gallery JSON {json_file}: {e}", "warning")
                continue
        
        return gallery_links
    
    def update_hard_links_for_image(self, image_id):
        """Update all hard links for an image after proxy mode change."""
        # Get current image data
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Image not found"
        
        # Get the new source path based on current proxy mode
        new_source = self.get_hard_link_source(row)
        if not new_source:
            conn.close()
            return False, "No valid source found for hard link"
        
        conn.close()
        
        # Find all existing hard links for this image
        gallery_links = self.find_gallery_hard_links(image_id)
        
        updated_count = 0
        errors = []
        
        for link_info in gallery_links:
            old_link_path = Path(link_info['path'])
            
            try:
                # Remove old hard link
                if old_link_path.exists():
                    old_link_path.unlink()
                
                # Create new hard link
                os.link(new_source, str(old_link_path))
                updated_count += 1
                
            except OSError as e:
                error_msg = f"Failed to update {link_info['gallery']}/{link_info['filename']}: {e}"
                errors.append(error_msg)
                self.broadcast_progress(f"❌ {error_msg}", "error")
        
        if errors:
            return False, f"Updated {updated_count} links, but {len(errors)} failed: {'; '.join(errors)}"
        elif updated_count > 0:
            return True, f"Updated {updated_count} gallery hard links"
        else:
            return True, "No gallery hard links found (image may not be in any galleries)"
    
    def get_available_presets(self):
        """Get lists of available camera standards and style presets."""
        presets_dir = Path("RawTherapee Presets")
        if not presets_dir.exists():
            return {'camera_standards': [], 'style_presets': []}
        
        all_presets = [p.name for p in presets_dir.glob("*.pp3")]
        camera_standards = [p for p in all_presets if p.startswith("Standard_")]
        style_presets = [p for p in all_presets if not p.startswith("Standard_") and not p.startswith("Exposure_") and "_Full" not in p]
        
        # Format for API response
        camera_standards_formatted = []
        for preset in sorted(camera_standards):
            name = preset.replace("Standard_", "").replace(".pp3", "").replace("_", " ")
            camera_standards_formatted.append({
                'name': name,
                'file': preset,
                'path': str((presets_dir / preset).resolve())
            })
        
        style_presets_formatted = []
        # Add "None" option first
        style_presets_formatted.append({
            'name': 'None (Camera Standard Only)',
            'file': 'None',
            'path': 'None'
        })
        for preset in sorted(style_presets):
            name = preset.replace("_01", "").replace(".pp3", "").replace("_", " ")
            style_presets_formatted.append({
                'name': name,
                'file': preset,
                'path': str((presets_dir / preset).resolve())
            })
        
        return {
            'camera_standards': camera_standards_formatted,
            'style_presets': style_presets_formatted
        }
    

    def generate_raw_proxy_with_preset(self, image_id, camera_standard=None, style_preset=None, quality=95, exposure=0.0):
        """Generate custom RAW proxy with specified preset using dedicated script."""
        import subprocess
        import sys
        
        try:
            # Get the script path
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                script_path = "generate_raw_proxies.py"
                working_dir = "."
            else:
                script_path = "Scripts/generate_raw_proxies.py"
                working_dir = "."
            
            # Build command to generate custom proxy for specific image
            cmd = [sys.executable, script_path, "--image-id", str(image_id), "--force", "--quality", str(quality), "--exposure", str(exposure)]
            
            # Add camera standard - always pass one to ensure our modified presets are used
            if camera_standard:
                # Extract just the filename from full path
                camera_name = Path(camera_standard).name
                cmd.extend(["--camera-standard", camera_name])
                self.broadcast_progress(f"📷 Using camera standard: {camera_name}", "info")
            else:
                self.broadcast_progress("🔍 Auto-detecting camera standard from EXIF", "info")
            
            # Add style preset if provided
            if style_preset and style_preset != "None":
                # Extract just the filename from full path
                style_name = Path(style_preset).name
                cmd.extend(["--style-preset", style_name])
                self.broadcast_progress(f"🎨 Using style preset: {style_name}", "info")
            elif style_preset == "None":
                self.broadcast_progress("🎨 No style preset - using camera standard only", "info")
            
            self.broadcast_progress(f"🚀 Running RAW proxy generation: {' '.join(cmd)}", "info")
            
            # Execute the script
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Log stdout for debugging
                if result.stdout:
                    self.broadcast_progress(f"📝 Script output: {result.stdout[:200]}...", "info")
                    for line in result.stdout.split('\n'):
                        if '🔧 Command:' in line or 'rawtherapee-cli' in line:
                            self.broadcast_progress(line.strip(), "info")
                else:
                    self.broadcast_progress("📝 No stdout captured from script", "info")
                
                # Regenerate thumbnail from new proxy
                self.regenerate_thumbnail(image_id)
                
                camera_name = Path(camera_standard).stem if camera_standard else "auto"
                style_name = Path(style_preset).stem if style_preset and style_preset != "None" else "none"
                self.broadcast_progress(f"✅ Generated custom proxy with {camera_name} + {style_name}", "success")
                return True, f"Generated custom proxy with {camera_name} + {style_name}"
            else:
                error_msg = result.stderr.strip() if result.stderr else "RAW proxy generation failed"
                self.broadcast_progress(f"❌ RAW proxy generation failed: {error_msg}", "error")
                return False, f"RAW proxy generation failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            self.broadcast_progress("❌ RAW proxy generation timeout", "error")
            return False, "RAW proxy generation timeout"
        except Exception as e:
            self.broadcast_progress(f"❌ Error generating RAW proxy: {e}", "error")
            return False, f"Error generating RAW proxy: {str(e)}"
    
    def generate_video_proxy_with_luts(self, image_id, correction_lut=None, style_lut=None):
        """Generate video proxy with optional LUTs using dedicated script."""
        import subprocess
        import sys
        
        try:
            # Get the script path
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                script_path = "generate_video_proxies.py"
                working_dir = "."
            else:
                script_path = "Scripts/generate_video_proxies.py"
                working_dir = "."
            
            # Build command to generate video proxy for specific image
            cmd = [sys.executable, script_path, "--video-id", str(image_id), "--force"]
            
            # Add correction LUT if provided
            if correction_lut and correction_lut.strip():
                cmd.extend(["--correction-lut", correction_lut])
                self.broadcast_progress(f"🎨 Using correction LUT: {Path(correction_lut).name}", "info")
            
            # Add style LUT if provided
            if style_lut and style_lut.strip():
                cmd.extend(["--style-lut", style_lut])
                self.broadcast_progress(f"🌈 Using style LUT: {Path(style_lut).name}", "info")
            
            if not correction_lut and not style_lut:
                self.broadcast_progress("📹 Generating standard video proxy (no LUTs)", "info")
            
            self.broadcast_progress(f"🚀 Running video proxy generation: {' '.join(cmd)}", "info")
            
            # Execute the script
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=3600  # 60 minute timeout for video processing
            )
            
            if result.returncode == 0:
                # Log stdout for debugging
                if result.stdout:
                    self.broadcast_progress(f"📝 Script output: {result.stdout[:200]}...", "info")
                    for line in result.stdout.split('\n'):
                        if '🔄 Encoding' in line or 'ffmpeg' in line:
                            self.broadcast_progress(line.strip(), "info")
                else:
                    self.broadcast_progress("📝 No stdout captured from script", "info")
                
                # Mark as using custom proxy in database and update hard links
                proxy_update_success, proxy_message = self.switch_video_proxy_mode(image_id, True)
                
                lut_info = ""
                if correction_lut or style_lut:
                    luts = []
                    if correction_lut:
                        luts.append(f"correction: {Path(correction_lut).name}")
                    if style_lut:
                        luts.append(f"style: {Path(style_lut).name}")
                    lut_info = f" with LUTs ({', '.join(luts)})"
                
                base_message = f"Generated video proxy{lut_info}"
                
                if proxy_update_success:
                    full_message = f"{base_message}. {proxy_message}"
                else:
                    full_message = f"{base_message}. Warning: {proxy_message}"
                
                self.broadcast_progress(f"✅ {base_message}", "success")
                return True, full_message
            else:
                error_msg = result.stderr.strip() if result.stderr else "Video proxy generation failed"
                self.broadcast_progress(f"❌ Video proxy generation failed: {error_msg}", "error")
                return False, f"Video proxy generation failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            self.broadcast_progress("❌ Video proxy generation timeout (>60 minutes)", "error")
            return False, "Video proxy generation timeout (>60 minutes)"
        except Exception as e:
            self.broadcast_progress(f"❌ Error generating video proxy: {e}", "error")
            return False, f"Error generating video proxy: {str(e)}"
    
    def switch_video_proxy_mode(self, image_id, use_custom_proxy):
        """Switch between original video and custom proxy for a video file."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get current video info
            cursor.execute("SELECT path, filename, video_proxy_type FROM images WHERE id = ?", (image_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False, "Video not found"
            
            original_path = Path(row[0])
            current_proxy_type = row[2] if row[2] else 'original'
            
            # Determine new proxy type
            if use_custom_proxy:
                # Check if custom proxy exists
                proxy_path = f"Video Proxies/{image_id}.mp4"
                if not os.path.exists(proxy_path):
                    conn.close()
                    return False, "Custom video proxy not found"
                new_proxy_type = "custom_generated"
            else:
                # Switch back to original video
                if not original_path.exists():
                    conn.close()
                    return False, "Original video file not found"
                new_proxy_type = "original"
            
            # Update database
            cursor.execute("""
                UPDATE images 
                SET video_proxy_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_proxy_type, image_id))
            
            conn.commit()
            conn.close()
            
            # Update hard links in all galleries
            hard_link_success, hard_link_message = self.update_video_hard_links_for_image(image_id)
            
            base_message = f"Switched to {'custom video proxy' if use_custom_proxy else 'original video'}"
            
            if hard_link_success:
                return True, f"{base_message}. {hard_link_message}"
            else:
                return True, f"{base_message}. Warning: {hard_link_message}"
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f"Error switching video proxy mode: {e}"
    
    def update_video_hard_links_for_image(self, image_id):
        """Update all hard links for a video after proxy mode change."""
        # Get current video data
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Video not found"
        
        # Get the new source path based on current proxy mode
        new_source = self.get_video_hard_link_source(row)
        if not new_source:
            conn.close()
            return False, "No valid source found for video hard link"
        
        conn.close()
        
        # Find all existing hard links for this video
        gallery_links = self.find_gallery_hard_links(image_id)
        
        updated_count = 0
        errors = []
        
        for link_info in gallery_links:
            old_link_path = Path(link_info['path'])
            
            try:
                # Remove old hard link
                if old_link_path.exists():
                    old_link_path.unlink()
                
                # Create new hard link
                os.link(new_source, str(old_link_path))
                updated_count += 1
                
            except OSError as e:
                error_msg = f"Failed to update {link_info['gallery']}/{link_info['filename']}: {e}"
                errors.append(error_msg)
                self.broadcast_progress(f"❌ {error_msg}", "error")
        
        if errors:
            return False, f"Updated {updated_count} links, but {len(errors)} failed: {'; '.join(errors)}"
        elif updated_count > 0:
            return True, f"Updated {updated_count} gallery hard links"
        else:
            return True, "No gallery hard links found (video may not be in any galleries)"
    
    def get_video_hard_link_source(self, row):
        """Determine the correct hard link source for a video file."""
        original_path = row['path']
        try:
            video_proxy_type = row['video_proxy_type']
        except (KeyError, IndexError):
            video_proxy_type = 'original'
        image_id = row['id']
        
        # For video files, determine the correct source
        if video_proxy_type == 'custom_generated':
            # Use the generated proxy from Video Proxies folder
            proxy_path = f"Video Proxies/{image_id}.mp4"
            if os.path.exists(proxy_path):
                return proxy_path
            else:
                self.broadcast_progress(f"⚠️ Custom video proxy not found for video {image_id}: {proxy_path}", "warning")
                return None
        else:
            # Use original video file
            if os.path.exists(original_path):
                return original_path
            else:
                self.broadcast_progress(f"⚠️ Original video file not found for video {image_id}: {original_path}", "warning")
                return None
    
    def check_video_proxy_exists(self, image_id):
        """Check if a video proxy exists for the given image ID."""
        proxy_path = f"Video Proxies/{image_id}.mp4"
        return os.path.exists(proxy_path)
    
    def get_available_luts(self):
        """Get lists of available correction and style LUTs."""
        # Handle different working directories
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            luts_dir = Path("../LUTS")
        else:
            luts_dir = Path("LUTS")
            
        if not luts_dir.exists():
            return {'correctionLuts': [], 'styleLuts': []}
        
        correction_luts = []
        style_luts = []
        
        # Find correction LUTs (.cube files) in LUTS root folder
        for cube_file in luts_dir.glob("*.cube"):
            correction_luts.append({
                'name': cube_file.stem,  # Filename without extension
                'path': str(cube_file.resolve()),
                'relative_path': cube_file.name
            })
        
        # Find style LUTs (.png files) in LUTS/Fujifilm XTrans III/ folder
        fuji_dir = luts_dir / "Fujifilm XTrans III"
        if fuji_dir.exists():
            for png_file in fuji_dir.glob("*.png"):
                style_luts.append({
                    'name': png_file.stem,  # Filename without extension
                    'path': str(png_file.resolve()),
                    'relative_path': str(png_file.relative_to(luts_dir))
                })
        
        return {
            'correctionLuts': sorted(correction_luts, key=lambda x: x['name']),
            'styleLuts': sorted(style_luts, key=lambda x: x['name'])
        }
    
    def check_video_proxy_exists(self, image_id):
        """Check if video proxy exists for the given image ID."""
        # Handle different working directories
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            proxy_path = Path(f"../Video Proxies/{image_id}.mp4")
        else:
            proxy_path = Path(f"Video Proxies/{image_id}.mp4")
        return proxy_path.exists()
    
    def regenerate_thumbnail(self, image_id):
        """Regenerate thumbnail for an image using generate_thumbnails.py"""
        try:
            import subprocess
            import sys
            
            # Call generate_thumbnails.py with specific image ID
            cmd = [sys.executable, "Scripts/generate_thumbnails.py", "--image-id", str(image_id), "--force"]
            
            # If we're running from Scripts directory, adjust the path
            if os.path.basename(os.getcwd()) == "Scripts":
                cmd = [sys.executable, "generate_thumbnails.py", "--image-id", str(image_id), "--force"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.broadcast_progress(f"✅ Regenerated thumbnail for image {image_id}", "success")
                return True
            else:
                self.broadcast_progress(f"⚠️ Thumbnail regeneration warning for image {image_id}: {result.stderr}", "warning")
                return False  # Don't fail the whole operation for thumbnail issues
                
        except Exception as e:
            self.broadcast_progress(f"⚠️ Error regenerating thumbnail for image {image_id}: {e}", "warning")
            return False  # Don't fail the whole operation for thumbnail issues
    
    def switch_proxy_mode(self, image_id, use_custom_proxy):
        """Switch between original JPG and custom proxy for an image."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get current image info
            cursor.execute("SELECT path, filename, raw_proxy_type FROM images WHERE id = ?", (image_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False, "Image not found"
            
            original_path = Path(row[0])
            current_proxy_type = row[2]
            
            # Determine new proxy type
            if use_custom_proxy:
                # Check if custom proxy exists
                proxy_path = f"RAW Proxies/{image_id}.jpg"
                if not os.path.exists(proxy_path):
                    conn.close()
                    return False, "Custom proxy not found"
                new_proxy_type = "custom_generated"
            else:
                # Check if adjacent JPG exists
                has_adjacent_jpg = False
                for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                    adjacent_jpg = original_path.with_suffix(ext)
                    if adjacent_jpg.exists():
                        has_adjacent_jpg = True
                        break
                
                if not has_adjacent_jpg:
                    conn.close()
                    return False, "Adjacent JPG not found"
                new_proxy_type = "original_jpg"
            
            # Update database
            cursor.execute("""
                UPDATE images 
                SET raw_proxy_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_proxy_type, image_id))
            
            conn.commit()
            conn.close()
            
            # Update hard links in all galleries
            hard_link_success, hard_link_message = self.update_hard_links_for_image(image_id)
            
            # Regenerate thumbnail from new source
            self.regenerate_thumbnail(image_id)
            
            base_message = f"Switched to {'custom proxy' if use_custom_proxy else 'original JPG'}"
            
            if hard_link_success:
                return True, f"{base_message}. {hard_link_message}"
            else:
                return True, f"{base_message}. Warning: {hard_link_message}"
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f"Error switching proxy mode: {e}"
    
    def assign_face_to_person(self, face_id, person_id):
        """Assign a face to a person."""
        if not face_id or not person_id:
            self.broadcast_progress(f"❌ Invalid parameters: face_id={face_id}, person_id={person_id}", "error")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if face exists
            cursor.execute("SELECT id, image_id FROM faces WHERE id = ?", (face_id,))
            face = cursor.fetchone()
            if not face:
                self.broadcast_progress(f"❌ Face {face_id} not found", "error")
                conn.close()
                return False
            
            # Check if person exists
            cursor.execute("SELECT id, name FROM persons WHERE id = ?", (person_id,))
            person = cursor.fetchone()
            if not person:
                self.broadcast_progress(f"❌ Person {person_id} not found", "error")
                conn.close()
                return False
            
            # Assign face to person
            cursor.execute("""
                UPDATE faces 
                SET person_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (person_id, face_id))
            
            conn.commit()
            conn.close()
            
            self.broadcast_progress(f"✅ Assigned face {face_id} (image {face[1]}) to {person[1]} (person {person_id})", "success")
            return True
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error assigning face: {e}", "error")
            return False
    
    def ignore_face(self, face_id):
        """Mark a face as ignored."""
        if not face_id:
            self.broadcast_progress(f"❌ Invalid face_id: {face_id}", "error")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if face exists
            cursor.execute("SELECT id, image_id FROM faces WHERE id = ?", (face_id,))
            face = cursor.fetchone()
            if not face:
                self.broadcast_progress(f"❌ Face {face_id} not found", "error")
                conn.close()
                return False
            
            # Mark face as ignored
            cursor.execute("""
                UPDATE faces 
                SET ignored = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (face_id,))
            
            conn.commit()
            conn.close()
            
            self.broadcast_progress(f"✅ Ignored face {face_id} (image {face[1]})", "success")
            return True
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error ignoring face: {e}", "error")
            return False
    
    def rename_person_with_label_mode(self, person_id, new_name):
        """Rename a person using the face recognition script's label mode."""
        import subprocess
        import os
        
        if not person_id or not new_name.strip():
            return False, "Invalid person_id or new_name"
        
        try:
            # Get person info first
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM persons WHERE id = ?", (person_id,))
            person = cursor.fetchone()
            conn.close()
            
            if not person:
                return False, f"Person {person_id} not found"
            
            old_name = person[0]
            
            # Call the face recognition script with label mode
            script_path = os.path.join(os.path.dirname(__file__), 'face_recognizer_insightface.py')
            cmd = [
                'python3', script_path,
                '--label', str(person_id), new_name.strip()
            ]
            
            self.broadcast_progress(f"🏷️  Renaming person {person_id} from '{old_name}' to '{new_name}'...", "info")
            self.broadcast_progress(f"Running command: {' '.join(cmd)}", "info")
            
            # Set the working directory to the parent directory (where the Scripts folder is)
            parent_dir = os.path.dirname(os.path.dirname(__file__))
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=parent_dir)
            
            if result.returncode == 0:
                self.broadcast_progress(f"✅ Successfully renamed person {person_id} to '{new_name}'", "success")
                return True, f"Person renamed from '{old_name}' to '{new_name}'"
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                self.broadcast_progress(f"❌ Failed to rename person: {error_msg}", "error")
                return False, f"Failed to rename person: {error_msg}"
                
        except subprocess.TimeoutExpired:
            self.broadcast_progress("❌ Label operation timed out", "error")
            return False, "Label operation timed out"
        except Exception as e:
            self.broadcast_progress(f"❌ Error renaming person: {e}", "error")
            return False, f"Error renaming person: {str(e)}"
    
    def get_comprehensive_stats(self):
        """Get comprehensive database statistics for the dashboard."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Overview statistics
            overview = self.get_overview_stats(cursor)
            
            # Camera statistics  
            cameras = self.get_camera_stats(cursor)
            
            # Lens statistics
            lenses = self.get_lens_stats(cursor)
            
            # Focal length statistics
            focal_lengths = self.get_focal_length_stats(cursor)
            
            # Year statistics
            years = self.get_year_stats(cursor)
            
            # Face/people statistics
            faces = self.get_face_stats(cursor)
            
            # File type statistics
            file_types = self.get_file_type_stats(cursor)
            
            # Pick/reject status statistics
            status = self.get_status_stats()
            
            return {
                'overview': overview,
                'cameras': cameras,
                'lenses': lenses,
                'focal_lengths': focal_lengths,
                'years': years,
                'faces': faces,
                'file_types': file_types,
                'status': status
            }
            
        finally:
            conn.close()
    
    def get_overview_stats(self, cursor):
        """Get overview statistics."""
        stats = {}
        
        # Total images
        cursor.execute("SELECT COUNT(*) as count FROM images")
        stats['Total Images'] = cursor.fetchone()['count']
        
        # Total cameras (unique camera make/model combinations)
        cursor.execute("""
            SELECT COUNT(DISTINCT CASE 
                WHEN camera_make IS NOT NULL AND camera_model IS NOT NULL 
                THEN camera_make || ' ' || camera_model 
                ELSE NULL 
            END) as count FROM images
        """)
        stats['Total Cameras'] = cursor.fetchone()['count']
        
        # Total lenses
        cursor.execute("""
            SELECT COUNT(DISTINCT lens_model) as count 
            FROM images 
            WHERE lens_model IS NOT NULL AND lens_model != ''
        """)
        stats['Total Lenses'] = cursor.fetchone()['count']
        
        # Total people
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM persons 
            WHERE name IS NOT NULL AND name != ''
        """)
        stats['Total People'] = cursor.fetchone()['count']
        
        # Images with faces
        cursor.execute("SELECT COUNT(*) as count FROM images WHERE has_faces > 0")
        stats['Images with Faces'] = cursor.fetchone()['count']
        
        # Processed images
        cursor.execute("SELECT COUNT(*) as count FROM images WHERE needs_processing = 0")
        stats['Processed Images'] = cursor.fetchone()['count']
        
        return stats
    
    def get_camera_stats(self, cursor):
        """Get camera usage statistics."""
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN camera_make IS NOT NULL AND camera_model IS NOT NULL 
                    THEN camera_make || ' ' || camera_model
                    ELSE 'Unknown Camera'
                END as camera,
                COUNT(*) as count
            FROM images 
            GROUP BY camera_make, camera_model
            ORDER BY count DESC
            LIMIT 20
        """)
        
        return [{'camera': row['camera'], 'count': row['count']} for row in cursor.fetchall()]
    
    def get_lens_stats(self, cursor):
        """Get lens usage statistics."""
        cursor.execute("""
            SELECT 
                COALESCE(lens_model, 'Unknown Lens') as lens,
                COUNT(*) as count
            FROM images 
            WHERE lens_model IS NOT NULL AND lens_model != ''
            GROUP BY lens_model
            ORDER BY count DESC
            LIMIT 20
        """)
        
        return [{'lens': row['lens'], 'count': row['count']} for row in cursor.fetchall()]
    
    def get_focal_length_stats(self, cursor):
        """Get focal length (35mm equivalent) statistics."""
        cursor.execute("""
            SELECT 
                COALESCE(focal_length_35mm, 0) as focal_length,
                COUNT(*) as count
            FROM images 
            WHERE focal_length_35mm IS NOT NULL AND focal_length_35mm > 0
            GROUP BY focal_length_35mm
            ORDER BY focal_length_35mm ASC
            LIMIT 30
        """)
        
        return [{'focal_length': f"{row['focal_length']}mm", 'count': row['count']} for row in cursor.fetchall()]
    
    def get_year_stats(self, cursor):
        """Get yearly statistics."""
        cursor.execute("""
            SELECT 
                strftime('%Y', date_taken) as year,
                COUNT(*) as count
            FROM images 
            WHERE date_taken IS NOT NULL
            GROUP BY strftime('%Y', date_taken)
            ORDER BY year DESC
        """)
        
        return [{'year': row['year'] or 'Unknown', 'count': row['count']} for row in cursor.fetchall()]
    
    def get_face_stats(self, cursor):
        """Get face/people statistics."""
        cursor.execute("""
            SELECT 
                p.name as person,
                COUNT(DISTINCT f.image_id) as count
            FROM persons p
            JOIN faces f ON p.id = f.person_id
            WHERE p.name IS NOT NULL AND p.name != ''
                AND (f.ignored IS NULL OR f.ignored = 0)
            GROUP BY p.id, p.name
            ORDER BY count DESC
            LIMIT 20
        """)
        
        return [{'person': row['person'], 'count': row['count']} for row in cursor.fetchall()]
    
    def get_file_type_stats(self, cursor):
        """Get file type statistics."""
        cursor.execute("""
            SELECT 
                UPPER(COALESCE(file_format, 'Unknown')) as type,
                COUNT(*) as count
            FROM images 
            GROUP BY UPPER(file_format)
            ORDER BY count DESC
        """)
        
        return [{'type': row['type'], 'count': row['count']} for row in cursor.fetchall()]
    
    def get_status_stats(self):
        """Get pick/reject status statistics from JSON files."""
        stats = []
        
        try:
            # Load picks
            picks_file = self.get_json_path('picks.json')
            picks_count = 0
            if os.path.exists(picks_file):
                with open(picks_file, 'r') as f:
                    picks_data = json.load(f)
                    picks_count = len(picks_data)
            
            stats.append({'status': 'Picked', 'count': picks_count})
            
            # Load rejects
            rejects_file = self.get_json_path('delete_list.json')
            rejects_count = 0
            if os.path.exists(rejects_file):
                with open(rejects_file, 'r') as f:
                    rejects_data = json.load(f)
                    rejects_count = len(rejects_data)
            
            stats.append({'status': 'Rejected', 'count': rejects_count})
            
            # Calculate unprocessed (total - picks - rejects)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM images")
            total_images = cursor.fetchone()[0]
            conn.close()
            
            unprocessed_count = total_images - picks_count - rejects_count
            stats.append({'status': 'Unprocessed', 'count': max(0, unprocessed_count)})
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error loading pick/reject stats: {e}", "error")
            stats = [
                {'status': 'Picked', 'count': 0},
                {'status': 'Rejected', 'count': 0},
                {'status': 'Unprocessed', 'count': 0}
            ]
        
        return stats
    
    def save_picks_to_file(self, picks_list):
        """Save picks list to picks.json file."""
        try:
            picks_file = self.get_json_path('picks.json')
            with open(picks_file, 'w') as f:
                json.dump(picks_list, f, indent=2)
            
            self.broadcast_progress(f"💾 Saved {len(picks_list)} picks to {picks_file}", "success")
            return True
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error saving picks: {e}", "error")
            return False
    
    def save_rejects_to_file(self, rejects_list):
        """Save rejects list to delete_list.json file."""
        try:
            rejects_file = self.get_json_path('delete_list.json')
            with open(rejects_file, 'w') as f:
                json.dump(rejects_list, f, indent=2)
            
            self.broadcast_progress(f"🗑️ Saved {len(rejects_list)} rejects to {rejects_file}", "success")
            return True
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error saving rejects: {e}", "error")
            return False
    
    def load_picks_from_file(self):
        """Load picks list from picks.json file."""
        try:
            picks_file = self.get_json_path('picks.json')
            if os.path.exists(picks_file):
                with open(picks_file, 'r') as f:
                    picks_list = json.load(f)
                
                self.broadcast_progress(f"📂 Loaded {len(picks_list)} picks from {picks_file}", "info")
                return picks_list
            else:
                # No picks file exists - return empty list (this is normal)
                return []
                
        except Exception as e:
            self.broadcast_progress(f"❌ Error loading picks: {e}", "error")
            return None
    
    def load_rejects_from_file(self):
        """Load rejects list from delete_list.json file."""
        try:
            rejects_file = self.get_json_path('delete_list.json')
            if os.path.exists(rejects_file):
                with open(rejects_file, 'r') as f:
                    rejects_list = json.load(f)
                
                self.broadcast_progress(f"🗑️ Loaded {len(rejects_list)} rejects from {rejects_file}", "info")
                return rejects_list
            else:
                # No rejects file exists - return empty list (this is normal)
                return []
                
        except Exception as e:
            self.broadcast_progress(f"❌ Error loading rejects: {e}", "error")
            return None
    
    def create_gallery_from_search(self, search_string, gallery_name, face_samples=False, picks_file=None):
        """Create gallery using search string via the gallery creation script."""
        try:
            import subprocess
            import sys
            
            # Get the script path
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                script_path = "gallery_create_search.py"
                working_dir = "."
            else:
                script_path = "Scripts/gallery_create_search.py"
                working_dir = "."
            
            # Clean gallery name (remove special characters but preserve spaces)
            clean_gallery_name = "".join(c if c.isalnum() or c in " -_" else "" for c in gallery_name)
            
            # Build command
            if face_samples:
                cmd = [sys.executable, script_path, "--name", clean_gallery_name, "--face-samples"]
            elif picks_file:
                cmd = [sys.executable, script_path, "--name", clean_gallery_name, "--picks-file", picks_file]
            elif search_string:
                cmd = [sys.executable, script_path, search_string, "--name", clean_gallery_name]
            else:
                return False, "No search criteria provided"
            
            self.broadcast_progress(f"🚀 Running gallery creation: {' '.join(cmd)}", "info")
            
            # Run the gallery creation script
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Success - rebuild the galleries.json
                self.rebuild_galleries_json()
                self.broadcast_progress(f"✅ Gallery '{clean_gallery_name}' created successfully", "success")
                return True, f"Gallery '{clean_gallery_name}' created successfully"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Gallery creation failed"
                self.broadcast_progress(f"❌ Gallery creation failed: {error_msg}", "error")
                return False, f"Gallery creation failed: {error_msg}"
            
        except subprocess.TimeoutExpired:
            self.broadcast_progress("❌ Gallery creation timed out (>5 minutes)", "error")
            return False, "Gallery creation timed out (>5 minutes)"
        except Exception as e:
            self.broadcast_progress(f"❌ Error creating gallery: {e}", "error")
            return False, f"Error creating gallery: {str(e)}"
    
    def preview_rejected_files(self):
        """Preview files that will be deleted without actually deleting them."""
        try:
            # Check if delete_list.json exists
            rejects_file = self.get_json_path('delete_list.json')
            if not os.path.exists(rejects_file):
                return False, "No delete_list.json file found"
            
            # Load the delete list
            try:
                with open(rejects_file, 'r') as f:
                    delete_ids = json.load(f)
                if not delete_ids:
                    return False, "delete_list.json is empty"
            except json.JSONDecodeError:
                return False, "delete_list.json is not valid JSON"
            
            # Convert to integers
            try:
                delete_ids = [int(id) for id in delete_ids]
            except ValueError:
                return False, "All items in delete list must be valid database IDs (integers)"
            
            # Get file information from database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            placeholders = ','.join(['?'] * len(delete_ids))
            cursor.execute(f"""
                SELECT id, path, filename, raw_proxy_type
                FROM images 
                WHERE id IN ({placeholders})
            """, delete_ids)
            
            results = cursor.fetchall()
            conn.close()
            
            preview_data = {
                'total_images': len(delete_ids),
                'files_found': len(results),
                'files': []
            }
            
            for row in results:
                image_id = row['id']
                original_path = row['path']
                filename = row['filename']
                raw_proxy_type = row['raw_proxy_type']
                
                files_to_delete = []
                
                # Add the original file
                if os.path.exists(original_path):
                    files_to_delete.append({
                        'path': original_path,
                        'type': 'original',
                        'exists': True
                    })
                    
                    # For RAW files with adjacent JPGs
                    if raw_proxy_type == 'original_jpg':
                        original_path_obj = Path(original_path)
                        for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                            adjacent_jpg = original_path_obj.with_suffix(ext)
                            if adjacent_jpg.exists():
                                files_to_delete.append({
                                    'path': str(adjacent_jpg),
                                    'type': 'adjacent_jpg',
                                    'exists': True
                                })
                                break
                    
                    # For custom generated proxies
                    elif raw_proxy_type == 'custom_generated':
                        proxy_path = f"RAW Proxies/{image_id}.jpg"
                        if os.path.exists(proxy_path):
                            files_to_delete.append({
                                'path': proxy_path,
                                'type': 'raw_proxy',
                                'exists': True
                            })
                else:
                    files_to_delete.append({
                        'path': original_path,
                        'type': 'original',
                        'exists': False
                    })
                
                preview_data['files'].append({
                    'id': image_id,
                    'filename': filename,
                    'files_to_delete': files_to_delete
                })
            
            return True, preview_data
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error previewing rejected files: {e}", "error")
            return False, f"Error previewing rejected files: {str(e)}"

    def delete_rejected_files(self):
        """Delete files listed in delete_list.json using delete_all_culled_by_id.py."""
        try:
            import subprocess
            import sys
            
            # Get the script path - call delete_all_culled_by_id.py directly
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                script_path = "delete_all_culled_by_id.py"
                working_dir = ".."
            else:
                script_path = "Scripts/delete_all_culled_by_id.py"
                working_dir = "."
            
            # Check if delete_list.json exists
            rejects_file = self.get_json_path('delete_list.json')
            if not os.path.exists(rejects_file):
                return False, "No delete_list.json file found"
            
            # Check if the file has any content
            try:
                with open(rejects_file, 'r') as f:
                    rejects_data = json.load(f)
                if not rejects_data:
                    return False, "delete_list.json is empty"
            except json.JSONDecodeError:
                return False, "delete_list.json is not valid JSON"
            
            # Build command to run delete script with auto-confirm
            cmd = [sys.executable, script_path]
            
            self.broadcast_progress(f"🗑️ Starting deletion of {len(rejects_data)} rejected files...", "info")
            
            # Run the deletion script with auto-confirmation
            # We'll provide "yes" as input to auto-confirm the deletion
            result = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send "yes" to confirm deletion
            stdout, stderr = result.communicate(input="yes\n")
            
            if result.returncode == 0:
                self.broadcast_progress("✅ Deletion completed successfully", "success")
                
                # Rebuild galleries.json after successful deletion
                self.broadcast_progress("🔨 Rebuilding galleries.json after deletion...", "info")
                self.rebuild_galleries_json()
                
                return True, f"Successfully deleted {len(rejects_data)} rejected files and updated galleries"
            else:
                error_msg = stderr.strip() if stderr else stdout.strip()
                self.broadcast_progress(f"❌ Deletion failed: {error_msg}", "error")
                return False, f"Deletion failed: {error_msg}"
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error starting deletion: {e}", "error")
            return False, f"Error starting deletion: {str(e)}"
    
    def rebuild_galleries_json(self):
        """Rebuild the main galleries.json file by calling the standalone script."""
        try:
            import subprocess
            import sys
            
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
            
            self.broadcast_progress(f"🔨 Running gallery rebuild: {' '.join(cmd)}", "info")
            
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.broadcast_progress("✅ Gallery rebuild completed successfully", "success")
                return True
            else:
                error_msg = result.stderr.strip() if result.stderr else "Gallery rebuild failed"
                self.broadcast_progress(f"❌ Gallery rebuild failed: {error_msg}", "error")
                return False
                
        except subprocess.TimeoutExpired:
            self.broadcast_progress("❌ Gallery rebuild timed out", "error")
            return False
        except Exception as e:
            self.broadcast_progress(f"❌ Error running gallery rebuild: {e}", "error")
            return False
    
    def rebuild_gallery_json(self, gallery_path):
        """Rebuild a specific gallery's image_data.json file."""
        try:
            import subprocess
            import sys
            import os
            
            # Validate gallery path
            if not os.path.isdir(gallery_path):
                return False, f"Gallery directory not found: {gallery_path}"
            
            # Get the script path
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                script_path = "gallery_rebuild_json.sh"
                working_dir = ".."
            else:
                script_path = "Scripts/gallery_rebuild_json.sh"
                working_dir = "."
            
            # Make sure the script is executable
            script_full_path = os.path.join(working_dir, script_path)
            if not os.path.exists(script_full_path):
                return False, f"Gallery rebuild script not found: {script_full_path}"
            
            # Call the rebuild script with the gallery path
            cmd = ["bash", script_path, gallery_path]
            
            self.broadcast_progress(f"🔨 Running gallery rebuild for {gallery_path}: {' '.join(cmd)}", "info")
            
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for large galleries
            )
            
            if result.returncode == 0:
                self.broadcast_progress(f"✅ Gallery rebuild completed successfully for {gallery_path}", "success")
                
                # Extract useful information from output
                lines = result.stdout.strip().split('\n')
                summary_lines = [line for line in lines if any(indicator in line for indicator in ['✅', '📊', '🎉', '⚠️'])]
                summary = '\n'.join(summary_lines[-3:]) if summary_lines else "Gallery rebuilt successfully"
                
                return True, summary
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                self.broadcast_progress(f"❌ Gallery rebuild failed for {gallery_path}: {error_msg}", "error")
                return False, f"Gallery rebuild failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            self.broadcast_progress(f"❌ Gallery rebuild timed out for {gallery_path}", "error")
            return False, "Gallery rebuild timed out (>5 minutes)"
        except Exception as e:
            self.broadcast_progress(f"❌ Error running gallery rebuild for {gallery_path}: {e}", "error")
            return False, f"Error running gallery rebuild: {str(e)}"
    
    def rebuild_galleries_list(self):
        """Rebuild the main galleries.json list by calling the rebuild script."""
        try:
            import subprocess
            import sys
            
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
    
    def process_new_images(self, directory="Master Photo Library"):
        """Process new images: extract metadata, generate thumbnails/proxies, detect faces, cluster."""
        try:
            import subprocess
            import sys
            import os
            
            # Validate directory
            if not os.path.exists(directory):
                return False, f"Directory not found: {directory}"
            
            self.broadcast_progress(f"🚀 Processing new images from: {directory}", "info")
            
            # Get the working directory
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                working_dir = ".."
            else:
                working_dir = "."
            
            steps_completed = []
            
            # Step 1: Extract Metadata
            self.broadcast_progress("📊 Step 1: Extracting metadata...", "info")
            try:
                cmd = [sys.executable, "Scripts/extract_metadata.py", directory]
                result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    steps_completed.append("✅ Metadata extracted")
                    self.broadcast_progress("✅ Metadata extraction completed", "success")
                else:
                    steps_completed.append("⚠️ Metadata extraction failed")
                    self.broadcast_progress(f"⚠️ Metadata extraction failed: {result.stderr}", "warning")
            except Exception as e:
                steps_completed.append("⚠️ Metadata extraction failed")
                self.broadcast_progress(f"⚠️ Metadata extraction error: {e}", "error")
            
            # Step 2: Generate Thumbnails
            self.broadcast_progress("🖼️ Step 2: Generating thumbnails...", "info")
            try:
                cmd = [sys.executable, "Scripts/generate_thumbnails.py"]
                result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    steps_completed.append("✅ Thumbnails generated")
                    self.broadcast_progress("✅ Thumbnail generation completed", "success")
                else:
                    steps_completed.append("⚠️ Thumbnail generation failed")
                    self.broadcast_progress(f"⚠️ Thumbnail generation failed: {result.stderr}", "warning")
            except Exception as e:
                steps_completed.append("⚠️ Thumbnail generation failed")
                self.broadcast_progress(f"⚠️ Thumbnail generation error: {e}", "error")
            
            # Step 3: Generate HEIC Proxies
            self.broadcast_progress("🖼️ Step 3: Generating HEIC proxies...", "info")
            try:
                cmd = [sys.executable, "Scripts/generate_heic_proxies.py"]
                result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    steps_completed.append("✅ HEIC proxies generated")
                    self.broadcast_progress("✅ HEIC proxy generation completed", "success")
                else:
                    steps_completed.append("⚠️ HEIC proxy generation failed")
                    self.broadcast_progress(f"⚠️ HEIC proxy generation failed: {result.stderr}", "warning")
            except Exception as e:
                steps_completed.append("⚠️ HEIC proxy generation failed")
                self.broadcast_progress(f"⚠️ HEIC proxy generation error: {e}", "error")
            
            # Step 4: Generate RAW Proxies
            self.broadcast_progress("🎞️ Step 4: Generating RAW proxies...", "info")
            try:
                cmd = [sys.executable, "Scripts/generate_raw_proxies.py"]
                result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    steps_completed.append("✅ RAW proxies generated")
                    self.broadcast_progress("✅ RAW proxy generation completed", "success")
                else:
                    steps_completed.append("⚠️ RAW proxy generation failed")
                    self.broadcast_progress(f"⚠️ RAW proxy generation failed: {result.stderr}", "warning")
            except Exception as e:
                steps_completed.append("⚠️ RAW proxy generation failed")
                self.broadcast_progress(f"⚠️ RAW proxy generation error: {e}", "error")
            
            # Step 5: Extract Faces
            self.broadcast_progress("👥 Step 5: Extracting faces...", "info")
            try:
                cmd = [sys.executable, "Scripts/face_recognizer_insightface.py", "--extract"]
                result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    steps_completed.append("✅ Face extraction completed")
                    self.broadcast_progress("✅ Face extraction completed", "success")
                else:
                    steps_completed.append("⚠️ Face extraction failed")
                    self.broadcast_progress(f"⚠️ Face extraction failed: {result.stderr}", "warning")
            except Exception as e:
                steps_completed.append("⚠️ Face extraction failed")
                self.broadcast_progress(f"⚠️ Face extraction error: {e}", "error")
            
            # Step 6: Cluster New Faces
            self.broadcast_progress("🔗 Step 6: Clustering new faces...", "info")
            try:
                cmd = [sys.executable, "Scripts/face_recognizer_insightface.py", "--cluster-new-loop"]
                result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
                if result.returncode == 0:
                    steps_completed.append("✅ Face clustering completed")
                    self.broadcast_progress("✅ Face clustering completed", "success")
                else:
                    steps_completed.append("⚠️ Face clustering failed")
                    self.broadcast_progress(f"⚠️ Face clustering failed: {result.stderr}", "warning")
            except Exception as e:
                steps_completed.append("⚠️ Face clustering failed")
                self.broadcast_progress(f"⚠️ Face clustering error: {e}", "error")
            
            # Create summary message
            summary = f"New image processing completed for '{directory}':\n\n" + "\n".join(steps_completed)
            summary += "\n\nProcessing workflow finished. Check the gallery to see new images."
            
            self.broadcast_progress("🎉 New image processing workflow completed!", "success")
            return True, summary
                
        except Exception as e:
            self.broadcast_progress(f"❌ Error in process_new_images: {e}", "error")
            return False, f"Error processing new images: {str(e)}"
    
    def handle_progress_stream(self):
        """Handle Server-Sent Events for progress streaming."""
        try:
            # Set up SSE headers
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_cors_headers()
            self.end_headers()
            
            # Send initial connection message
            import time
            timestamp = time.strftime("%H:%M:%S")
            data = f"data: {json.dumps({'message': 'Connected to progress stream', 'type': 'info', 'timestamp': timestamp})}\n\n"
            self.wfile.write(data.encode('utf-8'))
            self.wfile.flush()
            
            # Keep connection alive with periodic heartbeats
            try:
                while True:
                    time.sleep(5)  # Send heartbeat every 5 seconds
                    timestamp = time.strftime("%H:%M:%S")
                    data = f"data: {json.dumps({'message': 'heartbeat', 'type': 'ping', 'timestamp': timestamp})}\n\n"
                    self.wfile.write(data.encode('utf-8'))
                    self.wfile.flush()
            except Exception as e:
                print(f"SSE client disconnected: {e}")
                    
        except Exception as e:
            print(f"Error in progress stream: {e}")
    
    def send_progress_event(self, message, event_type="info"):
        """Send a progress event via SSE."""
        try:
            import time
            timestamp = time.strftime("%H:%M:%S")
            data = f"data: {json.dumps({'message': message, 'type': event_type, 'timestamp': timestamp})}\n\n"
            self.wfile.write(data.encode('utf-8'))
            self.wfile.flush()
        except Exception as e:
            # Connection lost, ignore
            print(f"SSE send error: {e}")
            pass
    
    def broadcast_progress(self, message, event_type="info"):
        """Log progress messages to file for web interface polling."""
        import time
        import os
        
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{event_type.upper()}] {message}\n"
        
        # Print to console
        print(log_entry.strip())
        
        # Write to progress log file
        try:
            log_file = "progress.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
                f.flush()
        except Exception as e:
            print(f"Error writing to progress log: {e}")  # Keep as print since this is the log system itself
    
    def get_progress_log(self, offset=0):
        """Get progress log entries from the specified offset."""
        try:
            log_file = "progress.log"
            if not os.path.exists(log_file):
                return {"entries": [], "total_lines": 0}
            
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Get lines from offset onwards
            new_lines = lines[offset:]
            
            # Parse each line to extract timestamp, type, and message
            entries = []
            for line in new_lines:
                line = line.strip()
                if line and line.startswith('['):
                    try:
                        # Parse format: [HH:MM:SS] [TYPE] message
                        import re
                        match = re.match(r'\[(\d{2}:\d{2}:\d{2})\] \[(\w+)\] (.+)', line)
                        if match:
                            timestamp, log_type, message = match.groups()
                            entries.append({
                                "timestamp": timestamp,
                                "type": log_type.lower(),
                                "message": message
                            })
                        else:
                            # Fallback for lines that don't match the format
                            entries.append({
                                "timestamp": "",
                                "type": "info",
                                "message": line
                            })
                    except:
                        # Fallback for any parsing errors
                        entries.append({
                            "timestamp": "",
                            "type": "info", 
                            "message": line
                        })
            
            return {
                "entries": entries,
                "total_lines": len(lines),
                "new_entries": len(entries)
            }
            
        except Exception as e:
            self.broadcast_progress(f"❌ Error reading progress log: {e}", "error")
            return {"entries": [], "total_lines": 0, "error": str(e)}
    
    def log_message(self, format, *args):
        """Override to reduce log noise."""
        pass

def create_handler_class(db_path):
    """Create handler class with database path."""
    class Handler(FaceAPIHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, db_path=db_path, **kwargs)
    return Handler

def main():
    parser = argparse.ArgumentParser(description='Face detection API server')
    parser.add_argument('--port', type=int, default=8001, help='Server port')
    parser.add_argument('--bind', default='127.0.0.1', help='Bind address (default: 127.0.0.1)')
    parser.add_argument('--db', help='Database file path (auto-detected if not specified)')
    
    args = parser.parse_args()
    
    # Auto-detect database path if not specified
    if args.db is None:
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            args.db = "image_metadata.db"  # Same directory
        else:
            args.db = "Scripts/image_metadata.db"  # Scripts subdirectory
    
    handler_class = create_handler_class(args.db)
    server = HTTPServer((args.bind, args.port), handler_class)
    
    print(f"🚀 Face API server starting on http://{args.bind}:{args.port}")
    print(f"📊 Database: {args.db}")
    print("🔍 Endpoints:")
    print(f"   GET /api/faces/{{image_id}} - Get faces for image")
    print(f"   GET /api/stats - Get detection statistics")
    print("\nPress Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        server.shutdown()

if __name__ == "__main__":
    main()