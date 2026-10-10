"""Generuje animowany naglowek i plansze technologii do assets/.

Uruchamiane recznie po zmianie listy: python scripts/assets.py
Nowa technologia = nowy wpis w STACK, README nie trzeba ruszac.
"""
import os
import random
import re
import urllib.request
from xml.sax.saxutils import escape

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
FONT = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,Menlo,monospace"
SI = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{}.svg"
SKILL = "https://skillicons.dev/icons?i={}"

# kolory jak w Primer (GitHub); jasny motyw przez prefers-color-scheme
STYLE = (
    "<style>.fg{fill:#1f2328}.fgs{stroke:#1f2328}.m{fill:#59636e}.ln{stroke:#d1d9e0}"
    "@media (prefers-color-scheme:dark){.fg{fill:#e6edf3}.fgs{stroke:#e6edf3}"
    ".m{fill:#9198a1}.ln{stroke:#262c36}}</style>"
)

# kategoria -> [(ikona, podpis, kolor)]
# ikona: "si:<slug>"    - simple-icons
#        "skill:<slug>" - skillicons.dev (bierzemy same ksztalty)
#        "arc:<slug>"   - konturowa ikona z Arcticons (CC BY-SA 4.0, Donnnno / Arcticons-Team,
#                         github.com/Arcticons-Team/Arcticons) - tu owoc FL Studio
#        "mono:<XX>"    - monogram, gdy brak sensownego logo (Adobe, Vulkan)
#        "grok"         - rysowane recznie
# kolor "fg" = kolor tekstu (dla marek czarno-bialych)
STACK = [
    ("Engine", [("si:unrealengine", "Unreal Engine", "fg"), ("mono:Vk", "Vulkan", "#ac162c"),
                ("si:blender", "Blender", "#e87d0d")]),
    ("Languages", [("si:cplusplus", "C++", "#00599c"), ("si:go", "Go", "#00add8"),
                   ("si:python", "Python", "#3776ab")]),
    ("Tooling", [("skill:vscode", "VS Code", "#007acc"), ("si:cursor", "Cursor", "fg"),
                 ("si:git", "Git", "#f05032"), ("si:github", "GitHub", "fg"),
                 ("si:perforce", "Perforce P4", "fg"), ("si:discord", "Discord", "#5865f2")]),
    ("AI", [("si:claude", "Claude", "#d97757"), ("grok", "Grok", "fg"),
            ("si:huggingface", "Hugging Face", "#ffb000")]),
    ("Infra", [("si:oracle", "Oracle OCI", "#f80000"), ("si:docker", "Docker", "#2496ed"),
               ("si:tailscale", "Tailscale", "fg"), ("si:cloudflare", "Cloudflare", "#f38020"),
               ("si:caddy", "Caddy", "#1f88c0")]),
    ("Systems", [("si:linux", "Linux", "#e8a800"), ("si:windows", "Windows 10", "#0078d4"),
                 ("si:apple", "macOS", "fg")]),
    ("Video", [("mono:Ps", "Photoshop", "#31a8ff"), ("mono:Pr", "Premiere Pro", "#9999ff"),
               ("mono:Ae", "After Effects", "#9999ff"), ("si:ffmpeg", "FFmpeg", "#2fa83a")]),
    ("Substance 3D", [("mono:Pa", "Painter", "#ff7a45"), ("mono:Dn", "Designer", "#ffb300"),
                      ("mono:St", "Stager", "#4fc3f7")]),
    ("Audio", [("arc:fl-studio-mobile", "FL Studio", "#ff8c00"), ("si:abletonlive", "Ableton Live", "fg")]),
]

# "lekko rysowane": drzenie tylko na ramce i cienkim cieniu-kresce, logo zostaje ostre
ROUGH = "".join(
    f'<filter id="r{i}" x="-10%" y="-10%" width="120%" height="120%">'
    f'<feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="1" seed="{i * 7 + 3}"/>'
    '<feDisplacementMap in="SourceGraphic" scale="2.2" xChannelSelector="R" yChannelSelector="G"/></filter>'
    for i in range(5)
)

# (tekst, klasa koloru, rozmiar)
HEADER = [
    ("Hi, I'm airr_", "fg", 34),
    ("Game dev · Graphics · Systems · Infra · AI · Automation · 3D · Audio · Video editing", "m", 16),
]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "c-airr"})) as r:
        return r.read().decode()


