import os
import json
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs


PROJECT_DIR = Path(__file__).resolve().parent
NESTED_STATIC_DIR = PROJECT_DIR / "my_site_copy" / "my.funpapers.net"
STATIC_DIR = PROJECT_DIR if (PROJECT_DIR / "index.html").exists() else NESTED_STATIC_DIR
LOCAL_ASSET_DIR = PROJECT_DIR / "project-main"
TOKENS_FILE = PROJECT_DIR / "tokens.json"


def load_tokens():
    if not TOKENS_FILE.exists():
        return {}
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)


def get_token_data(raw_token):
    if not raw_token:
        return None
    tokens = load_tokens()
    key = "full:" + raw_token
    data = tokens.get(key)
    if not data:
        return None
    if data.get("expires_at", 0) <= time.time():
        return None
    return data


class SpaStaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
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
        if path.startswith("/api/photo") and (LOCAL_ASSET_DIR / "photo.jpg").exists():
            self.send_file_bytes(LOCAL_ASSET_DIR / "photo.jpg", "image/jpeg")
            return True

        if path.startswith("/api/signa") and (LOCAL_ASSET_DIR / "sign.png").exists():
            self.send_file_bytes(LOCAL_ASSET_DIR / "sign.png", "image/png")
            return True

        if path.startswith("/api/check"):
            self.send_json({
                "status": "ok",
                "code": "ok",
                "is_ban": 0,
                "version": "local-demo",
                "color": "B3C4E3",
                "password": "1111",
                "wm": "0",
                "nosign": 1,
                "offline": 1,
                "name": "TEST USER",
                "date": "01.01.2000",
                "birthday": "01.01.2000",
                "doc_number": "DEMO-000000",
                "number": "DEMO-000000",
                "tax_number": "0000000000",
                "rnokpp": "0000000000",
                "inn": "0000000000",
                "birth_street": "DEMO ADDRESS",
                "birth_street_date": "01.01.2000",
                "cords": "DEMO ONLY",
                "reg_date": "01.01.2000",
                "sign": "demo",
                "photo": "demo",
                "renewed": "DEMO",
                "barcode": "DEMO",
                "passport_start": "01.01.2000",
                "passport_end": "01.01.2099",
                "get_organ": "DEMO",
                "get_organ_international": "DEMO",
                "translit": "TEST USER",
                "sex": "X",
                "number_unzr": "00000000-00000",
                "qr_enable": 0,
                "qr_text": "DEMO QR",
                "qr_link_doc": "DEMO QR",
                "qr_link_international": "DEMO QR",
                "international": 0,
                "international_number": "DEMO-000000",
                "international_start": "01.01.2000",
                "international_end": "01.01.2099",
                "addDocs": 0
            })
            return True

        if path.startswith("/api/news") or path.endswith("ews.json"):
            self.send_json([
                {
                    "id": 0,
                    "title": "Документи доступні",
                    "text": ["Локальний режим увімкнено. Дані завантажені без зовнішнього API."],
                    "date": "10.05.2026"
                },
                {
                    "id": 1,
                    "title": "Новини працюють",
                    "text": ["Ця вкладка показує локальні демо-новини, щоб екран не залишався порожнім."],
                    "date": "10.05.2026"
                }
            ])
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

        # Token validation endpoint
        if path == "/api/validate-token":
            qs = parse_qs(urlparse(self.path).query)
            raw_token = qs.get("token", [None])[0]
            data = get_token_data(raw_token)
            if data:
                self.send_json({
                    "valid": True,
                    "name": data.get("name", ""),
                    "photo_updated": data.get("photo_updated", 0)
                })
            else:
                self.send_json({"valid": False})
            return

        # Token-specific config
        if path == "/api/config":
            qs = parse_qs(urlparse(self.path).query)
            raw_token = qs.get("token", [None])[0]
            data = get_token_data(raw_token)
            if data:
                self.send_json({
                    "name": data.get("name", ""),
                    "photo_updated": data.get("photo_updated", 0)
                })
            else:
                self.send_json({"name": "", "photo_updated": 0})
            return

        # Token-specific custom photo
        if path == "/api/custom-photo":
            qs = parse_qs(urlparse(self.path).query)
            raw_token = qs.get("token", [None])[0]
            prefix = raw_token[:16] if raw_token else ""
            custom_photo = PROJECT_DIR / f"custom_photo_{prefix}.jpg"
            if custom_photo.exists():
                self.send_file_bytes(custom_photo, "image/jpeg")
            else:
                self.send_file_bytes(PROJECT_DIR / "photo.jpg", "image/jpeg")

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
    server.serve_forever()


if __name__ == "__main__":
    main()
