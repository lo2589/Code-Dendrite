#!/usr/bin/env python3
"""
Quick HTML Viewer Server
Usage: python view_html.py [html_file] [port]
"""

import http.server
import socketserver
import webbrowser
from pathlib import Path
import sys

# Get file path and port from command line
html_file = sys.argv[1] if len(sys.argv) > 1 else "code_tree_view.html"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

# Convert to absolute path
html_path = Path(html_file).resolve()

if not html_path.exists():
    print(f"❌ File not found: {html_path}")
    sys.exit(1)

print(f"📄 Serving: {html_path}")
print(f"🌐 Port: {port}")
print(f"🔗 URL: http://localhost:{port}/{html_path.name}")
print(f"\n🚀 Opening browser...")

# Change to the directory containing the HTML file
import os
os.chdir(html_path.parent)

# Create HTTP server
class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

with socketserver.TCPServer(("", port), Handler) as httpd:
    # Open browser
    url = f"http://localhost:{port}/{html_path.name}"
    webbrowser.open(url)
    
    print(f"\n✅ Server running at {url}")
    print(f"💡 Press Ctrl+C to stop\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        httpd.shutdown()
