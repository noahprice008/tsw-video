#!/usr/bin/env python3
"""Upgrade a renderer folder (render.mjs) to the sharper-video settings.
Usage: python3 upgrade_quality.py /path/to/renderer-folder
Safe to run twice. Keeps a backup copy as render.mjs.bak."""
import sys, re, shutil, os
d = sys.argv[1] if len(sys.argv) > 1 else "."
p = os.path.join(d, "render.mjs")
if not os.path.isfile(p): sys.exit(f"no render.mjs in {d}")
s = open(p).read()
if "RENDER_SCALE" in s: sys.exit(f"{d}: already upgraded")
orig = s
done, missed = [], []
def sub(name, pat, rep, required=True, count=1):
    global s
    new, n = re.subn(pat, rep, s, count=count, flags=re.S)
    if n: s = new; done.append(name)
    else: (missed if required else done).append(name + ("" if required else " (not present, skipped)"))
sub("settings", r"(const FPS = \d+;\n)", r'''\1// Sharpness: draw each frame at SCALE x resolution, then shrink to 1080x1920 (supersampling = crisper text and edges).
// RENDER_SCALE=1 restores the old fast mode if rendering ever gets too slow.
const SCALE = Number(process.env.RENDER_SCALE || 2);
const CRF = process.env.RENDER_CRF || "17";
const PRESET = process.env.RENDER_PRESET || "medium";
''')
sub("page scale", r"newPage\(\{ viewport: \{ width: 1080, height: 1920 \} \}\)", "newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: SCALE })")
sub("cover", r'(const coverJpg = await page\.screenshot\(\{ type: "jpeg", quality: )90( \}\);)', r"\g<1>95\2")
sub("cover file", r'(await fs\.writeFile\(outFile\.replace\(/\\\.mp4\$/, "-cover\.jpg"\), )coverJpg(\);)', r'\1await page.screenshot({ type: "jpeg", quality: 92, scale: "css" })\2')
sub("stock filter", r"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,(fps=\$\{FPS\},trim=duration=\$\{\(n / FPS\)\.toFixed\(3\)\},setpts=PTS-STARTPTS)\[bg\];\[bg\]\[1:v\]overlay=shortest=1",
    r"scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,\1[bg];[1:v]scale=1080:1920:flags=lanczos[fg];[bg][fg]overlay=shortest=1", required=False)
sub("stock encode", r'("-an", "-c:v", "libx264", "-preset", )"veryfast", "-crf", "\d+"', r'\1PRESET, "-crf", CRF', required=False)
sub("frame encode", r'("-c:v", "mjpeg", "-i", "-",\s*)"-c:v", "libx264", "-preset", "veryfast", "-crf", "\d+"', r'\1"-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-tune", "animation"')
sub("frame quality", r'(page\.screenshot\(\{ type: "jpeg", quality: )92( \}\))', r"\g<1>95\2", count=0)
sub("audio", r'"-b:a", "160k"', '"-b:a", "192k"', required=False)
if missed:
    sys.exit(f"{d}: NOT changed. Could not find: {', '.join(missed)}. Send this message to Claude.")
shutil.copy(p, p + ".bak"); open(p, "w").write(s)
print(f"{d}: upgraded ({', '.join(done)})")
