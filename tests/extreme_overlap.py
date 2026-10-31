#!/usr/bin/env python3
"""Controllo automatico delle compenetrazioni del Percorso Estremo (percorso, santuari, bivio e arredo
delle cartelle ExtremeDecorA / ExtremeDecorB).

Uso (dalla radice del progetto; basta python3 con numpy, niente server):
    python3 tests/extreme_overlap.py                    # rifa' il dump con Lune e stampa il rapporto
    python3 tests/extreme_overlap.py --section 2        # solo la sezione 2 (1 Rapide, 2 Deserto, 3 Lab,
                                                        #   4 Inferno, 0 bivio/ingresso)
    python3 tests/extreme_overlap.py --folder ExtremeDecorA   # solo i problemi che toccano quella cartella
    python3 tests/extreme_overlap.py --verbose          # anche i casi minori, nascosti e quelli voluti
    python3 tests/extreme_overlap.py --dump file.json   # usa un dump gia' fatto, che deve essere di
        .tools/bin/lune run tests/extreme_dump.luau --all --poses --terrain --out file.json
    python3 tests/extreme_overlap.py --json out.json    # salva anche il rapporto completo in JSON
Esce con codice 1 se resta almeno un problema visibile (righe "!!" e "!"), 0 altrimenti.

Cosa controlla (tutte le parti visibili, anche quelle che il client accende solo a tratti, come fiamme,
laser e getti; le sponde e l'arredo compresi):
  ZF  z-fighting: facce complanari (entro 0.02 stud) rivolte dalla stessa parte che si sovrappongono,
      con colore/materiale/trasparenza diversi e non coperte da altre parti
  TR  compenetrazioni con una parte trasparente (si vede la parte che c'e' dentro): veli d'acqua nelle
      vasche, laser nei pavimenti... Sono normali i sassi e le pareti che escono da un liquido
  SG  un cartello (faccia col testo) tagliato o coperto da un'altra parte
  PK  una parte che esce di poco (< 0.6 stud) dal lato opposto di quella in cui entra (pavimento che
      spunta dietro una sponda, palo che buca il cartello...)
  XP  una parte che ne attraversa un'altra da parte a parte e si vede dai due lati (pali che bucano un
      pavimento sospeso, travi che passano nei muri...)
  MV  elementi mobili: il volume spazzato in un periodo (pose campionate come le calcola il client)
      che entra in una parte ferma visibile (sponde, pareti, altri appoggi, arredo)
  TE  il terreno che spunta sopra pavimenti, vasche e sponde del percorso
Gravita': "!!" chiaramente visibile dal percorso, "!" visibile ma piccolo o lontano, "." nascosto o
voluto (solo con --verbose). Per ogni problema: sezione, coordinate di sezione (u = distanza lungo il
percorso dall'inizio della sezione, v = spostamento laterale, y = quota; come in Shared.Extreme),
posizione nel mondo e le due parti (nome, cartella, materiale, misura).

Casi riconosciuti come voluti (non segnalati): parte tutta dentro un'altra opaca; parti dello stesso
elemento (corda del tronco, strisce del nastro); blocchi con lo stesso materiale e colore (una forma
sola); parti piantate in un'altra da una faccia sola (pali nel pavimento, sponde nel terreno, liquido
che entra nelle sponde); coperture e bordi (muschio, cornici) che avvolgono uno spigolo; anelli e
collari attorno a una colonna; corde e aste sottili che passano nei paletti; elementi mobili nel
liquido (tronchi che galleggiano, piastrelle che affondano) e attorno al proprio perno.
La visibilita' si stima con raggi dai punti di vista lungo il percorso (sopra ogni appoggio, all'altezza
degli occhi e della telecamera) verso i punti del difetto, con le parti opache come ostacoli.
"""

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUMP = ROOT / "art/out/overlap/extreme_overlap_dump.json"

# Percorso (come in src/shared/Extreme.luau)
COURSE_Z = 215.0
HALF_WIDTH = 19.0
SECTIONS = [  # (indice, nome, x0, lunghezza + santuario)
    (1, "Rapide", -60.0, 396 + 60),
    (2, "Deserto", -516.0, 360 + 60),
    (3, "Laboratorio", -936.0, 340 + 60),
    (4, "Inferno", -1336.0, 360 + 70),
]

CYL_SEGMENTS = 24
COPLANAR = 0.02  # facce piu' vicine di cosi' fanno z-fighting
NEAR_COPLANAR = 0.06  # da 0.02 a 0.06: sfarfallano solo da lontano
SLIVER = 0.6  # sporgenze piu' sottili di cosi' sono quasi sempre accidentali
SEE_THROUGH = 0.1  # parti con trasparenza da qui in su non nascondono cio' che c'e' dietro
ROCKY = {
    "Slate", "Sandstone", "Basalt", "Rock", "Granite", "Limestone", "Cobblestone", "Pebble", "Concrete",
    "Marble", "Ground", "Mud", "Sand", "Salt", "CrackedLava", "Asphalt", "Brick", "Grass", "LeafyGrass",
}


def section_of(x):
    """Sezione (1..4) di una x del percorso; 0 = bivio/ingresso (prima della partenza)."""
    if x > SECTIONS[0][2]:
        return 0
    for idx, _, x0, _ in reversed(SECTIONS):
        if x <= x0:
            return idx
    return 1


def local_coords(p):
    """Coordinate di sezione (u, y, v) di un punto del mondo."""
    s = section_of(p[0])
    x0 = SECTIONS[max(s, 1) - 1][2]
    return s, x0 - p[0], p[1], p[2] - COURSE_Z


