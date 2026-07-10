import re

with open("app/app.py", "r") as f:
    content = f.read()

# Replace the middleware
pattern = r'@app\.middleware\("http"\)\s*async def add_root_path\(request: Request, call_next\):\s*prefix = request\.headers\.get\("X-Forwarded-Prefix"\)\s*if prefix:\s*request\.scope\["root_path"\] = prefix\s*return await call_next\(request\)'

replacement = """class ProxyHeadersMiddleware:
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

app.add_middleware(ProxyHeadersMiddleware)"""

new_content = re.sub(pattern, replacement, content)

with open("app/app.py", "w") as f:
    f.write(new_content)
