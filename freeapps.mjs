// FreeApps videos: sharp, scripted screen captures of the real apps inside a large phone frame.
// Spec (POST /render with "format": "freeapps"):
// { format:"freeapps", seed, accent:"#F5A623", bg:"#0b1424", icon_from:"https://app/",
//   scenes:[ { headline:"Stuck at the *gate*?", pill:"Example map", sticker:false, url:"https://...", viewport:[430,932],
//              settle:1.5, dur:3.6, localStorage:{k:"v"},
//              steps:[ {wait:1}, {click:"text=Play"}, {type:"input", text:"hello"}, {scroll:600, over:1.5}, {eval:"js"} ] } ],
//   end:{ name:"TravelPlay", line:"Play free now", url:"travelplay.fun", badges:"soon"|"live", note:"..." },
//   hook:{ headline, app, dur, style?:"boxes"|"phone"|"stamp", kicker? },   // with style: hook card uses the cover design
//   cover:{ headline:"No wifi.|9 hours.|*Zero* boredom", kicker:"POV:", style:"boxes"|"phone"|"stamp", shot_scene:0, shot_at:2.5 },
//   music:"upbeat"|"calm"|"none", crf:21 }   // music "none" = silent track (sound added in TikTok); crf overrides RENDER_CRF
// Quality: captured at 2x with Chrome's screencast, composed with ffmpeg, encoded with the same settings as render.mjs.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FPS = 30;
let CRF = process.env.RENDER_CRF || "17";
const PRESET = process.env.RENDER_PRESET || "medium";
const PY = process.env.PYTHON || "python3";
const END_SECONDS = 2.6;
const HOOK_SECONDS = 1.7;
const SCREEN = { x: 200, y: 330, w: 680, h: 1470 }; // the phone screen hole in freeapps.html

export function run(cmd, args) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d)); p.stderr.on("data", (d) => (err += d));
    p.on("close", (c) => (c === 0 ? resolve(out) : reject(new Error(`${cmd} failed (${c}): ${err.slice(-800)}`))));
  });
}
export const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));
export const launch = () => chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH, args: ["--no-sandbox"] } : {});

const RIPPLE_CSS = `@keyframes __r{from{transform:translate(-50%,-50%) scale(.3);opacity:.8}to{transform:translate(-50%,-50%) scale(1.7);opacity:0}}
.__rip{position:fixed;width:84px;height:84px;border-radius:50%;background:rgba(255,255,255,.45);border:3px solid rgba(255,255,255,.95);pointer-events:none;z-index:2147483647;animation:__r .6s ease-out forwards}`;

async function runStep(page, st, warnings, idx) {
  try {
    if (st.wait != null) return await sleep(st.wait);
    if (st.click) {
      const loc = page.locator(st.click).first();
      await loc.scrollIntoViewIfNeeded({ timeout: 4000 });
      const b = await loc.boundingBox({ timeout: 4000 });
      if (b) {
        await page.evaluate(([x, y]) => { const d = document.createElement("div"); d.className = "__rip"; d.style.left = x + "px"; d.style.top = y + "px"; document.body.appendChild(d); setTimeout(() => d.remove(), 800); }, [b.x + b.width / 2, b.y + b.height / 2]);
        await sleep(0.15);
      }
      return await loc.click({ timeout: 4000 });
    }
    if (st.type) {
      const loc = page.locator(st.type).first();
      await loc.click({ timeout: 4000 });
      return await page.keyboard.type(st.text || "", { delay: st.delay ?? 90 });
    }
    if (st.scroll != null) {
      return await page.evaluate(async ([px, over, sel]) => {
        const el = sel ? document.querySelector(sel) : (document.scrollingElement || document.documentElement);
        const from = el.scrollTop, t0 = performance.now(), ms = Math.max(200, over * 1000);
        await new Promise((res) => { const f = (t) => { const k = Math.min(1, (t - t0) / ms); const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; el.scrollTop = from + px * e; k < 1 ? requestAnimationFrame(f) : res(); }; requestAnimationFrame(f); });
      }, [st.scroll, st.over ?? 1.2, st.scrollSel || null]);
    }
    if (st.eval) return await page.evaluate(st.eval);
  } catch (e) { warnings.push(`step ${idx} (${JSON.stringify(st).slice(0, 80)}): ${/closed/.test(e.message) ? "scene ended before this step ran" : String(e.message).split("\n")[0]}`); }
}

