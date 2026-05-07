#!/usr/bin/env python3
"""HTTP server with no-cache headers for dashboard development."""
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8502
DIR = os.path.dirname(os.path.abspath(__file__))

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        pass  # quiet

if __name__ == '__main__':
    print(f"🔄 No-cache HTTP server on http://localhost:{PORT}")
    http.server.HTTPServer(('', PORT), NoCacheHandler).serve_forever()