def paint(color, prop="fill", opacity=1):
    """Atrybuty koloru; "fg" idzie przez klase, zeby dzialal jasny/ciemny motyw."""
    op = f' {prop}-opacity="{opacity}"' if opacity != 1 else ""
    if color == "fg":
        return f'class="{"fg" if prop == "fill" else "fgs"}"{op}'
    return f'{prop}="{color}"{op}'


def glyph(spec, x, y, s, attrs):
    """Sam ksztalt logo s x s w (x, y) z podanymi atrybutami wypelnienia/obrysu."""
    kind, _, src = spec.partition(":")
    if kind == "si":
        d = " ".join(re.findall(r' d="([^"]+)"', get(SI.format(src))))
        k = s / 24
        return f'<path {attrs} stroke-width="{1.2 / k:.2f}" transform="translate({x:.1f} {y:.1f}) scale({k:.4f})" d="{d}"/>'
    if kind == "skill":
        raw = get(SKILL.format(src))
        inner = re.search(r'<svg[^>]*viewBox="0 0 256 256"><rect[^>]*/>(.*?)</svg>', raw, re.S).group(1)
        d = " ".join(re.findall(r' d="([^"]+)"', inner))
        k = s / 200  # logo skillicons ma margines ~13%, wiec lekko powiekszamy
        return (
            f'<path {attrs} stroke-width="{1.2 / k:.2f}" '
            f'transform="translate({x - 28 * k:.1f} {y - 28 * k:.1f}) scale({k:.4f})" d="{d}"/>'
        )
    if kind == "arc":
        # Arcticons to same kreski (siatka 48), wiec kolor idzie w obrys
        raw = get(f"https://api.iconify.design/arcticons/{src}.svg")
        d = " ".join(re.findall(r' d="([^"]+)"', raw))
        # ikony Arcticons maja spory margines (ksztalt ok. y 4..44, srodek x ~24),
        # wiec skalujemy do wysokosci ksztaltu, a nie calej siatki 48
        k = s / 40
        tx, ty = x + s / 2 - 24 * k, y - 4 * k
        stroke = attrs.replace("fill=", "stroke=").replace('class="fg"', 'class="fgs"')
        return (
            f'<path {stroke} fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" '
            f'transform="translate({tx:.1f} {ty:.1f}) scale({k:.4f})" d="{d}"/>'
        )
    if kind == "mono":
        return (
            f'<text {attrs} stroke-width="1" x="{x + s / 2:.1f}" y="{y + s / 2 + 1:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="{FONT}" font-size="{s * 0.62:.1f}" font-weight="800">{src}</text>'
        )
    if kind == "grok":
        c, r = s / 2, s * 0.32
        # Grok to same kreski, wiec kolor wypelnienia przenosimy na obrys
        stroke = attrs.replace("fill=", "stroke=").replace('class="fg"', 'class="fgs"')
        return (
            f'<g {stroke} fill="none" '
            f'stroke-width="2.4" stroke-linecap="round"><circle cx="{x + c:.1f}" cy="{y + c:.1f}" r="{r:.1f}"/>'
            f'<line x1="{x + 3:.1f}" y1="{y + s - 3:.1f}" x2="{x + s - 3:.1f}" y2="{y + 3:.1f}"/></g>'
        )
    raise ValueError(spec)


def icon(spec, color, cx, cy, n, box=64):
    """Ikona w jednolitej oprawie: podbarwiony kafelek w kolorze marki z lekko
    drzaca ramka, logo w kolorze marki i cienka kreska olowka przesunieta w bok."""
    s, rx, off = box / 2, box * 0.28, box * 0.028
    bx, by = cx - box / 2, cy - box / 2
    gx, gy = cx - s / 2, cy - s / 2
    f = n % 5
    pencil = 'class="fgs" fill="none" stroke-opacity="0.3"'
    return (
        f'<rect x="{bx:.1f}" y="{by:.1f}" width="{box}" height="{box}" rx="{rx:.1f}" {paint(color, "fill", 0.12)}/>'
        f'<g filter="url(#r{f})"><rect x="{bx:.1f}" y="{by:.1f}" width="{box}" height="{box}" rx="{rx:.1f}" '
        f'fill="none" {paint(color, "stroke", 0.55)} stroke-width="1.4"/></g>'
        f'<g filter="url(#r{(f + 2) % 5})" transform="translate({off:.1f} {off:.1f})">'
        f"{glyph(spec, gx, gy, s, pencil)}</g>"
        + glyph(spec, gx, gy, s, paint(color))
    )


