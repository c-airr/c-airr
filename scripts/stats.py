"""Generuje assets/stats.svg (karta w stylu GitHuba) z danych GitHub GraphQL.

Uruchamiane przez .github/workflows/stats.yml raz dziennie.
Token: STATS_TOKEN (PAT, widzi tez prywatne repo) albo GITHUB_TOKEN.
"""
import datetime as dt
import json
import os
import urllib.request
from xml.sax.saxutils import escape

LOGIN = os.environ.get("GH_LOGIN", "c-airr")
TOKEN = os.environ["GH_TOKEN"]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "stats.svg")

FONT = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,Menlo,monospace"
DIM = "#7d8590"

# kolory jak w Primer (GitHub); jasny motyw przez prefers-color-scheme
STYLE = f"""
text{{font-family:{FONT};fill:#1f2328}}
.m{{fill:#59636e}}.ln{{stroke:#d1d9e0}}.trk{{stroke:#eff2f5}}.bgc{{fill:#ffffff}}
@keyframes ring{{to{{stroke-dashoffset:0}}}}
@media (prefers-color-scheme:dark){{
  text{{fill:#e6edf3}}
  .m{{fill:#9198a1}}.ln{{stroke:#262c36}}.trk{{stroke:#151b23}}.bgc{{fill:#0d1117}}
}}"""


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": LOGIN},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if body.get("errors"):
        raise SystemExit(json.dumps(body["errors"], indent=2))
    return body["data"]


def fetch():
    user = gql(
        """query($login:String!){ user(login:$login){
          name login createdAt
          repositories(ownerAffiliations:OWNER, isFork:false, first:100){
            totalCount
            nodes{ isPrivate stargazerCount languages(first:10, orderBy:{field:SIZE,direction:DESC}){
              edges{ size node{ name color } } } } } } }""",
        {"login": LOGIN},
    )["user"]

    # kalendarz rok po roku, od zalozenia konta
    start_year = int(user["createdAt"][:4])
    today = dt.date.today()
    days, commits = {}, 0
    for year in range(start_year, today.year + 1):
        frm = dt.datetime(year, 1, 1).isoformat() + "Z"
        to = dt.datetime(year, 12, 31, 23, 59, 59).isoformat() + "Z"
        cc = gql(
            """query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
              contributionsCollection(from:$from, to:$to){
                totalCommitContributions restrictedContributionsCount
                contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }""",
            {"login": LOGIN, "from": frm, "to": to},
        )["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]
        for w in cc["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                # kalendarz biezacego roku zawiera tez przyszle dni z zerami
                if d["date"] <= today.isoformat():
                    days[d["date"]] = d["contributionCount"]
    return user, days, commits


def streaks(days):
    """Zwraca (dlugosc, start, koniec) dla biezacego i najdluzszego streaka."""
    dates = sorted(days)
    best = (0, None, None)
    run, start = 0, None
    for d in dates:
        if days[d]:
            run, start = run + 1, start if run else d
            if run > best[0]:
                best = (run, start, d)
        else:
            run = 0
    # biezacy streak: dzisiaj moze jeszcze byc 0, wtedy liczymy od wczoraj
    cur, i = 0, len(dates) - 1
    if i >= 0 and days[dates[i]] == 0:
        i -= 1
    end = dates[i] if i >= 0 else None
    while i >= 0 and days[dates[i]]:
        cur += 1
        i -= 1
    cur_range = (cur, dates[i + 1], end) if cur else (0, None, None)
    return cur_range, best


def fmt(iso, with_year=False):
    d = dt.date.fromisoformat(iso)
    s = f"{d:%b} {d.day}"
    return f"{s}, {d.year}" if with_year or d.year != dt.date.today().year else s


def span(start, end):
    if not start:
        return "—"
    return fmt(start) if start == end else f"{fmt(start)} – {fmt(end)}"


def languages(repos):
    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or DIM
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:5]
    return [(n, s / total, colors[n]) for n, s in top]


FLAME = (  # Primer Octicons flame-16 (MIT)
    "M9.533.753V.752c.217 2.385 1.463 3.626 2.653 4.81C13.37 6.74 14.498 7.863 14.498 10c0 3.5-3 6-6.5 6S1.5 "
    "13.512 1.5 10c0-1.298.536-2.56 1.425-3.286.376-.308.862 0 1.035.454C4.46 8.487 5.581 8.419 6 8c.282-.282"
    ".341-.811-.003-1.5C4.34 3.187 7.035.75 8.77.146c.39-.137.726.194.763.607ZM7.998 14.5c2.832 0 5-1.98 5-4.5 "
    "0-1.463-.68-2.19-1.879-3.383l-.036-.037c-1.013-1.008-2.3-2.29-2.834-4.434-.322.256-.63.579-.864.953-.432"
    ".696-.621 1.58-.046 2.73.473.947.67 2.284-.278 3.232-.61.61-1.545.84-2.403.633a2.79 2.79 0 0 1-1.436-.874"
    "A3.198 3.198 0 0 0 3 10c0 2.53 2.164 4.5 4.998 4.5Z"
)
ORANGE = "#fb8f44"


def render(user, days, commits):
    repos = user["repositories"]
    (cur, cur_s, cur_e), (best, best_s, best_e) = streaks(days)
    total = sum(days.values())
    first = min((d for d, c in days.items() if c), default=None)

    W, H, PAD = 860, 250, 4
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f"<style>{STYLE}</style>",
    ]

    nodes = repos["nodes"]
    pub = sum(1 for r in nodes if not r["isPrivate"])
    priv = len(nodes) - pub

    # 4 kolumny: contributions | streak z pierscieniem i plomieniem | longest | repozytoria
    col = W / 4
    for i in (1, 2, 3):
        out.append(f'<line class="ln" x1="{col * i:.0f}" y1="22" x2="{col * i:.0f}" y2="132" stroke-width="1"/>')

    def side(cx, value, label, sub):
        out.append(f'<text x="{cx:.0f}" y="70" text-anchor="middle" font-size="32" font-weight="700">{value}</text>')
        out.append(f'<text x="{cx:.0f}" y="100" text-anchor="middle" font-size="13">{label}</text>')
        out.append(f'<text class="m" x="{cx:.0f}" y="122" text-anchor="middle" font-size="11">{escape(sub)}</text>')

    side(col / 2, f"{total:,}", "Total contributions",
         f"{commits:,} commits · since {dt.date.fromisoformat(first):%b %Y}" if first else "")
    side(col * 2.5, str(best), "Longest streak", span(best_s, best_e))
    side(col * 3.5, str(len(nodes)), "Repositories", f"{pub} public · {priv} private")

    # pierscien rysuje sie przy wczytaniu; przerwa u gory na plomien
    cx, cy, r = col * 1.5, 62, 40
    circ = 2 * 3.14159 * r
    out.append(f'<circle class="trk" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke-width="5"/>')
    out.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ORANGE}" stroke-width="5" stroke-linecap="round" '
        f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 {cx} {cy})" '
        f'style="animation:ring 1.2s .2s cubic-bezier(.4,0,.2,1) forwards"/>'
    )
    out.append(f'<circle class="bgc" cx="{cx}" cy="{cy - r}" r="13"/>')
    out.append(f'<path fill="{ORANGE}" transform="translate({cx - 10} {cy - r - 11}) scale(1.25)" d="{FLAME}"/>')
    out.append(f'<text x="{cx}" y="{cy + 11}" text-anchor="middle" font-size="32" font-weight="700">{cur}</text>')
    out.append(f'<text x="{cx}" y="{cy + 58}" text-anchor="middle" font-size="13" font-weight="700" style="fill:{ORANGE}">Current streak</text>')
    out.append(f'<text class="m" x="{cx}" y="{cy + 80}" text-anchor="middle" font-size="11">{escape(span(cur_s, cur_e))}</text>')

    # jezyki: jeden pasek ze wszystkich repo
    y0 = 170
    out.append(f'<text x="{PAD}" y="{y0 + 12}" font-size="13" font-weight="600">Languages</text>')
    out.append(
        f'<text class="m" x="{W - PAD}" y="{y0 + 12}" text-anchor="end" font-size="11">'
        f"all repositories</text>"
    )
    y = lang_block(out, y0 + 24, nodes, "all", W, PAD)
    H = y - 6
    out[0] = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    out.append("</svg>")
    return "\n".join(out)


