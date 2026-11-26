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
if MODE == "none":  # voice only: no music bed at all (platforms add trending sound)
    if np.max(np.abs(voice)) > 0: voice = voice / np.max(np.abs(voice)) * 0.92
    sf.write(os.path.join(wd, "mix.wav"), voice, SR)
    print(json.dumps({"audio": round(total, 2), "music": "none"})); sys.exit(0)
# calm progressions (pad chord, arpeggio), bar length in seconds
PROGS = [
 ([[48,55,64,71],[45,52,60,67],[41,48,57,64],[43,50,59,64]], [[72,76,79,83],[69,72,76,79],[65,69,72,76],[67,71,74,79]], 3.33),
 ([[50,57,62,66],[47,54,59,62],[43,50,55,59],[45,52,57,61]], [[74,78,81,85],[71,74,78,81],[67,71,74,79],[69,73,76,81]], 3.0),
 ([[53,60,65,69],[50,57,62,65],[46,53,58,62],[48,55,60,64]], [[77,81,84,88],[74,77,81,84],[70,74,77,82],[72,76,79,84]], 2.6),
 ([[45,52,60,64],[41,48,57,60],[48,55,64,67],[43,50,59,62]], [[69,72,76,79],[65,69,72,76],[72,76,79,84],[67,71,74,79]], 3.2),
 ([[52,59,64,68],[49,56,61,64],[45,52,57,61],[47,54,59,63]], [[76,80,83,88],[73,76,80,85],[69,73,76,81],[71,75,78,83]], 2.8),
]

