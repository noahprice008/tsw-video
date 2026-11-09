// Turns a video spec (JSON) into a finished vertical MP4.
// Steps: complete the spec (app scene + ending) -> narration -> frames per scene -> join -> music + voice mix.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FPS = 30;
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

  // 2. stock clips (story scenes); without a clip the scene falls back to the plain background
  for (let i = 0; i < spec.scenes.length; i++) {
    const sc = spec.scenes[i];
    if (sc.type !== "stock") continue;
    if (sc.clip_url) {
      try { sc._clip = path.join(workDir, `clip_${i}.mp4`); await download(sc.clip_url, sc._clip); }
      catch (e) { log(`clip ${i}: ${e.message}`); sc._clip = null; }
    }
    if (!sc._clip && sc.clip_file) sc._clip = sc.clip_file;
    if (!sc._clip) sc.type = "point";
  }

  // 3. frames -> one encoded file per scene
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
    await page.goto("file://" + path.join(HERE, "template.html"));
    await page.evaluate((s) => window.setSpec(s), spec);
    // cover image (thumbnail) + the same card as the first frames, so platforms that use frame 0 show it
    await page.evaluate(() => window.renderCover());
    const coverJpg = await page.screenshot({ type: "jpeg", quality: 90 });
    const coverPng = await page.screenshot({ type: "png" }); // opaque, for a first scene drawn over a stock clip
    await fs.writeFile(outFile.replace(/\.mp4$/, "-cover.jpg"), coverJpg);
    let T0 = 0;
    for (let i = 0; i < spec.scenes.length; i++) {
      const sc = spec.scenes[i];
      const n = Math.round(sc.dur * FPS);
      const tmp = path.join(workDir, `part_${i}.tmp.mp4`);
      const stock = sc.type === "stock";
      const args = stock
        ? ["-loglevel", "error", "-y", "-stream_loop", "-1", "-i", sc._clip, "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-",
           "-filter_complex", `[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=${FPS},trim=duration=${(n / FPS).toFixed(3)},setpts=PTS-STARTPTS[bg];[bg][1:v]overlay=shortest=1,format=yuv420p[v]`,
           "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", String(FPS), "-f", "mp4", tmp]
        : ["-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", String(FPS), "-f", "mp4", tmp];
      const ff = spawn("ffmpeg", args, { stdio: ["pipe", "ignore", "pipe"] });
      let ferr = ""; ff.stderr.on("data", (d) => (ferr += d));
      const done = new Promise((r) => ff.on("close", r));
      for (let f = 0; f < n; f++) {
        const t = f / FPS;
        let buf;
        if (i === 0 && f < COVER_FRAMES) buf = stock ? coverPng : coverJpg;
        else {
          await page.evaluate(([i, t, T]) => window.render(i, t, T), [i, t, T0 + t]);
          buf = stock ? await page.screenshot({ type: "png", omitBackground: true }) : await page.screenshot({ type: "jpeg", quality: 92 });
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
  await run(PY, [path.join(HERE, "audio.py"), workDir, String(spec.seed)]);
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "mix.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-ar", "48000", path.join(workDir, "mix14.wav")]);
  const tmpOut = outFile.replace(/\.mp4$/, ".tmp.mp4");
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "video_only.mp4"), "-i", path.join(workDir, "mix14.wav"),
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", "-f", "mp4", tmpOut]);
  await fs.rename(tmpOut, outFile);
  const duration = spec.scenes.reduce((a, s) => a + s.dur, 0);
  return { file: outFile, cover: outFile.replace(/\.mp4$/, "-cover.jpg"), duration: Math.round(duration * 10) / 10, cta: spec.cta, scenes: spec.scenes.length };
}
