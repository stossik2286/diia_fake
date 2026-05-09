import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
NESTED_STATIC_DIR = PROJECT_DIR / "my_site_copy" / "my.funpapers.net"
STATIC_DIR = PROJECT_DIR if (PROJECT_DIR / "index.html").exists() else NESTED_STATIC_DIR


class SpaStaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
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
