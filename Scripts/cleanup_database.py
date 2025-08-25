#!/usr/bin/env python3
"""
Database Cleanup Utility
Removes stale database entries for files that no longer exist on disk.
"""

import sqlite3
import os
import sys
from pathlib import Path

# Configuration - auto-detect paths
if os.path.basename(os.getcwd()) == "Scripts":
    DB_FILE = "image_metadata.db"
else:
    DB_FILE = "Scripts/image_metadata.db"

def cleanup_stale_entries():
    """Remove database entries for files that no longer exist."""
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        return
    
    print("🧹 DATABASE CLEANUP")
    print("=" * 40)
    print("Checking for stale database entries...")
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all file paths from database
    cursor.execute("SELECT id, path, filename FROM images ORDER BY id")
    all_entries = cursor.fetchall()
    
    print(f"📊 Found {len(all_entries)} entries in database")
    
    stale_entries = []
    checked = 0
    
    for row in all_entries:
        image_id = row['id']
        file_path = row['path']
        filename = row['filename']
        
        checked += 1
        if checked % 500 == 0:
            print(f"   Checked {checked}/{len(all_entries)} entries...")
        
        # Check if file still exists
        if not os.path.exists(file_path):
            stale_entries.append({
                'id': image_id,
                'path': file_path,
                'filename': filename
            })
    
    print(f"\n📋 Results:")
    print(f"   ✅ Valid entries: {len(all_entries) - len(stale_entries)}")
    print(f"   🗑️ Stale entries: {len(stale_entries)}")
    
    if not stale_entries:
        print("\n🎉 Database is clean - no stale entries found!")
        conn.close()
        return
    
    # Show sample of stale entries
    print(f"\n📄 Sample stale entries:")
    for entry in stale_entries[:10]:
        print(f"   • ID {entry['id']}: {entry['filename']}")
    if len(stale_entries) > 10:
        print(f"   ... and {len(stale_entries) - 10} more")
    
    # Confirm deletion
    print(f"\n⚠️ This will permanently remove {len(stale_entries)} database entries")
    print("   (This does NOT delete any actual files)")
    
    confirm = input("\nProceed with cleanup? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cleanup cancelled")
        conn.close()
        return
    
    # Delete stale entries
    print(f"\n🗑️ Removing {len(stale_entries)} stale entries...")
    
    deleted_count = 0
    for entry in stale_entries:
        try:
            # Delete related records (faces, etc.)
            cursor.execute("DELETE FROM faces WHERE image_id = ?", (entry['id'],))
            cursor.execute("DELETE FROM image_tags WHERE image_id = ?", (entry['id'],))
            cursor.execute("DELETE FROM collection_images WHERE image_id = ?", (entry['id'],))
            
            # Delete main record
            cursor.execute("DELETE FROM images WHERE id = ?", (entry['id'],))
            
            deleted_count += 1
            
            if deleted_count % 100 == 0:
                print(f"   Deleted {deleted_count}/{len(stale_entries)} entries...")
                
        except Exception as e:
            print(f"❌ Error deleting entry {entry['id']}: {e}")
    
    # Commit changes
    conn.commit()
    
    # Vacuum database to reclaim space
    print("\n🔧 Optimizing database...")
    cursor.execute("VACUUM")
    
    conn.close()
    
    print(f"\n🎉 Database cleanup complete!")
    print(f"   🗑️ Removed: {deleted_count} stale entries")
    print(f"   💾 Database optimized and space reclaimed")

def analyze_raw_files():
    """Analyze RAW file entries in the database."""
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        return
    
    print("\n🔍 RAW FILE ANALYSIS")
    print("=" * 40)
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # RAW file extensions
    raw_extensions = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.raw'}
    
    # Find all RAW files in database
    raw_conditions = " OR ".join([f"UPPER(filename) LIKE '%.{ext[1:].upper()}'" for ext in raw_extensions])
    cursor.execute(f"""
        SELECT id, path, filename, raw_proxy_type
        FROM images 
        WHERE ({raw_conditions})
        ORDER BY filename
    """)
    
    raw_files = cursor.fetchall()
    
    print(f"📊 RAW files in database: {len(raw_files)}")
    
    if not raw_files:
        print("✅ No RAW files found in database")
        conn.close()
        return
    
    # Analyze RAW files
    existing_raw = 0
    missing_raw = 0
    has_adjacent_jpg = 0
    has_custom_proxy = 0
    
    for row in raw_files:
        raw_path = Path(row['path'])
        
        if raw_path.exists():
            existing_raw += 1
            
            # Check for adjacent JPG
            for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                adjacent_jpg = raw_path.with_suffix(ext)
                if adjacent_jpg.exists():
                    has_adjacent_jpg += 1
                    break
            
            # Check for custom proxy
            proxy_path = f"RAW Proxies/{row['id']}.jpg"
            if os.path.exists(proxy_path):
                has_custom_proxy += 1
        else:
            missing_raw += 1
            print(f"   ⚠️ Missing: {row['filename']} (ID: {row['id']})")
    
    print(f"\n📈 RAW File Statistics:")
    print(f"   ✅ Existing RAW files: {existing_raw}")
    print(f"   ❌ Missing RAW files: {missing_raw}")
    print(f"   📄 With adjacent JPG: {has_adjacent_jpg}")
    print(f"   🎞️ With custom proxy: {has_custom_proxy}")
    
    # Proxy type analysis
    cursor.execute("""
        SELECT raw_proxy_type, COUNT(*) as count
        FROM images 
        WHERE raw_proxy_type IS NOT NULL
        GROUP BY raw_proxy_type
        ORDER BY count DESC
    """)
    
    proxy_stats = cursor.fetchall()
    if proxy_stats:
        print(f"\n🏷️ Proxy Type Distribution:")
        for stat in proxy_stats:
            print(f"   • {stat['raw_proxy_type']}: {stat['count']} files")
    
    conn.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Database maintenance utility')
    parser.add_argument('--cleanup', action='store_true', help='Clean up stale entries')
    parser.add_argument('--analyze', action='store_true', help='Analyze RAW files')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_stale_entries()
    elif args.analyze:
        analyze_raw_files()
    elif args.cleanup and args.analyze:
        cleanup_stale_entries()
        analyze_raw_files()
    elif args.interactive:
        interactive_mode()
    else:
        # Default to analysis only for quick info
        analyze_raw_files()

def interactive_mode():
    print("🛠️ DATABASE MAINTENANCE UTILITY")
    print("=" * 50)
    
    while True:
        print("\nSelect operation:")
        print("1. 🧹 Clean up stale entries (remove deleted files from database)")
        print("2. 🔍 Analyze RAW files in database")
        print("3. 🧹 + 🔍 Run both cleanup and analysis")
        print("4. ❌ Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            cleanup_stale_entries()
        elif choice == "2":
            analyze_raw_files()
        elif choice == "3":
            cleanup_stale_entries()
            analyze_raw_files()
        elif choice == "4":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-4.")

if __name__ == "__main__":
    main()