def lang_block(out, y, group, key, W, PAD):
    """Pasek jezykow jak na stronie repo + legenda z kropkami. Zwraca y pod blokiem."""
    ls = languages(group)
    rest = 1 - sum(s for _, s, _ in ls)
    if rest > 0.005:
        ls = ls + [("Other", rest, DIM)]
    bar_w = W - 2 * PAD
    out.append(
        f'<clipPath id="bar-{key}"><rect x="{PAD}" y="{y}" width="{bar_w}" height="8" rx="4"/></clipPath>'
        f'<g clip-path="url(#bar-{key})">'
    )
    x = PAD
    for _, share, color in ls:
        w = share * bar_w
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 0):.1f}" height="8" fill="{color}"/>')
        x += w
    out.append("</g>")
    x = PAD
    for name, share, color in ls:
        out.append(f'<circle cx="{x + 4}" cy="{y + 30}" r="4" fill="{color}"/>')
        out.append(
            f'<text x="{x + 14}" y="{y + 34}" font-size="12"><tspan font-weight="600">{escape(name)}</tspan>'
            f'<tspan class="m"> {share * 100:.1f}%</tspan></text>'
        )
        x += 14 + (len(name) + len(f" {share * 100:.1f}%")) * 7.2 + 22
    return y + 50


def render_langs(user, scope):
    """Mala karta z samymi jezykami: scope = "public" albo "private"."""
    want_private = scope == "private"
    nodes = [r for r in user["repositories"]["nodes"] if r["isPrivate"] == want_private]
    W, PAD = 860, 4
    out = ["", f"<style>{STYLE}</style>"]
    out.append(f'<text x="{PAD}" y="16" font-size="12" font-weight="600">Only {scope}</text>')
    out.append(
        f'<text class="m" x="{W - PAD}" y="16" text-anchor="end" font-size="11">{len(nodes)} repositories</text>'
    )
    y = lang_block(out, 28, nodes, scope, W, PAD)
    H = y - 6
    out[0] = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    data = fetch()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(*data))
    for scope in ("public", "private"):
        with open(OUT.replace("stats.svg", f"langs-{scope}.svg"), "w", encoding="utf-8") as f:
            f.write(render_langs(data[0], scope))
    print("ok", OUT)