# --------------------------------------------------------------------------------------- poliedri
def _orient(verts, faces):
    """Ordina i vertici di ogni faccia in senso antiorario visto da fuori (normale uscente)."""
    c = verts.mean(axis=0)
    out = []
    for f in faces:
        pts = verts[list(f)]
        n = np.zeros(3)
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            n += np.cross(a, b)
        if np.dot(n, pts.mean(axis=0) - c) < 0:
            f = list(reversed(f))
        out.append(list(f))
    return out


def local_polytope(shape, size, mesh_scale=None):
    """Vertici (n,3) e facce (liste di indici) nelle coordinate locali della parte, piu' quali facce sono
    piane davvero (le facce laterali dei cilindri e delle sfere approssimano superfici curve: per i
    controlli sono una faccia sola, il gruppo -1 = lato del cilindro, -2 = superficie della sfera)."""
    h = np.asarray(size, dtype=float) / 2
    if shape == "Cylinder":
        r = min(h[1], h[2])
        ang = np.arange(CYL_SEGMENTS) * 2 * math.pi / CYL_SEGMENTS
        ring = np.stack([np.cos(ang) * r, np.sin(ang) * r], axis=1)
        verts = np.concatenate([
            np.column_stack([np.full(CYL_SEGMENTS, -h[0]), ring]),
            np.column_stack([np.full(CYL_SEGMENTS, h[0]), ring]),
        ])
        n = CYL_SEGMENTS
        faces = [list(range(n)), list(range(n, 2 * n))]
        flat = [True, True]
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, n + j, n + i])
            flat.append(False)
        return verts, _orient(verts, faces), flat, [0, 1] + [-1] * n
    if shape in ("Ball", "Sphere"):
        rad = np.full(3, h.min()) if shape == "Ball" else h * (np.asarray(mesh_scale) if mesh_scale else 1)
        rings, segs = 6, 12
        verts = [[0, rad[1], 0]]
        for i in range(1, rings):
            th = math.pi * i / rings
            for j in range(segs):
                ph = 2 * math.pi * j / segs
                verts.append([rad[0] * math.sin(th) * math.cos(ph), rad[1] * math.cos(th),
                              rad[2] * math.sin(th) * math.sin(ph)])
        verts.append([0, -rad[1], 0])
        verts = np.array(verts, dtype=float)
        faces = []
        for j in range(segs):
            faces.append([0, 1 + j, 1 + (j + 1) % segs])
        for i in range(rings - 2):
            for j in range(segs):
                a = 1 + i * segs + j
                b = 1 + i * segs + (j + 1) % segs
                faces.append([a, b, b + segs, a + segs])
        last = len(verts) - 1
        base = 1 + (rings - 2) * segs
        for j in range(segs):
            faces.append([base + j, base + (j + 1) % segs, last])
        return verts, _orient(verts, faces), [False] * len(faces), [-2] * len(faces)
    if shape == "Wedge":
        verts = np.array([[-h[0], -h[1], -h[2]], [h[0], -h[1], -h[2]], [h[0], -h[1], h[2]], [-h[0], -h[1], h[2]],
                          [-h[0], h[1], h[2]], [h[0], h[1], h[2]]])
        faces = [[0, 1, 2, 3], [3, 2, 5, 4], [0, 4, 5, 1], [0, 3, 4], [1, 5, 2]]
        return verts, _orient(verts, faces), [True] * 5, list(range(5))
    if shape == "CornerWedge":
        # approssimazione: base quadrata e vertice in alto sullo spigolo (+x, -z)
        verts = np.array([[-h[0], -h[1], -h[2]], [h[0], -h[1], -h[2]], [h[0], -h[1], h[2]], [-h[0], -h[1], h[2]],
                          [h[0], h[1], -h[2]]])
        faces = [[0, 1, 2, 3], [0, 4, 1], [1, 4, 2], [2, 4, 3], [3, 4, 0]]
        return verts, _orient(verts, faces), [True] * 5, list(range(5))
    verts = np.array([[sx * h[0], sy * h[1], sz * h[2]] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    faces = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    return verts, _orient(verts, faces), [True] * 6, list(range(6))


class Poly:
    """Poliedro convesso nel mondo: facce (liste di vertici), piani uscenti n.x <= d."""

    __slots__ = ("faces", "normals", "offsets", "flat", "group", "verts", "lo", "hi")

    def __init__(self, verts, faces, flat, group):
        self.verts = verts
        self.faces = [verts[f] for f in faces]
        self.flat = flat
        self.group = group
        normals, offsets = [], []
        for pts in self.faces:
            n = face_normal(pts)
            normals.append(n)
            offsets.append(float(n @ pts.mean(axis=0)))
        self.normals = np.array(normals)
        self.offsets = np.array(offsets)
        self.lo = verts.min(axis=0)
        self.hi = verts.max(axis=0)


def make_poly(local, pos, rot):
    verts, faces, flat, group = local
    return Poly(verts @ rot.T + pos, faces, flat, group)


def _ncross(a, b):
    """Prodotto vettoriale riga per riga di due array (k, 3) (piu' veloce di np.cross)."""
    return np.stack([a[:, 1] * b[:, 2] - a[:, 2] * b[:, 1], a[:, 2] * b[:, 0] - a[:, 0] * b[:, 2],
                     a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]], axis=1)


def _vcross(a, b):
    return np.array([a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]])