def upbeat_music(intensity=1.0):
    """Original cinematic motivational / hustle bed (dark trap-cinematic): half-time drums, heavy gliding 808, hi-hat rolls,
    slow string pad and a sparse piano motif in a big reverb, impact hits and risers. No samples, no licences.
    intensity 1 = full, ~0.6 = softer (news)."""
    r = random.Random(seed * 7 + 3); rs = np.random.RandomState(seed + 11)
    bpm = r.choice([152, 156, 160, 164]); beat = 60.0 / bpm; sp = beat / 4
    root = r.choice([45, 43, 41, 40, 38, 47])  # A, G, F, E, D, B (low minor keys)
    # minor-key cinematic progressions: (semitone offset of chord root, is_minor)
    prog = r.choice([[(0, 1), (-4, 0), (-9, 0), (-2, 0)], [(0, 1), (-2, 0), (-4, 0), (-2, 0)], [(0, 1), (-4, 0), (3, 0), (-2, 0)]])
    motif = r.choice([[7, 5, 3, 0], [12, 10, 7, 3], [3, 7, 10, 7], [0, 3, 7, 5]])
    def verb(x, sec=1.9, mix=.35):
        k = int(sec * SR); t = np.arange(k) / SR; ir = rs.randn(k) * np.exp(-t * 3.0)
        fr = np.fft.rfftfreq(k, 1 / SR); ir = np.fft.irfft(np.fft.rfft(ir) / (1 + (fr / 3500) ** 2), k)
        N = 1 << int(np.ceil(np.log2(len(x) + k)))
        w = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]
        return x + mix * w / (np.max(np.abs(w)) + 1e-9) * (np.max(np.abs(x)) + 1e-9)
    def put(buf, st, sig):
        st = int(st * SR)
        if st >= n or st < 0: return
        m = min(len(sig), n - st); buf[st:st + m] += sig[:m]
    def kick():
        k = int(.4 * SR); x = np.arange(k) / SR
        f = 42 + 140 * np.exp(-x * 40); ph = 2 * np.pi * np.cumsum(f) / SR
        return np.tanh(1.8 * np.sin(ph)) * np.exp(-x * 7.5) * (1 - np.exp(-x * 1500))
    def clap():
        k = int(.45 * SR); x = np.arange(k) / SR; nz = rs.randn(k)
        nz = nz - np.convolve(nz, np.ones(5) / 5, 'same')
        return .6 * nz * (np.exp(-x * 14) + .8 * np.exp(-((x - .01) * 120) ** 2) + .6 * np.exp(-((x - .024) * 120) ** 2))
    def hat(v=1.0, open_=False):
        k = int((.16 if open_ else .035) * SR); x = np.arange(k) / SR; nz = rs.randn(k)
        nz = nz - np.convolve(nz, np.ones(3) / 3, 'same')
        return v * (.16 if open_ else .12) * nz * np.exp(-x * (20 if open_ else 140))
    def b808(m, d, glide_to=None):
        k = int(d * SR); x = np.arange(k) / SR; f0 = hz(m)
        f = f0 * (1 + .0 * x) if glide_to is None else f0 * (hz(glide_to) / f0) ** np.clip(x / (d * .35), 0, 1)
        ph = 2 * np.pi * np.cumsum(f) / SR; w = np.tanh(1.9 * np.sin(ph)) + .1 * np.sin(2 * ph)
        return .75 * w * np.clip(x / .004, 0, 1) * np.clip((d - x) / .06, 0, 1) * np.exp(-x * 1.3)
    def strings(ms, d):
        k = int(d * SR); x = np.arange(k) / SR; w = np.zeros(k); cnt = 0
        for m in ms:
            f = hz(m)
            for dt in (-.0075, -.003, 0, .003, .0075):
                w += 2 * ((f * (1 + dt) * x + rs.rand()) % 1) - 1; cnt += 1
        w /= cnt; sp_ = np.fft.rfft(w); fr = np.fft.rfftfreq(k, 1 / SR)
        sp_ *= 1 / (1 + (fr / 1600) ** 4); w = np.fft.irfft(sp_, k)
        return .9 * w * np.clip(x / .5, 0, 1) * np.clip((d - x) / .6, 0, 1)
    def piano(m, d=1.6):
        k = int(d * SR); x = np.arange(k) / SR; f = hz(m)
        w = np.sin(2 * np.pi * f * x) + .28 * np.sin(4 * np.pi * f * x) + .1 * np.sin(6 * np.pi * f * x)
        return .22 * w * np.exp(-x * 2.6) * np.clip(x / .004, 0, 1)
    def impact(d=2.6):
        k = int(d * SR); x = np.arange(k) / SR
        boom = np.sin(2 * np.pi * (34 + 60 * np.exp(-x * 5)) * x) * np.exp(-x * 1.7)
        nz = rs.randn(k); fr = np.fft.rfftfreq(k, 1 / SR); nz = np.fft.irfft(np.fft.rfft(nz) / (1 + (fr / 900) ** 2), k)
        return 1.1 * boom + .5 * nz * np.exp(-x * 2.2) / (np.max(np.abs(nz)) + 1e-9) * 3
    def riser(d):
        k = int(d * SR); x = np.arange(k) / SR; nz = rs.randn(k); fr = np.fft.rfftfreq(k, 1 / SR)
        sp_ = np.fft.rfft(nz) / (1 + (fr / 2500) ** 2); nz = np.fft.irfft(sp_, k)
        nz = nz - np.convolve(nz, np.ones(int(.004 * SR)) / int(.004 * SR), 'same') * .5
        return .22 * nz / (np.max(np.abs(nz)) + 1e-9) * (x / d) ** 2.2
    bars = int(total / (4 * beat)) + 2
    drums = np.zeros(n); sub = np.zeros(n); pad = np.zeros(n); keys = np.zeros(n); fx = np.zeros(n); kick_t = []
    put(fx, 0, impact())
    for b in range(bars):
        t0 = b * 4 * beat; off, minor = prog[b % 4]; cr = root + off
        third = cr + (3 if minor else 4); fifth = cr + 7
        put(pad, t0, strings([cr + 24, third + 24, fifth + 24, cr + 36], 4 * beat + .6))
        # half-time drums: kick 1 and 2&, clap on 3, rolling hats
        for st in ((0, 0.75, 1.5, 2.75, 3.5) if b % 2 else (0, 1.5, 2.5, 3.25)):
            put(drums, t0 + st * beat, kick()); kick_t.append(t0 + st * beat)
        put(drums, t0 + 2 * beat, clap()); put(drums, t0 + 2 * beat, clap() * .5)
        if b % 4 == 3:
            for q in range(8): put(drums, t0 + 3 * beat + q * beat / 8, clap() * (.25 + .08 * q))
        for j in range(16):
            put(drums, t0 + j * beat / 4, hat((1.0 if j % 4 == 0 else .75 if j % 2 == 0 else .5), open_=(j == 14)))
        for j in range(8):
            if j in (3, 7) and b % 2 == 1:
                for q in range(4): put(drums, t0 + j * beat / 2 + q * beat / 8, hat(.45 + .15 * q))
        put(sub, t0, b808(cr - 12, beat * 1.45))
        put(sub, t0 + 1.5 * beat, b808(cr - 12, beat * 2.2, glide_to=cr - 12 - 5 if b % 4 == 3 else None))
        if b % 2 == 1: put(sub, t0 + 3.5 * beat, b808(cr - 12 + 7, beat * .5)); put(sub, t0 + 2.5 * beat, b808(cr - 12, beat * .6))
        for j, o in enumerate(motif):
            if (b % 2 == 0 and j < 3) or b % 2 == 1:
                put(keys, t0 + (j * 1.0 + (.5 if b % 2 else 0)) * beat, piano(cr + 24 + o + (0 if minor or o not in (3,) else 1)))
        if b % 8 == 7: put(fx, t0 + 2 * beat, riser(2 * beat))
        if b % 8 == 0 and b > 0: put(fx, t0, impact(1.8))
    atmos = verb(pad * .55 + keys * 1.0, 2.0, .45)
    duck = np.ones(n)
    for tk in kick_t:
        i = int(tk * SR)
        if i >= n: continue
        m = min(int(.4 * SR), n - i); duck[i:i + m] = np.minimum(duck[i:i + m], 1 - .5 * np.exp(-np.arange(m) / SR * 8))
    out = drums * (1.15 * intensity + .2) + sub * 1.45 + atmos * duck * (1.0 - .25 * intensity) + fx * (.6 + .3 * intensity)
    x = np.arange(n) / SR; out *= np.clip(np.minimum(1, x / .05), 0, 1) * np.clip(np.minimum(1, (total - x) / 1.5), 0, 1)
    out = np.tanh(1.15 * out / (np.max(np.abs(out)) + 1e-9))
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
music = upbeat_music(1.0 if MODE == "upbeat" else 0.6)  # every video gets the modern bed; calm = a softer mix
d = int(.29 * SR); echo = np.zeros_like(music); echo[d:] = music[:-d] * .35

x = np.arange(n) / SR

win = max(1, int(.25 * SR)); env = np.convolve(np.abs(voice), np.ones(win) / win, 'same')
music *= 1 - .45 * np.clip(env / 0.05, 0, 1)
music /= np.max(np.abs(music)) + 1e-9
if np.max(np.abs(voice)) > 0: voice /= np.max(np.abs(voice))
mix = 0.92 * voice + (0.27 if MODE == "upbeat" else 0.2) * music
mix /= max(1, np.max(np.abs(mix)) / 0.95)
sf.write(os.path.join(wd, "mix.wav"), mix, SR)
print(json.dumps({"audio": round(total, 2)}))
