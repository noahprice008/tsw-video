// Turns a video spec (JSON) into a finished vertical MP4.
// Steps: complete the spec (app scene + ending) -> narration -> frames per scene -> join -> music + voice mix.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FPS = 30;
// Sharpness: draw each frame at SCALE x resolution, then shrink it to 1080x1920 (supersampling = crisper text and edges).
// SCALE=1 gives the old fast behaviour; set env RENDER_SCALE=1 on the server if rendering ever gets too slow.
const SCALE = Number(process.env.RENDER_SCALE || 2);
const CRF = process.env.RENDER_CRF || "17";
const PRESET = process.env.RENDER_PRESET || "medium";
const COVER_FRAMES = 3; // 0.1 s of the cover card at the very start (Facebook/TikTok use frame 0 as the cover)
const PY = process.env.PYTHON || "python3";

const APP_LINES = [
  ["I use the free Travel Safety Watch app. Official advice, weather, and local news, for wherever you're going.",
   "I use the free Travel Safety Watch app. Official advice, weather and local news, for wherever you're going."],
  ["I check the free Travel Safety Watch app before every trip. Official advice, weather, and local news, in plain English.",
   "I check the free Travel Safety Watch app before every trip. Official advice, weather and local news, in plain English."],
  ["The free Travel Safety Watch app puts official advice, weather, and local news for your destination in one place.",
   "The free Travel Safety Watch app puts official advice, weather and local news for your destination in one place."],
];

function run(cmd, args, { input } = {}) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { stdio: [input ? "pipe" : "ignore", "pipe", "pipe"] });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("close", (code) => (code === 0 ? resolve(out) : reject(new Error(`${cmd} failed (${code}): ${err.slice(-800)}`))));
    if (input) { p.stdin.end(input); }
  });
}

export function completeSpec(spec, now = new Date()) {
  const s = structuredClone(spec);
  const launch = process.env.LAUNCH_DATE || "2026-11-21";
  const today = now.toISOString().slice(0, 10);
  if (!s.cta || s.cta === "auto") s.cta = today >= launch ? "play" : "soon";
  // App Store: set IOS_DATE (YYYY-MM-DD) once the iPhone app is approved; until then it shows as "coming soon".
  const ios = process.env.IOS_DATE;
  if (s.ios === undefined) s.ios = !!ios && today >= ios && s.cta !== "soon";
  s.format = s.format === "quick" ? "quick" : "main";
  s.scenes = (s.scenes || []).filter((sc) => !["app", "outro", "endcard"].includes(sc.type));
  const seed = Number(s.seed ?? Math.floor(Math.random() * 1e6));
  s.seed = seed;
  if (s.format === "main") {
    const [say, caption] = APP_LINES[seed % APP_LINES.length];
    s.scenes.push({ type: "app", say, caption });
    s.scenes.push(s.cta === "soon"
      ? { type: "outro", say: "Coming soon to Google Play and the App Store. Use it free now, at travel safety watch dot com.", caption: "Coming soon to Google Play and the App Store. Use it free now at travelsafetywatch.com", extra: 1.4 }
      : s.ios
        ? { type: "outro", say: "Get it free on Google Play and the App Store. Link in bio.", caption: "Get it free on Google Play and the App Store. Link in bio.", extra: 1.4 }
        : { type: "outro", say: "Get it free on Google Play. App Store coming soon. Link in bio.", caption: "Get it free on Google Play. App Store coming soon. Link in bio.", extra: 1.4 });
  } else {
    s.scenes.push({ type: "endcard", say: "", hold: s.cta === "soon" ? 2.6 : 2.2 });
  }
  return s;
}

// Photo -> 9:16 clip with a slow zoom (alternating in / out and drifting direction) so stills feel alive.
async function kenBurns(img, out, dur, k) {
  const n = Math.max(2, Math.round(dur * FPS)), zin = k % 2 === 0;
  const z = zin ? `min(1+0.0012*on,1.22)` : `max(1.22-0.0012*on,1.0)`;
  const x = ["iw/2-(iw/zoom/2)", "(iw-iw/zoom)*on/" + n, "(iw-iw/zoom)*(1-on/" + n + ")"][k % 3];
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", img, "-vf",
    `scale=1800:3200:force_original_aspect_ratio=increase:flags=lanczos,crop=1800:3200,zoompan=z='${z}':x='${x}':y='ih/2-(ih/zoom/2)':d=${n}:s=1080x1920:fps=${FPS},format=yuv420p`,
    "-frames:v", String(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-an", out]);
  return out;
}

async function download(url, file) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`clip download failed ${r.status}`);
  await fs.writeFile(file, Buffer.from(await r.arrayBuffer()));
}

