"""
Vercel Serverless Function — /api/scan
Runs the AI Disaster Scanner and returns JSON results.

Query params:
  ?days=7  (default 7, max 90)
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scanner import run_scan


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        days = min(int(query.get("days", ["7"])[0]), 90)

        try:
            result = run_scan(days=days)
            body = json.dumps(result, ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "s-maxage=3600, stale-while-revalidate=1800")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
