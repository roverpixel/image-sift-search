from fastapi.testclient import TestClient
from app.app import app
import os
from unittest.mock import patch

client = TestClient(app)

def test_read_root_found(tmp_path):
    with patch("app.app.STATIC_DIR", str(tmp_path)):
        # Create an index.html file in the mocked STATIC_DIR
        index_file = tmp_path / "index.html"
        index_file.write_text("<h1>Mocked Index</h1>")

        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "<h1>Mocked Index</h1>"

def test_read_root_not_found(tmp_path):
    with patch("app.app.STATIC_DIR", str(tmp_path)):
        # Do not create index.html
        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "<h1>Index.html not found</h1>"
