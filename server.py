import http.server
import socketserver
import json
import os
import urllib.parse
from datetime import datetime

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "gifts.json")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

def load_gifts():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_gifts(gifts):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(gifts, f, ensure_ascii=False, indent=2)

class WishlistHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/gifts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            gifts = load_gifts()
            self.wfile.write(json.dumps(gifts, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/" or parsed.path == "":
            self.path = "/index.html"
            return super().do_GET()
        else:
            return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            data = {}

        if parsed.path == "/api/reserve":
            gift_id = data.get("id")
            name = (data.get("name") or "").strip()
            wishes = (data.get("wishes") or "").strip()

            if not gift_id or not name:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Вкажіть ваше ім'я"}).encode("utf-8"))
                return

            gifts = load_gifts()
            found = False
            for g in gifts:
                if g["id"] == gift_id:
                    if g.get("reserved"):
                        self.send_response(409)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": f"Цей подарунок уже зарезервовано ({g.get('reservedBy')})"}).encode("utf-8"))
                        return
                    g["reserved"] = True
                    g["reservedBy"] = name
                    g["wishes"] = wishes
                    g["reservedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    found = True
                    break

            if found:
                save_gifts(gifts)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "gifts": gifts}).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Подарунок не знайдено"}).encode("utf-8"))

        elif parsed.path == "/api/unreserve":
            gift_id = data.get("id")
            gifts = load_gifts()
            found = False
            for g in gifts:
                if g["id"] == gift_id:
                    g["reserved"] = False
                    g["reservedBy"] = ""
                    g["wishes"] = ""
                    g["reservedAt"] = None
                    found = True
                    break

            if found:
                save_gifts(gifts)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "gifts": gifts}).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Подарунок не знайдено"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), WishlistHandler) as httpd:
        print(f"Wishlist server is running at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
