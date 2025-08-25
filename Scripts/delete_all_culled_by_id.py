#!/usr/bin/env python3
"""
Delete images based on database IDs from delete_list.json.
Handles removal from gallery folders and master locations.
Supports RAW files and their adjacent JPGs.
"""

import os
import json
import sqlite3
import subprocess
from pathlib import Path

def get_database_path():
    """Auto-detect database location."""
    current_dir = Path.cwd()
    if current_dir.name == "Scripts":
        return "image_metadata.db"
    else:
        return "Scripts/image_metadata.db"

def get_delete_list_path():
    """Auto-detect delete list JSON location."""
    current_dir = Path.cwd()
    if current_dir.name == "Scripts":
        return '../JSON/delete_list.json'
    else:
        return 'JSON/delete_list.json'

def find_gallery_files_with_ids(delete_ids, galleries_path):
    """Find files in gallery folders that match the database IDs."""
    gallery_files_to_remove = []
    gallery_json_updates = {}
    
    if not os.path.exists(galleries_path):
        print(f"❌ Hard Link Galleries folder not found at: {galleries_path}")
        return gallery_files_to_remove, gallery_json_updates
    
    # Search through all gallery folders
    for gallery_folder in os.listdir(galleries_path):
        gallery_path = os.path.join(galleries_path, gallery_folder)
        if not os.path.isdir(gallery_path):
            continue
            
        # Check for image_data.json in this gallery
        json_file = os.path.join(gallery_path, 'image_data.json')
        if not os.path.exists(json_file):
            continue
            
        try:
            with open(json_file, 'r') as f:
                gallery_data = json.load(f)
                
            # Track which entries to remove and updated gallery data
            updated_gallery_data = []
            entries_to_remove = []
            
            # Check each image in the gallery JSON
            for image_data in gallery_data:
                image_id = image_data.get('_imageId')
                if image_id in delete_ids:
                    # Found a match - add the actual file path to removal list
                    source_file = image_data.get('SourceFile', '')
                    if source_file:
                        full_path = os.path.join(os.getcwd(), source_file)
                        if os.path.exists(full_path):
                            gallery_files_to_remove.append({
                                'path': full_path,
                                'gallery': gallery_folder,
                                'image_id': image_id,
                                'filename': os.path.basename(full_path)
                            })
                            entries_to_remove.append(image_data)
                            print(f"🎯 Found in '{gallery_folder}': ID {image_id}")
                else:
                    # Keep this entry
                    updated_gallery_data.append(image_data)
            
            # If we have entries to remove, store the updated gallery data
            if entries_to_remove:
                gallery_json_updates[json_file] = {
                    'updated_data': updated_gallery_data,
                    'removed_count': len(entries_to_remove)
                }
                        
        except Exception as e:
            print(f"⚠️ Error reading gallery JSON {json_file}: {e}")
            continue
    
    return gallery_files_to_remove, gallery_json_updates

def get_original_file_paths(delete_ids, db_path):
    """Get original file paths from database for the given IDs."""
    original_files = []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get original file paths for all delete IDs
    placeholders = ','.join(['?'] * len(delete_ids))
    cursor.execute(f"""
        SELECT id, path, filename, raw_proxy_type
        FROM images 
        WHERE id IN ({placeholders})
    """, delete_ids)
    
    results = cursor.fetchall()
    
    for row in results:
        original_path = row['path']
        raw_proxy_type = row['raw_proxy_type']
        image_id = row['id']
        filename = row['filename']
        
        files_to_delete = []
        
        # Add the original file
        if os.path.exists(original_path):
            files_to_delete.append(original_path)
            
            # For RAW files with adjacent JPGs, also delete the adjacent JPG
            if raw_proxy_type == 'original_jpg':
                original_path_obj = Path(original_path)
                for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                    adjacent_jpg = original_path_obj.with_suffix(ext)
                    if adjacent_jpg.exists():
                        files_to_delete.append(str(adjacent_jpg))
                        break
            
            # For custom generated proxies, delete the proxy file
            elif raw_proxy_type == 'custom_generated':
                proxy_path = f"RAW Proxies/{image_id}.jpg"
                if os.path.exists(proxy_path):
                    files_to_delete.append(proxy_path)
        
        original_files.append({
            'id': image_id,
            'filename': filename,
            'files': files_to_delete
        })
    
    conn.close()
    return original_files

