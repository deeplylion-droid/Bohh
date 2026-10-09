"""Uovissimo Imperatore - pet Divino (creatura meme originale).

Un uovo d'oro lucido che si crede imperatore: corona ingioiellata, mantello rosso con bordo
di ermellino (bianco a codine nere), baffi arricciati, scettro con gemma in una manina e
piedini minuscoli.
"""
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.sdf import (SDF, Frame, bezier, capped_cone, capsule, egg, ellipsoid, look_matrix, project,  # noqa: E402
                     project_curve, round_cone, sphere, tube, union)
from lib.toy import Model  # noqa: E402

GOLD_EGG = (255, 198, 52)
GOLD_CROWN = (255, 176, 36)
RUBY = (226, 22, 58)
SAPPHIRE = (36, 92, 236)
VELVET = (200, 24, 44)
ERMINE = (255, 253, 248)
ERMINE_DOT = (28, 26, 34)
MUSTACHE = (84, 46, 30)
GEM_GLOW = (60, 160, 255)
EYE = (30, 22, 30)
WHITE = (255, 255, 255)
BLUSH = (255, 120, 120)
MOUTH = (120, 40, 40)

m = Model("UovissimoImperatore", "pet")

# ---------------------------------------------------------------- uovo
Z0 = 0.1
EH = 2.3
ER = 1.0
TAPER = 0.22


def egg_r(z):
    t = np.clip((z - Z0) / EH, 0.0, 1.0)
    u = 2.0 * t - 1.0
    return ER * np.sqrt(np.clip(1.0 - u * u, 0.0, 1.0)) * (1.0 - TAPER * u)


shell = egg(ER, EH, TAPER).translate((0, 0, Z0))
feet = union(*[ellipsoid((0.2, 0.27, 0.12), (sx * 0.3, -0.3, 0.11)) for sx in (1, -1)])
COLLAR_Z = 0.92
HAND_R = (0.84, -0.84, 0.66)
HAND_L = (-0.8, -0.86, 0.62)
arms = union(capsule((0.6, -0.56, 0.74), HAND_R, 0.085), capsule((-0.58, -0.58, 0.7), HAND_L, 0.085),
             sphere(0.12, HAND_R), sphere(0.12, HAND_L), k=0.06)
body = union(shell, feet, k=0.1)
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
# zucchetto di velluto rosso dentro la corona
CROWN_Z0 = 2.1
velvet = ellipsoid((0.5, 0.5, 0.26), (0, 0, 2.36))
m.add("Cape", union(cape, velvet), VELVET, role="detail", tris=2200)

# ---------------------------------------------------------------- ermellino: colletto, bordi e orlo


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
m.add("Ermine", ermine, ERMINE, role="detail", tris=2000)

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
m.add("ErmineDots", ermine.offset(0.012).intersect(union(*dots)), ERMINE_DOT, role="detail", tris=700, voxel=0.012)

# ---------------------------------------------------------------- corona ingioiellata (fascia a punte)
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
    d_top = (z - top) * 0.75
    d_bot = CROWN_Z0 - z
    return np.maximum(np.maximum(d_shell, d_top), d_bot) - 0.012


crown_band = SDF(crown_fn, (-0.75, -0.75, CROWN_Z0 - 0.05), (0.75, 0.75, CROWN_Z0 + CROWN_H + POINT_H + 0.05))
tips = []
for i in range(NPTS):
    th = 2 * math.pi * i / NPTS  # una punta davanti (-Y)
    zt = CROWN_Z0 + CROWN_H + POINT_H
    r = crown_rad(zt)
    tips.append(sphere(0.062, (r * math.sin(th), -r * math.cos(th), zt + 0.035)))
crown = union(crown_band, *tips, k=0.02)
m.add("Crown", crown, GOLD_CROWN, material="Metal", role="detail", tris=1600, voxel=0.012)

# gemme sotto ogni punta: rubino grande davanti, zaffiri ai lati, rubini dietro
# (posizione calcolata a mano: la fascia e' un guscio sottile, project partirebbe da fuori)
gems_r, gems_b = [], []
ZG = CROWN_Z0 + CROWN_H * 0.5
for i in range(NPTS):
    th = 2 * math.pi * i / NPTS
    n = np.array([math.sin(th), -math.cos(th), -0.12])
    n /= np.linalg.norm(n)
    rg = crown_rad(ZG) + 0.035 + 0.012
    p = np.array([rg * math.sin(th), -rg * math.cos(th), ZG])
    if i == 0:
        g = ellipsoid((0.11, 0.05, 0.1))
    else:
        g = ellipsoid((0.085, 0.045, 0.085))
    g = g.rotate(look_matrix(n)).translate(p - n * 0.012)
    (gems_b if i in (1, 4) else gems_r).append(g)
