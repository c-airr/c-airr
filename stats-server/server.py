"""Serwer kart statystyk profilu na oraclearm (za Caddy: stats.discordbothosting.pl/profile).

  /stats          - streak + jezyki ze wszystkich repo
  /langs/public   - jezyki tylko z publicznych repo
  /langs/private  - jezyki tylko z prywatnych repo

Token GitHub bierzemy z PAT_1 (ten sam .env co github-readme-stats), dane
cache'ujemy na 30 min, zeby nie mielic API przy kazdym wejsciu na profil.
"""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("GH_TOKEN", os.environ.get("PAT_1", ""))
import stats  # noqa: E402 - stats czyta GH_TOKEN przy imporcie

TTL = int(os.environ.get("CACHE_TTL", 1800))
PORT = int(os.environ.get("PORT", 8791))

_lock = threading.Lock()
_cache = {"at": 0.0, "data": None}


def data():
    with _lock:
        if _cache["data"] is None or time.time() - _cache["at"] > TTL:
            _cache["data"] = stats.fetch()
            _cache["at"] = time.time()
        return _cache["data"]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        try:
            if path == "/stats":
                body = stats.render(*data())
            elif path in ("/langs/public", "/langs/private"):
                body = stats.render_langs(data()[0], path.rsplit("/", 1)[1])
            else:
                self.send_error(404)
                return
        except Exception as e:  # GitHub API padlo itp.
            self.log_error("render failed: %r", e)
            self.send_error(502)
            return
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "image/svg+xml; charset=utf-8")
        # camo (proxy GitHuba) respektuje no-cache; swiezosc trzyma nasz cache po stronie serwera
        self.send_header("cache-control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    print(f"profile-stats on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
