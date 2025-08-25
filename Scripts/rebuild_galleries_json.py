#!/usr/bin/env python3
"""
Quick Galleries JSON Rebuilder
Regenerates the main galleries.json file by scanning Hard Link Galleries directory.
"""

import json
import os
from pathlib import Path

def rebuild_galleries_json():
    """Rebuild galleries.json by scanning Hard Link Galleries directory."""
    print("🔨 Rebuilding main gallery list...")
    
    # Determine if we're running from Scripts/ or main directory
    current_dir = Path.cwd()
    if current_dir.name == "Scripts":
        base_dir = current_dir.parent
    else:
        base_dir = current_dir
    
    galleries = []
    hard_link_path = base_dir / "Hard Link Galleries"
    
    if not hard_link_path.exists():
        print("❌ Hard Link Galleries directory not found")
        return False
    
    total_images = 0
    
    for gallery_dir in hard_link_path.iterdir():
        if gallery_dir.is_dir() and not gallery_dir.name.startswith('.'):
            gallery_name = gallery_dir.name
            json_file = gallery_dir / "image_data.json"
            
            if json_file.exists():
                try:
                    # Read the JSON to get image count and verify it's valid
                    with open(json_file, 'r') as f:
                        gallery_data = json.load(f)
                    
                    image_count = len(gallery_data)
                    total_images += image_count
                    
                    gallery_info = {
                        "name": gallery_name,
                        "jsonPath": str(json_file.relative_to(base_dir)),
                        "imageCount": image_count
                    }
                    
                    galleries.append(gallery_info)
                    print(f"✅ Found gallery: {gallery_name} ({image_count} images)")
                    
                except json.JSONDecodeError:
                    print(f"⚠️ Skipping {gallery_name}: Invalid JSON file")
                except Exception as e:
                    print(f"⚠️ Error reading {gallery_name}: {e}")
            else:
                print(f"⚠️ Skipping {gallery_name}: No image_data.json found")
    
    # Sort by name (keep alphabetical for gallery list)
    galleries.sort(key=lambda x: x['name'])
    
    # Write galleries.json
    galleries_file = base_dir / "JSON" / "galleries.json"
    try:
        with open(galleries_file, 'w') as f:
            json.dump(galleries, f, indent=2)
        
        print(f"\n🎉 Successfully rebuilt gallery list:")
        print(f"   📁 File: {galleries_file}")
        print(f"   📊 Galleries: {len(galleries)}")
        print(f"   📸 Total images: {total_images}")
        print(f"   🌐 Ready for web interface!")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to write galleries.json: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    # Script works from either Scripts/ directory or main directory
    
    print("🚀 Quick Galleries JSON Rebuilder")
    print("-" * 40)
    
    success = rebuild_galleries_json()
    
    if success:
        print("\n💡 Tip: Refresh your browser to see updated gallery list")
        sys.exit(0)
    else:
        print("\n❌ Failed to rebuild galleries.json")
        sys.exit(1)