m.add("Rubies", union(*gems_r), RUBY, role="detail", tris=400, voxel=0.01, reflectance=0.3)
m.add("Sapphires", union(*gems_b), SAPPHIRE, role="detail", tris=300, voxel=0.01, reflectance=0.3)

# ---------------------------------------------------------------- scettro nella manina destra
ROD_A = (HAND_R[0] + 0.02, HAND_R[1] - 0.02, HAND_R[2] - 0.32)
ROD_B = (HAND_R[0] + 0.17, HAND_R[1] - 0.08, HAND_R[2] + 0.8)
rod = union(capsule(ROD_A, ROD_B, 0.04), sphere(0.06, ROD_A),
            round_cone((ROD_B[0] - 0.012, ROD_B[1] + 0.006, ROD_B[2] - 0.12), ROD_B, 0.05, 0.08), k=0.03)
GEM_C = (ROD_B[0] + 0.012, ROD_B[1] - 0.006, ROD_B[2] + 0.12)
finial = union(capsule((GEM_C[0], GEM_C[1], GEM_C[2] + 0.1), (GEM_C[0], GEM_C[1], GEM_C[2] + 0.26), 0.025),
               capsule((GEM_C[0] - 0.07, GEM_C[1], GEM_C[2] + 0.2), (GEM_C[0] + 0.07, GEM_C[1], GEM_C[2] + 0.2), 0.025))
m.add("Sceptre", union(rod, finial, k=0.02), GOLD_CROWN, material="Metal", role="detail", tris=600, voxel=0.012)
m.add("SceptreGem", sphere(0.13, GEM_C), GEM_GLOW, material="Neon", role="glow", tris=400, voxel=0.012)

# ---------------------------------------------------------------- faccia: occhi, baffi, guance, bocca
FC = (0.0, 0.0, 1.45)
eye_shape = ellipsoid((0.165, 0.1, 0.22))
eye_frames = [Frame(body, FC, (0.37 * sx, -1.0, 0.24), sink=0.05) for sx in (1, -1)]
m.add("Eyes", union(*[f.place(eye_shape) for f in eye_frames]), EYE, role="eye", tris=700, voxel=0.014)
shines = []
for f in eye_frames:
    shines.append(f.place(sphere(0.064), (-0.052, -0.085, 0.082)))
    shines.append(f.place(sphere(0.032), (0.062, -0.08, -0.098)))
m.add("Shine", union(*shines), WHITE, role="shine", tris=400, voxel=0.01)
blush = ellipsoid((0.14, 0.04, 0.085))
m.add("Blush", union(*[Frame(body, FC, (0.66 * sx, -1.0, -0.12), sink=0.018).place(blush) for sx in (1, -1)]),
      BLUSH, role="detail", tris=400, voxel=0.013)

# baffi a manubrio arricciati
mus = []
for sx in (1, -1):
    pts2d = [(0.0, 1.28), (0.12, 1.24), (0.24, 1.22), (0.35, 1.26), (0.43, 1.34), (0.44, 1.42), (0.38, 1.45), (0.34, 1.4)]
    pts = project_curve(body, [(sx * x, -1.0, z) for x, z in pts2d], (0, -1, 0), inset=-0.03)
    mus.append(tube(pts, [0.085, 0.085, 0.075, 0.06, 0.048, 0.038, 0.032, 0.03]))
mus.append(sphere(0.09, project_curve(body, [(0.0, -1.0, 1.28)], (0, -1, 0), inset=-0.025)[0]))
# sopracciglia fiere, inarcate
for f in eye_frames:
    brow = [f.point((x, 0.0, z)) for x, z in ((0.13, 0.25), (0.05, 0.3), (-0.06, 0.31), (-0.15, 0.27))]
    brow = project_curve(body, [tuple(q) for q in brow], -f.normal, inset=0.0, start_back=0.4)
    mus.append(tube(brow, [0.028, 0.038, 0.038, 0.028]))
m.add("Moustache", union(*mus, k=0.03), MUSTACHE, role="detail", tris=800, voxel=0.012)

mouth_pts = project_curve(body, bezier((0.11, -1.0, 1.12), (0.05, -1.0, 1.07), (-0.05, -1.0, 1.07), (-0.11, -1.0, 1.12), 10),
                          (0, -1, 0), inset=0.008)
m.add("Mouth", tube(mouth_pts, 0.025), MOUTH, role="detail", tris=300, voxel=0.01)

if __name__ == "__main__":
    m.build(views=tuple(os.environ.get("VIEWS", "3q,front").split(",")), res=int(os.environ.get("RES", 700)))
