"""Sintesi procedurale dei suoni di "The Rake" (richiede numpy e ffmpeg).

Produce build/audio/Ambience.ogg (loop notturno di 60 s) e build/audio/Sfx.ogg (foglio di effetti:
ogni effetto occupa un intervallo fisso, riprodotto in gioco con Sound.PlaybackRegion).
Gli intervalli sono elencati in SEGMENTS e copiati in src/shared/Assets.luau da upload_audio.py.
"""
import json
import os
import subprocess
import sys

import numpy as np

SR = 44100
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "build", "audio")
rng = np.random.default_rng(13)


def t_axis(d):
    return np.arange(int(d * SR)) / SR


def noise(d, color="white"):
    n = rng.standard_normal(int(d * SR))
    if color == "white":
        return n
    spec = np.fft.rfft(n)
    f = np.fft.rfftfreq(len(n), 1 / SR)
    f[0] = 1
    spec /= f ** (0.5 if color == "pink" else 1.0)
    out = np.fft.irfft(spec, len(n))
    return out / (np.abs(out).max() + 1e-9)


def band(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    mask = np.clip((f - lo) / (lo * 0.3 + 1), 0, 1) * np.clip((hi - f) / (hi * 0.3 + 1), 0, 1)
    return np.fft.irfft(spec * mask, len(x))


def env(n, attack, release, total=None):
    total = total or n / SR
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(attack, 1e-4))
    e *= np.clip((total - t) / max(release, 1e-4), 0, 1)
    return e


def reverb(x, decay=1.6, mix=0.35, predelay=0.02):
    ir_len = int(decay * SR)
    ir = rng.standard_normal(ir_len) * np.exp(-np.arange(ir_len) / SR * 6.9 / decay)
    ir = band(ir, 200, 6000)
    ir[: int(predelay * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum()) + 1e-9
    wet = np.fft.irfft(np.fft.rfft(x, len(x) + ir_len) * np.fft.rfft(ir, len(x) + ir_len))[: len(x)]
    return x * (1 - mix) + wet * mix * 3


def norm(x, peak=0.9):
    return x / (np.abs(x).max() + 1e-9) * peak


def saw(freq, t):
    phase = np.cumsum(freq / SR)
    return 2 * (phase % 1) - 1


def sine(freq, t):
    return np.sin(2 * np.pi * np.cumsum(freq / SR))


# ---------------------------------------------------------------------------------------------
# Effetti


def screech(d=1.7):
    t = t_axis(d)
    f0 = 900 + 700 * np.exp(-t * 3) + 120 * np.sin(2 * np.pi * 9 * t)
    voices = sum(saw(f0 * r, t) for r in (1.0, 1.013, 0.987, 1.5, 2.02))
    grit = band(noise(d), 1500, 7000) * 0.8
    x = np.tanh((voices * 0.5 + grit) * 3)
    x = band(x, 400, 9000) * env(len(t), 0.03, 0.6)
    return norm(reverb(x, 1.8, 0.4))


def call(d=2.8):
    t = t_axis(d)
    f0 = 420 + 260 * np.sin(np.pi * t / d) + 25 * np.sin(2 * np.pi * 6.5 * t)
    x = sine(f0, t) + 0.5 * sine(f0 * 2.01, t) + 0.3 * saw(f0 * 0.5, t)
    x += band(noise(d), 800, 3000) * 0.25
    x = np.tanh(x * 1.5) * env(len(t), 0.3, 1.0)
    clicks = np.zeros_like(t)
    for c in np.linspace(0.1, d - 0.4, 9):
        i = int(c * SR)
        clicks[i:i + 300] += np.hanning(300) * rng.uniform(0.5, 1)
    x = band(x, 150, 5000) + band(clicks * noise(d), 1000, 6000) * 0.6
    return norm(reverb(x, 2.6, 0.55))


def snap(d=0.5):
    t = t_axis(d)
    x = band(noise(d), 1200, 8000) * np.exp(-t * 60)
    x += band(noise(d), 300, 1500) * np.exp(-t * 25) * 0.6
    x[int(0.05 * SR):] += band(noise(d - 0.05), 2000, 9000) * np.exp(-t[: len(t) - int(0.05 * SR)] * 80) * 0.5
    return norm(reverb(x, 1.2, 0.3))


def heartbeat(d=1.6):
    t = t_axis(d)
    x = np.zeros_like(t)
    for start, amp in ((0.0, 1.0), (0.28, 0.7), (0.8, 1.0), (1.08, 0.7)):
        i = int(start * SR)
        n = int(0.18 * SR)
        tt = np.arange(n) / SR
        thump = np.sin(2 * np.pi * (55 - 20 * tt / 0.18) * tt) * np.exp(-tt * 22)
        x[i:i + n] += thump[: len(x) - i] * amp
    return norm(np.tanh(x * 2))


def static(d=4.0):
    x = band(noise(d), 300, 9000) * 0.6
    crackle = (rng.random(len(x)) > 0.9985) * rng.standard_normal(len(x)) * 4
    hum = np.sin(2 * np.pi * 60 * t_axis(d)) * 0.08
    x = x + band(crackle, 1000, 9000) + hum
    return norm(x, 0.7)


def rain(d=4.0):
    x = band(noise(d, "pink"), 400, 9000)
    drops = (rng.random(len(x)) > 0.997) * rng.standard_normal(len(x))
    x += band(drops, 2000, 9000) * 2
    return norm(x, 0.7)


def click(d=0.35):
    t = t_axis(d)
    x = band(noise(d), 2000, 9000) * np.exp(-t * 300)
    x[int(0.08 * SR):] += band(noise(d - 0.08), 1500, 7000)[: len(x) - int(0.08 * SR)] * np.exp(-t[: len(x) - int(0.08 * SR)] * 200) * 0.7
    beep = np.sin(2 * np.pi * 2400 * t) * ((t > 0.15) & (t < 0.25)) * 0.3
    return norm(x + beep, 0.8)


def breathing(d=3.0):
    t = t_axis(d)
    x = np.zeros_like(t)
    for k in range(4):
        start = k * 0.75
        i = int(start * SR)
        n = int(0.6 * SR)
        e = np.sin(np.linspace(0, np.pi, n)) ** 2
        lo, hi = (500, 2500) if k % 2 == 0 else (300, 1800)
        x[i:i + n] += band(noise(0.6), lo, hi)[:n] * e * (1.0 if k % 2 == 0 else 0.7)
    return norm(x, 0.8)


def steps(d=2.0):
    x = np.zeros(int(d * SR))
    for k in range(4):
        i = int((0.05 + k * 0.5 + rng.uniform(-0.02, 0.02)) * SR)
        n = int(0.35 * SR)
        tt = np.arange(n) / SR
        crunch = band(noise(0.35), 500, 6000) * np.exp(-tt * 12) * (rng.random(n) > 0.4)
        thud = np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 30) * 1.5
        x[i:i + n] += (crunch + thud)[: len(x) - i]
    return norm(reverb(x, 0.8, 0.2), 0.85)


