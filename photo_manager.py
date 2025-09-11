#!/usr/bin/env python3
"""
Photo Management Toolkit
Interactive CLI for managing photo library, metadata, galleries, and face recognition.
"""

import os
import subprocess
import sys
from pathlib import Path


class PhotoManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent

    def show_main_menu(self):
        """Display main menu options."""
        print("\n" + "=" * 60)
        print("📸 PHOTO MANAGEMENT TOOLKIT")
        print("=" * 60)
        print("1.  📊 Extract Metadata (scan photos → database)")
        print("2.  🗄️  Setup Database (create/initialize)")
        print("3.  🖼️  Create Virtual Gallery (date/face/picks)")
        print("4.  🔧 Rebuild Gallery JSON (refresh metadata)")
        print("5.  🖼️  Generate Thumbnails (fast loading)")
        print("6.  🖼️  Generate HEIC Proxies (WebP for web viewing)")
        print("7.  🎞️  Generate RAW Proxies (JPG for RAW files)")
        print("8.  📹 Generate Video Proxies (h.264 for fast playback)")
        print("9.  🎯 Regenerate RAW Picks (custom processing for picked images)")
        print(
            "10. 🚀 Process New Images (extract metadata + thumbnails + proxies + faces)"
        )
        print("11. 🌐 Start Gallery Server (web viewer)")
        print("12. 🛑 Stop Gallery Server (stop both servers)")
        print("13. 🔄 Restart Gallery Server (rebuild + restart)")
        print("14. 🔨 Quick Rebuild Galleries List (no restart)")
        print("15. 👥 Face Recognition (detect/label people)")
        print("16. 🔍 Database Debug (inspect/troubleshoot)")
        print("17. 🛠️ Database Cleanup (remove stale entries)")
        print("18. 🗑️  Delete Culled Images (cleanup)")
        print("19. 🗂️  Delete Galleries (cleanup)")
        print("20. ⚙️  Install Dependencies (complete toolkit + RAW support)")
        print("21. ❌ Exit")
        print("=" * 60)

    def run_script(self, script_name, args=None, is_python=True):
        """Run a script with arguments."""
        script_path = self.base_dir / script_name
        if not script_path.exists():
            print(f"❌ Script not found: {script_name}")
            return False

        if is_python:
            cmd = [sys.executable, str(script_path)]
        else:
            cmd = ["bash", str(script_path)]

        if args:
            cmd.extend(args)

        try:
            print(f"🚀 Running: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=str(self.base_dir))
            return True
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")
            return False
        except Exception as e:
            print(f"❌ Error running {script_name}: {e}")
            return False

    def extract_metadata(self):
        """Extract metadata from photos to database."""
        print("\n📊 EXTRACT METADATA")
        print("-" * 40)

        directory = input(
            "Photo directory (or Enter for 'Master Photo Library'): "
        ).strip()
        if not directory:
            directory = "Master Photo Library"

        if not os.path.exists(directory):
            print(f"❌ Directory not found: {directory}")
            return

        args = [directory]

        print("\nOptions:")
        if input("Force re-extract existing metadata? (y/N): ").lower().startswith("y"):
            args.append("--force")
        if input("Include file hashes? (slower) (y/N): ").lower().startswith("y"):
            args.append("--hash")
        if input("Skip deleted file cleanup? (y/N): ").lower().startswith("y"):
            args.append("--no-cleanup")

        self.run_script("Scripts/extract_metadata.py", args)

    def setup_database(self):
        """Create or initialize database."""
        print("\n🗄️ DATABASE SETUP")
        print("-" * 40)

        db_path = input(
            "Database path (or Enter for 'Scripts/image_metadata.db'): "
        ).strip()
        if not db_path:
            db_path = "Scripts/image_metadata.db"

        if os.path.exists(db_path):
            print(f"⚠️ Database already exists: {db_path}")
            if not input("Continue anyway? (y/N): ").lower().startswith("y"):
                return

        args = [] if db_path == "Scripts/image_metadata.db" else [db_path]
        self.run_script("Scripts/create_db.py", args)

    def create_gallery(self):
        """Create virtual gallery with flexible search functionality."""
        print("\n🖼️ CREATE VIRTUAL GALLERY")
        print("-" * 40)
        print(
            "This creates virtual galleries using hard links with smart RAW file handling."
        )
        print("Gallery types:")
        print("  • 🔍 Search-based galleries (flexible metadata search)")
        print("  • 📋 Picks-based galleries (from saved picks)")
        print("  • 👥 Face sample galleries (one image per person)")
        print()
        print("Search examples:")
        print("  • People: 'Ben', 'Sarah'")
        print("  • Lenses: '27mm fuji', '85mm', '24-70mm'")
        print("  • Dates: '2023', '2023-12', '2023-12-25'")
        print("  • Date ranges: '2023 to 2024', '2023-01 to 2023-06', '2023-2024'")
        print("  • Cameras: 'Canon', 'Sony', 'Fuji'")
        print("  • Combined: 'Ben 27mm 2023', 'fuji 85mm', '2020-2022 Canon'")
        print()
        print("RAW file features:")
        print("  • Smart handling of adjacent JPGs vs custom proxies")
        print("  • Database ID tracking for reliable deletion")
        print("  • Gallery folders contain display-ready files")

        input("\nPress Enter to start gallery creation...")
        self.run_script("Scripts/gallery_create_search.py")

    def rebuild_gallery_json(self):
        """Rebuild gallery JSON files."""
        print("\n🔧 REBUILD GALLERY JSON")
        print("-" * 40)

        directory = input("Gallery directory path (or Enter for interactive): ").strip()
        args = [directory] if directory else []

        self.run_script("Scripts/gallery_rebuild_json.sh", args, is_python=False)

    def generate_thumbnails(self):
        """Generate thumbnails for fast gallery loading."""
        print("\n🖼️ GENERATE THUMBNAILS")
        print("-" * 40)
        print("This creates optimized thumbnails for fast gallery loading.")
        print("Thumbnails are stored on main drive for maximum performance.")

        print("\nOptions:")
        limit = input("Limit to recent N images (or Enter for all): ").strip()

        args = []
        if limit and limit.isdigit():
            args.extend(["--limit", limit])
        if (
            input("Force regenerate existing thumbnails? (y/N): ")
            .lower()
            .startswith("y")
        ):
            args.append("--force")
        if (
            input("Generate thumbnails only for HEIC files? (y/N): ")
            .lower()
            .startswith("y")
        ):
            args.append("--heic-only")
        if input("Show statistics only? (y/N): ").lower().startswith("y"):
            args = ["--stats"]

        self.run_script("Scripts/generate_thumbnails.py", args)

    def generate_heic_proxies(self):
        """Generate WebP proxies from HEIC files for web viewing."""
        print("\n🖼️ GENERATE HEIC PROXIES")
        print("-" * 40)
        print(
            "This creates WebP proxies from HEIC files for web browser compatibility."
        )
        print("Benefits:")
        print("  • Enables HEIC viewing in Firefox/Chrome/Edge")
        print("  • Uses high-quality conversion with proper orientation")
        print("  • Maintains full resolution for gallery viewing")
        print("  • Files are named by database ID to avoid conflicts")
        print("  • Original HEIC files remain untouched")

        print(f"\nProxy storage: HEIC Proxies/")
        print("Conversion methods: ImageMagick → sips → PIL (fallback)")

        input("\nPress Enter to generate HEIC proxies...")
        self.run_script("Scripts/generate_heic_proxies.py")

    def generate_raw_proxies(self):
        """Generate JPG proxies from RAW files using RawTherapee CLI."""
        print("\n🎞️ GENERATE RAW PROXIES")
        print("-" * 40)
        print("This creates JPG proxies for RAW files using RawTherapee CLI.")
        print("Features:")
        print("  • Detects camera-generated adjacent JPGs automatically")
        print("  • Uses RawTherapee CLI for high-quality RAW processing")
        print("  • Handles orientation and color profiles correctly")
        print("  • Files are named by database ID to avoid conflicts")
        print("  • Original RAW files remain untouched")

        print(f"\nProxy storage: RAW Proxies/")
        print("Processing: Adjacent JPG → RawTherapee CLI conversion")

        args = []
        print("\nOptions:")
        if input("Force regenerate existing proxies? (y/N): ").lower().startswith("y"):
            args.append("--force")
        if input("Clean up orphaned proxies first? (y/N): ").lower().startswith("y"):
            # Run cleanup first
            print("\n🧹 Cleaning up orphaned proxies...")
            self.run_script("Scripts/generate_raw_proxies.py", ["--clean"])
            input("Press Enter to continue with proxy generation...")

        print("\nGenerating RAW proxies...")
        self.run_script("Scripts/generate_raw_proxies.py", args)

    def generate_video_proxies(self):
        """Generate h.264 video proxies for fast playback."""
        print("\n📹 GENERATE VIDEO PROXIES")
        print("-" * 40)
        print("This creates h.264 compressed video proxies for fast gallery playback.")
        print("Features:")
        print('  • Optimized for iPad Pro 12.9" retina display (2732px max)')
        print("  • h.264 compression with excellent quality/size balance")
        print("  • Maintains aspect ratio for all video formats")
        print("  • Files are named by database ID to avoid conflicts")
        print("  • Original video files remain untouched")
        print("  • Typical file size reduction: 70-90%")

        print(f"\nProxy storage: Video Proxies/")
        print("Processing: FFmpeg h.264 encoding (CRF 23)")

        args = []
        print("\nOptions:")

        limit = input("Limit to recent N videos (or Enter for all): ").strip()
        if limit and limit.isdigit():
            args.extend(["--limit", limit])

        if input("Force regenerate existing proxies? (y/N): ").lower().startswith("y"):
            args.append("--force")

        if input("Clean up orphaned proxies first? (y/N): ").lower().startswith("y"):
            # Run cleanup first
            self.run_script("Scripts/generate_video_proxies.py", ["--clean"])
            input("Press Enter to continue with proxy generation...")

        if input("Show statistics only? (y/N): ").lower().startswith("y"):
            args = ["--stats"]
        else:
            # Quality settings
            print("\nQuality settings:")
            crf = input(
                "Quality setting CRF (18-28, lower=better, Enter for 23): "
            ).strip()
            if crf and crf.isdigit() and 18 <= int(crf) <= 28:
                args.extend(["--crf", crf])

            max_dim = input(
                "Max dimension in pixels (Enter for 2732 iPad Pro): "
            ).strip()
            if max_dim and max_dim.isdigit():
                args.extend(["--max-dimension", max_dim])

        print("\nGenerating video proxies...")
        self.run_script("Scripts/generate_video_proxies.py", args)

    def regenerate_raw_picks(self):
        """Regenerate RAW picks with custom RawTherapee settings."""
        print("\n🎯 REGENERATE RAW PICKS")
        print("-" * 40)
        print(
            "This regenerates selected RAW files from picks.json with custom settings."
        )
        print("Features:")
        print("  • Reads from JSON/picks.json")
        print("  • Applies custom RawTherapee processing")
        print("  • Configurable quality and presets")
        print("  • Marks files as custom_generated in database")
        print("  • Gallery creation will use custom proxies")

        print(f"\nCurrent picks file: JSON/picks.json")

        args = []

        print("\nCustom settings:")
        quality = input("JPEG quality (1-100, Enter for 95): ").strip()
        if quality and quality.isdigit() and 1 <= int(quality) <= 100:
            args.extend(["--quality", quality])

        use_custom_style = (
            input("Use custom RawTherapee style? (Y/n): ").strip().lower()
        )
        if use_custom_style in ["n", "no"]:
            # User wants default settings - we'll pass an empty preset to skip interactive menu
            print("Using default RawTherapee settings...")
            args.extend(["--preset", "DEFAULT"])
        else:
            # Don't pass --preset argument, which will trigger interactive style selection
            print("Interactive style selection will be shown next...")

        if input("Force regenerate existing proxies? (y/N): ").lower().startswith("y"):
            args.append("--force")

        if input("Regenerate thumbnails after processing? (Y/n): ").lower() != "n":
            args.append("--regenerate-thumbnails")

        print("\nRegenerating RAW picks...")
        self.run_script("Scripts/regenerate_raw_picks.py", args)

    def process_new_images(self):
        """Complete automated workflow for processing new images."""
        print("\n🚀 PROCESS NEW IMAGES")
        print("=" * 60)
        print("This will automatically run the complete workflow for new images:")
        print("1. 📊 Extract metadata from photos (including RAW detection)")
        print("2. 🖼️  Generate thumbnails for fast loading")
        print("3. 🖼️  Generate HEIC proxies for web viewing")
        print("4. 🎞️  Generate RAW proxies for RAW file viewing")
        print("5. 👥 Extract faces from all images")
        print("6. 🔗 Add new faces to existing people clusters")
        print()

        directory = input(
            "Photo directory (or Enter for 'Master Photo Library'): "
        ).strip()
        if not directory:
            directory = "Master Photo Library"

        if not os.path.exists(directory):
            print(f"❌ Directory not found: {directory}")
            return

        print(f"\n🎯 Processing new images from: {directory}")
        print("=" * 60)

        # Step 1: Extract Metadata
        print("\n📊 STEP 1: Extracting metadata...")
        print("-" * 40)
        metadata_success = self.run_script("Scripts/extract_metadata.py", [directory])

        if not metadata_success:
            print("❌ Metadata extraction failed. Stopping workflow.")
            return

        # Step 1.5: Clean up orphaned HEIC proxies
        print("\n🧹 STEP 1.5: Cleaning orphaned HEIC proxies...")
        print("-" * 40)
        cleanup_success = self.run_script(
            "Scripts/generate_heic_proxies.py", ["--clean"]
        )

        if not cleanup_success:
            print("⚠️ Proxy cleanup failed, but continuing...")

        # Step 2: Generate Thumbnails
        print("\n🖼️  STEP 2: Generating thumbnails...")
        print("-" * 40)
        thumbnail_success = self.run_script(
            "Scripts/generate_thumbnails.py", ["--force"]
        )

        if not thumbnail_success:
            print("⚠️ Thumbnail generation failed, but continuing...")

        # Step 3: Generate HEIC Proxies
        print("\n🖼️  STEP 3: Generating HEIC proxies...")
        print("-" * 40)
        proxy_success = self.run_script("Scripts/generate_heic_proxies.py")

        if not proxy_success:
            print("⚠️ HEIC proxy generation failed, but continuing...")

        # Step 4: Generate RAW Proxies
        print("\n🎞️  STEP 4: Generating RAW proxies...")
        print("-" * 40)
        raw_proxy_success = self.run_script("Scripts/generate_raw_proxies.py")

        if not raw_proxy_success:
            print("⚠️ RAW proxy generation failed, but continuing...")

        # Step 5: Extract Faces
        print("\n👥 STEP 5: Extracting faces from all images...")
        print("-" * 40)
        face_extract_success = self.run_script(
            "Scripts/face_recognizer_insightface.py", ["--extract"]
        )

        if not face_extract_success:
            print("⚠️ Face extraction failed, but continuing...")

        # Step 6: Cluster New Faces
        print("\n🔗 STEP 6: Adding new faces to existing clusters (iterative)...")
        print("-" * 40)
        cluster_success = self.run_script(
            "Scripts/face_recognizer_insightface.py", ["--cluster-new-loop"]
        )

        if not cluster_success:
            print("⚠️ Face clustering failed, but workflow completed.")

        # Summary
        print("\n🎉 NEW IMAGE PROCESSING COMPLETE!")
        print("=" * 60)
        print("✅ Metadata extracted and database updated (including RAW detection)")
        print("✅ Orphaned HEIC proxies cleaned up")
        print("✅ Thumbnails generated for fast gallery loading")
        print("✅ HEIC proxies created for web browser compatibility")
        print("✅ RAW proxies generated for RAW file viewing")
        print("✅ Face recognition updated with new images")
        print("✅ New faces added to existing people clusters")
        print()
        print("💡 Next steps:")
        print("   • Review new people in face recognition (option 12)")
        print("   • Label any unidentified people")
        print("   • Create new galleries with the imported images (option 3)")
        print("   • Start gallery server to view results (option 8)")

    def start_gallery_server(self):
        """Start both gallery web server and face API server in background."""
        print("\n🌐 START GALLERY SERVER")
        print("-" * 40)
        print("This will start:")
        print("  • Face API Server (background)")
        print("  • Gallery Web Server (background)")
        print("You can then open http://localhost:8000 in your browser.")
        print("Face detection will be available in the gallery.")

        input("\nPress Enter to start servers...")

        try:
            # Start Face API Server in background
            print("🚀 Starting Face API Server...")
            face_api_process = subprocess.Popen(
                [sys.executable, str(self.base_dir / "Scripts" / "face_api_server.py")],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Give face API server time to start
            import time

            time.sleep(2)
            print("✅ Face API Server started (PID: {})".format(face_api_process.pid))

            # Start Gallery Server in background
            print("🚀 Starting Gallery Web Server...")
            gallery_process = subprocess.Popen(
                ["bash", str(self.base_dir / "Scripts" / "start_gallery_server.sh")],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            time.sleep(2)  # Give it time to start
            print("✅ Gallery Web Server started (PID: {})".format(gallery_process.pid))

            print("\n🌐 Servers are now running!")
            print("📱 Open: http://localhost:8000/index-display.html")
            print("🔧 Use option 7 to stop servers or option 8 to restart")
            print("👈 Returning to main menu...")

        except Exception as e:
            print(f"❌ Error starting servers: {e}")
            print("💡 Try stopping servers first (option 7) then restart")

    def stop_gallery_server(self):
        """Stop both gallery and face API servers."""
        print("\n🛑 STOP GALLERY SERVER")
        print("-" * 40)
        print("This will stop:")
        print("  • Face API Server")
        print("  • Gallery Web Server")
        print("  • Any related HTTP servers")

        try:
            print("🛑 Stopping servers...")

            # Stop face API server
            result1 = subprocess.run(
                ["pkill", "-f", "Scripts/face_api_server.py"], capture_output=True
            )

            # Stop gallery server
            result2 = subprocess.run(
                ["pkill", "-f", "Scripts/start_gallery_server.sh"], capture_output=True
            )

            # Stop any Python HTTP servers (from start_gallery_server.sh)
            result3 = subprocess.run(
                ["pkill", "-f", "python.*http.server"], capture_output=True
            )

            # More aggressive kill for processes using ports 8000 and 8001
            import time

            time.sleep(1)  # Give processes time to die gracefully

            # Check and kill anything still using port 8000
            try:
                lsof_result = subprocess.run(
                    ["lsof", "-t", "-i:8000"], capture_output=True, text=True
                )
                if lsof_result.stdout.strip():
                    pids = lsof_result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", pid], capture_output=True)
                        print(f"✅ Killed process {pid} using port 8000")
            except:
                pass

            # Check and kill anything still using port 8001
            try:
                lsof_result = subprocess.run(
                    ["lsof", "-t", "-i:8001"], capture_output=True, text=True
                )
                if lsof_result.stdout.strip():
                    pids = lsof_result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", pid], capture_output=True)
                        print(f"✅ Killed process {pid} using port 8001")
            except:
                pass

            # Check results
            stopped_any = False
            if result1.returncode == 0:
                print("✅ Face API Server stopped")
                stopped_any = True
            if result2.returncode == 0:
                print("✅ Gallery Server stopped")
                stopped_any = True
            if result3.returncode == 0:
                print("✅ HTTP Server stopped")
                stopped_any = True

            if not stopped_any:
                print("ℹ️ No servers were running")
            else:
                print("✅ All servers stopped successfully")

        except Exception as e:
            print(f"❌ Error stopping servers: {e}")
            print("💡 You may need to stop them manually with:")
            print("   pkill -f Scripts/face_api_server.py")
            print("   pkill -f 'python.*http.server'")

    def restart_gallery_server(self):
        """Restart servers with gallery list rebuild."""
        print("\n🔄 RESTART GALLERY SERVER")
        print("-" * 40)
        print("This will:")
        print("  • Stop any running servers")
        print("  • Rebuild main gallery list (galleries.json)")
        print("  • Restart both Face API and Gallery servers")
        print("  • Refresh available galleries in web interface")

        input("\nPress Enter to restart servers...")

        try:
            # Stop any running servers
            print("🛑 Stopping any running servers...")
            subprocess.run(
                ["pkill", "-f", "Scripts/face_api_server.py"], capture_output=True
            )
            subprocess.run(
                ["pkill", "-f", "Scripts/start_gallery_server.sh"], capture_output=True
            )
            subprocess.run(["pkill", "-f", "python.*http.server"], capture_output=True)

            # Give processes time to die gracefully
            import time

            time.sleep(1)

            # More aggressive kill for processes using ports 8000 and 8001
            try:
                lsof_result = subprocess.run(
                    ["lsof", "-t", "-i:8000"], capture_output=True, text=True
                )
                if lsof_result.stdout.strip():
                    pids = lsof_result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", pid], capture_output=True)
            except:
                pass

            try:
                lsof_result = subprocess.run(
                    ["lsof", "-t", "-i:8001"], capture_output=True, text=True
                )
                if lsof_result.stdout.strip():
                    pids = lsof_result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", pid], capture_output=True)
            except:
                pass

            print("✅ Stopped existing servers")

            # Rebuild galleries list using the dedicated script
            print("🔨 Rebuilding main gallery list...")

            # Run the standalone rebuild script
            result = subprocess.run(
                [
                    "python3",
                    str(self.base_dir / "Scripts" / "rebuild_galleries_json.py"),
                ],
                cwd=str(self.base_dir),
                capture_output=False,
            )

            if result.returncode == 0:
                print("✅ Galleries list rebuilt successfully!")
            else:
                print("❌ Failed to rebuild galleries list")
                return

            # Small delay to ensure cleanup
            import time

            time.sleep(1)

            # Start servers again
            print("🚀 Starting servers...")

            # Start Face API Server in background
            print("🚀 Starting Face API Server...")
            face_api_process = subprocess.Popen(
                [sys.executable, str(self.base_dir / "Scripts" / "face_api_server.py")],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Give face API server time to start
            import time

            time.sleep(2)
            print("✅ Face API Server started (PID: {})".format(face_api_process.pid))

            # Start Gallery Server in background
            print("🚀 Starting Gallery Web Server...")
            gallery_process = subprocess.Popen(
                ["bash", str(self.base_dir / "Scripts" / "start_gallery_server.sh")],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            time.sleep(2)  # Give it time to start
            print("✅ Gallery Web Server started (PID: {})".format(gallery_process.pid))

            print("\n🔄 Servers restarted successfully!")
            print("📱 Open: http://localhost:8000/index-display.html")
            print("👈 Returning to main menu...")

        except KeyboardInterrupt:
            print("\n⚠️ Restart cancelled")
        except Exception as e:
            print(f"❌ Error during restart: {e}")

    def quick_rebuild_galleries(self):
        """Quick rebuild of galleries.json without restarting servers."""
        print("\n🔨 QUICK REBUILD GALLERIES LIST")
        print("-" * 40)
        print("This will:")
        print("  • Scan Hard Link Galleries directory")
        print("  • Rebuild galleries.json with current galleries")
        print("  • Update web interface gallery list")
        print("  • Keep servers running (no restart needed)")

        input("\nPress Enter to rebuild galleries list...")

        try:
            # Run the standalone rebuild script
            result = subprocess.run(
                [
                    "python3",
                    str(self.base_dir / "Scripts" / "rebuild_galleries_json.py"),
                ],
                cwd=str(self.base_dir),
                capture_output=False,
            )

            if result.returncode == 0:
                print("\n🎉 Galleries list rebuilt successfully!")
                print("💡 Refresh your browser to see updated gallery list")
            else:
                print("\n❌ Failed to rebuild galleries list")

        except KeyboardInterrupt:
            print("\n⚠️ Rebuild cancelled")
        except Exception as e:
            print(f"❌ Error during rebuild: {e}")

    def face_recognition_menu(self):
        """Face recognition submenu."""
        while True:
            print("\n👥 FACE RECOGNITION")
            print("-" * 40)
            print("1. Extract Face Embeddings")
            print("2. Cluster Faces (Full Reset)")
            print("3. Add New Faces to Clusters")
            print("4. ⚙️  Configure Clustering Settings")
            print("5. Label People")
            print("6. View Statistics")
            print("7. Start Face API Server (standalone)")
            print("8. Back to main menu")
            print()
            print("💡 Tip: Use 'Start Gallery Server' (main menu option 11)")
            print("   to automatically start both servers together.")

            choice = input("\nChoice (1-8): ").strip()

            if choice == "1":
                print("\n🔍 EXTRACT FACE EMBEDDINGS")
                print("-" * 40)
                limit = input(
                    "Number of images to process (or Enter for all): "
                ).strip()
                if limit:
                    try:
                        int(limit)  # Validate it's a number
                        args = ["--extract", limit]
                    except ValueError:
                        print("❌ Invalid number")
                        continue
                else:
                    args = ["--extract"]
                self.run_script("Scripts/face_recognizer_insightface.py", args)

            elif choice == "2":
                print("\n🧠 CLUSTER FACES (Full Reset)")
                print("-" * 40)
                print("⚠️  This will reset all existing face groupings!")
                if input("Continue? (y/N): ").lower() == "y":
                    args = ["--cluster"]
                    self.run_script("Scripts/face_recognizer_insightface.py", args)
                else:
                    print("❌ Clustering cancelled")

            elif choice == "3":
                print("\n🔄 ADD NEW FACES TO CLUSTERS")
                print("-" * 40)
                print(
                    "This preserves existing labels and adds new faces to known people."
                )
                args = ["--cluster-new"]
                self.run_script("Scripts/face_recognizer_insightface.py", args)

            elif choice == "4":
                self.face_clustering_settings()

            elif choice == "5":
                print("\n🏷️  LABEL PEOPLE")
                print("-" * 40)
                print("First, view statistics to see person IDs:")
                self.run_script("Scripts/face_recognizer_insightface.py", ["--stats"])
                print("\nEnter label command:")
                person_id = input("Person ID: ").strip()
                name = input("Person Name: ").strip()
                if person_id and name:
                    args = ["--label", person_id, name]
                    self.run_script("Scripts/face_recognizer_insightface.py", args)
                else:
                    print("❌ Both Person ID and Name are required")

            elif choice == "6":
                print("\n📊 FACE RECOGNITION STATISTICS")
                print("-" * 40)
                self.run_script("Scripts/face_recognizer_insightface.py", ["--stats"])

            elif choice == "7":
                print("\n🌐 Starting Face API Server (standalone)...")
                print("This enables face detection in the gallery viewer.")
                print("Note: Gallery server must be started separately.")
                print("Press Ctrl+C to stop the server.")

                input("\nPress Enter to start...")
                self.run_script("Scripts/face_api_server.py")

            elif choice == "8":
                break
            else:
                print("❌ Invalid choice. Please enter 1-8.")

    def face_clustering_settings(self):
        """Interactive configuration of face clustering parameters."""
        print("\n⚙️ FACE CLUSTERING SETTINGS")
        print("=" * 50)
        print("Configure parameters for face recognition clustering")
        print()

        # Load current defaults from script
        current_settings = {
            "eps": 0.38,
            "min_samples": 16,
            "similarity_threshold": 0.6,
            "min_samples_new": 30,
            "max_iterations": 10,
        }

        print("📋 CURRENT SETTINGS:")
        print(f"  • Clustering Sensitivity (eps): {current_settings['eps']}")
        print(f"  • Min Samples per Person: {current_settings['min_samples']}")
        print(f"  • Similarity Threshold: {current_settings['similarity_threshold']}")
        print(f"  • Min Faces for New People: {current_settings['min_samples_new']}")
        print(f"  • Max Iterations: {current_settings['max_iterations']}")
        print()

        # Interactive configuration
        new_settings = {}

        # Clustering Sensitivity (eps)
        print("🎯 CLUSTERING SENSITIVITY (eps)")
        print("Controls how strict face grouping is:")
        print("  • Lower values (0.2-0.3): Stricter - fewer, more accurate groups")
        print(
            "  • Higher values (0.4-0.6): Looser - more groups, may include similar people"
        )
        print(f"  • Recommended range: 0.25-0.50 (current: {current_settings['eps']})")
        eps = self.prompt_float_parameter(
            "Enter clustering sensitivity",
            current_settings["eps"],
            min_val=0.2,
            max_val=0.8,
        )
        new_settings["eps"] = eps

        # Min Samples
        print("\n👥 MINIMUM SAMPLES PER PERSON")
        print("Minimum number of face photos needed to create a person:")
        print("  • Lower values (8-12): Create people from fewer photos")
        print("  • Higher values (20-30): Require more photos for confidence")
        print(
            f"  • Recommended range: 10-25 (current: {current_settings['min_samples']})"
        )
        min_samples = self.prompt_int_parameter(
            "Enter minimum samples per person",
            current_settings["min_samples"],
            min_val=3,
            max_val=50,
        )
        new_settings["min_samples"] = min_samples

        # Similarity Threshold
        print("\n🔍 SIMILARITY THRESHOLD")
        print("How similar faces must be to match existing people:")
        print("  • Lower values (0.4-0.5): Stricter matching")
        print("  • Higher values (0.7-0.8): More lenient matching")
        print(
            f"  • Recommended range: 0.5-0.7 (current: {current_settings['similarity_threshold']})"
        )
        similarity = self.prompt_float_parameter(
            "Enter similarity threshold",
            current_settings["similarity_threshold"],
            min_val=0.3,
            max_val=0.9,
        )
        new_settings["similarity_threshold"] = similarity

        # Show summary and apply
        print("\n📊 NEW SETTINGS SUMMARY:")
        print("=" * 50)
        for key, value in new_settings.items():
            old_value = current_settings[key]
            change = "→" if value != old_value else "✓"
            print(f"  • {key.replace('_', ' ').title()}: {old_value} {change} {value}")

        print("\n🚀 APPLY SETTINGS:")
        print("1. Test with current cluster operation")
        print("2. Save settings for future use")
        print("3. Cancel changes")

        choice = input("\nChoice (1-3): ").strip()

        if choice == "1":
            print("\n🧠 Testing clustering with new settings...")
            # Apply settings to clustering command
            args = [
                "--cluster",
                "--eps",
                str(new_settings["eps"]),
                "--min-samples",
                str(new_settings["min_samples"]),
            ]
            print(f"Running: face_recognizer_insightface.py {' '.join(args)}")
            self.run_script("Scripts/face_recognizer_insightface.py", args)

        elif choice == "2":
            print("💾 Settings saved! (Feature coming in Phase 2)")
            print("For now, remember these values for manual use.")

        elif choice == "3":
            print("❌ Settings cancelled")

        input("\nPress Enter to continue...")

    def prompt_float_parameter(self, prompt, current_value, min_val, max_val):
        """Prompt for a float parameter with validation."""
        while True:
            try:
                response = input(f"{prompt} [{current_value}]: ").strip()
                if not response:
                    return current_value

                value = float(response)
                if min_val <= value <= max_val:
                    return value
                else:
                    print(f"❌ Value must be between {min_val} and {max_val}")

            except ValueError:
                print("❌ Please enter a valid number")

    def prompt_int_parameter(self, prompt, current_value, min_val, max_val):
        """Prompt for an integer parameter with validation."""
        while True:
            try:
                response = input(f"{prompt} [{current_value}]: ").strip()
                if not response:
                    return current_value

                value = int(response)
                if min_val <= value <= max_val:
                    return value
                else:
                    print(f"❌ Value must be between {min_val} and {max_val}")

            except ValueError:
                print("❌ Please enter a valid integer")

    def database_debug(self):
        """Database debugging and inspection."""
        print("\n🔍 DATABASE DEBUG")
        print("-" * 40)
        print("This will show database statistics and help diagnose issues.")

        self.run_script("Scripts/debug_db.py")

    def database_cleanup(self):
        """Database cleanup and maintenance."""
        print("\n🛠️ DATABASE CLEANUP")
        print("-" * 40)
        print("This will help maintain your database by:")
        print("  • Removing entries for deleted files")
        print("  • Analyzing RAW file entries")
        print("  • Optimizing database storage")
        print("  • Providing detailed statistics")

        input("\nPress Enter to start database maintenance...")
        self.run_script("Scripts/cleanup_database.py", ["--interactive"])

    def delete_culled(self):
        """Delete images marked as culled."""
        print("\n🗑️ DELETE CULLED IMAGES")
        print("-" * 40)
        print("This will delete images by database ID from delete_list.json")
        print("⚠️ WARNING: This action cannot be undone!")
        print("Features:")
        print("  • Works with RAW files and adjacent JPGs")
        print("  • Removes from galleries and master location")
        print("  • Cleans up proxy files")
        print("  • Uses reliable database ID tracking")

        if input("\nAre you absolutely sure? (y/N): ").lower().startswith("y"):
            self.run_script("Scripts/delete_all_culled_by_id.py")
        else:
            print("❌ Cancelled - no files deleted")

    def delete_galleries(self):
        """Delete galleries and update galleries.json."""
        import json
        import shutil
        
        print("\n🗂️ DELETE GALLERIES")
        print("-" * 40)
        print("This allows you to delete gallery folders and update the galleries list.")
        print("⚠️ WARNING: This action cannot be undone!")
        print("Features:")
        print("  • Removes hard link gallery folders completely")
        print("  • Updates JSON/galleries.json automatically")  
        print("  • Original photos in Master Photo Library remain safe")
        
        galleries_json_path = self.base_dir / "JSON" / "galleries.json"
        
        # Load galleries list
        try:
            with open(galleries_json_path, 'r') as f:
                galleries = json.load(f)
        except FileNotFoundError:
            print("❌ No galleries.json found. Run gallery server first.")
            return
        except json.JSONDecodeError:
            print("❌ Invalid galleries.json file.")
            return
            
        if not galleries:
            print("📭 No galleries found.")
            return
            
        print(f"\n📋 Found {len(galleries)} galleries:")
        for i, gallery in enumerate(galleries, 1):
            gallery_path = self.base_dir / gallery['jsonPath'].replace('/image_data.json', '')
            size = f"({gallery['imageCount']} images)" if gallery['imageCount'] > 0 else "(empty)"
            exists = "✅" if gallery_path.exists() else "❌ Missing"
            print(f"  {i:2d}. {gallery['name']} {size} {exists}")
        
        print("\nEnter gallery numbers to delete (comma-separated, or 'all'):")
        selection = input("Galleries to delete: ").strip()
        
        if not selection:
            print("❌ No selection made.")
            return
        
        galleries_to_delete = []
        
        if selection.lower() == 'all':
            if input(f"\n⚠️ Delete ALL {len(galleries)} galleries? (y/N): ").lower().startswith('y'):
                galleries_to_delete = list(range(len(galleries)))
        else:
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                galleries_to_delete = [i for i in indices if 0 <= i < len(galleries)]
            except ValueError:
                print("❌ Invalid input. Please enter numbers separated by commas.")
                return
        
        if not galleries_to_delete:
            print("❌ No valid galleries selected.")
            return
            
        # Show confirmation
        print(f"\n🗑️ Will delete {len(galleries_to_delete)} galleries:")
        for i in galleries_to_delete:
            print(f"  • {galleries[i]['name']} ({galleries[i]['imageCount']} images)")
        
        if not input(f"\nType 'DELETE' to confirm: ").strip() == 'DELETE':
            print("❌ Cancelled - no galleries deleted")
            return
            
        # Delete galleries
        deleted_count = 0
        remaining_galleries = []
        
        for i, gallery in enumerate(galleries):
            if i in galleries_to_delete:
                gallery_path = self.base_dir / gallery['jsonPath'].replace('/image_data.json', '')
                try:
                    if gallery_path.exists():
                        shutil.rmtree(gallery_path)
                        print(f"✅ Deleted: {gallery['name']}")
                        deleted_count += 1
                    else:
                        print(f"⚠️ Already gone: {gallery['name']}")
                        deleted_count += 1
                except Exception as e:
                    print(f"❌ Failed to delete {gallery['name']}: {e}")
            else:
                remaining_galleries.append(gallery)
        
        # Update galleries.json
        try:
            with open(galleries_json_path, 'w') as f:
                json.dump(remaining_galleries, f, indent=2)
            print(f"\n✅ Updated galleries.json ({len(remaining_galleries)} remaining)")
        except Exception as e:
            print(f"❌ Failed to update galleries.json: {e}")
            
        print(f"\n🎉 Successfully deleted {deleted_count} galleries!")
        if deleted_count > 0:
            print("💡 Refresh your web browser to see the updated gallery list.")

    def install_dependencies(self):
        """Install complete toolkit dependencies including RAW support."""
        print("\n⚙️ INSTALL DEPENDENCIES")
        print("-" * 40)
        print("This will install all dependencies for the photo management toolkit:")
        print("  • Python packages (PIL, SQLite, NumPy)")
        print("  • Image processing tools (exiftool, ImageMagick)")
        print("  • RAW processing tools (RawTherapee CLI)")
        print("  • Face detection dependencies (OpenCV, dlib, MediaPipe, InsightFace)")
        print("\nNote: Requires MacPorts and sudo access. May take several minutes.")

        if input("\nProceed with installation? (y/N): ").lower().startswith("y"):
            self.run_script(
                "Scripts/install_dependencies_macports_smart.sh", is_python=False
            )
        else:
            print("❌ Installation cancelled")

    def show_quick_start(self):
        """Show quick start guide."""
        print("\n🚀 QUICK START GUIDE")
        print("-" * 40)
        print("For new users, follow these steps:")
        print()
        print("1. Setup Database (option 2)")
        print("2. Extract Metadata from 'Master Photo Library' (option 1)")
        print("3. Create a Virtual Gallery (option 3)")
        print("4. Start Gallery Server to view photos (option 11)")
        print()
        print("Optional:")
        print("• Install Dependencies for face detection (option 19)")
        print("• Run Face Recognition to detect people (option 15)")
        print("• Quick rebuild galleries list when needed (option 14)")
        print()
        input("Press Enter to return to main menu...")

    def run(self):
        """Main program loop."""
        # Show quick start on first run
        if input("Show quick start guide? (Y/n): ").lower() not in ["n", "no"]:
            self.show_quick_start()

        while True:
            try:
                self.show_main_menu()
                choice = input("\nEnter choice (1-20): ").strip()

                if choice == "1":
                    self.extract_metadata()
                elif choice == "2":
                    self.setup_database()
                elif choice == "3":
                    self.create_gallery()
                elif choice == "4":
                    self.rebuild_gallery_json()
                elif choice == "5":
                    self.generate_thumbnails()
                elif choice == "6":
                    self.generate_heic_proxies()
                elif choice == "7":
                    self.generate_raw_proxies()
                elif choice == "8":
                    self.generate_video_proxies()
                elif choice == "9":
                    self.regenerate_raw_picks()
                elif choice == "10":
                    self.process_new_images()
                elif choice == "11":
                    self.start_gallery_server()
                elif choice == "12":
                    self.stop_gallery_server()
                elif choice == "13":
                    self.restart_gallery_server()
                elif choice == "14":
                    self.quick_rebuild_galleries()
                elif choice == "15":
                    self.face_recognition_menu()
                elif choice == "16":
                    self.database_debug()
                elif choice == "17":
                    self.database_cleanup()
                elif choice == "18":
                    self.delete_culled()
                elif choice == "19":
                    self.delete_galleries()
                elif choice == "20":
                    self.install_dependencies()
                elif choice == "21":
                    print("\n👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice. Please enter 1-21.")

                if choice != "20":
                    input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("Press Enter to continue...")


if __name__ == "__main__":
    manager = PhotoManager()
    manager.run()