def clip_faces(faces, n, d, eps=1e-6):
    """Taglia un poliedro convesso (lista di facce) col semispazio n.x <= d."""
    out, cap, cut = [], [], False
    for f in faces:
        s = f @ n - d
        if s.max() <= eps:
            out.append(f)
            continue
        cut = True
        if s.min() >= -eps:
            cap.extend(f[np.abs(s) <= eps])
            continue
        kept = []
        k = len(f)
        for i in range(k):
            sa, sb = s[i], s[(i + 1) % k]
            if sa <= eps:
                kept.append(f[i])
                if sa >= -eps:
                    cap.append(f[i])
            if (sa < -eps and sb > eps) or (sb < -eps and sa > eps):
                a = f[i]
                q = a + (f[(i + 1) % k] - a) * (sa / (sa - sb))
                kept.append(q)
                cap.append(q)
        if len(kept) >= 3:
            out.append(np.array(kept))
    if not cut or not out:
        return out
    if len(cap) >= 3:
        pts = np.array(cap)
        seen = {}
        for k, key in enumerate(map(tuple, np.round(pts, 5).tolist())):
            seen.setdefault(key, k)
        if len(seen) >= 3:
            pts = pts[list(seen.values())]
            c = pts.mean(axis=0)
            u = _vcross(n, np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0]))
            u /= math.sqrt(u @ u)
            w = _vcross(n, u)
            rel = pts - c
            out.append(pts[np.argsort(np.arctan2(rel @ w, rel @ u))])
    return out


def clip_poly(faces, normals, offsets, skip=None):
    for j in range(len(normals)):
        if j == skip:
            continue
        faces = clip_faces(faces, normals[j], offsets[j])
        if not faces:
            return []
    return faces


def volume(faces):
    v = 0.0
    for f in faces:
        if len(f) >= 3:
            v += float(np.sum(_ncross(f[1:-1], f[2:]) @ f[0]))
    return v / 6.0


def face_normal(pts):
    a = _ncross(pts, np.roll(pts, -1, axis=0)).sum(axis=0)
    ln = math.sqrt(a @ a)
    return a / ln if ln > 1e-12 else a


def poly_area(pts, n):
    a = _ncross(pts, np.roll(pts, -1, axis=0)).sum(axis=0)
    return abs(a @ n) / 2