def delete_from_database(delete_ids, db_path):
    """Remove the image records from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Delete related records (foreign key constraints should handle this)
    placeholders = ','.join(['?'] * len(delete_ids))
    
    cursor.execute(f"DELETE FROM images WHERE id IN ({placeholders})", delete_ids)
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return deleted_count

def main():
    print("🗑️ DELETE CULLED IMAGES BY DATABASE ID")
    print("=" * 50)
    
    # Get paths
    db_path = get_database_path()
    delete_list_path = get_delete_list_path()
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        print("Please run metadata extraction first.")
        return
    
    # Load delete list
    if not os.path.exists(delete_list_path):
        print(f"❌ Delete list not found: {delete_list_path}")
        print("Please create a JSON file with an array of database IDs to delete.")
        return
    
    try:
        with open(delete_list_path, 'r') as f:
            delete_list = json.load(f)
    except Exception as e:
        print(f"❌ Error reading delete list: {e}")
        return
    
    if not isinstance(delete_list, list):
        print(f"❌ Delete list must be an array of database IDs")
        return
    
    # Convert to integers
    try:
        delete_ids = [int(id) for id in delete_list]
    except ValueError:
        print(f"❌ All items in delete list must be valid database IDs (integers)")
        return
    
    print(f"📋 Loaded {len(delete_ids)} image IDs to delete")
    print(f"   IDs: {delete_ids}")
    
    # Find files in gallery folders
    galleries_path = "Hard Link Galleries"
    gallery_files, gallery_json_updates = find_gallery_files_with_ids(delete_ids, galleries_path)
    
    # Get original file paths from database
    original_files = get_original_file_paths(delete_ids, db_path)
    
    # Show summary
    print(f"\n📊 DELETION SUMMARY:")
    print(f"   Gallery files found: {len(gallery_files)}")
    print(f"   Gallery JSON files to update: {len(gallery_json_updates)}")
    total_original_files = sum(len(f['files']) for f in original_files)
    print(f"   Original files found: {total_original_files}")
    print(f"   Database records: {len(delete_ids)}")
    
    if not gallery_files and not original_files:
        print("❌ No files found to delete")
        return
    
    # Confirm deletion
    print(f"\n⚠️ This will permanently delete:")
    for gf in gallery_files:
        print(f"   🔗 Gallery: {gf['gallery']}/{gf['filename']} (ID: {gf['image_id']})")
    for of in original_files:
        print(f"   📁 Original: {of['filename']} (ID: {of['id']}) + {len(of['files'])} file(s)")
    
    confirm = input(f"\nContinue with deletion? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Deletion cancelled")
        return
    
    # Delete gallery files (hard links)
    gallery_deleted = 0
    for gf in gallery_files:
        try:
            os.remove(gf['path'])
            print(f"🗑️ Removed from gallery: {gf['gallery']}/{gf['filename']}")
            gallery_deleted += 1
        except Exception as e:
            print(f"❌ Failed to remove gallery file {gf['path']}: {e}")
    
    # Delete original files
    original_deleted = 0
    for of in original_files:
        for file_path in of['files']:
            try:
                os.remove(file_path)
                print(f"🗑️ Deleted: {file_path}")
                original_deleted += 1
            except Exception as e:
                print(f"❌ Failed to delete {file_path}: {e}")
    
    # Update gallery JSON files
    json_updated = 0
    for json_file, update_info in gallery_json_updates.items():
        try:
            with open(json_file, 'w') as f:
                json.dump(update_info['updated_data'], f, indent=2, default=str)
            print(f"📝 Updated gallery JSON: {os.path.basename(os.path.dirname(json_file))} (removed {update_info['removed_count']} entries)")
            json_updated += 1
        except Exception as e:
            print(f"❌ Failed to update gallery JSON {json_file}: {e}")
    
    # Delete from database
    db_deleted = delete_from_database(delete_ids, db_path)
    
    print(f"\n🎉 DELETION COMPLETE:")
    print(f"   🔗 Gallery files removed: {gallery_deleted}")
    print(f"   📝 Gallery JSON files updated: {json_updated}")
    print(f"   📁 Original files deleted: {original_deleted}")
    print(f"   💾 Database records removed: {db_deleted}")

if __name__ == "__main__":
    main()