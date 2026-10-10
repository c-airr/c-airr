"""Karty Last.fm: top artysci i top utwory za wybrany okres.

Dane z Last.fm (user.getTopArtists / user.getTopTracks), zdjecia z Deezera,
bo Last.fm od lat zwraca zamiast zdjec artystow szare gwiazdki. Obrazki
wklejamy jako data: URI - camo (proxy GitHuba) nie laduje obrazkow
zagniezdzonych w SVG.
"""
import base64
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("LASTFM_USER", "realairr_")
FONT = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,Menlo,monospace"
TTL = 1800
PERIODS = {
    "7day": "last 7 days",
    "1month": "last 30 days",
    "6month": "last 6 months",
    "12month": "last 12 months",
}
RED = "#d51007"  # czerwien Last.fm

STYLE = """<style>
text{font-family:%s;fill:#1f2328}.m{fill:#59636e}.ph{fill:#eff2f5}.trk{fill:#eff2f5}
@media (prefers-color-scheme:dark){text{fill:#e6edf3}.m{fill:#9198a1}.ph{fill:#151b23}.trk{fill:#151b23}}
</style>""" % FONT

_lock = threading.Lock()
_cache = {}  # klucz -> (czas, dane)
_img = {}  # url -> data URI (zdjecia sie nie zmieniaja, trzymamy bez limitu)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "c-airr-profile"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def _lastfm(method, period, limit=5):
    key = os.environ.get("LASTFM_API_KEY")
    if not key:
        raise RuntimeError("brak LASTFM_API_KEY w .env")
    q = urllib.parse.urlencode(
        {"method": method, "user": USER, "period": period, "limit": limit, "api_key": key, "format": "json"}
    )
    return json.loads(_get(f"https://ws.audioscrobbler.com/2.0/?{q}"))


def _cached(name, period, fn):
    k = (name, period)
    with _lock:
        hit = _cache.get(k)
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
    data = fn()
    with _lock:
        _cache[k] = (time.time(), data)
    return data


def _data_uri(url):
    if not url:
        return None
    if url in _img:
        return _img[url]
    try:
        raw = _get(url)
        uri = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
    except Exception:
        uri = None
    _img[url] = uri
    return uri


def _deezer(path, q):
    try:
        res = json.loads(_get(f"https://api.deezer.com/{path}?" + urllib.parse.urlencode({"q": q, "limit": 1})))
        return (res.get("data") or [None])[0]
    except Exception:
        return None


def artist_photo(name):
    hit = _deezer("search/artist", name)
    return _data_uri(hit and hit.get("picture_medium"))


def track_cover(artist, title):
    # skladnia artist:"" track:"" w Deezerze zwraca 0 wynikow, zwykle zapytanie dziala;
    # dopiski "(with ...)", "(feat. ...)", "- Remastered" tylko psuja trafienia
    clean = re.sub(r"\s*[\(\[].*?[\)\]]|\s+-\s+.*$", "", title).strip() or title
    hit = _deezer("search", f"{artist} {clean}")
    return _data_uri(hit and (hit.get("album") or {}).get("cover_medium"))