def clip2d(subject, clip):
    """Intersezione di due poligoni convessi 2D (antiorari)."""
    out = list(subject)
    for i in range(len(clip)):
        if not out:
            break
        a, b = clip[i], clip[(i + 1) % len(clip)]
        inp, out = out, []
        edge = b - a

        def side(p):
            return edge[0] * (p[1] - a[1]) - edge[1] * (p[0] - a[0])

        for j in range(len(inp)):
            p, q = inp[j], inp[(j + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                out.append(p + (q - p) * t)
    return out


def area2d(pts):
    if len(pts) < 3:
        return 0.0
    p = np.array(pts)
    return 0.5 * abs(np.dot(p[:, 0], np.roll(p[:, 1], -1)) - np.dot(p[:, 1], np.roll(p[:, 0], -1)))


def plane_basis(n):
    u = np.cross(n, [1.0, 0, 0] if abs(n[0]) < 0.9 else [0, 1.0, 0])
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)


def to2d(pts, u, w):
    p2 = np.stack([pts @ u, pts @ w], axis=1)
    # antiorario
    if area_signed(p2) < 0:
        p2 = p2[::-1]
    return p2


def area_signed(p):
    return 0.5 * (np.dot(p[:, 0], np.roll(p[:, 1], -1)) - np.dot(p[:, 1], np.roll(p[:, 0], -1)))


def min_width2d(pts):
    """Larghezza minima di un poligono convesso 2D (per scartare sovrapposizioni ridotte a una riga)."""
    p = np.array(pts)
    best = math.inf
    for i in range(len(p)):
        e = p[(i + 1) % len(p)] - p[i]
        ln = np.linalg.norm(e)
        if ln < 1e-9:
            continue
        nrm = np.array([-e[1], e[0]]) / ln
        d = (p - p[i]) @ nrm
        best = min(best, d.max() - d.min())
    return best


# --------------------------------------------------------------------------------------- parti
SUPPORT_KINDS = {"Solid", "Mover", "Spinner", "Faller", "Bounce", "Conveyor"}


class Part:
    def __init__(self, i, e):
        self.i = i
        self.e = e
        self.name = e["n"]
        self.cls = e.get("c", "Part")
        self.folder = e.get("f", "")
        self.size = np.array(e["s"], dtype=float)
        self.pos = np.array(e["p"], dtype=float)
        r = np.array(e["r"][:3], dtype=float)
        u = np.array(e["r"][3:6], dtype=float)
        self.rot = np.stack([r, u, np.cross(r, u)], axis=1)
        self.color = tuple(e.get("k", (163, 162, 165)))
        self.mat = e.get("m", "Plastic")
        self.t = float(e.get("t", 0))
        shape = e.get("sh", "Block")
        if e.get("sm") == "Sphere":
            shape = "Sphere"
        self.approx = self.cls not in ("Part", "WedgePart", "CornerWedgePart", "TrussPart", "SpawnLocation", "Seat")
        if self.approx or shape not in ("Block", "Cylinder", "Ball", "Wedge", "CornerWedge", "Sphere"):
            shape = "Block"  # MeshPart, unioni...: si usa la scatola (approssimazione)
        self.shape = shape
        self.local = local_polytope(shape, self.size, e.get("ms"))
        self.poly = make_poly(self.local, self.pos, self.rot)
        self.vol = volume(self.poly.faces)
        self.piece = e.get("pc")
        self.kind = e.get("kd")
        self.deco = bool(e.get("dc"))
        self.wall = bool(e.get("wl"))
        self.style = e.get("st")
        self.role = e.get("ro")
        self.cc = bool(e.get("cc", True))
        self.poses = None
        if e.get("sw"):
            self.poses = [(np.array(p[0:3], dtype=float), np.stack([
                np.array(p[3:6], dtype=float), np.array(p[6:9], dtype=float),
                np.cross(np.array(p[3:6], dtype=float), np.array(p[6:9], dtype=float))], axis=1), float(p[9]))
                for p in e["sw"]]
        trs = [self.t] + ([p[2] for p in self.poses] if self.poses else [])
        self.tv = min(trs)  # la volta che si vede di piu'
        self.moving = bool(self.poses) and any(
            np.linalg.norm(p[0] - self.pos) > 1e-3 or np.abs(p[1] - self.rot).max() > 1e-3 for p in self.poses)
        self.section = section_of(self.pos[0])

    # --- ruoli
    @property
    def visible(self):
        return self.tv < 0.98

    @property
    def opaque(self):
        """Nasconde cio' che ha dietro/dentro (sempre: le parti che cambiano trasparenza no)."""
        return self.t < SEE_THROUGH and self.tv >= self.t - 1e-6 and not self.moving and (
            not self.poses or all(p[2] < SEE_THROUGH for p in self.poses))

    @property
    def is_liquid(self):
        return (self.piece is not None and self.deco and not self.cc and self.style is None and self.size[1] <= 2.5
                and self.size[0] >= 8 and self.size[2] >= 2 * HALF_WIDTH)

    @property
    def is_sign(self):
        return self.name == "Sign" or self.name.endswith("Sign")

    @property
    def is_support(self):
        return (self.kind in SUPPORT_KINDS and self.cc and not self.deco and not self.wall) or self.name == "ExtremeBranch"

    def look(self):
        return (self.color, self.mat, round(self.t, 2))

    def label(self):
        dims = "x".join(f"{v:g}" for v in np.round(self.size, 2))
        what = self.name
        if self.piece and self.name == self.piece:
            tags = [self.kind or "?"]
            if self.style:
                tags.append(self.style)
            if self.is_liquid:
                tags.append("liquido")
            elif self.deco:
                tags.append("deco")
            if self.wall:
                tags.append("sponda/parete")
            what = f"{self.name}[{','.join(tags)}]"
        elif self.role:
            what = f"{self.name}[{self.role} di {self.piece}]"
        tr = f" t={self.tv:g}" if self.tv > 0 else ""
        sh = "" if self.shape == "Block" else f" {self.shape}"
        return f"{what} ({self.folder}) {self.mat} {self.color}{tr}{sh} {dims}"

    def where(self):
        return fmt_where(self.pos)

    def front_face(self):
        """Indice della faccia anteriore (-Z locale: quella del testo dei cartelli)."""
        want = -self.rot[:, 2]
        return int(np.argmax(self.poly.normals @ want))


def fmt_where(p):
    s, u, y, v = local_coords(p)
    name = "bivio" if s == 0 else SECTIONS[s - 1][1]
    return f"{name} u={u:.1f} v={v:+.1f} y={y:.1f} (mondo {p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})"


def load_parts(path):
    data = json.load(open(path))
    parts = [Part(i, e) for i, e in enumerate(data["parts"])]
    return data, parts


# --------------------------------------------------------------------------------------- visibilita'
class Viewer:
    """Punti di vista lungo il percorso: occhi e telecamera sopra ogni appoggio, e raggi verso i difetti
    con le parti opache (ferme) come ostacoli."""

    CAMS = [(0, 4.5, 0), (10, 9, 0), (-8, 8, 0), (0, 9, 9), (0, 9, -9), (18, 13, 0)]

    def __init__(self, parts, terrain):
        self.parts = parts
        self.terrain = terrain
        spots = []
        for p in parts:
            if not p.is_support:
                continue
            up = p.rot[:, 1]
            if p.shape == "Cylinder":
                axis = p.rot[:, 0]
                if abs(axis[1]) > 0.7:
                    spots.append(p.pos + np.array([0, p.size[0] / 2, 0]))
                else:
                    spots.append(p.pos + np.array([0, min(p.size[1], p.size[2]) / 2, 0]))
                continue
            if up[1] < 0.5:
                continue
            hx, hy, hz = p.size / 2
            nx = max(1, int(math.ceil(p.size[0] / 8)))
            nz = max(1, int(math.ceil(p.size[2] / 8)))
            for a in range(nx):
                for b in range(nz):
                    lx = -hx + (a + 0.5) * p.size[0] / nx
                    lz = -hz + (b + 0.5) * p.size[2] / nz
                    spots.append(p.pos + p.rot @ np.array([lx, hy, lz]))
        spots = np.array(spots)
        spots = spots[np.abs(spots[:, 2] - COURSE_Z) <= HALF_WIDTH + 1]
        # un punto ogni 3 stud basta
        key = np.round(spots / 3).astype(int)
        _, keep = np.unique(key, axis=0, return_index=True)
        self.spots = spots[np.sort(keep)]
        cams = []
        owner = []
        for k, s in enumerate(self.spots):
            for c in self.CAMS:
                q = s + np.array(c, dtype=float)
                if abs(q[2] - COURSE_Z) <= HALF_WIDTH + 8:
                    cams.append(q)
                    owner.append(k)
        self.cams = np.array(cams)
        self.owner = np.array(owner)
        occ = [p for p in parts if p.opaque and p.visible]
        self.occ = occ
        self.occ_lo = np.array([p.poly.lo for p in occ])
        self.occ_hi = np.array([p.poly.hi for p in occ])
        # le telecamere dentro una parte opaca non contano (Roblox le sposta davanti)
        inside = np.zeros(len(self.cams), dtype=bool)
        for p in occ:
            m = np.all((self.cams >= p.poly.lo) & (self.cams <= p.poly.hi), axis=1)
            if m.any():
                idx = np.where(m)[0]
                s = self.cams[idx] @ p.poly.normals.T - p.poly.offsets
                inside[idx[np.all(s <= 0, axis=1)]] = True
        self.cams = self.cams[~inside]
        self.owner = self.owner[~inside]

    def terrain_height(self, x, z):
        return terrain_height(self.terrain, x, z)

    def visible_from(self, points, exclude=(), max_dist=160.0):
        """Quanti punti del percorso vedono almeno uno dei punti (e la distanza minima)."""
        points = np.atleast_2d(np.asarray(points, dtype=float))
        if len(points) == 0 or len(self.cams) == 0:
            return 0, math.inf
        lo = points.min(axis=0) - max_dist
        hi = points.max(axis=0) + max_dist
        cm = np.all((self.cams >= lo) & (self.cams <= hi), axis=1)
        cams = self.cams[cm]
        owners = self.owner[cm]
        if len(cams) == 0:
            return 0, math.inf
        seen_owner = set()
        best = math.inf
        excl = set(exclude)
        for pt in points:
            d = np.linalg.norm(cams - pt, axis=1)
            sel = d <= max_dist
            if not sel.any():
                continue
            o = cams[sel]
            ow = owners[sel]
            dd = d[sel]
            vis = self._clear(o, pt, excl)
            if vis.any():
                seen_owner.update(ow[vis].tolist())
                best = min(best, dd[vis].min())
        return len(seen_owner), best

    def _clear(self, origins, target, excl):
        """Raggi liberi dalle origini al bersaglio (fermandosi 0.03 stud prima)."""
        seg = target - origins
        ln = np.linalg.norm(seg, axis=1)
        tmax = 1 - 0.03 / np.maximum(ln, 1e-6)
        lo = np.minimum(origins.min(axis=0), target)
        hi = np.maximum(origins.max(axis=0), target)
        m = np.all((self.occ_lo <= hi) & (self.occ_hi >= lo), axis=1)
        clear = np.ones(len(origins), dtype=bool)
        for k in np.where(m)[0]:
            p = self.occ[k]
            if p.i in excl:
                continue
            n, d = p.poly.normals, p.poly.offsets
            num = d[None, :] - origins @ n.T
            den = seg @ n.T
            with np.errstate(divide="ignore", invalid="ignore"):
                t = num / den
            enter = np.where(den < -1e-12, t, -np.inf).max(axis=1)
            leave = np.where(den > 1e-12, t, np.inf).min(axis=1)
            par_out = np.any((np.abs(den) <= 1e-12) & (num < 0), axis=1)
            t0 = np.maximum(enter, 0)
            t1 = np.minimum(leave, tmax)
            hit = (t0 <= t1) & ~par_out
            clear &= ~hit
            if not clear.any():
                break
        if self.terrain is not None and clear.any():
            # il terreno (dove c'e') nasconde cio' che ha sotto
            for f in (0.15, 0.3, 0.5, 0.7, 0.85, 0.97):
                q = origins + seg * f
                h = terrain_height(self.terrain, q[:, 0], q[:, 2])
                clear &= ~(q[:, 1] < h - 0.5)
        return clear


def terrain_height(T, x, z):
    """Quota del terreno (colonne di voxel da 4 stud) nel punto; -inf dove non c'e' terreno."""
    if T is None:
        return np.full(np.shape(x), -np.inf)
    rows = T["_rows"]
    ix = np.floor((np.asarray(x) - T["x0"]) / T["step"] + 0.5).astype(int)
    iz = np.floor((np.asarray(z) - T["z0"]) / T["step"] + 0.5).astype(int)
    ok = (ix >= 0) & (ix < rows.shape[1]) & (iz >= 0) & (iz < rows.shape[0])
    out = np.full(np.shape(ix), -np.inf)
    out[ok] = rows[iz[ok], ix[ok]]
    return out


# --------------------------------------------------------------------------------------- coppie
def broad_pairs(items_lo, items_hi, pad=0.0):
    """Coppie (i < j) di scatole allineate agli assi che si toccano (spazzata lungo x)."""
    order = np.argsort(items_lo[:, 0])
    lo_sorted = items_lo[order, 0]
    pairs = []
    for a, i in enumerate(order):
        end = np.searchsorted(lo_sorted, items_hi[i, 0] + pad, side="right")
        cand = order[a + 1:end]
        if len(cand) == 0:
            continue
        ok = np.all((items_lo[cand] <= items_hi[i] + pad) & (items_hi[cand] >= items_lo[i] - pad), axis=1)
        for j in cand[ok]:
            pairs.append((min(i, j), max(i, j)))
    return pairs


def inside_poly(poly, pts, eps=1e-4):
    pts = np.atleast_2d(pts)
    return np.all(pts @ poly.normals.T - poly.offsets <= eps, axis=1)


def match_planes(n, d, poly, tol=2e-3):
    return np.where((poly.normals @ n > 1 - 1e-5) & (np.abs(poly.offsets - d) < tol))[0]


def group_of(X, j):
    """Gruppo della faccia j: le facce piane sono un gruppo ciascuna, i lati curvi uno solo."""
    g = X.poly.group[j]
    return j if g >= 0 else g


def windows(I, X, Y):
    """Facce di X attraversate da Y: parti del contorno dell'intersezione che stanno su un piano di X e
    non su uno di Y (li' Y continua oltre la faccia di X). {gruppo di facce: [(faccia, poligono)]}"""
    out = {}
    for f in I:
        if len(f) < 3:
            continue
        n = face_normal(f)
        if n @ n < 0.25:
            continue
        d = float(n @ f.mean(axis=0))
        jx = match_planes(n, d, X.poly)
        if len(jx) == 0 or len(match_planes(n, d, Y.poly)) > 0:
            continue
        if poly_area(f, n) < 1e-4:
            continue
        j = int(jx[0])
        out.setdefault(group_of(X, j), []).append((j, f))
    return out


def depth_beyond(Y, X, g):
    """Quanto Y esce oltre il gruppo di facce g di X (dentro il prisma di quella faccia) e i vertici di
    quella sporgenza. Per il lato di un cilindro: quanto esce in direzione radiale fra le due basi."""
    if g == -2:
        return 99.0, np.zeros((0, 3))
    if g == -1:
        caps = [k for k in range(len(X.poly.normals)) if X.poly.group[k] >= 0]
        part = clip_poly(Y.poly.faces, X.poly.normals[caps], X.poly.offsets[caps])
        if not part:
            return 0.0, np.zeros((0, 3))
        pts = np.concatenate(part)
        axis = X.rot[:, 0]
        rel = pts - X.pos
        radial = np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1) - min(X.size[1], X.size[2]) / 2
        return float(radial.max()), pts[radial > 1e-3]
    nj = X.poly.normals[g]
    keep = [k for k in range(len(X.poly.normals)) if k != g and X.poly.normals[k] @ nj > -0.999]
    part = clip_poly(Y.poly.faces, X.poly.normals[keep], X.poly.offsets[keep])
    if not part:
        return 0.0, np.zeros((0, 3))
    pts = np.concatenate(part)
    sd = pts @ nj - X.poly.offsets[g]
    return float(sd.max()), pts[sd > 1e-3]


