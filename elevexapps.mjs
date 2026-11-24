// ELEVEX Apps videos: intro card, live-app screen captures in a phone frame, outro card, with a voice-over,
// the ELEVEX header (below the platform's top bar), the website link as a footer, music and slick transitions.
// Spec (POST /render with "format": "elevexapps"):
// { format:"elevexapps", seed, accent:"#F5A623", bg:"#0b1424", url:"elevexapps.elevex.digital",
//   voice:"bm_daniel", speed:1.0, music:"upbeat"|"calm"|"none", crf:19, icon_from:"https://app/" | icon_file:"assets/apps/x.webp",
//   intro:{ headline:"Heading *abroad*?|Travel informed.", kicker:"ELEVEX APPS", app:"Travel Safety Watch", say:"..." },
//   scenes:[ { headline:"Alerts *near you*", url:"https://...", viewport:[360,778], settle:1.5, localStorage:{k:"v"}, hide:"css selector",
//              steps:[ {wait:1}, {click:"text=Play"}, {type:"input", text:"hi"}, {scroll:600, over:1.5}, {eval:"js"} ], say:"narration" } ],
//   outro:{ name:"Travel Safety Watch", line:"Try it and tell us what you think", url:"travelsafetywatch.com", note:"...",
//           tester:{ title:"Want to be a tester on Google Play?", text:"Send us your email" }, say:"..." } }
// Each part lasts as long as its narration (plus a short pause); parts overlap by TRANS seconds in a transition (no sound).
import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { run, sleep, launch, captureScene, fetchIcon } from "./freeapps.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FPS = 30;
const PY = process.env.PYTHON || "python3";
const PRESET = process.env.RENDER_PRESET || "medium";
const TRANS = 0.32;
const SCREEN = { x: 270, y: 470, w: 540, h: 1170 }; // the phone screen hole in elevexapps.html
const MIN = { intro: 2.4, scene: 3.4, outro: 3.6 };
const TRANSITIONS = ["smoothleft", "fade", "smoothright", "circleopen", "slideup", "fade"];

