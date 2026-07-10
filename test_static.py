import asyncio
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles

app = FastAPI()

class ProxyHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            prefix = headers.get(b"x-forwarded-prefix", b"").decode("utf-8")
            if prefix:
                scope["root_path"] = prefix
                # memory says "and prepends the prefix to scope['path'] before FastAPI routing occurs"
                if not scope["path"].startswith(prefix):
                    scope["path"] = prefix + scope["path"]
        await self.app(scope, receive, send)

app.add_middleware(ProxyHeadersMiddleware)

app.mount("/thumbnails", StaticFiles(directory="thumbnails"), name="thumbnails")

@app.get("/search")
async def search(request: Request):
    return {"path": request.scope.get("path"), "root_path": request.scope.get("root_path")}

async def run():
    import os
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
            print("Message:", message)

    await app(scope, MockReceive(), MockSend())

asyncio.run(run())
