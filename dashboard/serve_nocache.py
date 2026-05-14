#!/usr/bin/env python3
"""Dalio Macro Dashboard — no-cache HTTP server.

CRITICAL: Never use python3 -m http.server — it sends NO Cache-Control headers.
Browsers aggressively cache HTML and the user sees stale versions.
This server injects no-cache headers on every response.

Usage: python3 serve_nocache.py [port]
Default port: 8502
"""
import http.server
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8502
DIR = os.path.dirname(os.path.abspath(__file__))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        # Suppress logs for data.json (polled frequently)
        if "data.json" in (args[0] if args else ""):
            return
        super().log_message(format, *args)


if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", PORT), NoCacheHandler)
    print(f"🚀 Dalio Dashboard → http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
