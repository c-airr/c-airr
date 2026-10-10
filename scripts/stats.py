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
.m{{fill:#59636e}}
@media (prefers-color-scheme:dark){{
  text{{fill:#e6edf3}}
  .m{{fill:#9198a1}}
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
            nodes{ stargazerCount languages(first:10, orderBy:{field:SIZE,direction:DESC}){
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
    dates = sorted(days)
    longest = run = 0
    for d in dates:
        run = run + 1 if days[d] else 0
        longest = max(longest, run)
    # biezacy streak: dzisiaj moze jeszcze byc 0, wtedy liczymy od wczoraj
    cur, i = 0, len(dates) - 1
    if i >= 0 and days[dates[i]] == 0:
        i -= 1
    while i >= 0 and days[dates[i]]:
        cur += 1
        i -= 1
    return cur, longest


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


def render(user, days, commits):
    repos = user["repositories"]
    cur, best = streaks(days)
    langs = languages(repos["nodes"])

    W, H, PAD = 860, 176, 4
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f"<style>{STYLE}</style>",
    ]

    # liczby jak w GitHub Insights: duza wartosc, pod nia podpis
    tiles = [
        (f"{commits:,}", "commits"),
        (str(repos["totalCount"]), "repositories"),
        (str(cur), "day streak"),
        (str(best), "longest streak"),
    ]
    colw = W / len(tiles)
    for i, (val, label) in enumerate(tiles):
        cx = colw * i + colw / 2
        out.append(f'<text x="{cx:.0f}" y="46" text-anchor="middle" font-size="28" font-weight="700">{val}</text>')
        out.append(f'<text class="m" x="{cx:.0f}" y="70" text-anchor="middle" font-size="12">{label}</text>')

    # jezyki: pasek jak na stronie repo + legenda z kropkami
    rest = 1 - sum(s for _, s, _ in langs)
    if rest > 0.005:
        langs = langs + [("Other", rest, DIM)]
    out.append(f'<text x="{PAD}" y="118" font-size="13" font-weight="600">Languages</text>')
    bar_w = W - 2 * PAD
    out.append(f'<clipPath id="bar"><rect x="{PAD}" y="130" width="{bar_w}" height="8" rx="4"/></clipPath><g clip-path="url(#bar)">')
    x = PAD
    for _, share, color in langs:
        w = share * bar_w
        out.append(f'<rect x="{x:.1f}" y="130" width="{max(w - 2, 0):.1f}" height="8" fill="{color}"/>')
        x += w
    out.append("</g>")
    x = PAD
    for name, share, color in langs:
        out.append(f'<circle cx="{x + 4}" cy="160" r="4" fill="{color}"/>')
        out.append(
            f'<text x="{x + 14}" y="164" font-size="12"><tspan font-weight="600">{escape(name)}</tspan>'
            f'<tspan class="m"> {share * 100:.1f}%</tspan></text>'
        )
        x += 14 + (len(name) + len(f" {share * 100:.1f}%")) * 7.2 + 22

    # heatmapy i liczby contributions nie ma, bo GitHub pokazuje je pod README
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    svg = render(*fetch())
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print("ok", OUT)
