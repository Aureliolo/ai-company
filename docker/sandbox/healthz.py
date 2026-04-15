"""Minimal health check HTTP server for the sandbox container.

Serves GET /healthz on port 15001 with a JSON response. Runs as a
background process alongside the sandbox's main sleep loop. Uses only
stdlib -- no external dependencies.
"""

import http.server
import json
import time


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/healthz":
            body = json.dumps({"status": "healthy", "uptime": int(time.monotonic())})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # Suppress access logs.


if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", 15001), _Handler)
    server.serve_forever()
