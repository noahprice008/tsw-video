#!/usr/bin/env python3
"""Add the ELEVEX brand header (placed at y=200px so the TikTok/Reels search bar at the top never covers it) (small logo + elevex.digital on every frame) to a renderer folder.
Usage: python3 add_elevex_header.py /root/elevex-video
For a renderer that only makes ELEVEX videos: the header is always on (a spec can switch it off with "brand": false).
Safe to run twice. Keeps a backup copy as template.html.bak. Changes nothing if the template looks different than expected."""
import sys, os, re, shutil
d = sys.argv[1] if len(sys.argv) > 1 else "."
here = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(d, "template.html")
if not os.path.isfile(p): sys.exit(f"no template.html in {d}")
s = open(p).read()
if 'id="brand"' in s: sys.exit(f"{d}: header already added, nothing to do")
missing = []
if "</style>" not in s: missing.append("</style>")
m_cap = re.search(r'\n?\s*<div id="cap"', s)
if not m_cap: missing.append('<div id="cap">')
m_set = re.search(r'window\.setSpec\s*=\s*async\s*\(?\s*spec\s*\)?\s*=>\s*\{', s)
if not m_set: missing.append("window.setSpec")
if missing: sys.exit(f"{d}: NOT changed. Could not find: {', '.join(missing)}. Send this message to Claude.")

css = ('#brand{left:0;top:200px;width:1080px;height:240px;display:none;text-align:center;'
       'background:linear-gradient(180deg,rgba(11,18,32,.75),rgba(11,18,32,0));pointer-events:none}\n'
       '#brand img{width:270px;margin-top:0;display:block;margin-left:auto;margin-right:auto}\n'
       '#brand div{font:600 40px Inter,Arial,sans-serif;color:#38BDF8;margin-top:12px;text-shadow:0 3px 8px rgba(0,0,0,.7)}\n')
js = ("\n // Brand header: small ELEVEX logo + website on every frame (spec.brand:false switches it off).\n"
      " {const bh=document.getElementById('brand');const on=spec.brand!==false;bh.style.display=on?'block':'none';"
      "bh.innerHTML=on?'<img src=\"assets/elevex-wordmark.png\"><div>elevex.digital</div>':'';}\n")
i = m_cap.start(); s = s[:i] + '\n <div id="brand" class="abs" style="position:absolute"></div>' + s[i:]
s = s.replace("</style>", css + "</style>", 1)
m_set = re.search(r'window\.setSpec\s*=\s*async\s*\(?\s*spec\s*\)?\s*=>\s*\{', s)
s = s[:m_set.end()] + js + s[m_set.end():]

os.makedirs(os.path.join(d, "assets"), exist_ok=True)
shutil.copy(os.path.join(here, "..", "assets", "elevex-wordmark.png"), os.path.join(d, "assets", "elevex-wordmark.png"))
shutil.copy(p, p + ".bak"); open(p, "w").write(s)
print(f"{d}: header added (backup in template.html.bak)")
