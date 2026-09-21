import os
import cv2
import numpy as np
from collections import Counter
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.http.models import SearchRequest

# Directories
THUMBNAILS_DIR = "thumbnails"
COLLECTION_NAME = "sift_features"
STATIC_DIR = "/app/static"

app = FastAPI()


allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:7008,http://localhost:8000,http://localhost,http://127.0.0.1:7008,http://127.0.0.1:8000,http://127.0.0.1").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RootPathMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            prefix = headers.get(b"x-forwarded-prefix")
            if prefix:
                prefix_str = prefix.decode("latin1")
                scope["root_path"] = prefix_str
                path = scope.get("path", "")
                if not path.startswith(prefix_str):
                    scope["path"] = prefix_str + path
        await self.app(scope, receive, send)

app.add_middleware(RootPathMiddleware)


os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files
app.mount("/thumbnails", StaticFiles(directory=THUMBNAILS_DIR), name="thumbnails")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Initialize Qdrant Client and SIFT
qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
try:
    client = QdrantClient(url=qdrant_url)
except Exception as e:
    print(f"Error connecting to Qdrant at {qdrant_url}: {e}")
    client = None

sift = cv2.SIFT_create()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return "<h1>Index.html not found</h1>"

@app.post("/search")
async def search_image(request: Request, file: UploadFile = File(...)):
    if not client:
        return {"error": "Qdrant client is not initialized."}

    # Read the uploaded image
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"error": "Invalid image format."}

    # Extract SIFT features
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    keypoints, descriptors = sift.detectAndCompute(gray, None)

    if descriptors is None:
        return {"error": "No features found in the uploaded image.", "matches": []}

    # We will aggregate votes for each filename
    filename_votes = Counter()

    # Perform batched search for efficiency
    # Qdrant client allows sending multiple search requests at once
    search_queries = []
    for kp, desc in zip(keypoints, descriptors):
        search_queries.append(
            SearchRequest(
                vector=desc.tolist(),
                limit=5, # Get top 5 nearest neighbors for each descriptor
                with_payload=True,
                with_vector=False
            )
        )

    # We can chunk search queries if there are too many (e.g. >1000)
    batch_size = 100
    all_results = []

    for i in range(0, len(search_queries), batch_size):
        batch = search_queries[i:i+batch_size]
        try:
            batch_results = client.search_batch(
                collection_name=COLLECTION_NAME,
                requests=batch
            )
            all_results.extend(batch_results)
        except Exception as e:
            print(f"Error during search_batch: {e}")
            pass

    # Group matched keypoints by filename
    filename_matches = {}

    # all_results matches search_queries indices
    for query_idx, result_list in enumerate(all_results):
        query_kp = keypoints[query_idx]
        for scored_point in result_list:
            if scored_point.payload and "filename" in scored_point.payload:
                filename = scored_point.payload["filename"]
                if "x" in scored_point.payload and "y" in scored_point.payload:
                    if filename not in filename_matches:
                        filename_matches[filename] = {"src_pts": [], "dst_pts": []}

                    filename_matches[filename]["src_pts"].append(query_kp.pt)
                    filename_matches[filename]["dst_pts"].append(
                        (scored_point.payload["x"], scored_point.payload["y"])
                    )

    # Calculate inliers for each file
    for filename, pts in filename_matches.items():
        src_pts = np.float32(pts["src_pts"]).reshape(-1, 1, 2)
        dst_pts = np.float32(pts["dst_pts"]).reshape(-1, 1, 2)

        inliers_count = 0
        if len(src_pts) >= 4:
            # Need at least 4 points to find a homography
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if mask is not None:
                inliers_count = int(np.sum(mask))
        else:
            # Fallback if less than 4 points are matched, though it's not a reliable homography
            # They don't have enough geometric info to establish a shape
            inliers_count = 0

        filename_votes[filename] = inliers_count

    # Get top 10 files by inlier count
    top_10 = filename_votes.most_common(10)

    matches = []
    for filename, inliers in top_10:
        if inliers > 0:
            matches.append({
                "filename": filename,
                "votes": inliers, # Keeping "votes" key for backward compatibility in JSON, but it represents inliers
                "thumbnail_url": f"{request.scope.get('root_path', '')}/thumbnails/{filename}"
            })

    mosaic_url_prefix = os.environ.get("MOSAIC_URL_PREFIX", "")

    return {
        "matches": matches,
        "total_features_extracted": len(descriptors),
        "mosaic_url_prefix": mosaic_url_prefix
    }
