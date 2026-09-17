"""RindenSjakk — local app server (no cloud, this PC only).

Serves the static viewer AND runs the video->move-tree engine on demand, so the
viewer's "Hent trekk" button works end-to-end. Everything stays local.

Start:  python server.py   (or double-click start.bat)
Then open http://localhost:8777/  (opens automatically).

The engine (OpenCV + python-chess) is imported lazily, so the viewer still
serves even if those packages are missing — only video extraction needs them.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(ROOT, "viewer")
DOWNLOADS = os.path.join(ROOT, "downloads")
PORT = 8777
MAX_BODY = 1 << 20  # 1 MB cap on request bodies


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=VIEWER, **kwargs)

    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def do_GET(self):
        if self.path.split("?")[0] == "/api/storage":
            try:
                self._json(200, storage_list())
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
            return
        super().do_GET()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY:
            raise ValueError("forespoersel for stor")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def do_POST(self):
        route = self.path.split("?")[0]
        try:
            body = self._read_body()
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": "ugyldig forespoersel: %s" % exc})
            return
        if route == "/api/extract":
            if not str(body.get("url", "")).strip():
                self._json(400, {"error": "mangler url"})
                return
            try:
                self._json(200, extract(body))
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
        elif route == "/api/storage/delete":
            try:
                self._json(200, storage_delete(body))
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"error": str(exc)})
        else:
            self.send_error(404, "not found")

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def extract(body):
    """Run the video pipeline and return a viewer repertoire record."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from engine.process_video import process, download_if_url
    from engine.tree_json import game_to_root

    url = str(body["url"]).strip()
    interval = float(body.get("interval", 1.5))
    start = float(body.get("start", 0))
    end_raw = body.get("end")
    end = float(end_raw) if end_raw not in (None, "") else None
    orientation = body.get("orientation", "auto")

    video = download_if_url(url)
    game, stats, _ = process(video, interval, start, end, orientation)
    return {
        "name": "Fra video",
        "source": "video: " + url,
        "orientation": stats.get("orientation", "white"),
        "root": game_to_root(game),
        "stats": stats,
    }


def storage_list():
    """Downloaded videos on disk, so Rinden can see usage and clean up."""
    files, total = [], 0
    if os.path.isdir(DOWNLOADS):
        for name in os.listdir(DOWNLOADS):
            path = os.path.join(DOWNLOADS, name)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                total += size
                files.append({"name": name, "size": size, "mtime": int(os.path.getmtime(path))})
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return {"files": files, "total": total, "dir": DOWNLOADS}


def _safe_download_path(name):
    if not name or name != os.path.basename(name) or name in (".", ".."):
        raise ValueError("ugyldig filnavn")
    path = os.path.abspath(os.path.join(DOWNLOADS, name))
    if os.path.commonpath([path, os.path.abspath(DOWNLOADS)]) != os.path.abspath(DOWNLOADS):
        raise ValueError("ugyldig sti")
    return path


def storage_delete(body):
    if body.get("all"):
        removed = 0
        if os.path.isdir(DOWNLOADS):
            for name in os.listdir(DOWNLOADS):
                path = os.path.join(DOWNLOADS, name)
                if os.path.isfile(path):
                    os.remove(path)
                    removed += 1
        return {"deleted": removed}
    path = _safe_download_path(str(body.get("name", "")))
    if os.path.isfile(path):
        os.remove(path)
        return {"deleted": 1}
    return {"deleted": 0}


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://localhost:%d/" % PORT
    print("RindenSjakk kjorer paa " + url)
    print("Lukk dette vinduet for aa stoppe.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStoppet.")


if __name__ == "__main__":
    main()
