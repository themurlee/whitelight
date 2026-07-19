import json
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer
import sys
import os

# Ensure project root is on sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

from src.api import APIServerHandler

def start_test_server(port=0):
    server = HTTPServer(("127.0.0.1", port), APIServerHandler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port, thread

def fetch(path, port):
    url = f"http://127.0.0.1:{port}{path}"
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()

def test_health_endpoint():
    server, port, thread = start_test_server()
    try:
        time.sleep(0.1)
        resp = fetch("/api/health", port)
        data = json.loads(resp)
        assert data.get("status") == "ok"
    finally:
        server.shutdown()
        thread.join()

def test_unknown_endpoint_returns_404():
    server, port, thread = start_test_server()
    try:
        time.sleep(0.1)
        try:
            fetch("/api/unknown", port)
            assert False, "Expected HTTPError for unknown endpoint"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
        thread.join()
