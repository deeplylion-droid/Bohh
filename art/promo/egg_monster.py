"""Uovo-mostro (EggMonster) per l'icona del gioco: "Chi c'e' dentro?".

Un grande uovo rosso a macchie con una crepa a zig-zag tutt'intorno che si apre come una bocca:
la calotta superiore si solleva all'indietro (cerniera sul retro, leggermente storta per un ghigno
asimmetrico) e le punte della crepa sono dentini aguzzi bianchi su entrambe le "mascelle". Dentro e'
buio (fodera scura) e due occhi gialli incandescenti con la pupilla a fessura e le palpebre aggrottate
sbirciano fuori; un corpo scuro riempie il fondo della cavita'. Tocco "toy horror": due crepe ricucite
con punti a X di filo bianco sul guscio.

Uso (dalla cartella art/): ../.tools/venv/bin/python promo/egg_monster.py
Uscita: art/out/promo/EggMonster/ (EggMonster.blend/.fbx/.json e anteprime). Variabili: OPEN (gradi di
apertura della calotta, 30), VIEWS (3q,front), RES (700), DRAFT=1 (voxel piu' grossi per iterare).
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART))
sys.path.insert(0, str(ART / "eggs"))
import eggs as E  # noqa: E402  (forma dell'uovo e macchie, riusate dagli uovi del gioco)
from lib.sdf import SDF, Frame, capsule, ellipsoid, project, sphere, tube, union  # noqa: E402
from lib.toy import Model  # noqa: E402

DRAFT = os.environ.get("DRAFT", "") == "1"
VX = 1.4 if DRAFT else 1.0
OPEN = float(os.environ.get("OPEN", 30))  # apertura della bocca (gradi)
TILT = float(os.environ.get("TILT", 7))  # calotta storta (gradi attorno all'asse avanti-dietro)

R, H = E.R, E.H  # 1.15, 3.1: lo stesso uovo del gioco
T = 0.1  # spessore del guscio
ZC = 1.66  # quota media della crepa
N = 13  # punte della crepa sul giro completo
SHELL = E.shell()

SHELL_RED = (232, 40, 56)  # rosso vivo: i denti bianchi e il buio della bocca risaltano (come nelle icone)
SPOT = (140, 14, 40)
SPOT2 = (255, 140, 132)
TOOTH = (252, 250, 244)
DARK = (30, 14, 38)
CREATURE = (20, 10, 26)
EYE = (255, 212, 52)
PUPIL = (26, 6, 8)
THREAD = (255, 250, 240)  # filo bianco, come le cuciture dell'interfaccia
CRACK = (62, 30, 34)


def radius_at(z: float) -> float:
    """Raggio del profilo dell'uovo alla quota z (stessa formula di lib.sdf.egg)."""
    u = 2.0 * z / H - 1.0
    return R * math.sqrt(max(1.0 - u * u, 0.0)) * (1.0 - 0.2 * u)


def phi_of(p: np.ndarray) -> np.ndarray:
    """Angolo attorno all'asse verticale: 0 davanti (-Y), positivo verso +X."""
    return np.arctan2(p[:, 0], -p[:, 1])


def amp(ph):
    """Altezza delle punte: grandi davanti, piccole vicino alla cerniera; un po' irregolari."""
    front = (0.5 + 0.5 * np.cos(ph)) ** 0.8
    jitter = 1.0 + 0.1 * np.sin(3 * ph + 1.3) + 0.07 * np.sin(5 * ph + 0.4)
    return (0.09 + 0.21 * front) * jitter


def zig(ph):
    """Onda triangolare: +1 = punta della mascella inferiore, -1 = punta della calotta (davanti: un dente
    in basso al centro e due zanne in alto ai suoi lati)."""
    return (2 / math.pi) * np.arcsin(np.clip(np.cos(N * ph), -1, 1))


def split_sdf(sign: float, gap: float = 0.012) -> SDF:
    """Semispazio sotto (sign=+1) o sopra (sign=-1) la crepa a zig-zag, con distanza normalizzata."""
    slope = 0.3 * N * 2 / (math.pi * 1.05)
    norm = math.sqrt(1 + slope * slope)

    def f(p):
        ph = phi_of(p)
        d = (p[:, 2] - (ZC + amp(ph) * zig(ph))) / norm
        return (sign * d + gap).astype(np.float32)

    return SDF(f, (-3, -3, -1), (3, 3, H + 1))


