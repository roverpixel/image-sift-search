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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProxyHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            # ASGI headers are byte strings, lowercase keys
            prefix = headers.get(b"x-forwarded-prefix", b"").decode("utf-8")
            if prefix:
                scope["root_path"] = prefix
                if not scope["path"].startswith(prefix):
                    scope["path"] = prefix + scope["path"]
        await self.app(scope, receive, send)

app.add_middleware(ProxyHeadersMiddleware)


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
    for desc in descriptors:
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

    # Tally votes based on filename payload
    for result_list in all_results:
        for scored_point in result_list:
            if scored_point.payload and "filename" in scored_point.payload:
                filename = scored_point.payload["filename"]
                # The score in L2 distance is distance (lower is better)
                # But Qdrant by default returns similarity for Cosine/Dot. For L2 it's just distance.
                # A simple voting mechanism: +1 vote for each appearance in top K
                filename_votes[filename] += 1

    # Get top 10 files by vote count
    top_10 = filename_votes.most_common(10)

    matches = []
    for filename, votes in top_10:
        matches.append({
            "filename": filename,
            "votes": votes,
            "thumbnail_url": f"{request.scope.get('root_path', '')}/thumbnails/{filename}"
        })

    mosaic_url_prefix = os.environ.get("MOSAIC_URL_PREFIX", "")

    return {
        "matches": matches,
        "total_features_extracted": len(descriptors),
        "mosaic_url_prefix": mosaic_url_prefix
    }
