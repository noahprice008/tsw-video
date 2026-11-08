"""Narration for every scene. Usage: python3 tts.py job.json workdir
job: {voice, lang, speed, scenes:[{say, caption?, hold?, extra?}]}
Writes workdir/scene_<i>.wav and workdir/timed.json (scene durations + word start times for captions)."""
import json, sys, os, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
MODEL_DIR = os.environ.get("KOKORO_DIR", "/opt/kokoro")
job = json.load(open(sys.argv[1])); wd = sys.argv[2]
k = Kokoro(f"{MODEL_DIR}/kokoro-v1.0.onnx", f"{MODEL_DIR}/voices-v1.0.bin")
LEAD, TAIL = 0.25, 0.45
out = []; sr = 24000
for i, sc in enumerate(job["scenes"]):
    say = (sc.get("say") or "").strip()
    if not say:
        out.append({"dur": float(sc.get("hold", 2.2)), "speech": 0, "words": [], "wav": None}); continue
    a, sr = k.create(say, voice=job.get("voice", "af_heart"), speed=float(job.get("speed", 1.08)), lang=job.get("lang", "en-us"))
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz): a = a[max(nz[0] - 200, 0): nz[-1] + 800]
    f = os.path.join(wd, f"scene_{i}.wav"); sf.write(f, a, sr)
    speech = len(a) / sr
    words = (sc.get("caption") or say).split(); w = [len(x) + 2 for x in words]; tot = sum(w); t = LEAD; times = []
    for x, wi in zip(words, w): times.append([x, round(t, 3)]); t += speech * wi / tot
    out.append({"dur": round(LEAD + speech + TAIL + float(sc.get("extra", 0)), 2), "speech": round(speech, 2), "words": times, "wav": f})
json.dump({"sr": sr, "lead": LEAD, "scenes": out}, open(os.path.join(wd, "timed.json"), "w"))
print(json.dumps({"total": round(sum(s["dur"] for s in out), 2)}))