def opposite(X, a, b):
    """Due gruppi di facce opposti (per i lati curvi: due facce del lato con normali opposte)."""
    if a < 0 or b < 0:
        return False
    return float(X.poly.normals[a] @ X.poly.normals[b]) < -0.9


def through(X, win):
    """Coppie di facce opposte di X attraversate (Y passa da parte a parte)."""
    out = []
    gs = list(win)
    for a in gs:
        for b in gs:
            if a < b and opposite(X, a, b):
                out.append((a, b))
    for g in gs:
        if g == -1:
            ns = np.array([X.poly.normals[j] for j, _ in win[g]])
            if len(ns) > 1 and (ns @ ns.T).min() < -0.9:
                out.append((g, g))
    return out


class PairGeom:
    """Intersezione fra due parti A e B (ferme)."""

    def __init__(self, A, B, I):
        self.A, self.B, self.I = A, B, I
        self.vol = volume(I)
        self.fa = self.vol / max(A.vol, 1e-9)
        self.fb = self.vol / max(B.vol, 1e-9)
        self.winB = windows(I, B, A)  # A esce da B da queste facce di B
        self.winA = windows(I, A, B)  # B esce da A da queste facce di A
        self._dep = {}
        pts = np.concatenate(I)
        self.center = pts.mean(axis=0)
        self.lo, self.hi = pts.min(axis=0), pts.max(axis=0)

    def depth(self, which, j):
        """Sporgenza oltre la faccia j: which="B" -> quanto A esce da B, "A" -> quanto B esce da A."""
        key = (which, j)
        if key not in self._dep:
            self._dep[key] = depth_beyond(self.A, self.B, j) if which == "B" else depth_beyond(self.B, self.A, j)
        return self._dep[key]

    def window_points(self, which):
        """Punti sulle cuciture (bordo delle finestre), appena fuori dalla parte attraversata."""
        X = self.B if which == "B" else self.A
        win = self.winB if which == "B" else self.winA
        out = []
        for g, polys in win.items():
            for j, f in polys:
                n = X.poly.normals[j]
                c = f.mean(axis=0)
                out.append(c + n * 0.05)
                for v in f:
                    out.append(v + (c - v) * 0.1 + n * 0.05)
        return out


