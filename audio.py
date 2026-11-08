"""Mix narration with an original music bed. Usage: python3 audio.py workdir seed
Reads workdir/timed.json, writes workdir/mix.wav."""
import json, sys, os, random, numpy as np, soundfile as sf
wd = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
T = json.load(open(os.path.join(wd, "timed.json"))); SR = T["sr"]; LEAD = T["lead"]
total = sum(s["dur"] for s in T["scenes"]); n = int(total * SR)
voice = np.zeros(n); t = 0
for s in T["scenes"]:
    if s["wav"]:
        a, _ = sf.read(s["wav"]); i = int((t + LEAD) * SR); m = min(len(a), n - i)
        if m > 0: voice[i:i + m] += a[:m]
    t += s["dur"]
# calm progressions (pad chord, arpeggio), bar length in seconds
PROGS = [
 ([[48,55,64,71],[45,52,60,67],[41,48,57,64],[43,50,59,64]], [[72,76,79,83],[69,72,76,79],[65,69,72,76],[67,71,74,79]], 3.33),
 ([[50,57,62,66],[47,54,59,62],[43,50,55,59],[45,52,57,61]], [[74,78,81,85],[71,74,78,81],[67,71,74,79],[69,73,76,81]], 3.0),
 ([[53,60,65,69],[50,57,62,65],[46,53,58,62],[48,55,60,64]], [[77,81,84,88],[74,77,81,84],[70,74,77,82],[72,76,79,84]], 2.6),
 ([[45,52,60,64],[41,48,57,60],[48,55,64,67],[43,50,59,62]], [[69,72,76,79],[65,69,72,76],[72,76,79,84],[67,71,74,79]], 3.2),
 ([[52,59,64,68],[49,56,61,64],[45,52,57,61],[47,54,59,63]], [[76,80,83,88],[73,76,80,85],[69,73,76,81],[71,75,78,83]], 2.8),
]
chords, arp, bar = PROGS[seed % len(PROGS)]
rnd = random.Random(seed)
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
def note(f, d, amp, att=0.6, rel=1.2):
    k = int(d * SR); x = np.arange(k) / SR
    w = sum(a * np.sin(2 * np.pi * f * h * x + h) for h, a in zip((1, 2, 3), (1, .35, .12)))
    return amp * w * np.clip(np.minimum(1, x / att) * np.minimum(1, (d - x) / rel), 0, 1)
def pluck(f, d=1.6, amp=.18):
    k = int(d * SR); x = np.arange(k) / SR
    return amp * np.sin(2 * np.pi * f * x) * np.exp(-x * 3.2) * (1 - np.exp(-x * 400))
def add(buf, st, sig):
    if st >= len(buf): return
    m = min(len(sig), len(buf) - st); buf[st:st + m] += sig[:m]
music = np.zeros(n)
for k in range(int(total / bar) + 2):
    st = int(k * bar * SR)
    for m in chords[k % 4]: add(music, st, note(hz(m), bar + 1.2, .05))
    order = list(arp[k % 4]);
    if rnd.random() < .5: order = order[::-1]
    for j, m in enumerate(order): add(music, st + int(j * bar / 4 * SR), pluck(hz(m)))
d = int(.29 * SR); echo = np.zeros_like(music); echo[d:] = music[:-d] * .35; music += echo
x = np.arange(n) / SR; music *= np.minimum(1, x / 1.5) * np.clip(np.minimum(1, (total - x) / 2.0), 0, 1)
win = max(1, int(.25 * SR)); env = np.convolve(np.abs(voice), np.ones(win) / win, 'same')
music *= 1 - .45 * np.clip(env / 0.05, 0, 1)
music /= np.max(np.abs(music)) + 1e-9
if np.max(np.abs(voice)) > 0: voice /= np.max(np.abs(voice))
mix = 0.92 * voice + 0.12 * music
mix /= max(1, np.max(np.abs(mix)) / 0.95)
sf.write(os.path.join(wd, "mix.wav"), mix, SR)
print(json.dumps({"audio": round(total, 2)}))
