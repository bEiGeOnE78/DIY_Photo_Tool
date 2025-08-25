#!/usr/bin/env python3
"""
Image Metadata Database Setup
Creates SQLite database schema for storing image metadata, EXIF data, and analysis results.
"""

import sqlite3
import os

def create_database(db_path=None):
    """Create SQLite database with image metadata schema."""
    
    if db_path is None:
        # Auto-detect database location
        from pathlib import Path
        current_dir = Path.cwd()
        if current_dir.name == "Scripts":
            db_path = "image_metadata.db"  # Same directory
        else:
            db_path = "Scripts/image_metadata.db"  # Scripts subdirectory
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Main images table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            file_size INTEGER,
            file_hash TEXT,
            last_modified DATETIME,
            
            -- Date/time information
            date_taken DATETIME,
            date_original DATETIME,
            date_digitized DATETIME,
            
            -- Image dimensions
            width INTEGER,
            height INTEGER,
            orientation INTEGER,
            
            -- Camera information
            camera_make TEXT,
            camera_model TEXT,
            lens_make TEXT,
            lens_model TEXT,
            
            -- Shooting parameters
            iso INTEGER,
            aperture REAL,
            shutter_speed TEXT,
            focal_length REAL,
            focal_length_35mm INTEGER,
            exposure_compensation REAL,
            flash TEXT,
            white_balance TEXT,
            exposure_mode TEXT,
            metering_mode TEXT,
            film_mode TEXT,
            
            -- Location data
            gps_latitude REAL,
            gps_longitude REAL,
            gps_altitude REAL,
            location_name TEXT,
            
            -- File format info
            file_format TEXT,
            color_space TEXT,
            bit_depth INTEGER,
            
            -- Processing flags
            needs_processing INTEGER DEFAULT 1,
            has_faces INTEGER DEFAULT 0,
            has_duplicates INTEGER DEFAULT 0,
            
            -- RAW file proxy tracking
            raw_proxy_type TEXT,  -- 'original_jpg', 'custom_generated', 'none'
            raw_processing_settings TEXT,  -- JSON blob for RawTherapee settings
            
            -- File type and video-specific fields
            file_type TEXT DEFAULT 'image',  -- 'image' or 'video'
            duration REAL,  -- Video duration in seconds
            bit_rate INTEGER,  -- Video bit rate
            codec TEXT,  -- Video codec
            frame_rate TEXT,  -- Video frame rate
            rotation INTEGER,  -- Video rotation
            audio_codec TEXT,  -- Audio codec
            audio_channels INTEGER,  -- Number of audio channels
            thumbnail_path TEXT  -- Path to generated thumbnail
            
            -- Timestamps
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Face detection results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            person_id INTEGER,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            confidence REAL,
            embedding BLOB,
            ignored INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
        )
    ''')
    
    # Person identification
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            confirmed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tags and categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT,
            color TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Image-tag relationships
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_tags (
            image_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'manual',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (image_id, tag_id),
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    ''')
    
    # Collections/albums
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            cover_image_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cover_image_id) REFERENCES images(id)
        )
    ''')
    
    # Image-collection relationships
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_images (
            collection_id INTEGER NOT NULL,
            image_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (collection_id, image_id),
            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
        )
    ''')
    
    # Create indexes for performance
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_images_path ON images(path)",
        "CREATE INDEX IF NOT EXISTS idx_images_date_taken ON images(date_taken)",
        "CREATE INDEX IF NOT EXISTS idx_images_filename ON images(filename)",
        "CREATE INDEX IF NOT EXISTS idx_images_camera_make ON images(camera_make)",
        "CREATE INDEX IF NOT EXISTS idx_images_last_modified ON images(last_modified)",
        "CREATE INDEX IF NOT EXISTS idx_images_needs_processing ON images(needs_processing)",
        "CREATE INDEX IF NOT EXISTS idx_faces_image_id ON faces(image_id)",
        "CREATE INDEX IF NOT EXISTS idx_faces_person_id ON faces(person_id)",
        "CREATE INDEX IF NOT EXISTS idx_image_tags_image_id ON image_tags(image_id)",
        "CREATE INDEX IF NOT EXISTS idx_image_tags_tag_id ON image_tags(tag_id)",
    ]
    
    for index_sql in indexes:
        cursor.execute(index_sql)
    
    # Add column migration for existing databases
    try:
        cursor.execute("ALTER TABLE images ADD COLUMN film_mode TEXT")
        print("Added film_mode column to existing database")
    except sqlite3.OperationalError:
        # Column already exists or table doesn't exist yet
        pass
    
    # Add RAW proxy tracking columns
    try:
        cursor.execute("ALTER TABLE images ADD COLUMN raw_proxy_type TEXT")
        print("Added raw_proxy_type column to existing database")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE images ADD COLUMN raw_processing_settings TEXT")
        print("Added raw_processing_settings column to existing database")
    except sqlite3.OperationalError:
        pass
    
    # Add ignored column to faces table for existing databases
    try:
        cursor.execute("ALTER TABLE faces ADD COLUMN ignored INTEGER DEFAULT 0")
        print("Added ignored column to existing faces table")
    except sqlite3.OperationalError:
        pass
    
    # Add updated_at column to faces table for existing databases
    try:
        cursor.execute("ALTER TABLE faces ADD COLUMN updated_at DATETIME")
        cursor.execute("UPDATE faces SET updated_at = created_at WHERE updated_at IS NULL")
        print("Added updated_at column to existing faces table")
    except sqlite3.OperationalError:
        pass
    
    # Add video support columns to existing databases
    video_columns = [
        ("file_type", "TEXT DEFAULT 'image'"),
        ("duration", "REAL"),
        ("bit_rate", "INTEGER"),
        ("codec", "TEXT"),
        ("frame_rate", "TEXT"),
        ("rotation", "INTEGER"),
        ("audio_codec", "TEXT"),
        ("audio_channels", "INTEGER"),
        ("thumbnail_path", "TEXT")
    ]
    
    for column_name, column_type in video_columns:
        try:
            cursor.execute(f"ALTER TABLE images ADD COLUMN {column_name} {column_type}")
            print(f"Added {column_name} column to existing database")
        except sqlite3.OperationalError:
            pass
    
    conn.commit()
    conn.close()
    
    print(f"Database created successfully: {db_path}")
    return db_path

if __name__ == "__main__":
    db_path = create_database()
    print(f"Image metadata database ready at: {os.path.abspath(db_path)}")