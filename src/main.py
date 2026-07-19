"""WhiteLight API entry point.

Runs the simple HTTP server defined in src.api.APIServerHandler.
"""

import argparse
import signal
from http.server import HTTPServer

# Import the request handler we already have
from src.api import APIServerHandler


def run_server(host: str, port: int) -> None:
    """Start the HTTP server and handle shutdown gracefully."""
    server = HTTPServer((host, port), APIServerHandler)

    def _handle_sigterm(sig: int, _: object) -> None:  # pragma: no cover
        print(f"\n[{host}:{port}] Received signal {sig}, shutting down...", flush=True)
        server.shutdown()

    # Register signal handlers for Ctrl‑C / SIGTERM
    signal.signal(signal.SIGINT, _handle_sigterm)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    print(f"[{host}:{port}] WhiteLight API server started – press Ctrl‑C to stop", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        print(f"[{host}:{port}] Server stopped.", flush=True)


def _parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the WhiteLight REST API server.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Hostname or IP address to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port to listen on (default: 8000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_cli()
    run_server(args.host, args.port)