def whisper(d=2.4):
    t = t_axis(d)
    x = band(noise(d), 1500, 6000) * (0.5 + 0.5 * np.sin(2 * np.pi * 3.3 * t) ** 2)
    drone = sine(55 + 3 * np.sin(2 * np.pi * 0.5 * t), t) * 0.6 + sine(82.5, t) * 0.3
    x = (x * 0.6 + drone) * env(len(t), 0.4, 0.9)
    return norm(reverb(x, 2.5, 0.5))


def torch_click(d=0.25):
    t = t_axis(d)
    x = band(noise(d), 2500, 9000) * np.exp(-t * 400)
    return norm(x, 0.7)


def dart_shot(d=0.6):
    t = t_axis(d)
    x = band(noise(d), 600, 7000) * np.exp(-t * 28)
    x += np.sin(2 * np.pi * 140 * t) * np.exp(-t * 40) * 0.8
    x[int(0.12 * SR):] += band(noise(d - 0.12), 2000, 6000)[: len(x) - int(0.12 * SR)] * np.exp(-t[: len(x) - int(0.12 * SR)] * 50) * 0.3
    return norm(reverb(x, 0.6, 0.15), 0.9)


def jaw_clicks(d=1.6):
    x = np.zeros(int(d * SR))
    k = 0.0
    while k < d - 0.05:
        i = int(k * SR)
        n = int(0.025 * SR)
        x[i:i + n] += band(noise(0.025), 1500, 7000)[:n] * np.hanning(n) * rng.uniform(0.5, 1)
        k += rng.uniform(0.03, 0.09) if rng.random() > 0.15 else rng.uniform(0.15, 0.3)
    return norm(reverb(x, 0.9, 0.3), 0.85)


def growl(d=2.2):
    t = t_axis(d)
    f0 = 70 + 15 * np.sin(2 * np.pi * 1.3 * t) + 8 * rng.standard_normal(len(t)).cumsum() / SR * 30
    x = saw(f0, t) * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * t) ** 2)
    x += band(noise(d), 200, 1200) * 0.6
    x = np.tanh(band(x, 60, 1800) * 3) * env(len(t), 0.25, 0.7)
    return norm(reverb(x, 1.4, 0.3), 0.9)


def bone_crack(d=0.45):
    x = np.zeros(int(d * SR))
    for k in range(rng.integers(3, 6)):
        i = int(rng.uniform(0, 0.25) * SR)
        n = int(0.04 * SR)
        x[i:i + n] += band(noise(0.04), 900, 6000)[:n] * np.exp(-np.arange(n) / SR * 120)
    return norm(x, 0.9)


def watch_beep(d=0.3):
    t = t_axis(d)
    x = np.sin(2 * np.pi * 3100 * t) * ((t < 0.07) | ((t > 0.12) & (t < 0.19)))
    return norm(x * np.exp(-t * 3), 0.5)


