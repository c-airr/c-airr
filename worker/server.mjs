// Serwer HTTP w Node opakowujacy handler z src/index.js (ten sam kod co dla
// Cloudflare Workers). Na oraclearm stoi za Caddy: stats.discordbothosting.pl/discord
import http from "node:http";
import worker from "./src/index.js";

const PORT = Number(process.env.PORT || 8790);

http
  .createServer(async (req, res) => {
    try {
      const r = await worker.fetch(new Request(`http://localhost${req.url}`));
      res.writeHead(r.status, Object.fromEntries(r.headers));
      res.end(await r.text());
    } catch (e) {
      res.writeHead(500, { "content-type": "text/plain" });
      res.end("error");
      console.error(e);
    }
  })
  .listen(PORT, () => console.log(`discord-presence on :${PORT}`));