def zband(z0: float, z1: float) -> SDF:
    return SDF(lambda p: np.maximum(z0 - p[:, 2], p[:, 2] - z1).astype(np.float32), (-3, -3, z0), (3, 3, z1))


def lid_transform(shape: SDF) -> SDF:
    """Apre la calotta: rotazione attorno alla cerniera sul retro (asse X), piu' un filo di inclinazione."""
    hinge = (0.0, radius_at(ZC) - T * 0.5, ZC)
    return shape.rot(-OPEN, 0, 0, pivot=hinge).rot(0, TILT, 0, pivot=(0.0, hinge[1], ZC + 0.2))


def spots_away(base: SDF, n: int, rmin: float, rmax: float, seed: int, keep_out: float = 0.38) -> SDF:
    """Come eggs.spots ma senza macchie a cavallo della crepa (verrebbero tagliate a meta')."""
    rng = np.random.default_rng(seed + 1)
    placed = []
    for d in E.surface_dirs(n * 6, seed, -0.75, 0.95):
        p, _ = project(base, E.CENTER, d)
        r = float(rng.uniform(rmin, rmax))
        if abs(float(p[2]) - ZC) < r + keep_out:
            continue
        if all(np.linalg.norm(p - q) > (r + rq) * 1.15 for q, rq in placed):
            placed.append((p, r))
        if len(placed) >= n:
            break
    return union(*[sphere(r, p) for p, r in placed])


def stitched_crack(base: SDF, center_dir, length: float, angle: float, seed: int, n_stitch: int = 4):
    """Crepa ricucita sulla superficie: (solco scuro, punti a X). angle = inclinazione sul guscio (gradi)."""
    rng = np.random.default_rng(seed)
    fr = Frame(base, E.CENTER, center_dir, sink=0.0)
    a = math.radians(angle)
    tang = np.array([math.cos(a), 0.0, math.sin(a)])  # nel piano locale X-Z (Y locale = fuori dal guscio)
    side = np.array([-math.sin(a), 0.0, math.cos(a)])
    pts = []
    n = 7
    for i in range(n + 1):
        t = (i / n - 0.5) * length
        jig = (0.07 if 0 < i < n else 0.0) * (1 if i % 2 else -1) * (0.6 + 0.6 * rng.random())
        loc = tang * t + side * jig
        pts.append(fr.point(loc))
    # riporta i punti sulla superficie
    surf = []
    for q in pts:
        p, nrm = project(base, E.CENTER, np.asarray(q) - np.asarray(E.CENTER))
        surf.append(tuple(np.asarray(p) - np.asarray(nrm) * 0.012))
    radii = [0.012] + [0.03] * (len(surf) - 2) + [0.012]
    groove = tube(surf, radii)
    stitches = []
    for i in range(n_stitch):
        t = ((i + 0.5) / n_stitch - 0.5) * length * 0.9
        for sgn in (-1, 1):
            p0 = tang * (t - 0.06) + side * (0.1 * sgn)
            p1 = tang * (t + 0.06) + side * (-0.1 * sgn)
            q0, n0 = project(base, E.CENTER, fr.point(p0) - np.asarray(E.CENTER))
            q1, n1 = project(base, E.CENTER, fr.point(p1) - np.asarray(E.CENTER))
            stitches.append(capsule(tuple(q0 + n0 * 0.008), tuple(q1 + n1 * 0.008), 0.024))
    return groove, union(*stitches)