// Records one scene of a live app as a CFR mp4 at 2x size. Returns { file, icon }.
export async function captureScene(browser, sc, dir, i, warnings, log) {
  const SCR = sc.screen || SCREEN; // phone screen size in the composed frame (default: FreeApps layout)
  const [vw, vh] = sc.viewport || [360, 778];
  const DSF = 2;
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: DSF, isMobile: true, hasTouch: true, colorScheme: sc.colorScheme || "light" });
  if (sc.localStorage) await ctx.addInitScript((kv) => { for (const k in kv) try { localStorage.setItem(k, kv[k]); } catch {} }, sc.localStorage);
  const page = await ctx.newPage();
  try {
    await page.goto(sc.url, { waitUntil: "load", timeout: 45000 });
    await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
    await page.addStyleTag({ content: RIPPLE_CSS });
    if (sc.hide) await page.addStyleTag({ content: `${sc.hide}{display:none !important}` });
    await sleep(sc.settle ?? 1.2);
    const cdp = await ctx.newCDPSession(page);
    const frames = [];
    cdp.on("Page.screencastFrame", async (f) => {
      frames.push({ t: f.metadata.timestamp, buf: Buffer.from(f.data, "base64") });
      cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
    });
    const start = Date.now();
    await cdp.send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: vw * DSF, maxHeight: vh * DSF, everyNthFrame: 1 });
    // run the scripted steps, but never past the scene length
    const steps = (async () => { let n = 0; for (const st of sc.steps || []) await runStep(page, st, warnings, `${i + 1}.${++n}`); })();
    await Promise.race([steps, sleep(sc.dur + 0.5)]);
    const left = sc.dur + 0.15 - (Date.now() - start) / 1000;
    if (left > 0) await sleep(left);
    await cdp.send("Page.stopScreencast").catch(() => {});
    if (!frames.length) { warnings.push(`scene ${i + 1}: no frames captured`); throw new Error("no frames"); }
    // frames -> constant-rate video, holding each frame until the next one arrived
    const t0 = frames[0].t;
    let list = "";
    for (let k = 0; k < frames.length; k++) {
      const f = path.join(dir, `cap${i}_${k}.jpg`);
      await fs.writeFile(f, frames[k].buf);
      const next = k + 1 < frames.length ? frames[k + 1].t : t0 + sc.dur;
      list += `file '${f}'\nduration ${Math.max(0.02, next - frames[k].t).toFixed(4)}\n`;
    }
    list += `file '${path.join(dir, `cap${i}_${frames.length - 1}.jpg`)}'\n`;
    await fs.writeFile(path.join(dir, `cap${i}.txt`), list);
    const out = path.join(dir, `cap${i}.mp4`);
    await run("ffmpeg", ["-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", path.join(dir, `cap${i}.txt`), "-vf", `fps=${FPS},scale=${SCR.w * 2}:${SCR.h * 2}:flags=lanczos`,
      "-t", String(sc.dur), "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p", out]);
    await Promise.all(frames.map((_, k) => fs.rm(path.join(dir, `cap${i}_${k}.jpg`), { force: true })));
    log(`captured scene ${i + 1}: ${frames.length} frames`);
    return out;
  } finally { await ctx.close(); }
}

export async function fetchIcon(browser, url) {
  if (!url) return null;
  const ctx = await browser.newContext();
  try {
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "load", timeout: 30000 });
    const href = await page.evaluate(() => { const q = (s) => document.querySelector(s)?.href; return q('link[rel*="apple-touch-icon"]') || q('link[rel~="icon"]') || null; });
    if (!href) return null;
    const r = await ctx.request.get(href);
    if (!r.ok()) return null;
    const type = (r.headers()["content-type"] || "image/png").split(";")[0];
    return `data:${type};base64,${(await r.body()).toString("base64")}`;
  } catch { return null; } finally { await ctx.close(); }
}

