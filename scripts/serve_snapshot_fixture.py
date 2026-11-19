"""Local TLS-only provider fixture; no cloud resources or real Blob credentials."""

import json
import os
import ssl
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

DIRECTORY = Path("/fixture")
ARCHIVE = next(DIRECTORY.glob("*.tar.gz"))
SHA256 = os.environ["FIXTURE_ARCHIVE_SHA256"]
TOKEN = os.environ["FIXTURE_CLIENT_TOKEN"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/api/internal/chroma-snapshot":
            if self.headers.get("Authorization") != "Bearer " + TOKEN:
                self.send_error(403)
                return
            body = json.dumps({"url": "https://fixture.private.blob.vercel-storage.com:8443/" + ARCHIVE.name + "?signature=fixture",
                "sha256": SHA256, "collection_id": "51cdb05c-3ee9-4b04-b85c-71cbf168ff0d",
                "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()}).encode()
            content_type = "application/json"
        elif path.path == "/" + ARCHIVE.name and path.query == "signature=fixture":
            body, content_type = ARCHIVE.read_bytes(), "application/gzip"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(DIRECTORY / "test-cert.pem", DIRECTORY / "test-key.pem")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
