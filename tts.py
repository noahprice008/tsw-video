"""Narration for every scene. Usage: python3 tts.py job.json workdir
job: {voice, lang, speed, scenes:[{say, caption?, hold?, extra?}]}
Writes workdir/scene_<i>.wav and workdir/timed.json (scene durations + word start times for captions)."""
import json, sys, os, re, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
MODEL_DIR = os.environ.get("KOKORO_DIR", "/opt/kokoro")
job = json.load(open(sys.argv[1])); wd = sys.argv[2]
k = Kokoro(f"{MODEL_DIR}/kokoro-v1.0.onnx", f"{MODEL_DIR}/voices-v1.0.bin")
LEAD, TAIL = 0.25, 0.45

# Pronunciation fixes for the voice only (on-screen captions keep the normal spelling).
# "live" as in alive/online (go live, is live): the engine reads it as "lives" without help, so respell it "lyve".
# Kept as "live" (lives) when it is clearly the verb: after I/you/we/they/who/people..., or before in/with/on/near/here...
_VERB_BEFORE = r"(?:i|you|we|they|who|people|folks|those|travell?ers|tourists|expats|families|locals)"
_VERB_AFTER = r"(?:in|with|on|near|at|by|here|there|abroad|alone|without|for|a|an|the|my|your|our|their|like|through|off)"
_ADJ_BEFORE = r"(?:go|goes|going|went|gone|is|are|was|were|be|been|being|it's|its|that's|now|stay|stays|staying|went|get|gets|getting|made|make|makes|site|app|sites|apps)"
def speak(t):
    t = re.sub(r"\bELEVEX\b", "Ellevex", t, flags=re.I)  # "ELL-eh-vex", said quickly, not "eleven"
    def fix(m):
        before = t[:m.start()].rstrip().split()[-1:] or [""]
        after = t[m.end():].lstrip().split()[:1] or [""]
        b = re.sub(r"[^a-z]", "", before[0].lower()); a = re.sub(r"[^a-z]", "", after[0].lower())
        if re.fullmatch(_ADJ_BEFORE, b): return "lyve" if m.group(0).islower() or m.group(0).istitle() else "LYVE"
        if re.fullmatch(_VERB_BEFORE, b) or re.fullmatch(_VERB_AFTER, a): return m.group(0)
        return "lyve" if m.group(0).islower() or m.group(0).istitle() else "LYVE"
    return re.sub(r"\blive\b", fix, t, flags=re.I)
out = []; sr = 24000
for i, sc in enumerate(job["scenes"]):
    say = (sc.get("say") or "").strip()
    if not say:
        out.append({"dur": float(sc.get("hold", 2.2)), "speech": 0, "words": [], "wav": None}); continue
    a, sr = k.create(speak(say), voice=job.get("voice", "af_heart"), speed=float(job.get("speed", 1.08)), lang=job.get("lang", "en-us"))
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz): a = a[max(nz[0] - 200, 0): nz[-1] + 800]
    f = os.path.join(wd, f"scene_{i}.wav"); sf.write(f, a, sr)
    speech = len(a) / sr
    words = (sc.get("caption") or say).split(); w = [len(x) + 2 for x in words]; tot = sum(w); t = LEAD; times = []
    for x, wi in zip(words, w): times.append([x, round(t, 3)]); t += speech * wi / tot
    out.append({"dur": round(LEAD + speech + TAIL + float(sc.get("extra", 0)), 2), "speech": round(speech, 2), "words": times, "wav": f})
json.dump({"sr": sr, "lead": LEAD, "scenes": out}, open(os.path.join(wd, "timed.json"), "w"))
print(json.dumps({"total": round(sum(s["dur"] for s in out), 2)}))