export async function render(inputSpec, { workDir, outFile, log = () => {} }) {
  const spec = completeSpec(inputSpec);
  await fs.mkdir(workDir, { recursive: true });

  // 1. narration + timing
  const job = { voice: spec.voice || "af_heart", lang: spec.lang || "en-us", speed: spec.speed || 1.08,
    scenes: spec.scenes.map((sc) => ({ say: sc.say || "", caption: sc.caption, hold: sc.hold, extra: sc.extra })) };
  await fs.writeFile(path.join(workDir, "job.json"), JSON.stringify(job));
  await run(PY, [path.join(HERE, "tts.py"), path.join(workDir, "job.json"), workDir]);
  const timed = JSON.parse(await fs.readFile(path.join(workDir, "timed.json"), "utf8"));
  spec.scenes.forEach((sc, i) => { sc.dur = timed.scenes[i].dur; sc.words = timed.scenes[i].words; });
  log(`narration ${timed.scenes.reduce((a, s) => a + s.dur, 0).toFixed(1)}s`);

  // 2. backgrounds: any scene can sit on a real video clip or a photo (spec.bg applies to the first scene and the cover).
  //    bg = { url | file, kind?: "video" | "photo" }; photos get a slow Ken Burns zoom. Legacy stock scenes (clip_url / clip_file) still work.
  const isVideo = (b) => b.kind ? b.kind === "video" : /\.(mp4|mov|webm|m4v)(\?|$)/i.test(b.url || b.file || "");
  for (let i = 0; i < spec.scenes.length; i++) {
    const sc = spec.scenes[i];
    if (["app", "outro", "endcard"].includes(sc.type)) continue;
    const bg = sc.bg || (i === 0 ? spec.bg : null) || (sc.clip_url || sc.clip_file ? { url: sc.clip_url, file: sc.clip_file, kind: "video" } : null);
    if (!bg) { if (sc.type === "stock") sc.type = "point"; continue; }
    try {
      let src = bg.file;
      if (!src && bg.url) { src = path.join(workDir, `bg_${i}${path.extname(new URL(bg.url).pathname) || (isVideo(bg) ? ".mp4" : ".jpg")}`); await download(bg.url, src); }
      if (!src) throw new Error("no file");
      if (isVideo(bg)) sc._clip = src;
      else sc._clip = await kenBurns(src, path.join(workDir, `kb_${i}.mp4`), sc.dur, i + (spec.seed || 0));
    } catch (e) { log(`background ${i}: ${e.message}`); sc._clip = null; if (sc.type === "stock") sc.type = "point"; }
  }
  // cover background (photo or a frame of the video)
  if (spec.bg || spec.cover?.bg_url || spec.cover?.bg_file) {
    try {
      const cb = spec.cover?.bg_url || spec.cover?.bg_file ? { url: spec.cover.bg_url, file: spec.cover.bg_file } : spec.bg;
      let img = cb.file;
      if (!img && cb.url) { img = path.join(workDir, "cover_src" + (isVideo(cb) ? ".mp4" : ".jpg")); await download(cb.url, img); }
      if (img && isVideo({ file: img })) { const f = path.join(workDir, "cover_bg.jpg"); await run("ffmpeg", ["-loglevel", "error", "-y", "-ss", "1", "-i", img, "-frames:v", "1", "-q:v", "2", f]); img = f; }
      if (img) spec.cover = { ...(spec.cover || {}), bg: "file://" + img };
    } catch (e) { log(`cover background: ${e.message}`); }
  }

  // 3. frames -> one encoded file per scene
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: SCALE });
    await page.goto("file://" + path.join(HERE, "template.html"));
    await page.evaluate((s) => window.setSpec(s), spec);
    // Never render (or post) a video with text running off the frame: fail loudly so n8n emails the problem instead.
    const layout = await page.evaluate(() => window.__layoutProblems || []);
    if (layout.length) throw new Error("layout check failed: " + layout.join("; "));
    // cover image (thumbnail) + the same card as the first frames, so platforms that use frame 0 show it
    await page.evaluate(() => window.renderCover());
    const coverJpg = await page.screenshot({ type: "jpeg", quality: 95 });
    const coverPng = await page.screenshot({ type: "png" }); // opaque, for a first scene drawn over a stock clip
    // the thumbnail file stays 1080x1920 (small upload); the frames above are at SCALE x for the video
    await fs.writeFile(outFile.replace(/\.mp4$/, "-cover.jpg"), await page.screenshot({ type: "jpeg", quality: 92, scale: "css" }));
    let T0 = 0;
    for (let i = 0; i < spec.scenes.length; i++) {
      const sc = spec.scenes[i];
      const n = Math.round(sc.dur * FPS);
      const tmp = path.join(workDir, `part_${i}.tmp.mp4`);
      const stock = sc.type === "stock" || !!sc._clip;
      const args = stock
        ? ["-loglevel", "error", "-y", "-stream_loop", "-1", "-i", sc._clip, "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-",
           "-filter_complex", `[0:v]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,fps=${FPS},trim=duration=${(n / FPS).toFixed(3)},setpts=PTS-STARTPTS[bg];[1:v]scale=1080:1920:flags=lanczos[fg];[bg][fg]overlay=shortest=1,format=yuv420p[v]`,
           "-map", "[v]", "-an", "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-pix_fmt", "yuv420p", "-r", String(FPS), "-f", "mp4", tmp]
        : ["-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
           "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-tune", "animation", "-pix_fmt", "yuv420p", "-r", String(FPS), "-f", "mp4", tmp];
      const ff = spawn("ffmpeg", args, { stdio: ["pipe", "ignore", "pipe"] });
      let ferr = ""; ff.stderr.on("data", (d) => (ferr += d));
      const done = new Promise((r) => ff.on("close", r));
      for (let f = 0; f < n; f++) {
        const t = f / FPS;
        let buf;
        if (i === 0 && f < COVER_FRAMES) buf = stock ? coverPng : coverJpg;
        else {
          await page.evaluate(([i, t, T]) => window.render(i, t, T), [i, t, T0 + t]);
          buf = stock ? await page.screenshot({ type: "png", omitBackground: true }) : await page.screenshot({ type: "jpeg", quality: 95 });
        }
        if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
      }
      ff.stdin.end();
      const code = await done;
      if (code !== 0) throw new Error(`scene ${i} encode failed: ${ferr.slice(-600)}`);
      await fs.rename(tmp, path.join(workDir, `part_${i}.mp4`));
      T0 += sc.dur;
      log(`scene ${i + 1}/${spec.scenes.length} ${sc.type}`);
    }
  } finally { await browser.close(); }

  // 4. join, mix, mux
  const list = spec.scenes.map((_, i) => `file '${path.join(workDir, `part_${i}.mp4`)}'`).join("\n");
  await fs.writeFile(path.join(workDir, "list.txt"), list);
  await run("ffmpeg", ["-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", path.join(workDir, "list.txt"), "-c", "copy", path.join(workDir, "video_only.mp4")]);
  await run(PY, [path.join(HERE, "audio.py"), workDir, String(spec.seed), spec.music === "upbeat" ? "upbeat" : "calm"]);
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "mix.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-ar", "48000", path.join(workDir, "mix14.wav")]);
  const tmpOut = outFile.replace(/\.mp4$/, ".tmp.mp4");
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "video_only.mp4"), "-i", path.join(workDir, "mix14.wav"),
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "-f", "mp4", tmpOut]);
  await fs.rename(tmpOut, outFile);
  const duration = spec.scenes.reduce((a, s) => a + s.dur, 0);
  return { file: outFile, cover: outFile.replace(/\.mp4$/, "-cover.jpg"), duration: Math.round(duration * 10) / 10, cta: spec.cta, scenes: spec.scenes.length };
}
