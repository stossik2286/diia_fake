import json as _json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import storage

PROJECT_DIR = Path(__file__).resolve().parent
PHOTO_DIR = PROJECT_DIR / "photos"
PHOTO_DIR.mkdir(exist_ok=True)
STATIC_DIR = PROJECT_DIR

_DEMO_DATA = _json.loads((PROJECT_DIR / "demo_data.json").read_text(encoding="utf-8"))


class SpaStaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload):
        body = _json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file_bytes(self, file_path, content_type):
        body = Path(file_path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_demo_api_response(self, path):
        if path.startswith("/api/check"):
            self.send_json(_DEMO_DATA["profile"])
            return True

        if path.startswith("/api/news") or path.endswith("ews.json"):
            self.send_json(_DEMO_DATA["news"])
            return True

        if path.startswith("/api/qr_"):
            self.send_json({
                "qr_link_doc": "DEMO QR",
                "qr_link_international": "DEMO QR",
                "qr_link": "DEMO QR"
            })
            return True

        if path.startswith("/api/"):
            self.send_json({"status": "ok"})
            return True

        return False

    def do_GET(self):
        path = urlparse(self.path).path

        if path.startswith("/api/photo/"):
            photo_id = path[len("/api/photo/"):]
            photo_path = PHOTO_DIR / f"{photo_id}.jpg"
            if photo_path.exists():
                self.send_file_bytes(photo_path, "image/jpeg")
            else:
                default = PROJECT_DIR / "photo.jpg"
                if default.exists():
                    self.send_file_bytes(default, "image/jpeg")
                else:
                    self.send_json({"error": "no photo"})
            return

        if path == "/api/validate-token":
            qs = parse_qs(urlparse(self.path).query)
            raw_token = qs.get("token", [None])[0]
            if not raw_token:
                raw_token = qs.get("t", [None])[0]
            payload = storage.verify_token(raw_token) if raw_token else None
            if payload:
                self.send_json({
                    "valid": True,
                    "name": payload.get("name", ""),
                    "photo_id": payload.get("photo_id", ""),
                    "birthday": payload.get("birthday", ""),
                    "exp": payload["exp"]
                })
            else:
                self.send_json({"valid": False})
            return

        if path == "/api/config":
            qs = parse_qs(urlparse(self.path).query)
            raw_token = qs.get("token", [None])[0]
            payload = storage.verify_token(raw_token) if raw_token else None
            if payload:
                self.send_json({
                    "name": payload.get("name", ""),
                    "photo_id": payload.get("photo_id", ""),
                    "birthday": payload.get("birthday", "")
                })
            else:
                self.send_json({"name": "", "photo_id": "", "birthday": ""})
            return

        if self.send_demo_api_response(path):
            return

        if path.startswith("/app/"):
            stripped_app_path = path.removeprefix("/app")
            if stripped_app_path.startswith(("/js/", "/css/", "/img/", "/fonts/")) or stripped_app_path in ("/photo.jpg", "/sign.png"):
                self.path = stripped_app_path

        requested_path = self.translate_path(self.path)
        if not Path(requested_path).exists() and "." not in Path(self.path).name:
            self.path = "/index.html"
        super().do_GET()


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), SpaStaticHandler)
    print(f"Serving {STATIC_DIR} on port {port}", flush=True)
    print(f"Photos directory: {PHOTO_DIR}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