CONTACT = 0.004  # compenetrazioni piu' sottili di cosi' sono solo contatto (arrotondamenti del dump)


def pair_geometry(A, B):
    """Intersezione di due parti ferme (None se si toccano soltanto)."""
    X, Y = (A, B) if A.vol < B.vol else (B, A)
    if not clip_poly(X.poly.faces, Y.poly.normals, Y.poly.offsets - CONTACT):
        return None
    I = clip_poly(X.poly.faces, Y.poly.normals, Y.poly.offsets)
    if not I or volume(I) < 2e-4:
        return None
    return PairGeom(A, B, I)


def coplanar_overlaps(A, B):
    """Facce complanari rivolte dalla stessa parte che si sovrappongono: (gap, area, larghezza, punti)."""
    res = []
    for fa in range(len(A.poly.faces)):
        if not A.poly.flat[fa]:
            continue
        na, da = A.poly.normals[fa], A.poly.offsets[fa]
        dots = B.poly.normals @ na
        for fb in np.where(dots > 1 - 1e-5)[0]:
            if not B.poly.flat[fb]:
                continue
            gap = abs(B.poly.offsets[fb] - da)
            if gap > NEAR_COPLANAR:
                continue
            u, w = plane_basis(na)
            pa = to2d(A.poly.faces[fa], u, w)
            pb = to2d(B.poly.faces[fb], u, w)
            ov = clip2d(list(pa), list(pb))
            area = area2d(ov)
            if area < 0.02:
                continue
            width = min_width2d(ov)
            if width < 0.04:
                continue
            pts = np.array([p[0] * u + p[1] * w + na * da for p in ov])
            res.append((float(gap), float(area), float(width), pts, na))
    return res


# --------------------------------------------------------------------------------------- regole
def same_look(A, B, tol=8):
    return A.mat == B.mat and max(abs(a - b) for a, b in zip(A.color, B.color)) <= tol and abs(A.t - B.t) < 0.05


def is_layer(P):
    """Strato sottile appoggiato (vernice, muschio, schiuma, strisce): spesso al massimo 0.25 stud."""
    s = np.sort(P.size)
    return s[0] <= 0.25 and s[1] >= 1.0


def is_rod(P):
    """Asta o corda sottile (le due misure minori fino a 0.6 stud)."""
    s = np.sort(P.size)
    return s[1] <= 0.6 and s[2] >= 4 * s[1]


def wraps(g, X, a):
    """La parte Y avvolge la sezione di X (attraversata lungo la normale della faccia a di Y): le facce di X
    perpendicolari a quella direzione sono tutte attraversate da Y (anelli, collari, piastre forate)."""
    Y = g.B if X is g.A else g.A
    win = g.winA if X is g.A else g.winB
    n = Y.poly.normals[a] if a >= 0 else None
    if n is None:
        return False
    need = []
    for j in range(len(X.poly.normals)):
        if abs(X.poly.normals[j] @ n) < 0.2:
            need.append(group_of(X, j))
    need = set(need)
    return bool(need) and need <= set(win)


