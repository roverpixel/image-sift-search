import os
import cv2
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

# Directories
IMAGES_DIR = "images"
THUMBNAILS_DIR = "thumbnails"
QDRANT_DATA_DIR = "qdrant_data"
COLLECTION_NAME = "sift_features"

# Make sure directories exist
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(QDRANT_DATA_DIR, exist_ok=True)

print("Connecting to local Qdrant database...")
client = QdrantClient(path=QDRANT_DATA_DIR)

# Recreate the collection
print(f"Recreating collection '{COLLECTION_NAME}'...")
client.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=128, distance=Distance.EUCLID),
)

sift = cv2.SIFT_create()

if not os.path.exists(IMAGES_DIR):
    print(f"Images directory '{IMAGES_DIR}' does not exist.")
    exit(1)

image_files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

print(f"Found {len(image_files)} images in '{IMAGES_DIR}'.")

batch_size = 1000
points_batch = []

total_descriptors = 0

for i, filename in enumerate(image_files):
    print(f"Processing image {i+1}/{len(image_files)}: {filename}")
    filepath = os.path.join(IMAGES_DIR, filename)

    # Read image
    img = cv2.imread(filepath)
    if img is None:
        print(f"  Warning: Could not read image {filepath}. Skipping.")
        continue

    # Generate and save thumbnail
    thumb_path = os.path.join(THUMBNAILS_DIR, filename)
    # maintain aspect ratio, max width/height 200
    h, w = img.shape[:2]
    scale = min(200 / w, 200 / h)
    if scale < 1:
        thumb = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        thumb = img.copy()
    cv2.imwrite(thumb_path, thumb)

    # Extract SIFT features
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    keypoints, descriptors = sift.detectAndCompute(gray, None)

    if descriptors is None:
        print(f"  Warning: No features found in {filename}.")
        continue

    # Add descriptors to batch
    for desc in descriptors:
        point_id = str(uuid.uuid4())
        # Qdrant client needs vectors as lists of floats
        vector = desc.tolist()
        payload = {"filename": filename}

        points_batch.append(
            PointStruct(id=point_id, vector=vector, payload=payload)
        )

        # Upload batch if it reaches the size limit
        if len(points_batch) >= batch_size:
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points_batch
            )
            total_descriptors += len(points_batch)
            points_batch = []

# Upload any remaining points in the batch
if points_batch:
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points_batch
    )
    total_descriptors += len(points_batch)

print(f"Ingestion complete. Extracted and stored a total of {total_descriptors} descriptors.")