def header():
    """Pisanie znak po znaku. textLength wymusza stala szerokosc znaku,
    wiec odsloniecie i kursor zgadzaja sie niezaleznie od czcionki."""
    W, H = 860, 110
    char_dt = 0.06
    parts, t = [], 0.3
    for i, (txt, cls, size) in enumerate(HEADER):
        cw = size * 0.6
        n = len(txt)
        y = 50 + i * 40
        width = n * cw
        x0 = (W - width) / 2  # wysrodkowane, bo README jest wysrodkowane
        steps = ";".join(f"{k * cw:.1f}" for k in range(n + 1))
        times = ";".join(f"{k / n:.4f}" for k in range(n + 1))
        dur = n * char_dt
        parts.append(
            f'<clipPath id="c{i}"><rect x="{x0:.1f}" y="{y - size}" height="{size * 1.4}" width="0">'
            f'<animate attributeName="width" begin="{t:.2f}s" dur="{dur:.2f}s" values="{steps}" '
            f'keyTimes="{times}" calcMode="discrete" fill="freeze"/></rect></clipPath>'
            f'<text class="{cls}" clip-path="url(#c{i})" x="{x0:.1f}" y="{y}" textLength="{width:.1f}" '
            f'lengthAdjust="spacing" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{700 if i == 0 else 400}" xml:space="preserve">{escape(txt)}</text>'
        )
        # kursor (cienka kreska) jedzie za tekstem; po ostatniej linii zostaje i miga
        last = i == len(HEADER) - 1
        xs = ";".join(f"{x0 + k * cw + 2:.1f}" for k in range(n + 1))
        blink = (
            f'<animate attributeName="opacity" begin="{t + dur:.2f}s" dur="1s" values="1;0" '
            'calcMode="discrete" repeatCount="indefinite"/>'
            if last else
            f'<set attributeName="opacity" to="0" begin="{t + dur + 0.25:.2f}s"/>'
        )
        parts.append(
            f'<rect class="fg" x="{x0 + 2:.1f}" y="{y - size + 2}" width="3" height="{size + 4}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{max(t - 0.25, 0):.2f}s"/>'
            f'<animate attributeName="x" begin="{t:.2f}s" dur="{dur:.2f}s" values="{xs}" '
            f'keyTimes="{times}" calcMode="discrete" fill="freeze"/>{blink}</rect>'
        )
        t += dur + 0.35
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        + STYLE + "".join(parts) + "</svg>"
    )


def technologies():
    """Luzna plansza jak plaster miodu: rzedy na przemian po 7 i 6, kazdy
    wysrodkowany; kafelki lekko przekrzywione, przesuniete i minimalnie innej
    wielkosci. Bez animacji. Ziarno stale, wiec uklad nie skacze miedzy buildami.
    Kolejnosc wg STACK (kategorie tylko porzadkuja liste, nie sa wyswietlane)."""
    rng = random.Random(7)
    items = [it for _, group in STACK for it in group]
    W, wide, box, row_h = 860, 7, 86, 138
    step = W / wide
    rows, i = [], 0
    while i < len(items):
        n_row = wide if len(rows) % 2 == 0 else wide - 1
        rows.append(items[i:i + n_row])
        i += n_row
    H = len(rows) * row_h + 20
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        STYLE, f"<defs>{ROUGH}</defs>",
    ]
    n = 0
    for r, row in enumerate(rows):
        x_off = (W - step * len(row)) / 2
        for c, (spec, name, color) in enumerate(row):
            cx = x_off + step * c + step / 2 + rng.uniform(-9, 9)
            cy = 20 + r * row_h + box / 2 + rng.uniform(-7, 7)
            tilt = rng.uniform(-3.5, 3.5)
            sc = rng.uniform(0.94, 1.06)
            out.append(
                f'<g transform="translate({cx:.1f} {cy:.1f}) rotate({tilt:.1f}) scale({sc:.3f}) '
                f'translate({-cx:.1f} {-cy:.1f})">'
                + icon(spec, color, cx, cy, n, box)
                + f'<text class="m" x="{cx:.1f}" y="{cy + box / 2 + 20:.1f}" text-anchor="middle" '
                f'font-family="{FONT}" font-size="10.5">{escape(name)}</text></g>'
            )
            n += 1
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    for name, svg in (("technologies", technologies()), ("header", header())):
        with open(os.path.join(ASSETS, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
        print(name, "ok")