def classify_static(g):
    """(codice, testo) di un difetto fra due parti ferme, oppure (None, motivo) se e' voluto/nascosto."""
    A, B = g.A, g.B
    if A.piece and A.piece == B.piece:
        return None, "stesso elemento"
    if g.fa > 0.995 and B.opaque:
        return None, "dentro un'altra parte"
    if g.fb > 0.995 and A.opaque:
        return None, "dentro un'altra parte"
    # cartelli: la faccia col testo tagliata o coperta
    for S, O, win in ((A, B, g.winA), (B, A, g.winB)):
        if S.is_sign and O.visible:
            f = S.front_face()
            if f in win:
                area = sum(poly_area(p, S.poly.normals[j]) for j, p in win[f])
                return "SG", f"{S.name} ha la faccia col testo tagliata da {O.name} ({area:.2f} stud²)"
    a_see, b_see = A.tv >= SEE_THROUGH, B.tv >= SEE_THROUGH
    if a_see and b_see:
        return "TR", f"due parti trasparenti compenetrate ({g.vol:.2f} stud³): si vedono una dentro l'altra"
    if A.is_liquid or B.is_liquid:
        L, O = (A, B) if A.is_liquid else (B, A)
        if O.tv < SEE_THROUGH:
            return None, "esce dal liquido"
    if a_see or b_see:
        L, O = (A, B) if a_see else (B, A)
        winO = g.winB if O is B else g.winA  # facce di O attraversate da L
        if through(O, winO):
            return "TR", f"{L.name} (trasparente) attraversa {O.name} da parte a parte"
        return None, "parte trasparente piantata in una opaca"
    if same_look(A, B):
        return None, "stessa forma (stesso materiale e colore)"
    if A.wall and B.wall:
        return None, "rocce delle sponde"
    if is_layer(A) or is_layer(B):
        return None, "strato sottile appoggiato"
    for X, Y, winY in ((A, B, g.winB), (B, A, g.winA)):
        thr = through(Y, winY)
        if not thr:
            continue
        if is_rod(X):
            return None, "corda/asta che passa nei paletti"
        which = "B" if Y is B else "A"
        for a, b in thr:
            da = g.depth(which, a)[0]
            db = g.depth(which, b)[0] if b != a else da
            thin = min(da, db)
            if thin < SLIVER:
                return "PK", f"{X.name} esce di {thin:.2f} stud dall'altro lato di {Y.name}"
            if wraps(g, X, a):
                continue  # anello/collare/piastra attorno a X
            return "XP", f"{X.name} attraversa {Y.name} da parte a parte (esce di {da:.1f} e {db:.1f} stud)"
    return None, "piantata o appoggiata"


def zfight_kind(A, B, gap):
    if A.piece and A.piece == B.piece:
        return None
    if same_look(A, B, tol=0):
        return None
    return "ZF" if gap <= COPLANAR else "ZF~"


# --------------------------------------------------------------------------------------- analisi
class Finding:
    def __init__(self, code, text, A, B, center, points, size, extra=""):
        self.code, self.text, self.A, self.B = code, text, A, B
        self.center = np.asarray(center, dtype=float)
        self.points = np.atleast_2d(np.asarray(points, dtype=float)) if len(points) else np.zeros((0, 3))
        self.size = size
        self.extra = extra
        self.seen, self.dist = 0, math.inf
        self.sev = "."

    def rank(self):
        return ({"!!": 0, "!": 1, ".": 2}[self.sev], -self.seen, self.dist)

    def as_dict(self):
        s, u, y, v = local_coords(self.center)
        return {"code": self.code, "sev": self.sev, "text": self.text, "section": s, "u": round(u, 2),
                "v": round(v, 2), "y": round(y, 2), "world": [round(c, 2) for c in self.center],
                "a": self.A.label() if self.A else None, "b": self.B.label() if self.B else None,
                "folders": sorted({p.folder for p in (self.A, self.B) if p}), "seen_from": self.seen,
                "distance": None if math.isinf(self.dist) else round(self.dist, 1), "size": round(self.size, 3),
                "extra": self.extra}


def hidden_points(points, parts_near, exclude):
    """Punti dentro una parte opaca (che li nasconde)."""
    pts = np.atleast_2d(points)
    hid = np.zeros(len(pts), dtype=bool)
    for P in parts_near:
        if P.i in exclude or not P.opaque or not P.visible:
            continue
        m = np.all((pts >= P.poly.lo - 1e-6) & (pts <= P.poly.hi + 1e-6), axis=1)
        if m.any():
            hid[m] |= inside_poly(P.poly, pts[m], eps=1e-6)
    return hid


class Posed:
    """Una parte mobile in una delle sue pose (per le stesse funzioni delle parti ferme)."""

    def __init__(self, P, k):
        pos, rot, tr = P.poses[k]
        self.__dict__.update(P.__dict__)
        self.pos, self.rot, self.tv, self.t = pos, rot, tr, tr
        self.poly = make_poly(P.local, pos, rot)
        self.pose = k