def scope_zoom(d=0.4):
    t = t_axis(d)
    x = band(noise(d), 1500, 5000) * np.exp(-((t - 0.15) / 0.08) ** 2) * 0.6
    x += np.sin(2 * np.pi * (900 + 600 * t) * t) * np.exp(-t * 12) * 0.2
    return norm(x, 0.6)


SEGMENTS2 = [
    ("DartShot", dart_shot, 0.0, False),
    ("JawClicks", jaw_clicks, 1.0, False),
    ("Growl", growl, 3.0, False),
    ("BoneCrack", bone_crack, 6.0, False),
    ("WatchBeep", watch_beep, 7.0, False),
    ("ScopeZoom", scope_zoom, 8.0, False),
]

SEGMENTS = [
    ("Screech", screech, 0.0, False),
    ("Call", call, 3.0, False),
    ("Snap", snap, 7.0, False),
    ("Heartbeat", heartbeat, 9.0, True),
    ("Static", static, 12.0, True),
    ("Rain", rain, 17.0, True),
    ("TrapClick", click, 22.0, False),
    ("Breathing", breathing, 24.0, True),
    ("Steps", steps, 28.0, True),
    ("Whisper", whisper, 31.0, False),
    ("TorchClick", torch_click, 34.5, False),
]


def ambience(d=60.0):
    t = t_axis(d)
    wind = band(noise(d, "brown"), 60, 900)
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * t / 17) * np.sin(2 * np.pi * t / 7.3 + 1)
    x = wind * gust * 0.9
    leaves = band(noise(d), 2500, 8000) * np.clip(gust - 0.6, 0, 1) * 0.5
    x += leaves
    # grilli: impulsi ad alta frequenza ritmici, con pause
    chirp = np.sin(2 * np.pi * 4300 * t) * (np.sin(2 * np.pi * 28 * t) > 0.3) * (np.sin(2 * np.pi * 0.9 * t) > -0.2)
    chirp *= (0.5 + 0.5 * np.sin(2 * np.pi * t / 23)) * 0.06
    chirp2 = np.sin(2 * np.pi * 5100 * t) * (np.sin(2 * np.pi * 31 * t + 2) > 0.4) * (np.sin(2 * np.pi * 0.7 * t + 1) > 0.1) * 0.04
    x += chirp + chirp2
    # civetta lontana e scricchiolii
    for start in (9.0, 38.5):
        i = int(start * SR)
        for k, (off, f) in enumerate(((0, 380), (0.45, 360), (0.75, 330))):
            n = int(0.35 * SR)
            tt = np.arange(n) / SR
            hoot = np.sin(2 * np.pi * (f + 15 * np.sin(2 * np.pi * 5 * tt)) * tt) * np.sin(np.linspace(0, np.pi, n)) ** 2
            j = i + int(off * SR)
            x[j:j + n] += band(hoot, 200, 900) * 0.12
    for start in (21.0, 47.0):
        i = int(start * SR)
        n = int(1.2 * SR)
        tt = np.arange(n) / SR
        creak = saw(np.full(n, 90 + 40 * np.sin(np.pi * tt / 1.2)), tt) * np.sin(np.linspace(0, np.pi, n)) * 0.1
        x[i:i + n] += band(creak, 200, 2500)
    x = reverb(x, 2.5, 0.3)
    # chiusura del loop con dissolvenza incrociata
    fade = int(2.0 * SR)
    x[:fade] = x[:fade] * np.linspace(0, 1, fade) + x[-fade:] * np.linspace(1, 0, fade)
    x = x[:-fade]
    return norm(x, 0.8)


def encode(samples, path):
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "libvorbis", "-q:a", "5", path], input=pcm, check=True)


def build_sheet(segments, total, path):
    data = np.zeros(int(total * SR))
    regions = {}
    for name, fn, start, loop in segments:
        clip = fn()
        i = int(start * SR)
        data[i:i + len(clip)] += clip
        regions[name] = {"start": start, "length": round(len(clip) / SR, 3), "loop": loop}
    encode(data, path)
    return regions


def main():
    os.makedirs(OUT, exist_ok=True)
    if "--sheet2" in sys.argv:
        regions2 = build_sheet(SEGMENTS2, 9.0, os.path.join(OUT, "Sfx2.ogg"))
        json.dump(regions2, open(os.path.join(OUT, "regions2.json"), "w"), indent=1)
        print("Creato Sfx2.ogg")
        return
    total = 36.0
    sheet = np.zeros(int(total * SR))
    regions = {}
    for name, fn, start, loop in SEGMENTS:
        clip = fn()
        i = int(start * SR)
        sheet[i:i + len(clip)] += clip
        regions[name] = {"start": start, "length": round(len(clip) / SR, 3), "loop": loop}
    encode(sheet, os.path.join(OUT, "Sfx.ogg"))
    encode(ambience(), os.path.join(OUT, "Ambience.ogg"))
    json.dump(regions, open(os.path.join(OUT, "regions.json"), "w"), indent=1)
    print("Creati Sfx.ogg e Ambience.ogg")


if __name__ == "__main__":
    sys.exit(main())
