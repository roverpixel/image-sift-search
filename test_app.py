import asyncio
import os
import sys
import types

sys.modules['cv2'] = types.ModuleType('cv2')
sys.modules['cv2'].SIFT_create = lambda: None
sys.modules['qdrant_client'] = types.ModuleType('qdrant_client')
sys.modules['qdrant_client.QdrantClient'] = lambda url: None
sys.modules['qdrant_client.http'] = types.ModuleType('qdrant_client.http')
sys.modules['qdrant_client.http.models'] = types.ModuleType('qdrant_client.http.models')
sys.modules['qdrant_client.http.models'].SearchRequest = lambda: None
sys.modules['numpy'] = types.ModuleType('numpy')

from app.app import app

async def run():
    os.makedirs("thumbnails", exist_ok=True)
    with open("thumbnails/test.txt", "w") as f:
        f.write("hello")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/thumbnails/test.txt",
        "root_path": "",
        "headers": [(b"x-forwarded-prefix", b"/image-sift-search")],
        "query_string": b"",
    }
    class MockReceive:
        async def __call__(self):
            return {"type": "http.request"}
    class MockSend:
        async def __call__(self, message):
            if message["type"] == "http.response.start":
                print("Status:", message["status"])

    await app(scope, MockReceive(), MockSend())

asyncio.run(run())