def static_pass(parts, viewer, findings, ignored):
    static = [p for p in parts if p.visible and not p.moving]
    lo = np.array([p.poly.lo for p in static])
    hi = np.array([p.poly.hi for p in static])
    for i, j in broad_pairs(lo, hi, pad=NEAR_COPLANAR + 0.01):
        A, B = static[i], static[j]
        # z-fighting
        for gap, area, width, pts, nrm in coplanar_overlaps(A, B):
            kind = zfight_kind(A, B, gap)
            if not kind:
                continue
            c = pts.mean(axis=0)
            samples = np.concatenate([[c], pts + (c - pts) * 0.15]) + nrm * 0.03
            near = [P for P in static if np.all(P.poly.lo <= samples.max(0) + 0.1) and np.all(P.poly.hi >= samples.min(0) - 0.1)]
            hid = hidden_points(samples, near, {A.i, B.i})
            exposed = samples[~hid]
            what = "facce complanari" if kind == "ZF" else f"facce quasi complanari ({gap:.3f} stud)"
            f = Finding("ZF", f"{what} sovrapposte per {area:.2f} stud² (largo {width:.2f}): {A.name} / {B.name}",
                        A, B, c, exposed, area, extra="near" if kind == "ZF~" else "")
            if len(exposed) == 0:
                f.sev = "."
                f.extra = "coperte da altre parti"
            findings.append(f)
        # compenetrazioni
        g = pair_geometry(A, B)
        if not g:
            continue
        code, why = classify_static(g)
        if code is None:
            ignored[why] = ignored.get(why, 0) + 1
            continue
        pts = g.window_points("A") + g.window_points("B")
        if code == "TR" or not pts:
            pts = list(np.concatenate(g.I))
        findings.append(Finding(code, why, A, B, g.center, pts, g.vol))


def mover_pass(parts, viewer, findings, ignored):
    static = [p for p in parts if p.visible and not p.moving]
    lo = np.array([p.poly.lo for p in static])
    hi = np.array([p.poly.hi for p in static])
    for M in parts:
        if not (M.moving and M.visible):
            continue
        worst = {}
        for k in range(len(M.poses)):
            if M.poses[k][2] >= 0.98:
                continue
            P = Posed(M, k)
            cand = np.where(np.all((lo <= P.poly.hi) & (hi >= P.poly.lo), axis=1))[0]
            for c in cand:
                S = static[c]
                if S.piece and S.piece == M.piece:
                    continue
                if not clip_poly(P.poly.faces, S.poly.normals, S.poly.offsets - CONTACT):
                    continue
                I = clip_poly(P.poly.faces, S.poly.normals, S.poly.offsets)
                vol = volume(I) if I else 0
                if vol < 2e-4:
                    continue
                w = worst.get(S.i)
                if w is None or vol > w[0]:
                    worst[S.i] = (vol, k, I, (w[3] if w else 0) + 1)
                else:
                    worst[S.i] = (w[0], w[1], w[2], w[3] + 1)
        for si, (vol, k, I, count) in worst.items():
            S = parts[si]
            pv = np.array(M.e.get("pv", M.pos), dtype=float)
            if S.is_liquid:
                ignored["mobile nel liquido"] = ignored.get("mobile nel liquido", 0) + 1
                continue
            if M.kind in ("Swing", "Sweeper", "Spinner") and np.all(
                    S.poly.normals @ pv - S.poly.offsets <= 0.6):
                ignored["perno/mozzo dell'elemento"] = ignored.get("perno/mozzo dell'elemento", 0) + 1
                continue
            P = Posed(M, k)
            g = PairGeom(P, S, I)
            frac = k / len(M.poses)
            tr = M.poses[k][2]
            text = (f"{M.name} ({M.kind}{'/' + M.role if M.role else ''}) entra in {S.name} per {vol:.2f} stud³ "
                    f"in {count} pose su {len(M.poses)} (la peggiore a {frac:.0%} del periodo)")
            pts = g.window_points("A") + g.window_points("B") or list(np.concatenate(I))
            f = Finding("MV", text, P, S, g.center, pts, vol)
            if tr >= 0.6:
                f.extra = f"trasparenza {tr:g} in quella posa"
            findings.append(f)


def terrain_pass(parts, terrain, findings):
    """Il terreno sopra le facce superiori (pavimenti, vasche, sponde) delle parti visibili."""
    if terrain is None:
        return
    T = terrain
    x0, x1 = T["x0"] - T["step"] / 2, T["x0"] + (T["_rows"].shape[1] - 0.5) * T["step"]
    for P in parts:
        if not P.visible or P.moving or P.poly.hi[0] < x0 or P.poly.lo[0] > x1:
            continue
        if abs(P.pos[2] - COURSE_Z) > HALF_WIDTH + 30 and P.folder == "Pieces":
            continue
        bad = []
        for j, f in enumerate(P.poly.faces):
            n = P.poly.normals[j]
            if n[1] < 0.3:
                continue
            u, w = plane_basis(n)
            p2 = f @ np.stack([u, w], axis=1)
            lo2, hi2 = p2.min(axis=0), p2.max(axis=0)
            nu = max(2, int((hi2[0] - lo2[0]) / 1.5) + 1)
            nw = max(2, int((hi2[1] - lo2[1]) / 1.5) + 1)
            gu, gw = np.meshgrid(np.linspace(lo2[0], hi2[0], nu), np.linspace(lo2[1], hi2[1], nw))
            cand = np.stack([gu.ravel(), gw.ravel()], axis=1)
            base = f[0] - (f[0] @ u) * u - (f[0] @ w) * w
            pts3 = base + np.outer(cand[:, 0], u) + np.outer(cand[:, 1], w)
            # solo i punti dentro la faccia
            inside = np.all(pts3 @ P.poly.normals.T - P.poly.offsets <= 1e-3, axis=1)
            pts3 = pts3[inside]
            if len(pts3) == 0:
                continue
            h = terrain_height(T, pts3[:, 0], pts3[:, 2])
            over = h - pts3[:, 1]
            m = over > 0.3
            if m.any():
                bad.extend([(pts3[q], over[q]) for q in np.where(m)[0]])
        if bad:
            pts = np.array([b[0] for b in bad])
            worst = max(b[1] for b in bad)
            findings.append(Finding("TE", f"il terreno spunta sopra {P.name} fino a {worst:.1f} stud ({len(bad)} punti)",
                                    P, None, pts.mean(axis=0), pts + np.array([0, 0.2, 0]), float(worst)))
