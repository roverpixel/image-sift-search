import asyncio
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse

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
                if not scope["path"].startswith(prefix):
                    scope["path"] = prefix + scope["path"]
        await self.app(scope, receive, send)

app.add_middleware(ProxyHeadersMiddleware)

@app.get("/search")
async def search(request: Request):
    return JSONResponse({"path": request.scope.get("path"), "root_path": request.scope.get("root_path")})

async def run():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/search",
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
    # Using the ASGI app directly
    await app(scope, MockReceive(), MockSend())

asyncio.run(run())