export async function renderFreeApps(spec, { workDir, outFile, log = () => {} }) {
  await fs.mkdir(workDir, { recursive: true });
  CRF = spec.crf ? String(spec.crf) : (process.env.RENDER_CRF || "17");
  const warnings = [];
  let coverJpg = null;
  const seed = Number(spec.seed ?? Math.floor(Math.random() * 1e6));
  const scenes = (spec.scenes || []).map((s) => ({ ...s, dur: Number(s.dur) || 3.4 }));
  const browser = await launch();
  const parts = [];
  try {
    const icon = (spec.end && spec.end.icon) || (await fetchIcon(browser, spec.icon_from || scenes[0]?.url));
    // 1. capture every scene from the live app
    const caps = [];
    for (let i = 0; i < scenes.length; i++) {
      try { caps.push(await captureScene(browser, scenes[i], workDir, i, warnings, log)); }
      catch (e) { warnings.push(`scene ${i + 1} failed: ${e.message}`); caps.push(null); }
    }
    if (caps.every((c) => !c)) throw new Error("no scene could be captured: " + warnings.join(" | "));
    // 2. static layers (background, phone frame + text, end card) from the design page
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 2 });
    await page.goto("file://" + path.join(HERE, "freeapps.html"));
    // fonts load lazily: load them before measuring, or text is fitted using a narrower fallback font
    await page.evaluate(() => Promise.all(["400 30px Inter", "600 30px Inter", "700 30px Inter", "800 90px Inter", "900 96px Inter"].map((f) => document.fonts.load(f, "Aa0"))));
    const shot = async (layer, data, file, alpha) => {
      await page.evaluate(([l, d]) => window.draw(l, d), [layer, data]);
      // never render (or post) a card with text running off the frame: fail loudly so n8n emails the problem instead
      const bad = await page.evaluate(() => window.__problems || []);
      if (bad.length) throw new Error(`layout check failed (${layer}): ` + bad.join("; "));
      await page.waitForTimeout(150);
      await page.screenshot({ path: file, type: "png", omitBackground: !!alpha, scale: "device" });
    };
    const common = { accent: spec.accent, bg: spec.bg };
    await shot("bg", common, path.join(workDir, "bg.png"), false);
    // a still of the real app, used behind styled hooks and covers
    let still = null;
    const wantStill = spec.cover?.headline || spec.hook?.style;
    if (wantStill) {
      const si = Number(spec.cover?.shot_scene ?? 0);
      const k = caps[si] ? si : caps.findIndex((c) => c);
      if (k >= 0) {
        const at = Math.min(Number(spec.cover?.shot_at ?? scenes[k].dur * 0.6), scenes[k].dur - 0.2);
        try { const f = path.join(workDir, "still.png"); await run("ffmpeg", ["-loglevel", "error", "-y", "-ss", String(Math.max(0, at)), "-i", caps[k], "-frames:v", "1", f]); still = "file://" + f; }
        catch (e) { warnings.push("still frame skipped: " + e.message); }
      }
    }
    if (spec.cover?.headline) {
      await shot("cover", { ...common, ...spec.cover, shot: still, icon, app: spec.cover.app || spec.end?.name }, path.join(workDir, "cover.png"), false);
      coverJpg = path.join(workDir, "cover.png");
    }
    // 2b. TikTok hook card: huge text on a vivid background (or a photo) for the first moment; doubles as the colourful cover
    let hasHook = false;
    if (spec.hook?.headline) {
      let bg = null;
      try {
        const hb = spec.hook.bg_url || spec.hook.bg_file;
        if (spec.hook.bg_file) bg = "file://" + spec.hook.bg_file;
        else if (spec.hook.bg_url) { const f = path.join(workDir, "hook_bg.jpg"); const r = await fetch(spec.hook.bg_url); if (!r.ok) throw new Error("hook background download " + r.status); await fs.writeFile(f, Buffer.from(await r.arrayBuffer())); bg = "file://" + f; }
      } catch (e) { warnings.push("hook background skipped: " + e.message); }
      if (spec.hook.style) await shot("cover", { ...common, headline: spec.hook.headline, kicker: spec.hook.kicker, style: spec.hook.style, shot: still, icon, app: spec.hook.app || spec.end?.name }, path.join(workDir, "hook.png"), false);
      else await shot("hook", { ...common, headline: spec.hook.headline, bg, icon, app: spec.hook.app }, path.join(workDir, "hook.png"), false);
      const dur = Number(spec.hook.dur) || HOOK_SECONDS, nfr = Math.round(dur * FPS);
      await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "hook.png"), "-vf",
        `scale=2160:3840:flags=lanczos,zoompan=z='1.14-0.14*min(1,on/9)+0.0004*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${nfr}:s=1080x1920:fps=${FPS},format=yuv420p`,
        "-frames:v", String(nfr), "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-pix_fmt", "yuv420p", "-r", String(FPS), path.join(workDir, "part_hook.mp4")]);
      parts.push({ file: path.join(workDir, "part_hook.mp4"), dur: nfr / FPS });
      hasHook = true;
    }
    // 3. compose each scene with ffmpeg
    for (let i = 0; i < scenes.length; i++) {
      if (!caps[i]) continue;
      const sc = scenes[i];
      const front = path.join(workDir, `front${i}.png`);
      await shot("front", { ...common, headline: sc.headline, pill: sc.pill, sticker: sc.sticker }, front, true);
      const out = path.join(workDir, `part_${i}.mp4`);
      const filter = `[0:v]scale=1080:1920:flags=lanczos[bg];[1:v]scale=${SCREEN.w}:${SCREEN.h}:flags=lanczos[c];[bg][c]overlay=${SCREEN.x}:${SCREEN.y}[a];[2:v]scale=1080:1920:flags=lanczos,format=rgba,fade=t=in:st=0:d=0.25:alpha=1[f];[a][f]overlay=0:0:format=auto,format=yuv420p[v]`;
      await run("ffmpeg", ["-loglevel", "error", "-y", "-framerate", String(FPS), "-loop", "1", "-t", String(sc.dur), "-i", path.join(workDir, "bg.png"),
        "-i", caps[i], "-framerate", String(FPS), "-loop", "1", "-t", String(sc.dur), "-i", front,
        "-filter_complex", filter, "-map", "[v]", "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-tune", "animation", "-pix_fmt", "yuv420p", "-r", String(FPS), "-t", String(sc.dur), out]);
      parts.push({ file: out, dur: sc.dur });
      log(`composed scene ${i + 1}/${scenes.length}`);
    }
    // end card
    if (spec.end) {
      await shot("end-bg", common, path.join(workDir, "endbg.png"), false);
      await shot("end", { ...common, end: { ...spec.end, icon } }, path.join(workDir, "endfront.png"), true);
      const out = path.join(workDir, "part_end.mp4");
      await run("ffmpeg", ["-loglevel", "error", "-y", "-framerate", String(FPS), "-loop", "1", "-t", String(END_SECONDS), "-i", path.join(workDir, "endbg.png"),
        "-framerate", String(FPS), "-loop", "1", "-t", String(END_SECONDS), "-i", path.join(workDir, "endfront.png"),
        "-filter_complex", `[0:v]scale=1080:1920:flags=lanczos[b];[1:v]scale=1080:1920:flags=lanczos,format=rgba,fade=t=in:st=0:d=0.3:alpha=1[f];[b][f]overlay=0:0:format=auto,format=yuv420p[v]`,
        "-map", "[v]", "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-tune", "animation", "-pix_fmt", "yuv420p", "-r", String(FPS), "-t", String(END_SECONDS), out]);
      parts.push({ file: out, dur: END_SECONDS });
    }
    await page.close();
  } finally { await browser.close(); }

  // 4. join, add the music bed, finish
  const total = parts.reduce((a, p) => a + p.dur, 0);
  await fs.writeFile(path.join(workDir, "list.txt"), parts.map((p) => `file '${p.file}'`).join("\n"));
  await run("ffmpeg", ["-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", path.join(workDir, "list.txt"), "-c", "copy", path.join(workDir, "video_only.mp4")]);
  await fs.writeFile(path.join(workDir, "timed.json"), JSON.stringify({ sr: 24000, lead: 0, scenes: parts.map((p) => ({ dur: p.dur, wav: null })) }));
  if (spec.music === "none") {
    // silent track: the sound is added in TikTok
    await run("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", String(total), path.join(workDir, "mix14.wav")]);
  } else {
    await run(PY, [path.join(HERE, "audio.py"), workDir, String(seed), spec.music === "calm" ? "calm" : "upbeat"]);
    await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "mix.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-ar", "48000", path.join(workDir, "mix14.wav")]);
  }
  const tmpOut = outFile.replace(/\.mp4$/, ".tmp.mp4");
  await run("ffmpeg", ["-loglevel", "error", "-y", "-i", path.join(workDir, "video_only.mp4"), "-i", path.join(workDir, "mix14.wav"),
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "-f", "mp4", tmpOut]);
  await fs.rename(tmpOut, outFile);
  const cover = outFile.replace(/\.mp4$/, "-cover.jpg");
  if (coverJpg) await run("ffmpeg", ["-loglevel", "error", "-y", "-i", coverJpg, "-q:v", "2", cover]);
  else await run("ffmpeg", ["-loglevel", "error", "-y", "-ss", spec.hook?.headline ? "0.5" : "0.9", "-i", outFile, "-frames:v", "1", "-q:v", "2", cover]);
  return { file: outFile, cover, duration: Math.round(total * 10) / 10, scenes: parts.length, warnings };
}
