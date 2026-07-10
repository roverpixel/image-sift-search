import asyncio
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging

class ProxyHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            prefix = headers.get(b"x-forwarded-prefix", b"").decode("utf-8")
            if prefix:
                scope["root_path"] = prefix
                # The issue with BaseHTTPMiddleware is that it passes the request to FastAPI which handles it.
                # If we use pure ASGI middleware and NOT change scope['path'], FastAPI router uses scope['path'].
                # If Nginx strips the prefix, scope['path'] is /thumbnails/1.jpg.
                # If Nginx did not strip, scope['path'] would be /image-sift-search/thumbnails/1.jpg.
                # Nginx proxy_pass with trailing slash strips the prefix.
                # So scope['path'] = '/thumbnails/1.jpg'.
                # But wait! If we do: scope["path"] = prefix + scope["path"]
                # Then scope["path"] = '/image-sift-search/thumbnails/1.jpg'.
                # And FastAPI routing will try to match this against its routes.
                # Since we mounted "/thumbnails", it won't match!
                # Wait... Starlette routing strips `root_path` from `path` BEFORE routing if `path` starts with `root_path`.
                # Let's test if Starlette strips `root_path`.
                if not scope["path"].startswith(prefix):
                    scope["path"] = prefix + scope["path"]
        await self.app(scope, receive, send)

app = FastAPI()
app_with_middleware = ProxyHeadersMiddleware(app)

app.mount("/thumbnails", StaticFiles(directory="thumbnails"), name="thumbnails")

@app.get("/search")
async def search(request: Request):
    return JSONResponse({"path": request.scope.get("path")})

async def run():
    import os
    os.makedirs("thumbnails", exist_ok=True)
    with open("thumbnails/test.txt", "w") as f:
        f.write("hello")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/thumbnails/test.txt", # What proxy sends when proxy_pass http://host/;
        "root_path": "",
        "headers": [(b"x-forwarded-prefix", b"/image-sift-search")],
        "query_string": b"",
    }
    class MockReceive:
        async def __call__(self):
            return {"type": "http.request"}
    class MockSend:
        async def __call__(self, message):
            print("Message:", message)

    await app_with_middleware(scope, MockReceive(), MockSend())

asyncio.run(run())
