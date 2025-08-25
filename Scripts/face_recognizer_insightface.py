#!/usr/bin/env python3
"""
Face Recognition System using InsightFace - Much more accurate than face_recognition library
"""

import sqlite3
import numpy as np
import cv2
import os
import argparse
from datetime import datetime
import json
from pathlib import Path

try:
    import insightface
    from sklearn.cluster import DBSCAN
    from sklearn.metrics.pairwise import cosine_similarity
    INSIGHTFACE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ InsightFace not installed: {e}")
    print("Install with: python3 -m pip install insightface")
    INSIGHTFACE_AVAILABLE = False

class InsightFaceRecognizer:
    def __init__(self, db_path=None):
        if db_path is None:
            # Auto-detect database location
            from pathlib import Path
            current_dir = Path.cwd()
            if current_dir.name == "Scripts":
                db_path = "image_metadata.db"  # Same directory
            else:
                db_path = "Scripts/image_metadata.db"  # Scripts subdirectory
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        if INSIGHTFACE_AVAILABLE:
            # Initialize InsightFace model
            self.app = insightface.app.FaceAnalysis(providers=['CPUExecutionProvider'])
            self.app.prepare(ctx_id=0, det_size=(640, 640))
        else:
            self.app = None
    
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_processing_image_path(self, image_row):
        """Get the appropriate image path for face processing, handling HEIC proxies and RAW proxies."""
        original_path = image_row['path']
        image_id = image_row['id']
        filename = image_row['filename']
        
        # Check if it's a HEIC file
        if filename and filename.upper().endswith('.HEIC'):
            # Look for HEIC proxy first - try both .webp and .jpg extensions
            for ext in ['.webp', '.jpg']:
                # Try both relative paths depending on working directory
                for base_path in ["HEIC Proxies", "../HEIC Proxies"]:
                    heic_proxy_path = f"{base_path}/{image_id}{ext}"
                    if os.path.exists(heic_proxy_path):
                        return heic_proxy_path
            print(f"⚠️ HEIC proxy not found for {filename} (ID: {image_id}), using original")
            return original_path
        
        # Check if it's a RAW file with custom proxy
        try:
            raw_proxy_type = image_row['raw_proxy_type']
        except (KeyError, IndexError):
            raw_proxy_type = None
        
        if raw_proxy_type == 'custom_generated':
            # Use the generated proxy from RAW Proxies folder
            # Try both relative paths depending on working directory
            for base_path in ["RAW Proxies", "../RAW Proxies"]:
                proxy_path = f"{base_path}/{image_id}.jpg"
                if os.path.exists(proxy_path):
                    return proxy_path
            print(f"⚠️ Custom RAW proxy not found for {filename} (ID: {image_id})")
        elif raw_proxy_type == 'original_jpg':
            # Use the adjacent JPG file
            original_path_obj = Path(original_path)
            for ext in ['.jpg', '.jpeg', '.JPG', '.JPEG']:
                adjacent_jpg = original_path_obj.with_suffix(ext)
                if adjacent_jpg.exists():
                    return str(adjacent_jpg)
            print(f"⚠️ Adjacent JPG not found for {filename}")
        
        # For regular files or if no proxies found, use original path
        return original_path
    
    def clear_mediapipe_data(self):
        """Clear all existing MediaPipe face detection data to start fresh with InsightFace."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM faces")
        cursor.execute("DELETE FROM persons")
        self.conn.commit()
        print("🧹 Cleared all existing face and person data")
    
    def extract_face_embeddings(self, limit=None):
        """Use InsightFace for both detection and recognition from scratch."""
        if not INSIGHTFACE_AVAILABLE:
            print("❌ InsightFace libraries not available")
            return
        
        cursor = self.conn.cursor()
        
        # Get images that haven't had face detection yet (or all if needs_processing flag isn't set properly)
        sql = """SELECT DISTINCT i.id, i.path, i.filename, i.raw_proxy_type 
                FROM images i 
                LEFT JOIN faces f ON i.id = f.image_id 
                WHERE f.image_id IS NULL OR i.needs_processing = 1"""
        
        if limit:
            sql += f" LIMIT {limit}"
            
        cursor.execute(sql)
        images_to_process = cursor.fetchall()
        
        if not images_to_process:
            print("❌ No images found")
            return
        
        print(f"🧠 Processing {len(images_to_process)} images with InsightFace detection+recognition...")
        
        total_faces = 0
        for i, image_row in enumerate(images_to_process):
            try:
                image_id = image_row['id']
                image_path = self.get_processing_image_path(image_row)
                
                if not os.path.exists(image_path):
                    continue
                
                # Load image
                image = cv2.imread(image_path)
                if image is None:
                    print(f"⚠️ Could not load image: {image_path}")
                    # Mark as processed even if we can't load it
                    cursor.execute("""
                        UPDATE images 
                        SET has_faces = 0, needs_processing = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (image_id,))
                    continue
                
                # Use InsightFace to detect all faces in the image
                faces = self.app.get(image)
                
                if not faces:
                    # Mark image as processed with no faces
                    cursor.execute("""
                        UPDATE images 
                        SET has_faces = 0, needs_processing = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (image_id,))
                    continue
                
                # Insert all detected faces with their embeddings
                for face in faces:
                    bbox = face.bbox.astype(int)
                    x, y, x2, y2 = bbox
                    width = x2 - x
                    height = y2 - y
                    confidence = float(face.det_score)
                    
                    # Convert to Python int to avoid numpy serialization issues
                    x, y, width, height = int(x), int(y), int(width), int(height)
                    
                    # Get embedding
                    embedding = face.embedding
                    embedding_blob = embedding.astype(np.float32).tobytes()
                    
                    # Insert face into database
                    cursor.execute("""
                        INSERT INTO faces (image_id, x, y, width, height, confidence, embedding, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (image_id, x, y, width, height, confidence, embedding_blob))
                    
                    total_faces += 1
                
                # Update image to mark it has faces
                cursor.execute("""
                    UPDATE images 
                    SET has_faces = ?, needs_processing = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (len(faces), image_id))
                
                if (i + 1) % 10 == 0:
                    print(f"📊 Progress: {i + 1}/{len(images_to_process)} images, {total_faces} faces found")
                    self.conn.commit()
                
            except Exception as e:
                print(f"❌ Error processing image {image_id}: {e}")
                print(f"   Image row keys: {list(image_row.keys()) if 'image_row' in locals() else 'No row'}")
                import traceback
                traceback.print_exc()
                continue
        
        self.conn.commit()
        print(f"✅ Detected and extracted embeddings for {total_faces} faces using InsightFace")
    
    def cluster_faces(self, eps=0.6, min_samples=3):
        """Cluster similar faces together using InsightFace embeddings."""
        if not INSIGHTFACE_AVAILABLE:
            print("❌ InsightFace libraries not available")
            return
        
        cursor = self.conn.cursor()
        
        # Get all faces with embeddings
        cursor.execute("""
            SELECT id, embedding FROM faces 
            WHERE embedding IS NOT NULL
        """)
        
        face_data = cursor.fetchall()
        
        if len(face_data) < min_samples:
            print(f"❌ Need at least {min_samples} faces with embeddings for clustering")
            return
        
        print(f"🧠 Clustering {len(face_data)} faces with InsightFace embeddings...")
        
        # Convert embeddings back to numpy arrays
        face_ids = []
        embeddings = []
        
        for row in face_data:
            face_ids.append(row['id'])
            # InsightFace embeddings are 512-dimensional float32
            embedding = np.frombuffer(row['embedding'], dtype=np.float32)
            embeddings.append(embedding)
        
        embeddings = np.array(embeddings)
        
        # Cluster using DBSCAN with cosine distance (better for normalized embeddings)
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
        cluster_labels = clustering.fit_predict(embeddings)
        
        # Create person records and assign faces
        unique_clusters = set(cluster_labels)
        unique_clusters.discard(-1)  # Remove noise cluster
        
        print(f"🎯 Found {len(unique_clusters)} distinct people")
        print(f"📊 {len([l for l in cluster_labels if l == -1])} faces couldn't be clustered")
        
        # Clear existing person assignments and delete old person records
        cursor.execute("UPDATE faces SET person_id = NULL")
        cursor.execute("DELETE FROM persons")
        print("🧹 Cleared existing person records")
        
        # Create new person records and assign faces
        for cluster_id in unique_clusters:
            # Create person record
            cursor.execute("""
                INSERT INTO persons (name, confirmed, created_at) 
                VALUES (?, 0, CURRENT_TIMESTAMP)
            """, (f"Person {cluster_id + 1}",))
            
            person_id = cursor.lastrowid
            
            # Assign faces to this person
            face_indices = [i for i, label in enumerate(cluster_labels) if label == cluster_id]
            for face_idx in face_indices:
                face_id = face_ids[face_idx]
                cursor.execute("""
                    UPDATE faces 
                    SET person_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (person_id, face_id))
            
            print(f"👤 Person {cluster_id + 1}: {len(face_indices)} faces")
        
        self.conn.commit()
        print("✅ Clustering complete")
    
    def cluster_new_faces(self, similarity_threshold=0.6, min_samples_new=30):
        """Add new faces to existing person clusters. Only creates new people if 30+ similar unmatched faces exist."""
        if not INSIGHTFACE_AVAILABLE:
            print("❌ InsightFace libraries not available")
            return
        
        cursor = self.conn.cursor()
        
        # Get faces that don't have person assignments yet
        cursor.execute("""
            SELECT id, embedding 
            FROM faces 
            WHERE embedding IS NOT NULL AND person_id IS NULL
        """)
        
        new_faces = cursor.fetchall()
        
        if not new_faces:
            print("✅ No new faces to cluster")
            return
        
        # Get existing person centroids (average embeddings)
        cursor.execute("""
            SELECT p.id, p.name, f.embedding
            FROM persons p
            JOIN faces f ON p.id = f.person_id
            WHERE f.embedding IS NOT NULL
        """)
        
        existing_data = cursor.fetchall()
        
        if not existing_data:
            print("❌ No existing persons found. Run full clustering first.")
            return
        
        print(f"🔄 Processing {len(new_faces)} new faces (min {min_samples_new} faces required for new people)...")
        
        # Calculate person centroids
        person_centroids = {}
        person_names = {}
        
        for row in existing_data:
            person_id = row['id']
            person_name = row['name']
            embedding = np.frombuffer(row['embedding'], dtype=np.float32)
            
            if person_id not in person_centroids:
                person_centroids[person_id] = []
                person_names[person_id] = person_name
            
            person_centroids[person_id].append(embedding)
        
        # Average embeddings for each person
        for person_id in person_centroids:
            person_centroids[person_id] = np.mean(person_centroids[person_id], axis=0)
        
        # Phase 1: Try to assign ALL faces to existing people
        assigned_count = 0
        unmatched_faces = []
        
        for face_row in new_faces:
            face_id = face_row['id']
            face_embedding = np.frombuffer(face_row['embedding'], dtype=np.float32)
            
            # Find closest existing person using cosine similarity
            best_person_id = None
            best_similarity = 0
            
            for person_id, centroid in person_centroids.items():
                from sklearn.metrics.pairwise import cosine_similarity
                similarity = cosine_similarity([face_embedding], [centroid])[0][0]
                
                if similarity > best_similarity and similarity > similarity_threshold:
                    best_similarity = similarity
                    best_person_id = person_id
            
            if best_person_id:
                # Assign to existing person
                cursor.execute("""
                    UPDATE faces 
                    SET person_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (best_person_id, face_id))
                
                assigned_count += 1
                print(f"👤 Assigned face {face_id} to {person_names[best_person_id]} (similarity: {best_similarity:.3f})")
                
                # Update centroid with new face
                old_centroid = person_centroids[best_person_id]
                person_centroids[best_person_id] = (old_centroid + face_embedding) / 2
            else:
                # Keep for potential new person creation
                unmatched_faces.append((face_id, face_embedding))
        
        # Phase 2: Cluster unmatched faces and only create new people if min_samples_new+ similar faces
        new_people_count = 0
        
        if len(unmatched_faces) >= min_samples_new:
            print(f"🔍 Clustering {len(unmatched_faces)} unmatched faces for potential new people...")
            
            # Extract embeddings for clustering
            unmatched_embeddings = np.array([emb for _, emb in unmatched_faces])
            unmatched_ids = [face_id for face_id, _ in unmatched_faces]
            
            # Cluster unmatched faces
            from sklearn.cluster import DBSCAN
            clustering = DBSCAN(eps=0.4, min_samples=min_samples_new, metric='cosine')
            cluster_labels = clustering.fit_predict(unmatched_embeddings)
            
            # Create new people for valid clusters
            unique_clusters = set(label for label in cluster_labels if label != -1)
            
            for cluster_id in unique_clusters:
                # Create new person
                next_person_num = len(person_centroids) + new_people_count + 1
                cursor.execute("""
                    INSERT INTO persons (name, confirmed, created_at)
                    VALUES (?, 0, CURRENT_TIMESTAMP)
                """, (f"Person {next_person_num}",))
                
                new_person_id = cursor.lastrowid
                
                # Assign faces to this new person
                cluster_faces = [unmatched_ids[i] for i, label in enumerate(cluster_labels) if label == cluster_id]
                
                for face_id in cluster_faces:
                    cursor.execute("""
                        UPDATE faces 
                        SET person_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (new_person_id, face_id))
                
                new_people_count += 1
                print(f"🆕 Created Person {next_person_num} with {len(cluster_faces)} faces")
            
            unassigned_count = sum(1 for label in cluster_labels if label == -1)
            if unassigned_count > 0:
                print(f"⏸️ {unassigned_count} faces remain unassigned (insufficient similar faces)")
        
        elif unmatched_faces:
            print(f"⏸️ {len(unmatched_faces)} faces remain unassigned (need {min_samples_new}+ similar faces for new people)")
        
        self.conn.commit()
        print(f"✅ Incremental clustering complete: {assigned_count} assigned to existing, {new_people_count} new people created")
        
        return assigned_count, new_people_count
    
    def cluster_new_faces_loop(self, similarity_threshold=0.6, min_samples_new=30, max_iterations=10):
        """Run cluster_new_faces in a loop until convergence (no more assignments)."""
        print(f"🔄 Starting iterative clustering loop (max {max_iterations} iterations)...")
        
        total_assigned = 0
        total_new_people = 0
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            assigned, new_people = self.cluster_new_faces(similarity_threshold, min_samples_new)
            total_assigned += assigned
            total_new_people += new_people
            
            # Stop if no faces were assigned in this iteration
            if assigned == 0 and new_people == 0:
                print(f"🎯 Convergence reached after {iteration} iterations!")
                break
            
            print(f"📊 Iteration {iteration} results: {assigned} assigned, {new_people} new people")
        
        if iteration >= max_iterations:
            print(f"⚠️ Stopped after maximum {max_iterations} iterations")
        
        print(f"\n🎉 Final results:")
        print(f"   📊 Total assigned to existing people: {total_assigned}")
        print(f"   🆕 Total new people created: {total_new_people}")
        print(f"   🔄 Iterations completed: {iteration}")
        
        return total_assigned, total_new_people
    
    def get_people_stats(self):
        """Get statistics about identified people."""
        cursor = self.conn.cursor()
        
        # Get person statistics
        cursor.execute("""
            SELECT 
                p.id,
                p.name,
                p.confirmed,
                COUNT(f.id) as face_count,
                COUNT(DISTINCT f.image_id) as image_count,
                AVG(f.confidence) as avg_confidence
            FROM persons p
            LEFT JOIN faces f ON p.id = f.person_id
            GROUP BY p.id, p.name, p.confirmed
            ORDER BY face_count DESC
        """)
        
        people = []
        for row in cursor.fetchall():
            people.append({
                'id': row['id'],
                'name': row['name'],
                'confirmed': bool(row['confirmed']),
                'face_count': row['face_count'],
                'image_count': row['image_count'],
                'avg_confidence': row['avg_confidence'] or 0.0
            })
        
        return people
    
    def label_person(self, person_id, name):
        """Assign a name to a person cluster, merging with existing person if name already exists."""
        cursor = self.conn.cursor()
        
        # Check if person exists
        cursor.execute("SELECT id, name FROM persons WHERE id = ?", (person_id,))
        current_person = cursor.fetchone()
        if not current_person:
            print(f"❌ Person {person_id} not found")
            return
        
        current_name = current_person[1]
        
        # Check if another person already has this name
        cursor.execute("SELECT id FROM persons WHERE name = ? AND id != ?", (name, person_id))
        existing_person = cursor.fetchone()
        
        if existing_person:
            existing_person_id = existing_person[0]
            print(f"🔄 Person with name '{name}' already exists (ID: {existing_person_id})")
            print(f"   Merging Person {person_id} ('{current_name}') into Person {existing_person_id}")
            
            # Get face count before merge
            cursor.execute("SELECT COUNT(*) FROM faces WHERE person_id = ?", (person_id,))
            face_count = cursor.fetchone()[0]
            
            # Reassign all faces from current person to existing person
            cursor.execute("""
                UPDATE faces 
                SET person_id = ?
                WHERE person_id = ?
            """, (existing_person_id, person_id))
            
            # Delete the now-empty person record
            cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
            
            self.conn.commit()
            print(f"✅ Merged {face_count} faces from Person {person_id} to Person {existing_person_id} ('{name}')")
            print(f"   Deleted duplicate Person {person_id} record")
        else:
            # No existing person with this name, just update the current person
            cursor.execute("""
                UPDATE persons 
                SET name = ?, confirmed = 1
                WHERE id = ?
            """, (name, person_id))
            self.conn.commit()
            print(f"✅ Labeled person {person_id} as '{name}'")
    
    def delete_unconfirmed_people(self):
        """Delete unconfirmed people but keep face data for future clustering."""
        cursor = self.conn.cursor()
        
        # Check counts
        cursor.execute('SELECT COUNT(*) FROM persons WHERE confirmed = 1')
        confirmed_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM persons WHERE confirmed = 0')
        unconfirmed_count = cursor.fetchone()[0]
        
        print(f"📊 People statistics:")
        print(f"   Confirmed: {confirmed_count}")
        print(f"   Unconfirmed: {unconfirmed_count}")
        
        if unconfirmed_count == 0:
            print("✅ No unconfirmed people to delete")
            return
        
        # Get face count that will be unassigned
        cursor.execute("""
            SELECT COUNT(*) FROM faces f 
            INNER JOIN persons p ON f.person_id = p.id 
            WHERE p.confirmed = 0
        """)
        faces_to_clear = cursor.fetchone()[0]
        
        # Clear person assignments for unconfirmed people (keeps face detection data)
        cursor.execute("""
            UPDATE faces SET person_id = NULL 
            WHERE person_id IN (SELECT id FROM persons WHERE confirmed = 0)
        """)
        
        # Delete unconfirmed person records
        cursor.execute('DELETE FROM persons WHERE confirmed = 0')
        deleted_count = cursor.rowcount
        
        self.conn.commit()
        
        print(f"🗑️ Deleted {deleted_count} unconfirmed people")
        print(f"📝 {faces_to_clear} faces unassigned (detection data preserved)")
        print("✅ Face embeddings kept for future clustering")

def main():
    parser = argparse.ArgumentParser(description='Face recognition using InsightFace')
    parser.add_argument('--db', help='Database file path (auto-detected if not specified)')
    parser.add_argument('--clear', action='store_true', help='Clear all MediaPipe face data to start fresh')
    parser.add_argument('--extract', nargs='?', const='all', help='Extract embeddings for N images (or all if no number specified)')
    parser.add_argument('--cluster', action='store_true', help='Cluster faces to identify people (resets all groupings)')
    parser.add_argument('--cluster-new', action='store_true', help='Add new faces to existing clusters (preserves labels)')
    parser.add_argument('--cluster-new-loop', action='store_true', help='Run cluster-new iteratively until convergence (no more assignments)')
    parser.add_argument('--stats', action='store_true', help='Show people statistics')
    parser.add_argument('--label', nargs=2, metavar=('PERSON_ID', 'NAME'), help='Label a person')
    parser.add_argument('--delete-unconfirmed', action='store_true', help='Delete all unconfirmed people and their face assignments')
    parser.add_argument('--eps', type=float, default=0.38, help='Clustering sensitivity (lower = stricter)')
    parser.add_argument('--min-samples', type=int, default=16, help='Minimum samples per cluster')
    parser.add_argument('--similarity', type=float, default=0.6, help='Similarity threshold for incremental clustering')
    parser.add_argument('--min-samples-new', type=int, default=30, help='Minimum faces required to create new people in incremental clustering')
    parser.add_argument('--max-iterations', type=int, default=10, help='Maximum iterations for cluster-new-loop')
    
    args = parser.parse_args()
    
    if not INSIGHTFACE_AVAILABLE:
        print("❌ InsightFace libraries are required")
        print("Install with: python3 -m pip install insightface")
        return 1
    
    recognizer = InsightFaceRecognizer(args.db)
    
    if args.clear:
        recognizer.clear_mediapipe_data()
    elif args.extract:
        if args.extract == 'all':
            # Extract from all images
            recognizer.extract_face_embeddings(None)
        else:
            # Extract from specific number of images
            try:
                limit = int(args.extract)
                recognizer.extract_face_embeddings(limit)
            except ValueError:
                print("❌ Invalid number for --extract")
                return 1
    elif args.cluster:
        recognizer.cluster_faces(eps=args.eps, min_samples=args.min_samples)
    elif args.cluster_new:
        recognizer.cluster_new_faces(similarity_threshold=args.similarity, min_samples_new=args.min_samples_new)
    elif args.cluster_new_loop:
        recognizer.cluster_new_faces_loop(similarity_threshold=args.similarity, min_samples_new=args.min_samples_new, max_iterations=args.max_iterations)
    elif args.stats:
        people = recognizer.get_people_stats()
        print(f"\n👥 People Statistics:")
        print(f"{'ID':<4} {'Name':<20} {'Faces':<8} {'Images':<8} {'Confidence':<12} {'Status'}")
        print("-" * 70)
        for person in people:
            status = "✓ Confirmed" if person['confirmed'] else "? Auto-detected"
            print(f"{person['id']:<4} {person['name']:<20} {person['face_count']:<8} "
                  f"{person['image_count']:<8} {person['avg_confidence']:<12.2f} {status}")
    elif args.label:
        person_id, name = args.label
        recognizer.label_person(int(person_id), name)
    elif args.delete_unconfirmed:
        recognizer.delete_unconfirmed_people()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()