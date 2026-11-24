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

def upbeat_music(intensity=1.0):
    """Original modern TikTok-style motivational bed: punchy kick with side-chain pump, snap, bouncy hats, sub bass,
    warm detuned pad, catchy plucked hook with echo. No samples, no licences. intensity 1 = full, ~0.6 = softer (news)."""
    r = random.Random(seed * 7 + 3); rs = np.random.RandomState(seed + 11)
    bpm = r.choice([100, 104, 108, 112, 116, 120]); beat = 60.0 / bpm; sp = beat / 4
    root = r.choice([57, 55, 53, 52, 50, 48])
    # I - V - vi - IV (uplifting), or vi - IV - I - V (emotional-motivational): (root offset, minor?)
    prog = r.choice([[(0, 0), (7, 0), (9, 1), (5, 0)], [(9, 1), (5, 0), (0, 0), (7, 0)], [(0, 0), (9, 1), (5, 0), (7, 0)]])
    out = np.zeros(n); kick_t = []
    def put(buf, st, sig):
        st = int(st * SR)
        if st >= n or st < 0: return
        m = min(len(sig), n - st); buf[st:st + m] += sig[:m]
    def kick():
        k = int(.32 * SR); x = np.arange(k) / SR
        f = 45 + 150 * np.exp(-x * 45); ph = 2 * np.pi * np.cumsum(f) / SR
        return 1.0 * np.tanh(1.6 * np.sin(ph)) * np.exp(-x * 9) * (1 - np.exp(-x * 1200))
    def snap():
        k = int(.25 * SR); x = np.arange(k) / SR; nz = rs.randn(k)
        nz = nz - np.convolve(nz, np.ones(5) / 5, 'same')
        body = np.sin(2 * np.pi * 190 * x) * np.exp(-x * 30) * .5
        return .55 * nz * (np.exp(-x * 20) + .5 * np.exp(-((x - .011) * 150) ** 2)) + body
    def hat(open_=False, v=1.0):
        k = int((.14 if open_ else .04) * SR); x = np.arange(k) / SR; nz = rs.randn(k)
        nz = nz - np.convolve(nz, np.ones(3) / 3, 'same')
        return v * (.2 if open_ else .14) * nz * np.exp(-x * (22 if open_ else 110))
    def sub(m, d):
        k = int(d * SR); x = np.arange(k) / SR; f = hz(m)
        w = np.tanh(1.3 * np.sin(2 * np.pi * f * x)) + .12 * np.sin(4 * np.pi * f * x)
        return .62 * w * np.clip(x / .006, 0, 1) * np.clip((d - x) / .05, 0, 1) * np.exp(-x * 1.6)
    def pad(ms, d):
        k = int(d * SR); x = np.arange(k) / SR; w = np.zeros(k)
        for m in ms:
            f = hz(m)
            for dt in (-.006, 0, .006):
                w += 2 * ((f * (1 + dt) * x) % 1) - 1
        w /= (3 * len(ms)); sp_ = np.fft.rfft(w); fr = np.fft.rfftfreq(k, 1 / SR)
        sp_ *= 1 / (1 + (fr / 2200) ** 4); w = np.fft.irfft(sp_, k)
        return .5 * w * np.clip(x / .12, 0, 1) * np.clip((d - x) / .25, 0, 1)
    def pluck(m, d=.5):
        k = int(d * SR); x = np.arange(k) / SR; f = hz(m)
        w = np.sin(2 * np.pi * f * x) + .45 * np.sin(4 * np.pi * f * x) + .22 * np.sin(6 * np.pi * f * x) + .08 * np.sin(8 * np.pi * f * x)
        return .17 * w * np.exp(-x * 7.5) * np.clip(x / .003, 0, 1)
    hook = [[0, None, 4, None, 7, None, 4, 2], [0, None, 4, 7, 12, None, 7, 4], [2, None, 7, None, 9, 7, 4, None], [0, 4, 7, None, 4, None, 2, 0]]
    hook = hook[r.randrange(len(hook))]
    bars = int(total / (4 * beat)) + 2
    drums = np.zeros(n); bassb = np.zeros(n); padb = np.zeros(n); leadb = np.zeros(n)
    for b in range(bars):
        t0 = b * 4 * beat; off, minor = prog[b % 4]; cr = root + off
        third = cr + (3 if minor else 4); fifth = cr + 7
        put(padb, t0, pad([cr, third, fifth, cr + 12], 4 * beat + .1))
        for q in range(4):
            tb = t0 + q * beat
            put(drums, tb, kick()); kick_t.append(tb)
            if q in (1, 3): put(drums, tb, snap())
            put(drums, tb + 2 * sp, hat(True, .9))
            for j in range(4): put(drums, tb + j * sp, hat(False, 1.0 if j % 2 == 0 else .55))
            if b % 2 == 1 and q == 3: put(drums, tb + 3 * sp, hat(False, .9)); put(drums, tb + 2.5 * sp, hat(False, .8))
        for st, d in ((0, 1.4), (1.5, .45), (2, 1.0), (3.5, .45)):
            put(bassb, t0 + st * beat, sub(cr - 24, d * beat))
        for j, o in enumerate(hook):
            if o is None: continue
            put(leadb, t0 + j * 2 * sp, pluck(cr + 12 + o + (0 if third - cr == 4 or o not in (4,) else -1)))
    # echo on the lead (dotted eighth) for width
    de = int(beat * .75 * SR); echo = np.zeros_like(leadb); echo[de:] = leadb[:-de] * .38; leadb = leadb + echo
    # side-chain pump: everything except drums ducks on each kick
    duck = np.ones(n)
    for tk in kick_t:
        i = int(tk * SR)
        if i >= n: continue
        m = min(int(.35 * SR), n - i); duck[i:i + m] = np.minimum(duck[i:i + m], 1 - .62 * np.exp(-np.arange(m) / SR * 9))
    body = (bassb * .9 + padb * .55 + leadb * 1.0) * duck
    out = drums * (.9 * intensity + .1) + body * (.75 + .25 * intensity)
    x = np.arange(n) / SR; out *= np.minimum(1, x / .12) * np.clip(np.minimum(1, (total - x) / 1.2), 0, 1)
    out = np.tanh(1.25 * out / (np.max(np.abs(out)) + 1e-9))
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
