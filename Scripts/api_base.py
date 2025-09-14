#!/usr/bin/env python3
"""
Base class for API servers with shared utilities.
"""

import sqlite3
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import threading


class BaseAPIHandler(BaseHTTPRequestHandler):
    """Base handler class with shared utilities for API servers."""
    
    def __init__(self, *args, db_path=None, **kwargs):
        if db_path is None:
            # Auto-detect database location
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                db_path = "image_metadata.db"  # Same directory
            else:
                db_path = "Scripts/image_metadata.db"  # Scripts subdirectory
        self.db_path = db_path
        
        # Progress streaming setup
        if not hasattr(self.__class__, '_progress_listeners'):
            self.__class__._progress_listeners = []
            self.__class__._progress_lock = threading.Lock()
            
        super().__init__(*args, **kwargs)
    
    def get_json_path(self, filename):
        """Get correct path to JSON file, works from Scripts/ or main directory."""
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            return f"../JSON/{filename}"
        else:
            return f"JSON/{filename}"
    
    def do_OPTIONS(self):
        """Handle preflight CORS requests."""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def send_cors_headers(self):
        """Send CORS headers for browser compatibility."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def send_json_response(self, data):
        """Send JSON response with proper headers."""
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def handle_progress_stream(self):
        """Handle Server-Sent Events for progress streaming."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_cors_headers()
        self.end_headers()
        
        # Add this client to listeners
        with self.__class__._progress_lock:
            self.__class__._progress_listeners.append(self.wfile)
        
        try:
            # Keep connection alive
            while True:
                import time
                time.sleep(1)
                self.wfile.write(b"data: ping\n\n")
                self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            # Remove this client from listeners
            with self.__class__._progress_lock:
                if self.wfile in self.__class__._progress_listeners:
                    self.__class__._progress_listeners.remove(self.wfile)
    
    def send_progress_event(self, data):
        """Send progress event to all connected clients."""
        event_data = f"data: {json.dumps(data)}\n\n"
        
        with self.__class__._progress_lock:
            disconnected = []
            for listener in self.__class__._progress_listeners[:]:
                try:
                    listener.write(event_data.encode())
                    listener.flush()
                except (ConnectionResetError, BrokenPipeError, OSError):
                    disconnected.append(listener)
            
            # Remove disconnected listeners
            for listener in disconnected:
                if listener in self.__class__._progress_listeners:
                    self.__class__._progress_listeners.remove(listener)
    
    def broadcast_progress(self, message, message_type="info"):
        """Broadcast progress message to all connected clients."""
        from datetime import datetime
        
        progress_data = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': message,
            'type': message_type
        }
        
        self.send_progress_event(progress_data)
        print(f"[{progress_data['timestamp']}] {message}")
    
    def log_message(self, format, *args):
        """Override to provide custom logging."""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {format % args}")


def create_server_factory(handler_class):
    """Factory function to create handler with database path."""
    def create_handler(*args, **kwargs):
        return handler_class(*args, **kwargs)
    return create_handler