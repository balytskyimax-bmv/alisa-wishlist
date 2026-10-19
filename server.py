import http.server
import socketserver
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
import threading
import time

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "gifts.json")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# Cloud Persistence Configurations
MANTLE_URL = "https://mantledb.sh/v2/alisa-bday-wishlist-2026-v1/reservations"
MANTLE_KEY = os.environ.get("MANTLE_KEY", "61b275b0540537928d79e56dafca4e7804e626de874012517b602c61e31cd71b")
BACKUP_KVDB_URL = "https://kvdb.io/HxrGi1TgiziTmfWDjiZjr1/reservations"

_last_remote_sync = 0
_remote_sync_interval = 2.0  # seconds between remote fetches to avoid spamming
_sync_lock = threading.Lock()

def fetch_remote_reservations():
    """Fetches reservations dictionary from MantleDB (or backup KVdb)."""
    # 1. Try MantleDB
    try:
        req = urllib.request.Request(
            MANTLE_URL,
            headers={
                "User-Agent": "AlisaWishlistServer/1.0",
                "X-Mantle-Key": MANTLE_KEY
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        print(f"[WARN] MantleDB fetch failed: {e}")

    # 2. Try Backup KVdb
    try:
        req = urllib.request.Request(
            BACKUP_KVDB_URL,
            headers={"User-Agent": "AlisaWishlistServer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        print(f"[WARN] KVdb fetch failed: {e}")

    return None

def push_remote_reservations(reservations_dict):
    """Pushes reservations to MantleDB and KVdb in a background thread."""
    def _push():
        payload = json.dumps(reservations_dict, ensure_ascii=False).encode("utf-8")
        
        # 1. MantleDB
        try:
            req = urllib.request.Request(
                MANTLE_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Mantle-Key": MANTLE_KEY,
                    "User-Agent": "AlisaWishlistServer/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                print(f"[CLOUD DB] MantleDB saved successfully (status {resp.status})")
        except Exception as e:
            print(f"[ERROR] MantleDB push failed: {e}")

        # 2. Backup KVdb
        try:
            req = urllib.request.Request(
                BACKUP_KVDB_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "AlisaWishlistServer/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                print(f"[CLOUD DB] Backup KVdb saved successfully (status {resp.status})")
        except Exception as e:
            print(f"[ERROR] KVdb push failed: {e}")

    threading.Thread(target=_push, daemon=True).start()

def get_reservations_map_from_gifts(gifts):
    """Extracts reservations map { gift_id: { reserved, reservedBy, wishes, reservedAt } }."""
    res_map = {}
    for g in gifts:
        if g.get("reserved"):
            res_map[g["id"]] = {
                "reserved": True,
                "reservedBy": g.get("reservedBy", ""),
                "wishes": g.get("wishes", ""),
                "reservedAt": g.get("reservedAt", "")
            }
    return res_map

def sync_reservations_into_gifts(gifts, remote_res):
    """Merges remote reservation records into the gifts list."""
    if not remote_res:
        return gifts
    for g in gifts:
        gid = g["id"]
        if gid in remote_res:
            r = remote_res[gid]
            g["reserved"] = bool(r.get("reserved", False))
            g["reservedBy"] = r.get("reservedBy", "") if g["reserved"] else ""
            g["wishes"] = r.get("wishes", "") if g["reserved"] else ""
            g["reservedAt"] = r.get("reservedAt", None) if g["reserved"] else None
        else:
            g["reserved"] = False
            g["reservedBy"] = ""
            g["wishes"] = ""
            g["reservedAt"] = None
    return gifts

def load_gifts(force_sync=False):
    global _last_remote_sync
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        gifts = json.load(f)

    # Check if we should sync from remote cloud store
    now = time.time()
    if force_sync or (now - _last_remote_sync > _remote_sync_interval):
        with _sync_lock:
            remote_res = fetch_remote_reservations()
            if remote_res:
                gifts = sync_reservations_into_gifts(gifts, remote_res)
                save_local_gifts(gifts)
            _last_remote_sync = time.time()

    return gifts

def save_local_gifts(gifts):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(gifts, f, ensure_ascii=False, indent=2)

# Initial startup sync
print("[STARTUP] Initializing server and syncing from cloud database...")
try:
    load_gifts(force_sync=True)
    print("[STARTUP] Initial cloud sync complete!")
except Exception as err:
    print(f"[STARTUP WARN] Cloud sync error during boot: {err}")

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
        elif parsed.path == "/api/sync":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            gifts = load_gifts(force_sync=True)
            self.wfile.write(json.dumps({"success": True, "gifts": gifts}, ensure_ascii=False).encode("utf-8"))
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

            gifts = load_gifts(force_sync=True)
            found = False
            for g in gifts:
                if g["id"] == gift_id:
                    if g.get("reserved"):
                        self.send_response(409)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": f"Цей подарунок уже зарезервовано ({g.get('reservedBy')})"}).encode("utf-8"))
                        return
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    g["reserved"] = True
                    g["reservedBy"] = name
                    g["wishes"] = wishes
                    g["reservedAt"] = now_str
                    found = True
                    print(f"✨ [NEW RESERVATION] Gift: '{g['title']}' (ID: {gift_id}) | By: '{name}' | Wishes: '{wishes}' | Time: {now_str}", flush=True)
                    break

            if found:
                save_local_gifts(gifts)
                res_map = get_reservations_map_from_gifts(gifts)
                push_remote_reservations(res_map)
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
            gifts = load_gifts(force_sync=True)
            found = False
            for g in gifts:
                if g["id"] == gift_id:
                    print(f"❌ [UNRESERVED] Gift: '{g['title']}' (ID: {gift_id}) was previously reserved by '{g.get('reservedBy')}'", flush=True)
                    g["reserved"] = False
                    g["reservedBy"] = ""
                    g["wishes"] = ""
                    g["reservedAt"] = None
                    found = True
                    break

            if found:
                save_local_gifts(gifts)
                res_map = get_reservations_map_from_gifts(gifts)
                push_remote_reservations(res_map)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "gifts": gifts}).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Подарунок не знайдено"}).encode("utf-8"))

        elif parsed.path == "/api/admin/reserve":
            gift_id = data.get("id")
            name = (data.get("name") or "").strip()
            wishes = (data.get("wishes") or "").strip()

            if not gift_id or not name:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Вкажіть назву подарунка та ім'я гостя"}).encode("utf-8"))
                return

            gifts = load_gifts(force_sync=True)
            found = False
            for g in gifts:
                if g["id"] == gift_id:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    g["reserved"] = True
                    g["reservedBy"] = name
                    g["wishes"] = wishes
                    g["reservedAt"] = now_str
                    found = True
                    print(f"👑 [ADMIN RESERVATION] Gift: '{g['title']}' (ID: {gift_id}) | By: '{name}' | Wishes: '{wishes}'", flush=True)
                    break

            if found:
                save_local_gifts(gifts)
                res_map = get_reservations_map_from_gifts(gifts)
                push_remote_reservations(res_map)
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