def cut(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def header(out, W, title, period):
    out.append(f'<text x="4" y="16" font-size="13" font-weight="600">{title}</text>')
    out.append(
        f'<text class="m" x="{W - 4}" y="16" text-anchor="end" font-size="11">{PERIODS[period]} · last.fm</text>'
    )


def render_artists(period):
    def load():
        items = _lastfm("user.gettopartists", period)["topartists"]["artist"]
        return [(a["name"], int(a["playcount"]), artist_photo(a["name"])) for a in items]

    items = _cached("artists", period, load)
    W, H, r = 860, 200, 46
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', STYLE]
    header(out, W, "Top artists", period)
    col = W / 5
    for i, (name, plays, img) in enumerate(items[:5]):
        cx, cy = col * i + col / 2, 40 + r
        out.append(f'<clipPath id="a{i}"><circle cx="{cx:.1f}" cy="{cy}" r="{r}"/></clipPath>')
        out.append(
            f'<image href="{img}" x="{cx - r:.1f}" y="{cy - r}" width="{2 * r}" height="{2 * r}" '
            f'clip-path="url(#a{i})" preserveAspectRatio="xMidYMid slice"/>'
            if img
            else f'<circle class="ph" cx="{cx:.1f}" cy="{cy}" r="{r}"/>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{cy + r + 24}" text-anchor="middle" font-size="13" font-weight="700">'
            f"{escape(cut(name, 20))}</text>"
        )
        out.append(
            f'<text class="m" x="{cx:.1f}" y="{cy + r + 42}" text-anchor="middle" font-size="11">{plays:,} plays</text>'
        )
    if not items:
        out.append(f'<text class="m" x="4" y="60" font-size="12">No scrobbles in this period</text>')
    out.append("</svg>")
    return "".join(out)


def render_tracks(period):
    def load():
        items = _lastfm("user.gettoptracks", period)["toptracks"]["track"]
        return [
            (t["name"], t["artist"]["name"], int(t["playcount"]), track_cover(t["artist"]["name"], t["name"]))
            for t in items
        ]

    items = _cached("tracks", period, load)
    W, row = 860, 54
    H = 30 + max(1, len(items[:5])) * row
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', STYLE]
    header(out, W, "Top tracks", period)
    top = max([p for _, _, p, _ in items] or [1])
    bar_x, bar_w = 600, 170
    for i, (name, artist, plays, img) in enumerate(items[:5]):
        y = 30 + i * row
        out.append(f'<text class="m" x="8" y="{y + 27}" font-size="12">{i + 1}</text>')
        out.append(f'<clipPath id="t{i}"><rect x="30" y="{y + 4}" width="42" height="42" rx="6"/></clipPath>')
        out.append(
            f'<image href="{img}" x="30" y="{y + 4}" width="42" height="42" clip-path="url(#t{i})" '
            f'preserveAspectRatio="xMidYMid slice"/>'
            if img
            else f'<rect class="ph" x="30" y="{y + 4}" width="42" height="42" rx="6"/>'
        )
        out.append(f'<text x="86" y="{y + 22}" font-size="13" font-weight="700">{escape(cut(name, 58))}</text>')
        out.append(f'<text class="m" x="86" y="{y + 40}" font-size="12">{escape(cut(artist, 58))}</text>')
        # pasek proporcjonalny do najczesciej granego utworu w tym okresie
        out.append(f'<rect class="trk" x="{bar_x}" y="{y + 22}" width="{bar_w}" height="4" rx="2"/>')
        out.append(
            f'<rect x="{bar_x}" y="{y + 22}" width="{bar_w * plays / top:.1f}" height="4" rx="2" fill="{RED}"/>'
        )
        out.append(f'<text class="m" x="{W - 4}" y="{y + 28}" text-anchor="end" font-size="11">{plays:,} plays</text>')
    if not items:
        out.append(f'<text class="m" x="4" y="60" font-size="12">No scrobbles in this period</text>')
    out.append("</svg>")
    return "".join(out)


# --- zwarta karta (30 dni) na dol profilu: artysci po lewej, utwory po prawej ---


def _small(url):
    # do zwartej karty wystarcza miniatury 56px (mniejszy SVG)
    return url.replace("/250x250-", "/56x56-") if url else url


def render_compact(period="1month"):
    def load():
        arts = _lastfm("user.gettopartists", period)["topartists"]["artist"]
        trks = _lastfm("user.gettoptracks", period)["toptracks"]["track"]
        a = []
        for x in arts:
            hit = _deezer("search/artist", x["name"])
            a.append((x["name"], int(x["playcount"]), _data_uri(_small(hit and hit.get("picture_medium")))))
        t = []
        for x in trks:
            artist, title = x["artist"]["name"], x["name"]
            clean = re.sub(r"\s*[\(\[].*?[\)\]]|\s+-\s+.*$", "", title).strip() or title
            hit = _deezer("search", f"{artist} {clean}")
            cover = hit and (hit.get("album") or {}).get("cover_medium")
            t.append((clean, artist, int(x["playcount"]), _data_uri(_small(cover))))
        return a, t

    arts, trks = _cached("compact", period, load)
    W, H = 860, 168
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', STYLE]
    out.append('<text class="m" x="4" y="12" font-size="10" letter-spacing="1">TOP ARTISTS</text>')
    out.append('<text class="m" x="444" y="12" font-size="10" letter-spacing="1">TOP TRACKS</text>')
    out.append(
        f'<text class="m" x="{W - 4}" y="12" text-anchor="end" font-size="10">{PERIODS[period]} · last.fm</text>'
    )
    col = 84
    for i, (name, plays, img) in enumerate(arts[:5]):
        cx, cy, r = 4 + col * i + col / 2, 52, 24
        out.append(f'<clipPath id="c{i}"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>')
        out.append(
            f'<image href="{img}" x="{cx - r}" y="{cy - r}" width="{2 * r}" height="{2 * r}" '
            f'clip-path="url(#c{i})" preserveAspectRatio="xMidYMid slice"/>'
            if img else f'<circle class="ph" cx="{cx}" cy="{cy}" r="{r}"/>'
        )
        out.append(
            f'<text x="{cx}" y="{cy + r + 17}" text-anchor="middle" font-size="10.5" font-weight="700">'
            f"{escape(cut(name, 12))}</text>"
        )
        out.append(f'<text class="m" x="{cx}" y="{cy + r + 31}" text-anchor="middle" font-size="9.5">{plays:,} plays</text>')
    for i, (title, artist, plays, img) in enumerate(trks[:5]):
        y = 22 + i * 28
        out.append(f'<clipPath id="t{i}"><rect x="444" y="{y}" width="22" height="22" rx="4"/></clipPath>')
        out.append(
            f'<image href="{img}" x="444" y="{y}" width="22" height="22" clip-path="url(#t{i})" '
            f'preserveAspectRatio="xMidYMid slice"/>'
            if img else f'<rect class="ph" x="444" y="{y}" width="22" height="22" rx="4"/>'
        )
        out.append(
            f'<text x="476" y="{y + 15}" font-size="11"><tspan font-weight="700">{escape(cut(title, 26))}</tspan>'
            f'<tspan class="m"> · {escape(cut(artist, 18))}</tspan></text>'
        )
        out.append(f'<text class="m" x="{W - 4}" y="{y + 15}" text-anchor="end" font-size="10">{plays:,} plays</text>')
    if not arts and not trks:
        out.append('<text class="m" x="4" y="60" font-size="11">No scrobbles in this period</text>')
    out.append("</svg>")
    return "".join(out)