export async function renderElevexApps(spec, { workDir, outFile, log = () => {} }) {
  await fs.mkdir(workDir, { recursive: true });
  const CRF = String(spec.crf || process.env.RENDER_CRF || "17");
  const warnings = [];
  const seed = Number(spec.seed ?? Math.floor(Math.random() * 1e6));
  const url = spec.url || "elevexapps.elevex.digital";
  const common = { accent: spec.accent, bg: spec.bg, url };

  // ---- 1. the parts, in order ------------------------------------------------------------
  const parts = [];
  if (spec.intro) parts.push({ kind: "intro", say: spec.intro.say || "", spec: spec.intro });
  for (const s of spec.scenes || []) parts.push({ kind: "scene", say: s.say || "", spec: s });
  if (spec.outro) parts.push({ kind: "outro", say: spec.outro.say || "", spec: spec.outro });
  if (!parts.some((p) => p.kind === "scene")) throw new Error("spec.scenes is required");

  // ---- 2. the voice-over decides how long every part is -----------------------------------
  const job = { voice: spec.voice || "bm_daniel", speed: spec.speed ?? 1.02, lang: spec.lang || "en-us", scenes: parts.map((p) => ({ say: p.say, hold: MIN[p.kind] })) };
  await fs.writeFile(path.join(workDir, "job.json"), JSON.stringify(job));
  await run(PY, [path.join(HERE, "tts.py"), path.join(workDir, "job.json"), workDir]);
  const timed = JSON.parse(await fs.readFile(path.join(workDir, "timed.json"), "utf8"));
  parts.forEach((p, i) => { p.dur = Math.max(timed.scenes[i].dur, MIN[p.kind]); timed.scenes[i].dur = p.dur; });
  await fs.writeFile(path.join(workDir, "timed.json"), JSON.stringify(timed));
  let t = 0; parts.forEach((p) => { p.start = t; t += p.dur; });
  const total = t;
  parts.forEach((p, i) => { p.len = p.dur + (i < parts.length - 1 ? TRANS : 0); }); // overlap for the transition
  log(`voice-over done: ${parts.map((p) => p.dur.toFixed(1)).join(" + ")} = ${total.toFixed(1)}s`);

  const browser = await launch();
  let coverJpg = null;
  try {
    // ---- 3. app icon ---------------------------------------------------------------------
    let icon = null;
    if (spec.icon_file) { const f = path.join(HERE, spec.icon_file); const ext = path.extname(f).slice(1).replace("jpg", "jpeg"); try { icon = `data:image/${ext};base64,` + (await fs.readFile(f)).toString("base64"); } catch (e) { warnings.push("icon file: " + e.message); } }
    if (!icon) icon = await fetchIcon(browser, spec.icon_from || parts.find((p) => p.kind === "scene")?.spec.url);

    // ---- 4. capture every app scene from the live app -----------------------------------------
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      if (p.kind !== "scene") continue;
      const sc = { ...p.spec, dur: p.len, screen: SCREEN };
      try {
        if (process.env.STUB_CAPTURE) { // local layout test only: a still instead of a live capture
          const out = path.join(workDir, `cap${i}.mp4`);
          await run("ffmpeg", ["-loglevel", "error", "-y", "-loop", "1", "-framerate", String(FPS), "-i", process.env.STUB_CAPTURE, "-vf", `scale=${SCREEN.w * 2}:${SCREEN.h * 2}:force_original_aspect_ratio=increase,crop=${SCREEN.w * 2}:${SCREEN.h * 2}`, "-t", String(p.len), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", out]);
          p.cap = out;
        } else p.cap = await captureScene(browser, sc, workDir, i, warnings, log);
      } catch (e) { warnings.push(`scene ${i + 1} failed: ${e.message}`); p.cap = null; }
    }
    if (parts.filter((p) => p.kind === "scene").every((p) => !p.cap)) throw new Error("no scene could be captured: " + warnings.join(" | "));

    // ---- 5. static layers from the design page -------------------------------------------------
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 2 });
    await page.goto("file://" + path.join(HERE, "elevexapps.html"));
    await page.evaluate(() => Promise.all(["400 30px Inter", "600 30px Inter", "700 30px Inter", "800 90px Inter", "900 96px Inter"].map((f) => document.fonts.load(f, "Aa0"))));
    await page.waitForFunction(() => [...document.images].every((i) => i.complete), null, { timeout: 5000 }).catch(() => {});
    const shot = async (layer, data, file, alpha) => {
      await page.evaluate(([l, d]) => window.draw(l, d), [layer, data]);
      await page.waitForFunction(() => [...document.images].every((i) => i.complete), null, { timeout: 5000 }).catch(() => {});
      const bad = await page.evaluate(() => window.__problems || []);
      if (bad.length) throw new Error(`layout check failed (${layer}): ` + bad.join("; "));
      await page.waitForTimeout(150);
      await page.screenshot({ path: file, type: "png", omitBackground: !!alpha, scale: "device" });
    };
    await shot("bg", common, path.join(workDir, "bg.png"), false);

    // ---- 6. compose every part ------------------------------------------------------------------
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      const out = path.join(workDir, `part_${i}.mp4`);
      const enc = ["-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-tune", "animation", "-pix_fmt", "yuv420p", "-r", String(FPS), "-t", String(p.len), out];
      if (p.kind === "scene") {
        if (!p.cap) { parts[i] = null; continue; }
        const front = path.join(workDir, `front${i}.png`);
        await shot("frame", { ...common, headline: p.spec.headline }, front, true);
        const filter = `[0:v]scale=1080:1920:flags=lanczos[bg];[1:v]scale=${SCREEN.w}:${SCREEN.h}:flags=lanczos[c];[bg][c]overlay=${SCREEN.x}:${SCREEN.y}[a];[2:v]scale=1080:1920:flags=lanczos,format=rgba[f];[a][f]overlay=0:0:format=auto,format=yuv420p[v]`;
        await run("ffmpeg", ["-loglevel", "error", "-y", "-framerate", String(FPS), "-loop", "1", "-t", String(p.len), "-i", path.join(workDir, "bg.png"),
          "-i", p.cap, "-framerate", String(FPS), "-loop", "1", "-t", String(p.len), "-i", front, "-filter_complex", filter, "-map", "[v]", ...enc]);
      } else {
        const png = path.join(workDir, `${p.kind}.png`);
        if (p.kind === "intro") await shot("intro", { ...common, ...p.spec, icon }, png, false);
        else await shot("outro", { ...common, end: { icon, url, ...p.spec } }, png, false);
        const nfr = Math.round(p.len * FPS);
        // a slow push-in keeps the card alive
        await run("ffmpeg", ["-loglevel", "error", "-y", "-i", png, "-vf", `scale=2160:3840:flags=lanczos,zoompan=z='1.0+0.00045*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${nfr}:s=1080x1920:fps=${FPS},format=yuv420p`,
          "-frames:v", String(nfr), "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-pix_fmt", "yuv420p", "-r", String(FPS), out]);
        if (p.kind === "intro") coverJpg = png;
      }
      log(`composed part ${i + 1}/${parts.length} (${p.kind})`);
    }
    await page.close();
  } finally { await browser.close(); }

  // a scene that could not be captured is dropped: rebuild timings without it
  const live = parts.filter(Boolean);
  if (live.length !== parts.length) {
    warnings.push("some scenes were dropped; voice-over timing re-aligned");
    throw new Error("a scene failed to capture, nothing was rendered: " + warnings.join(" | "));
  }

  // ---- 7. join with transitions (visual only) ---------------------------------------------------
  const inputs = []; live.forEach((_, i) => inputs.push("-i", path.join(workDir, `part_${i}.mp4`)));
  let filter = "", prev = "[0:v]";
  for (let k = 1; k < live.length; k++) {
    const tr = TRANSITIONS[(seed + k) % TRANSITIONS.length];
    filter += `${prev}[${k}:v]xfade=transition=${tr}:duration=${TRANS}:offset=${live[k].start.toFixed(3)}[x${k}];`;
    prev = `[x${k}]`;
  }
  filter = filter.replace(/;$/, "").replace(/\[x(\d+)\]$/, "[vout]");
  if (live.length === 1) filter = "[0:v]null[vout]";
  await run("ffmpeg", ["-loglevel", "error", "-y", ...inputs, "-filter_complex", filter, "-map", "[vout]", "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-pix_fmt", "yuv420p", "-r", String(FPS), "-t", String(total.toFixed(3)), path.join(workDir, "video_only.mp4")]);

  // ---- 8. voice + music, finish ------------------------------------------------------------------------
  const music = spec.music || "upbeat";
  if (music === "none") {
    await run("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", String(total), path.join(workDir, "mix.wav")]);
  } else await run(PY, [path.join(HERE, "audio.py"), workDir, String(seed), music === "calm" ? "calm" : "upbeat"]);
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "mix.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-ar", "48000", path.join(workDir, "mix14.wav")]);
  const tmpOut = outFile.replace(/\.mp4$/, ".tmp.mp4");
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "video_only.mp4"), "-i", path.join(workDir, "mix14.wav"),
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", String(total.toFixed(3)), "-movflags", "+faststart", "-f", "mp4", tmpOut]);
  await fs.rename(tmpOut, outFile);
  const cover = outFile.replace(/\.mp4$/, "-cover.jpg");
  if (coverJpg) await run("ffmpeg", ["-loglevel", "error", "-y", "-i", coverJpg, "-q:v", "2", cover]);
  else await run("ffmpeg", ["-loglevel", "error", "-y", "-ss", "0.5", "-i", outFile, "-frames:v", "1", "-q:v", "2", cover]);
  return { file: outFile, cover, duration: Math.round(total * 10) / 10, scenes: live.length, warnings };
}
