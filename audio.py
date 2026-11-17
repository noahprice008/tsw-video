"""Mix narration with an original music bed. Usage: python3 audio.py workdir seed
Reads workdir/timed.json, writes workdir/mix.wav."""
import json, sys, os, random, numpy as np, soundfile as sf
wd = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
MODE = sys.argv[3] if len(sys.argv) > 3 else "calm"
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

def upbeat_music():
    """Original upbeat dance-pop bed (about 124 BPM): kick, clap, hats, bass, chord stabs, bright arp. No samples, no licences."""
    r = random.Random(seed * 7 + 3)
    bpm = r.choice([118, 122, 124, 126, 128]); beat = 60.0 / bpm
    root = r.choice([57, 55, 53, 52, 50])  # A, G, F, E, D (minor-key pop)
    prog = r.choice([[0, -4, -9, -2], [0, -2, -4, -5], [0, 3, -4, -2], [0, -4, 3, -2]])  # semitone offsets of chord roots
    out = np.zeros(n)
    def put(st, sig):
        st = int(st * SR)
        if st >= n: return
        m = min(len(sig), n - st); out[st:st + m] += sig[:m]
    def kick():
        k = int(.28 * SR); x = np.arange(k) / SR
        f = 48 + 110 * np.exp(-x * 38); ph = 2 * np.pi * np.cumsum(f) / SR
        return .95 * np.sin(ph) * np.exp(-x * 11) * (1 - np.exp(-x * 900))
    def clap():
        k = int(.22 * SR); x = np.arange(k) / SR; nz = np.random.RandomState(seed).randn(k)
        nz = np.convolve(nz, np.ones(6) / 6, 'same')
        return .5 * nz * (np.exp(-x * 24) + .6 * np.exp(-((x - .012) * 140) ** 2))
    def hat(open_=False):
        k = int((.18 if open_ else .05) * SR); x = np.arange(k) / SR; nz = np.random.RandomState(seed + 1).randn(k)
        nz = nz - np.convolve(nz, np.ones(4) / 4, 'same')
        return (.22 if open_ else .16) * nz * np.exp(-x * (18 if open_ else 80))
    def bass(m, d):
        k = int(d * SR); x = np.arange(k) / SR; f = hz(m)
        w = np.sin(2 * np.pi * f * x) + .4 * np.sin(4 * np.pi * f * x) + .15 * np.sign(np.sin(2 * np.pi * f * x))
        return .5 * w * np.exp(-x * 3.5) * np.clip(x / .008, 0, 1) * np.clip((d - x) / .03, 0, 1)
    def stab(ms, d=.22):
        k = int(d * SR); x = np.arange(k) / SR; w = np.zeros(k)
        for m in ms:
            f = hz(m)
            for dt in (-.004, .004): w += np.sign(np.sin(2 * np.pi * f * (1 + dt) * x)) * .5 + np.sin(2 * np.pi * f * x)
        return .09 * w * np.exp(-x * 14) * np.clip(x / .004, 0, 1)
    def lead(m, d):
        k = int(d * SR); x = np.arange(k) / SR; f = hz(m)
        w = np.sin(2 * np.pi * f * x) + .5 * np.sin(4 * np.pi * f * x) + .25 * np.sin(6 * np.pi * f * x)
        return .13 * w * np.exp(-x * 9) * np.clip(x / .004, 0, 1)
    bars = int(total / (4 * beat)) + 2
    for b in range(bars):
        t0 = b * 4 * beat; cr = root + prog[b % 4]
        third = cr + 3; fifth = cr + 7
        for q in range(4):
            tb = t0 + q * beat
            if b >= 1 or total < 6: put(tb, kick())              # intro bar: no kick, builds energy
            if q in (1, 3): put(tb, clap())
            put(tb + beat / 2, hat(open_=True)); put(tb, hat())
            put(tb + beat / 4, hat()); put(tb + 3 * beat / 4, hat())
            put(tb, bass(cr - 12, beat * .9)); put(tb + beat / 2, bass(cr - 12 + (12 if q % 2 else 0), beat * .4))
            put(tb + beat / 2, stab([cr, third, fifth + 12]))
        pat = [0, 7, 12, 7, 15, 12, 7, 12] if b % 2 == 0 else [12, 7, 15, 12, 19, 15, 12, 7]
        for j, o in enumerate(pat):
            put(t0 + j * beat / 2, lead(cr + 12 + o, beat * .45))
    # a little shared echo for width
    d = int(beat * .75 * SR); e = np.zeros_like(out); e[d:] = out[:-d] * .18; out += e
    x = np.arange(n) / SR; out *= np.minimum(1, x / .15) * np.clip(np.minimum(1, (total - x) / 1.2), 0, 1)
    return out / (np.max(np.abs(out)) + 1e-9)

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
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
music = np.zeros(n)
for k in range(0 if MODE == "upbeat" else int(total / bar) + 2):
    st = int(k * bar * SR)
    for m in chords[k % 4]: add(music, st, note(hz(m), bar + 1.2, .05))
    order = list(arp[k % 4]);
    if rnd.random() < .5: order = order[::-1]
    for j, m in enumerate(order): add(music, st + int(j * bar / 4 * SR), pluck(hz(m)))
if MODE == "upbeat": music = upbeat_music()
d = int(.29 * SR); echo = np.zeros_like(music); echo[d:] = music[:-d] * .35
if MODE != "upbeat": music += echo
x = np.arange(n) / SR
if MODE != "upbeat": music *= np.minimum(1, x / 1.5) * np.clip(np.minimum(1, (total - x) / 2.0), 0, 1)
win = max(1, int(.25 * SR)); env = np.convolve(np.abs(voice), np.ones(win) / win, 'same')
music *= 1 - .45 * np.clip(env / 0.05, 0, 1)
music /= np.max(np.abs(music)) + 1e-9
if np.max(np.abs(voice)) > 0: voice /= np.max(np.abs(voice))
mix = 0.92 * voice + (0.22 if MODE == "upbeat" else 0.12) * music
mix /= max(1, np.max(np.abs(mix)) / 0.95)
sf.write(os.path.join(wd, "mix.wav"), mix, SR)
print(json.dumps({"audio": round(total, 2)}))
