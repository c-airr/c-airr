// Karta "co teraz robie na Discordzie" jako SVG do README.
// Dane z Lanyard (api.lanyard.rest) - wymaga bycia na serwerze discord.gg/lanyard.
// Styl jak reszta profilu: monospace, kolory Primer, jasny/ciemny motyw.

const USER_ID = "894957673777356840";
const FONT = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,Menlo,monospace";
const W = 860;
const H = 96;

const STATUS = {
  online: ["#3ba55d", "online"],
  idle: ["#faa81a", "idle"],
  dnd: ["#ed4245", "do not disturb"],
  offline: ["#80848e", "offline"],
};
const VERB = { 0: "Playing", 1: "Streaming", 2: "Listening to", 3: "Watching", 5: "Competing in" };

const STYLE = `<style>
.fg{fill:#1f2328}.m{fill:#59636e}.ring{stroke:#ffffff}.ph{fill:#eff2f5}.trk{fill:#d1d9e0}
@media (prefers-color-scheme:dark){.fg{fill:#e6edf3}.m{fill:#9198a1}.ring{stroke:#0d1117}.ph{fill:#151b23}.trk{fill:#30363d}}
</style>`;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const cut = (s, n) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");

// GitHub przepuszcza obrazki przez proxy (camo), ktore nie laduje zewnetrznych
// obrazkow wewnatrz SVG - dlatego avatar i okladki wklejamy jako data: URI
async function dataUri(url) {
  if (!url) return null;
  try {
    const r = await fetch(url, { cf: { cacheTtl: 3600 } });
    if (!r.ok) return null;
    const buf = new Uint8Array(await r.arrayBuffer());
    let bin = "";
    for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    return `data:${r.headers.get("content-type") || "image/png"};base64,${btoa(bin)}`;
  } catch {
    return null;
  }
}

function assetUrl(act) {
  const img = act.assets?.large_image;
  if (!img) return null;
  if (img.startsWith("mp:")) return `https://media.discordapp.net/${img.slice(3)}`;
  if (img.startsWith("spotify:")) return `https://i.scdn.co/image/${img.slice(8)}`;
  if (act.application_id) return `https://cdn.discordapp.com/app-assets/${act.application_id}/${img}.png?size=128`;
  return null;
}

function elapsed(start) {
  if (!start) return "";
  const min = Math.floor((Date.now() - start) / 60000);
  if (min < 1) return "just started";
  const h = Math.floor(min / 60);
  return h ? `${h}h ${min % 60}m` : `${min}m`;
}

const MAX_ACTS = 2;

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

// Pasek postepu utworu + czas "0:26 / 3:11". Obrazek powstaje w chwili wejscia,
// a dalej pasek i sekundy leca same (SMIL), az do konca utworu.
function progress(a, x1, x2) {
  const total = Math.max(1, Math.round((a.end - a.start) / 1000));
  const now = Math.min(total, Math.max(0, Math.round((Date.now() - a.start) / 1000)));
  const left = total - now;
  const w = x2 - x1;
  const w0 = (w * now) / total;
  const out = [
    `<rect class="trk" x="${x1}" y="87" width="${w}" height="3" rx="1.5"/>`,
    `<rect x="${x1}" y="87" width="${w0.toFixed(1)}" height="3" rx="1.5" fill="#1db954">` +
      (left ? `<animate attributeName="width" from="${w0.toFixed(1)}" to="${w}" dur="${left}s" fill="freeze"/>` : "") +
      `</rect>`,
  ];
  // licznik sekund: osobny tekst na kazda sekunde, pokazywany przez <set> (max 15 min)
  const tag = (t, extra) =>
    `<text class="m" x="${x2}" y="79" text-anchor="end" font-family="${FONT}" font-size="11"${extra}>${mmss(t)} / ${mmss(total)}</text>`;
  if (!left || left > 900) return out.concat(tag(now, "")).join("");
  for (let k = 0; k <= left; k++) {
    const last = k === left;
    out.push(
      tag(now + k, k ? ' visibility="hidden"' : "").replace(
        "</text>",
        (k ? `<set attributeName="visibility" to="visible" begin="${k}s"${last ? "" : ' dur="1s"'}/>` : "") +
          (last ? "" : `<set attributeName="visibility" to="hidden" begin="${k + 1}s"/>`) +
          "</text>"
      )
    );
  }
  return out.join("");
}

