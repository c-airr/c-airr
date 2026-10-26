"""Karta "top gry": ile czasu spedzone w ktorej grze na Discordzie.

Discord (Lanyard) daje tylko biezaca aktywnosc, bez historii - wiec co minute
odpytujemy Lanyard i dopisujemy czas do liczników w pliku JSON. Ranking
rosnie od momentu uruchomienia serwera.
"""
import json
import os
import threading
import time
import urllib.request
from xml.sax.saxutils import escape

USER_ID = os.environ.get("DISCORD_ID", "894957673777356840")
FILE = os.environ.get("GAMES_FILE", "/data/games.json")
POLL = 60
# aplikacje z presence typu "Playing", ktore nie sa grami
IGNORE = {s.strip().lower() for s in os.environ.get(
    "GAMES_IGNORE", "Visual Studio Code,Cursor,Code,Visual Studio,Claude,Spotify,Premiere Pro,"
    "Adobe Premiere Pro,After Effects,Photoshop,FL Studio,Ableton Live,Blender,Unreal Editor,JetBrains").split(",")}
FONT = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,Menlo,monospace"
STYLE = """<style>
text{font-family:%s;fill:#1f2328}.m{fill:#59636e}.trk{fill:#eff2f5}
@media (prefers-color-scheme:dark){text{fill:#e6edf3}.m{fill:#9198a1}.trk{fill:#151b23}}
</style>""" % FONT

_lock = threading.Lock()


def _load():
    try:
        with open(FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _poll_once():
    req = urllib.request.Request(f"https://api.lanyard.rest/v1/users/{USER_ID}", headers={"User-Agent": "c-airr-profile"})
    with urllib.request.urlopen(req, timeout=10) as r:
        acts = json.load(r)["data"].get("activities", [])
    names = {a["name"] for a in acts if a.get("type") == 0 and a["name"].lower() not in IGNORE}
    if not names:
        return
    with _lock:
        d = _load()
        for n in names:
            d[n] = d.get(n, 0) + POLL
        os.makedirs(os.path.dirname(FILE), exist_ok=True)
        tmp = FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, FILE)


def _loop():
    while True:
        try:
            _poll_once()
        except Exception as e:  # Lanyard chwilowo pada - nastepna proba za minute
            print(f"games poll failed: {e!r}", flush=True)
        time.sleep(POLL)


def start():
    threading.Thread(target=_loop, daemon=True).start()


def _fmt(sec):
    h, m = divmod(sec // 60, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def render(limit=5):
    with _lock:
        d = _load()
    top = sorted(d.items(), key=lambda kv: -kv[1])[:limit]
    W, H = 860, 28 + max(1, len(top)) * 26
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', STYLE,
           '<text x="4" y="16" font-size="13" font-weight="600">Most played</text>',
           f'<text class="m" x="{W - 4}" y="16" text-anchor="end" font-size="11">tracked on discord</text>']
    if not top:
        out.append('<text class="m" x="4" y="46" font-size="11">No games tracked yet</text>')
    mx = top[0][1] if top else 1
    for i, (name, sec) in enumerate(top):
        y = 28 + i * 26
        bar = max(4, int(300 * sec / mx))
        out.append(f'<text x="4" y="{y + 14}" font-size="11" font-weight="700">{escape(name[:28])}</text>')
        out.append(f'<rect class="trk" x="260" y="{y + 5}" width="300" height="10" rx="5"/>')
        out.append(f'<rect x="260" y="{y + 5}" width="{bar}" height="10" rx="5" fill="#5865f2"/>')
        out.append(f'<text class="m" x="{W - 4}" y="{y + 14}" text-anchor="end" font-size="10">{_fmt(sec)}</text>')
    out.append("</svg>")
    return "".join(out)