def build() -> Model:
    m = Model("EggMonster", "promo", voxel=0.02 * VX)
    s = SHELL
    hollow = s.subtract(s.offset(-T))
    # denti: le punte della crepa oltre la linea media, piu' spesse del guscio (smalto) e con gli spigoli
    # arrotondati, cosi' sembrano dentini e non schegge
    thick = s.offset(0.014).subtract(s.offset(-T - 0.06))
    below, above = split_sdf(+1), split_sdf(-1)
    # parti colorate del guscio: fino alla linea media della crepa (le punte oltre sono denti)
    low_shell = hollow.intersect(below).intersect(zband(-1, ZC - 0.012))
    top_shell = hollow.intersect(above).intersect(zband(ZC + 0.012, H + 1))
    low_teeth = thick.intersect(below, k=0.012).intersect(zband(ZC + 0.012, H), k=0.02)
    top_teeth = thick.intersect(above, k=0.012).intersect(zband(-1, ZC - 0.012), k=0.02)
    # buio dentro l'uovo: due pieni scuri (fondo e sotto la calotta) appena dentro il guscio
    fill = s.offset(-T + 0.006)
    low_fill = fill.intersect(zband(-1, ZC - 0.07))
    top_fill = fill.intersect(zband(ZC + 0.07, H + 1))

    # macchie (come l'uovo comune) e crepe ricucite: vanno disegnate a calotta chiusa
    lift = s.offset(0.012)
    paint = lift.subtract(s.offset(-0.05))
    spots_big = paint.intersect(spots_away(s, 14, 0.12, 0.22, seed=7))
    spots_small = paint.intersect(spots_away(s, 12, 0.06, 0.1, seed=19))
    crack_a, stitch_a = stitched_crack(s, (-0.85, -0.55, 0.62), 0.75, 62, seed=3)  # sulla calotta, a sinistra
    crack_b, stitch_b = stitched_crack(s, (0.82, -0.6, -0.25), 0.62, -55, seed=9, n_stitch=3)  # in basso a destra

    def top(x):
        return lid_transform(x.intersect(zband(ZC + 0.1, H + 1)))

    def low(x):
        return x.intersect(zband(-1, ZC - 0.1))

    m.add("Shell", union(low_shell, lid_transform(top_shell)), SHELL_RED, tris=10000, voxel=0.024 * VX)
    m.add("Teeth", union(low_teeth, lid_transform(top_teeth)), TOOTH, role="detail", tris=3000, voxel=0.012 * VX)
    m.add("Inside", union(low_fill, lid_transform(top_fill)), DARK, role="eye", tris=2500, voxel=0.03 * VX)
    m.add("Spots", union(low(spots_big), top(spots_big)), SPOT, role="detail", tris=2000, voxel=0.014 * VX)
    m.add("Spots2", union(low(spots_small), top(spots_small)), SPOT2, role="detail", tris=1200, voxel=0.013 * VX)
    m.add("Cracks", union(top(crack_a), low(crack_b)), CRACK, role="detail", tris=900, voxel=0.011 * VX)
    m.add("Stitches", union(top(stitch_a), low(stitch_b)), THREAD, role="detail", tris=900, voxel=0.011 * VX)

    # la creatura nel buio: testa scura, palpebre aggrottate, occhi gialli incandescenti con pupilla a fessura
    rf = radius_at(ZC + 0.45)
    ey = -(rf - 0.36)  # occhi arretrati dentro il guscio
    ez = ZC + 0.44
    head = ellipsoid((0.72, 0.42, 0.42), (0.0, ey + 0.34, ez - 0.02))
    eyes, pupils, lids = [], [], []
    for sx in (-1, 1):
        c = (sx * 0.3, ey, ez)
        eye = ellipsoid((0.22, 0.12, 0.16)).rot(0, sx * 14, 0).translate(c)
        eyes.append(eye)
        pupils.append(ellipsoid((0.035, 0.05, 0.12)).rot(0, sx * 6, 0).translate((c[0] + sx * 0.01, c[1] - 0.1, c[2] - 0.005)))
        # palpebra superiore: copre la parte alta dell'occhio, inclinata verso il centro (sguardo cattivo)
        lid = ellipsoid((0.27, 0.16, 0.1)).rot(0, -sx * 24, 0).translate((c[0] - sx * 0.02, c[1] - 0.02, c[2] + 0.12))
        lids.append(lid)
    # corpo scuro che riempie il fondo della cavita' (dalle fessure laterali non si vede attraverso l'uovo)
    body = ellipsoid((0.95, 0.8, 0.62), (0.0, 0.22, ZC + 0.18)).intersect(s.offset(-T - 0.012))
    m.add("Creature", union(head, *lids, k=0.04).union(body, k=0.12), CREATURE, role="eye", tris=2200, voxel=0.018 * VX)
    m.add("Eyes", union(*eyes).subtract(union(*lids)), EYE, material="Neon", role="glow", tris=900, voxel=0.011 * VX)
    m.add("Pupils", union(*pupils).subtract(union(*lids)), PUPIL, role="eye", tris=500, voxel=0.009 * VX)
    m.meta["promo"] = "icona: uovo-mostro"
    return m


if __name__ == "__main__":
    build().build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