function describe(d) {
  const out = [];
  // Spotify ma osobne pole z ladniejszymi danymi; jego wpis w activities pomijamy
  if (d.listening_to_spotify && d.spotify) {
    out.push({
      line: `Listening to ${d.spotify.song}`,
      sub: `by ${d.spotify.artist}`,
      img: d.spotify.album_art_url,
      name: "Spotify",
      start: d.spotify.timestamps?.start,
      end: d.spotify.timestamps?.end,
    });
  }
  for (const act of d.activities || []) {
    if (act.type === 4 || (out.length && act.name === "Spotify" && act.type === 2)) continue;
    out.push({
      line: `${VERB[act.type] || "Playing"} ${act.name}`,
      sub: [act.details, act.state, elapsed(act.timestamps?.start)].filter(Boolean).join(" · "),
      img: assetUrl(act),
      name: act.name,
    });
  }
  return out.slice(0, MAX_ACTS);
}

async function render(d) {
  const u = d?.discord_user;
  const [dot, statusText] = STATUS[d?.discord_status] || STATUS.offline;
  const name = u?.global_name || u?.username || "Discord";
  const custom = (d?.activities || []).find((a) => a.type === 4)?.state;
  const acts = d ? describe(d) : [];

  const [avatar, ...arts] = await Promise.all([
    dataUri(u?.avatar ? `https://cdn.discordapp.com/avatars/${u.id}/${u.avatar}.png?size=128` : null),
    ...acts.map((a) => dataUri(a.img)),
  ]);

  const tx = 92; // poczatek tekstu za avatarem
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`,
    STYLE,
    `<clipPath id="av"><circle cx="40" cy="48" r="32"/></clipPath>`,
    avatar
      ? `<image href="${avatar}" x="8" y="16" width="64" height="64" clip-path="url(#av)"/>`
      : `<circle class="ph" cx="40" cy="48" r="32"/>`,
    `<circle class="ring" cx="64" cy="72" r="9" fill="${dot}" stroke-width="4"/>`,
    `<text class="fg" x="${tx}" y="30" font-family="${FONT}" font-size="16" font-weight="700">${esc(cut(name, 24))}` +
      `<tspan class="m" font-size="12" font-weight="400" dx="10">${esc(statusText)}` +
      `${custom && acts.length ? ` · ${esc(cut(custom, 50))}` : ""}</tspan></text>`,
  ];

  if (acts.length) {
    // aktywnosci obok siebie, kazda: miniatura 40x40 + dwie linie tekstu
    const bw = (W - tx) / acts.length;
    acts.forEach((a, i) => {
      const x = tx + i * bw;
      const chars = Math.floor((bw - 64) / 7.8);
      parts.push(`<clipPath id="art${i}"><rect x="${x}" y="44" width="40" height="40" rx="8"/></clipPath>`);
      parts.push(
        arts[i]
          ? `<image href="${arts[i]}" x="${x}" y="44" width="40" height="40" clip-path="url(#art${i})" preserveAspectRatio="xMidYMid slice"/>`
          : `<rect class="ph" x="${x}" y="44" width="40" height="40" rx="8"/>` +
              `<text class="m" x="${x + 20}" y="69" text-anchor="middle" font-family="${FONT}" font-size="16" font-weight="700">` +
              `${esc((a.name.match(/[A-Za-z0-9]/) || ["?"])[0].toUpperCase())}</text>`
      );
      const prog = a.start && a.end ? progress(a, x + 52, x + bw - 16) : "";
      parts.push(
        `<text class="fg" x="${x + 52}" y="60" font-family="${FONT}" font-size="13">${esc(cut(a.line, chars))}</text>`,
        `<text class="m" x="${x + 52}" y="79" font-family="${FONT}" font-size="12">${esc(cut(a.sub, prog ? chars - 8 : chars + 6))}</text>`,
        prog
      );
    });
  } else {
    const idle = d ? custom || "Not doing anything right now" : "Presence unavailable";
    parts.push(`<text class="m" x="${tx}" y="62" font-family="${FONT}" font-size="13">${esc(cut(idle, 90))}</text>`);
  }
  parts.push("</svg>");
  return parts.join("");
}

export default {
  async fetch(request) {
    let data = null;
    try {
      const r = await fetch(`https://api.lanyard.rest/v1/users/${USER_ID}`);
      const j = await r.json();
      if (j.success) data = j.data;
    } catch {}
    return new Response(await render(data), {
      headers: {
        "content-type": "image/svg+xml; charset=utf-8",
        // camo (proxy GitHuba) respektuje no-cache, wiec karta odswieza sie przy kazdym wejsciu
        "cache-control": "no-cache, no-store, must-revalidate, max-age=0",
      },
    });
  },
};

export { render }; // do testow lokalnych
