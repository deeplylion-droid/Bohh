"""Uovissimo Imperatore - pet Divino (creatura meme originale).

Un uovo d'oro lucido che si crede imperatore: corona ingioiellata, mantello rosso con bordo di
ermellino (bianco a codine nere), baffi arricciati, scettro con gemma, guanti bianchi.
Carattere: lo sbruffone - mento all'insu', palpebre pesanti a meta', un sopracciglio alzato,
sorrisetto storto con un dente d'oro, la mano infilata nel colletto e una crepa ricucita sul guscio.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, capsule, egg, ellipsoid, euler, look_matrix,  # noqa: E402
                     project, round_cone, sphere, tube, union)
from lib.toy import Model  # noqa: E402

GOLD_EGG = (255, 184, 26)
GOLD_CROWN = (255, 166, 22)
RUBY = (214, 12, 48)
SAPPHIRE = (30, 70, 220)
VELVET = (176, 12, 40)
ERMINE = (255, 253, 248)
ERMINE_DOT = (24, 22, 30)
MUSTACHE = (60, 30, 18)
GEM_GLOW = (236, 22, 58)
EYE = (26, 18, 28)
WHITE = (255, 255, 255)
MOUTH = (60, 20, 22)

m = Model("UovissimoImperatore", "pet")


# ---------------------------------------------------------------- helper locali
def normal_at(base, p, eps=1e-3):
    p = np.asarray(p, dtype=np.float32)
    g = np.array([base((p + e)[None, :])[0] - base((p - e)[None, :])[0]
                  for e in np.eye(3, dtype=np.float32) * eps])
    return g / max(np.linalg.norm(g), 1e-9)


def stitches(base, pts, n, dash, r, across=True, lift=0.006):
    """Punti di cucitura (trattini) lungo una polilinea che sta sulla superficie."""
    pts = np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0.0, s[-1], n):
        i = min(np.searchsorted(s, t, side="right") - 1, len(seg) - 1)
        w = (t - s[i]) / max(seg[i], 1e-9)
        p = pts[i] * (1 - w) + pts[i + 1] * w
        tan = (pts[i + 1] - pts[i]) / max(seg[i], 1e-9)
        nrm = normal_at(base, p)
        d = np.cross(nrm, tan) if across else tan - nrm * float(tan @ nrm)
        d /= np.linalg.norm(d)
        c = p + nrm * lift
        out.append(capsule(c - d * dash * 0.5, c + d * dash * 0.5, r))
    return union(*out)


def on_surf(base, src, q):
    """Punto (e normale) della superficie colpito andando da src (interno) verso q."""
    src = np.asarray(src, dtype=np.float64)
    return project(base, src, np.asarray(q, dtype=np.float64) - src)


# ---------------------------------------------------------------- uovo (mento all'insu')
Z0 = 0.2
EH = 2.3
ER = 1.0
TAPER = 0.22
TILT = (-6.0, 0.0, 0.0)
PIV = (0.0, 0.0, 0.95)
RT = euler(*TILT)


def tilted(p):
    return RT @ (np.asarray(p, dtype=np.float32) - np.asarray(PIV, dtype=np.float32)) + np.asarray(PIV, dtype=np.float32)


def egg_r(z):
    t = np.clip((z - Z0) / EH, 0.0, 1.0)
    u = 2.0 * t - 1.0
    return ER * np.sqrt(np.clip(1.0 - u * u, 0.0, 1.0)) * (1.0 - TAPER * u)


shell = egg(ER, EH, TAPER).translate((0, 0, Z0)).rot(*TILT, pivot=PIV)
legs = []
for sx in (1, -1):
    legs += [capsule((sx * 0.27, -0.12, 0.36), (sx * 0.31, -0.22, 0.12), 0.1),
             ellipsoid((0.2, 0.28, 0.12), (sx * 0.32, -0.32, 0.11))]
COLLAR_Z = 0.88
HAND_R = (0.86, -0.84, 0.66)  # pugno che stringe lo scettro
HAND_L = (-0.6, -0.92, 0.5)  # pugno appoggiato sulla pancia, soddisfatto
arms = union(capsule((0.66, -0.5, 0.78), HAND_R, 0.09),
             capsule((-0.7, -0.5, 0.74), HAND_L, 0.09), k=0.05)
body = union(shell, union(*legs, k=0.05), k=0.1)
body = union(body, arms, k=0.05)
m.add("Egg", body, GOLD_EGG, material="Foil", tris=4000, reflectance=0.1)

# ---------------------------------------------------------------- mantello rosso con pieghe
TH0 = math.radians(58)  # il mantello copre i fianchi e la schiena (|angolo dal davanti| > TH0)
CAPE_BOT = 0.04


def collar_z(th):
    """Altezza del colletto: basso davanti, alto dietro (come un mantello sulle spalle)."""
    return COLLAR_Z + 0.36 * (1.0 - np.cos(th)) * 0.5


def cape_r(z, th):
    top = collar_z(th)
    drop = np.clip((top - z) / (top - CAPE_BOT), 0.0, 1.0)
    return egg_r(top) + 0.1 + 0.2 * drop ** 1.3 + 0.055 * np.sin(10.0 * th) * np.clip(drop * 1.5, 0.0, 1.0)


def cape_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    rho = np.sqrt(x * x + y * y)
    th = np.arctan2(x, -y)
    d_shell = np.abs(rho - cape_r(z, th)) - 0.04
    d_ang = (TH0 - np.abs(th)) * rho
    d_z = np.maximum(z - collar_z(th), CAPE_BOT - z)
    return np.maximum(np.maximum(d_shell, d_ang), d_z)


cape = SDF(cape_fn, (-1.5, -1.5, CAPE_BOT - 0.05), (1.5, 1.5, COLLAR_Z + 0.5))
CROWN_Z0 = 2.2
velvet = ellipsoid((0.5, 0.5, 0.26), (0, 0, CROWN_Z0 + 0.26)).rot(*TILT, pivot=PIV)
m.add("Cape", union(cape, velvet), VELVET, role="detail", tris=2000)


# ---------------------------------------------------------------- ermellino (colletto, bordi, orlo) e guanti
def collar_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    rho = np.sqrt(x * x + y * y)
    th = np.arctan2(x, -y)
    zc = collar_z(th)
    return np.sqrt((rho - (egg_r(zc) + 0.07)) ** 2 + ((z - zc) * 1.1) ** 2) - 0.15


collar = SDF(collar_fn, (-1.35, -1.35, COLLAR_Z - 0.2), (1.35, 1.35, COLLAR_Z + 0.6))


def hem_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    rho = np.sqrt(x * x + y * y)
    th = np.arctan2(x, -y)
    d = np.sqrt((rho - cape_r(np.full_like(z, CAPE_BOT + 0.03), th)) ** 2 + (z - (CAPE_BOT + 0.06)) ** 2) - 0.085
    return np.maximum(d, (TH0 - 0.03 - np.abs(th)) * rho)


hem = SDF(hem_fn, (-1.6, -1.6, 0.0), (1.6, 1.6, 0.3))
edges = []
for sx in (1, -1):
    pts = []
    for z in np.linspace(CAPE_BOT + 0.06, COLLAR_Z, 10):
        r = float(cape_r(np.array([z]), np.array([sx * TH0]))[0])
        pts.append((sx * r * math.sin(TH0), -r * math.cos(TH0), z))
    edges.append(tube(pts, 0.085))
ermine = union(collar, hem, *edges, k=0.04)

# guanti bianchi a dita tozze: pugno sullo scettro e pugno sulla pancia
ROD_A = (HAND_R[0] + 0.02, HAND_R[1] - 0.05, HAND_R[2] - 0.34)
ROD_B = (HAND_R[0] + 0.44, HAND_R[1] - 0.2, HAND_R[2] + 0.72)
rod_dir = np.array(ROD_B) - np.array(ROD_A)
rod_dir /= np.linalg.norm(rod_dir)
fist_c = np.array(HAND_R) + np.array([0.0, -0.03, 0.0])
fist = [sphere(0.125, fist_c)]
for dz in (-0.07, 0.0, 0.07):  # tre dita avvolte davanti al manico
    c = fist_c + rod_dir * dz + np.array([0.0, -0.08, 0.0])
    fist.append(capsule(c + np.array([0.075, 0.03, 0.0]), c + np.array([-0.075, 0.03, 0.0]), 0.05))
fist.append(capsule(fist_c + np.array([-0.06, -0.02, 0.1]), fist_c + np.array([0.04, -0.09, 0.13]), 0.048))  # pollice
fist.append(sphere(0.1, np.array(HAND_R) + np.array([-0.08, 0.1, 0.03])))  # polsino
tucked = [ellipsoid((0.13, 0.11, 0.12), HAND_L), sphere(0.1, (HAND_L[0] - 0.06, HAND_L[1] + 0.14, HAND_L[2] + 0.1))]
for dz in (-0.06, 0.0, 0.06):  # nocche tozze del pugno
    tucked.append(capsule((HAND_L[0] - 0.02, HAND_L[1] - 0.08, HAND_L[2] + dz),
                          (HAND_L[0] + 0.1, HAND_L[1] - 0.06, HAND_L[2] + dz), 0.048))
gloves = union(union(*fist, k=0.03), union(*tucked, k=0.03))
m.add("Ermine", union(ermine, gloves), ERMINE, role="detail", tris=2200)

# codine nere dell'ermellino
dots = []
for i in range(16):
    phi = 2 * math.pi * i / 16 + 0.1
    th = math.atan2(math.cos(phi), -math.sin(phi))
    zc = float(collar_z(np.array([th]))[0])
    rc = float(egg_r(np.array([zc]))[0]) + 0.07
    psi = math.radians(30 if i % 2 else 68)
    radial = np.array([math.cos(phi), math.sin(phi), 0.0])
    c = np.array([0, 0, zc]) + radial * rc
    p, n = project(ermine, c, radial * math.cos(psi) + np.array([0, 0, 1.0]) * math.sin(psi))
    dots.append(ellipsoid((0.035, 0.035, 0.06), p))
for sx in (1, -1):
    for z in (0.28, 0.58):
        r = float(cape_r(np.array([z]), np.array([sx * TH0]))[0])
        c = np.array([sx * r * math.sin(TH0), -r * math.cos(TH0), z])
        p, n = project(ermine, c, (sx * math.sin(TH0) * 0.6, -math.cos(TH0), 0.0))
        dots.append(ellipsoid((0.035, 0.035, 0.06), p))
for th in np.radians(np.arange(78, 290, 24)):
    tw = th if th <= math.pi else th - 2 * math.pi
    r = float(cape_r(np.array([CAPE_BOT + 0.03]), np.array([tw]))[0])
    c = np.array([r * math.sin(th), -r * math.cos(th), CAPE_BOT + 0.06])
    p, n = project(ermine, c, (math.sin(th), -math.cos(th), 0.5))
    dots.append(ellipsoid((0.035, 0.035, 0.06), p))
m.add("ErmineDots", ermine.offset(0.012).intersect(union(*dots)), ERMINE_DOT, role="detail", tris=500, voxel=0.012)

# ---------------------------------------------------------------- corona ingioiellata (fascia a punte), inclinata con l'uovo
CROWN_H, POINT_H, NPTS = 0.24, 0.3, 5


def crown_rad(z):
    return float(egg_r(CROWN_Z0)) + 0.035 + 0.12 * np.clip(z - CROWN_Z0, 0.0, 1.0)


def crown_fn(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    rho = np.sqrt(x * x + y * y)
    th = np.arctan2(x, -y)
    d_shell = np.abs(rho - crown_rad(z)) - 0.035
    saw = np.abs(((th / (2 * np.pi) * NPTS) % 1.0) - 0.5) * 2.0  # 1 sulle punte, 0 fra le punte
    top = CROWN_Z0 + CROWN_H + POINT_H * saw
    return np.maximum(np.maximum(d_shell, (z - top) * 0.75), CROWN_Z0 - z) - 0.012


crown_band = SDF(crown_fn, (-0.75, -0.75, CROWN_Z0 - 0.05), (0.75, 0.75, CROWN_Z0 + CROWN_H + POINT_H + 0.05))
tips = []
for i in range(NPTS):
    th = 2 * math.pi * i / NPTS  # una punta davanti (-Y)
    zt = CROWN_Z0 + CROWN_H + POINT_H
    r = crown_rad(zt)
    tips.append(sphere(0.062, (r * math.sin(th), -r * math.cos(th), zt + 0.035)))
crown = union(crown_band, *tips, k=0.02).rot(*TILT, pivot=PIV)

# gemme sotto ogni punta (posizione calcolata a mano: la fascia e' un guscio sottile)
gems_r, gems_b = [], []
ZG = CROWN_Z0 + CROWN_H * 0.5
for i in range(NPTS):
    th = 2 * math.pi * i / NPTS
    n = np.array([math.sin(th), -math.cos(th), -0.12])
    n /= np.linalg.norm(n)
    rg = crown_rad(ZG) + 0.035 + 0.012
    p = np.array([rg * math.sin(th), -rg * math.cos(th), ZG])
    g = ellipsoid((0.11, 0.05, 0.1)) if i == 0 else ellipsoid((0.085, 0.045, 0.085))
    g = g.rotate(look_matrix(n)).translate(p - n * 0.012).rot(*TILT, pivot=PIV)
    (gems_b if i in (1, 4) else gems_r).append(g)
m.add("Rubies", union(*gems_r), RUBY, role="detail", tris=300, voxel=0.01, reflectance=0.3)
m.add("Sapphires", union(*gems_b), SAPPHIRE, role="detail", tris=250, voxel=0.01, reflectance=0.3)

# ---------------------------------------------------------------- scettro
rod = union(capsule(ROD_A, ROD_B, 0.04), sphere(0.06, ROD_A),
            round_cone(tuple(np.array(ROD_B) - rod_dir * 0.12), ROD_B, 0.05, 0.08), k=0.03)
GEM_C = tuple(np.array(ROD_B) + rod_dir * 0.12)
finial = union(capsule((GEM_C[0], GEM_C[1], GEM_C[2] + 0.1), (GEM_C[0], GEM_C[1], GEM_C[2] + 0.26), 0.025),
               capsule((GEM_C[0] - 0.07, GEM_C[1], GEM_C[2] + 0.2), (GEM_C[0] + 0.07, GEM_C[1], GEM_C[2] + 0.2), 0.025))
m.add("Sceptre", union(rod, finial, k=0.02), GOLD_CROWN, material="Metal", role="detail", tris=500, voxel=0.012)
m.add("SceptreGem", sphere(0.13, GEM_C), GEM_GLOW, material="Neon", role="glow", tris=300, voxel=0.012)

# ---------------------------------------------------------------- faccia da sbruffone
FC = tuple(tilted((0.0, 0.0, 1.61)))
EYE_R = (0.165, 0.095, 0.2)
eye_frames = [Frame(body, FC, (0.37 * sx, -1.0, 0.16), sink=0.045) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(ellipsoid(EYE_R)) for f in eye_frames]), EYE, role="eye", tris=500, voxel=0.013)
lids, lashes, shines = [], [], []
LID_Z0, LID_SLOPE = 0.015, -0.2  # palpebre a meta', il bordo scende verso l'esterno: aria annoiata
for f, sx in zip(eye_frames, (1, -1)):
    rr = (EYE_R[0] + 0.03, EYE_R[1] + 0.03, EYE_R[2] + 0.03)
    lid_shell = ellipsoid(rr)

    def cut(p, sx=sx):
        return (LID_Z0 - LID_SLOPE * sx * p[:, 0] - p[:, 2]) / math.sqrt(1 + LID_SLOPE ** 2)
    lids.append(f.place(lid_shell.intersect(SDF(cut, lid_shell.lo, lid_shell.hi))))
    pts = []
    for x in np.linspace(-rr[0] * 0.96, rr[0] * 0.96, 11):
        z = LID_Z0 - LID_SLOPE * sx * x
        v = 1 - (x / rr[0]) ** 2 - (z / rr[2]) ** 2
        if v > 0.02:
            pts.append(f.point((x, -rr[1] * math.sqrt(v) + 0.004, z)))
    lashes.append(tube(pts, 0.019))
    shines.append(f.place(sphere(0.034), (-0.06, -0.08, -0.07)))
    shines.append(f.place(sphere(0.017), (0.065, -0.075, -0.12)))
m.add("Lids", union(*lids), GOLD_EGG, material="Foil", role="skin", tris=600, voxel=0.012, reflectance=0.1)
m.add("Shine", union(*shines), WHITE, role="shine", tris=200, voxel=0.008)

# baffi a manubrio, sopracciglia (una alzata) e ciglia: stesso marrone scuro
mus = []
for sx in (1, -1):
    pts2d = [(0.0, 1.33), (0.12, 1.29), (0.24, 1.27), (0.35, 1.31), (0.43, 1.39), (0.44, 1.47), (0.38, 1.5), (0.34, 1.45)]
    pts = [on_surf(body, FC, tilted((sx * x, -1.2, z)))[0] for x, z in pts2d]
    pts = [p + normal_at(body, p) * 0.03 for p in pts]
    mus.append(tube(pts, [0.085, 0.085, 0.075, 0.06, 0.048, 0.038, 0.032, 0.03]))
c0 = on_surf(body, FC, tilted((0.0, -1.2, 1.33)))[0]
mus.append(sphere(0.09, c0 + normal_at(body, c0) * 0.025))
for f, sx, brow in zip(eye_frames, (1, -1), (
        ((-0.2, 0.27), (-0.1, 0.36), (0.02, 0.4), (0.13, 0.37)),   # alzato, arcuato
        ((-0.2, 0.25), (-0.08, 0.27), (0.04, 0.27), (0.14, 0.24)))):  # piatto, scettico
    pts = [on_surf(body, FC, f.point((sx * xi, -0.3, z)))[0] for xi, z in brow]
    mus.append(tube(pts, [0.03, 0.042, 0.042, 0.03]))
m.add("Moustache", union(union(*mus[:3], k=0.03), *mus[3:], *lashes), MUSTACHE, role="detail", tris=900,
      voxel=0.011)

# sorrisetto storto (bocca chiusa) con un dente d'oro che spunta all'angolo alzato
smirk2d = [(-0.14, 1.15), (-0.07, 1.125), (0.01, 1.122), (0.08, 1.138), (0.13, 1.165), (0.16, 1.19)]
smirk = [on_surf(body, FC, tilted((x, -1.2, z)))[0] for x, z in smirk2d]
m.add("Mouth", tube([p + normal_at(body, p) * 0.006 for p in smirk], [0.022, 0.026, 0.026, 0.026, 0.022, 0.018]),
      MOUTH, role="detail", tris=300, voxel=0.01)
t0, n0 = on_surf(body, FC, tilted((0.065, -1.2, 1.13)))
t1, n1 = on_surf(body, FC, tilted((0.068, -1.2, 1.06)))
gold_tooth = round_cone(t0 + n0 * 0.02, t1 + n1 * 0.024, 0.04, 0.03)
m.add("Crown", union(crown, gold_tooth), GOLD_CROWN, material="Metal", role="detail", tris=1500, voxel=0.012)

# crepa sul guscio ricucita con punti grossi
crack = []
for deg, z in [(48, 2.08), (55, 1.99), (47, 1.92), (56, 1.84), (49, 1.76), (55, 1.68)]:
    a = math.radians(deg)
    p, n = on_surf(body, tilted((0.0, 0.0, z)), tilted((1.2 * math.sin(a), -1.2 * math.cos(a), z)))
    crack.append(p + n * 0.004)
mid = []
for z in np.linspace(2.06, 1.7, 7):  # linea media della crepa, sulla superficie
    a = math.radians(51.5)
    mid.append(on_surf(body, tilted((0.0, 0.0, z)), tilted((1.2 * math.sin(a), -1.2 * math.cos(a), z)))[0])
line = stitches(body, mid, 4, 0.15, 0.02)
m.add("Crack", union(tube(crack, 0.022), line), MUSTACHE, role="detail", tris=600, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
