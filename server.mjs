// Small private web service used by n8n.
//   POST /render   body: video spec JSON      -> { id, duration, cta, file: "/files/<id>.mp4" }
//   GET  /files/<id>.mp4                        -> the video
//   GET  /files/<id>-cover.jpg                  -> its cover image (thumbnail)
//   GET  /health                                -> ok
// Every request needs the header  X-Render-Key: <RENDER_KEY>  (except /health).
import http from "node:http";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { render } from "./render.mjs";
import { renderFreeApps } from "./freeapps.mjs";

const PORT = Number(process.env.PORT || 8090);
const KEY = process.env.RENDER_KEY || "";
const OUT = process.env.OUT_DIR || "/data/videos";
const WORK = process.env.WORK_DIR || "/data/work";
const KEEP_DAYS = Number(process.env.KEEP_DAYS || 7);
await fsp.mkdir(OUT, { recursive: true });
await fsp.mkdir(WORK, { recursive: true });

let busy = Promise.resolve(); // one render at a time keeps the server light
const send = (res, code, body, type = "application/json") => {
  res.writeHead(code, { "Content-Type": type });
  res.end(type === "application/json" ? JSON.stringify(body) : body);
};

async function cleanup() {
  const cutoff = Date.now() - KEEP_DAYS * 864e5;
  for (const dir of [OUT, WORK]) {
    for (const f of await fsp.readdir(dir)) {
      const p = path.join(dir, f);
      const st = await fsp.stat(p).catch(() => null);
      if (st && st.mtimeMs < cutoff) await fsp.rm(p, { recursive: true, force: true });
    }
  }
}

http.createServer(async (req, res) => {
  try {
    if (req.url === "/health") return send(res, 200, { ok: true });
    if (!KEY || req.headers["x-render-key"] !== KEY) return send(res, 401, { error: "unauthorised" });

    if (req.method === "GET" && req.url.startsWith("/files/")) {
      const name = path.basename(req.url.split("?")[0]);
      const file = path.join(OUT, name);
      const m = /^[\w-]+\.(mp4|jpg)$/.exec(name);
      if (!m || !fs.existsSync(file)) return send(res, 404, { error: "not found" });
      res.writeHead(200, { "Content-Type": m[1] === "mp4" ? "video/mp4" : "image/jpeg", "Content-Length": fs.statSync(file).size });
      return fs.createReadStream(file).pipe(res);
    }

    if (req.method === "POST" && req.url === "/render") {
      let body = "";
      for await (const c of req) body += c;
      const spec = JSON.parse(body || "{}");
      if (!Array.isArray(spec.scenes) || !spec.scenes.length) return send(res, 400, { error: "spec.scenes is required" });
      const id = new Date().toISOString().slice(0, 10) + "-" + crypto.randomBytes(4).toString("hex");
      const job = busy.then(async () => {
        const workDir = path.join(WORK, id);
        const started = Date.now();
        const r = await (spec.format === "freeapps" ? renderFreeApps : render)(spec, { workDir, outFile: path.join(OUT, `${id}.mp4`), log: (m) => console.log(id, m) });
        await fsp.rm(workDir, { recursive: true, force: true });
        console.log(id, `done in ${Math.round((Date.now() - started) / 1000)}s`);
        return r;
      });
      busy = job.catch(() => {});
      const r = await job;
      cleanup().catch(() => {});
      return send(res, 200, { id, duration: r.duration, cta: r.cta, scenes: r.scenes, warnings: r.warnings, file: `/files/${id}.mp4`, cover: `/files/${id}-cover.jpg` });
    }
    send(res, 404, { error: "not found" });
  } catch (e) {
    console.error(e);
    send(res, 500, { error: String(e.message || e) });
  }
}).listen(PORT, () => console.log(`tsw-video renderer on :${PORT}`));
