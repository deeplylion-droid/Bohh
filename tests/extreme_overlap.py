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
import copy
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

    CAMS = [(0, 4.5, 0), (12, 9, 0), (0, 9, 9), (0, 9, -9)]

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
        # un punto ogni 5 stud basta
        key = np.round(spots / 5).astype(int)
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

    def _tables(self):
        """Piani di tutti gli ostacoli impilati (per i raggi vettorizzati)."""
        if hasattr(self, "_N"):
            return
        N, D, own = [], [], []
        for k, p in enumerate(self.occ):
            N.append(p.poly.normals)
            D.append(p.poly.offsets)
            own.append(np.full(len(p.poly.offsets), k))
        self._N = np.concatenate(N)
        self._D = np.concatenate(D)
        self._own = np.concatenate(own)

    def visible_from(self, points, exclude=(), max_dist=150.0, enough=8, chunk=64):
        """Quanti punti del percorso vedono almeno uno dei punti (si ferma a 'enough') e la distanza
        minima. Le telecamere si provano dalla piu' vicina."""
        points = np.atleast_2d(np.asarray(points, dtype=float))
        if len(points) == 0 or len(self.cams) == 0:
            return 0, math.inf
        if len(points) > 10:
            points = points[np.linspace(0, len(points) - 1, 10).astype(int)]
        self._tables()
        c = points.mean(axis=0)
        d = np.linalg.norm(self.cams - c, axis=1)
        order = np.argsort(d)
        order = order[d[order] <= max_dist]
        excl_occ = np.array([p.i in set(exclude) for p in self.occ])
        seen, best = set(), math.inf
        for a in range(0, len(order), chunk):
            idx = order[a:a + chunk]
            cams = self.cams[idx]
            R = len(cams) * len(points)
            org = np.repeat(cams, len(points), axis=0)
            tgt = np.tile(points, (len(cams), 1))
            vis = self._clear_many(org, tgt, excl_occ).reshape(len(cams), len(points)).any(axis=1)
            if vis.any():
                seen.update(self.owner[idx[vis]].tolist())
                best = min(best, float(np.linalg.norm(cams[vis] - c, axis=1).min()))
                if len(seen) >= enough:
                    break
            del R
        return len(seen), best

    def _clear_many(self, org, tgt, excl_occ):
        seg = tgt - org
        ln = np.linalg.norm(seg, axis=1)
        tmax = 1 - 0.03 / np.maximum(ln, 1e-6)
        lo = np.minimum(org.min(axis=0), tgt.min(axis=0))
        hi = np.maximum(org.max(axis=0), tgt.max(axis=0))
        cand = np.all((self.occ_lo <= hi) & (self.occ_hi >= lo), axis=1) & ~excl_occ
        clear = np.ones(len(org), dtype=bool)
        if cand.any():
            sel = cand[self._own]
            N, D, own = self._N[sel], self._D[sel], self._own[sel]
            starts = np.concatenate([[0], np.where(np.diff(own) != 0)[0] + 1])
            num = D[None, :] - org @ N.T
            den = seg @ N.T
            with np.errstate(divide="ignore", invalid="ignore"):
                t = num / den
            enter = np.maximum.reduceat(np.where(den < -1e-12, t, -np.inf), starts, axis=1)
            leave = np.minimum.reduceat(np.where(den > 1e-12, t, np.inf), starts, axis=1)
            par = np.logical_or.reduceat((np.abs(den) <= 1e-12) & (num < 0), starts, axis=1)
            hit = (np.maximum(enter, 0) <= np.minimum(leave, tmax[:, None])) & ~par
            clear = ~hit.any(axis=1)
        if self.terrain is not None and clear.any():
            # il terreno (dove c'e') nasconde cio' che ha sotto
            for f in (0.15, 0.3, 0.5, 0.7, 0.85, 0.97):
                q = org + seg * f
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
    """Strato sottile appoggiato (vernice, muschio, schiuma, strisce): spesso al massimo 0.5 stud."""
    s = np.sort(P.size)
    return s[0] <= 0.5 and s[1] >= 1.0


def is_rod(P):
    """Asta o corda sottile (le due misure minori fino a 0.6 stud)."""
    s = np.sort(P.size)
    return s[1] <= 0.6 and s[2] >= 4 * s[1]


def exit_components(X, Y):
    """Pezzi di X fuori da Y: X meno Y e' l'unione dei pezzi convessi X ∩ {oltre la faccia j di Y}; due
    pezzi che si toccano sono lo stesso pezzo. Restituisce le componenti: [(facce di Y, sporgenza, punti)].
    Una sola componente = X piantata/appoggiata in Y; due o piu' = X spunta in punti separati (passa da
    parte a parte, o esce dietro)."""
    pieces = {}
    for j in range(len(Y.poly.normals)):
        n, d = Y.poly.normals[j], Y.poly.offsets[j]
        part = clip_faces(X.poly.faces, -n, -d - CONTACT)
        if part and volume(part) > 1e-4:
            pts = np.concatenate(part)
            pieces[j] = (part, float((pts @ n - d).max()), pts)
    keys = list(pieces)
    parent = {k: k for k in keys}

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            ja, jb = keys[a], keys[b]
            if root(ja) == root(jb):
                continue
            both = clip_faces(pieces[ja][0], -Y.poly.normals[jb], -Y.poly.offsets[jb] - CONTACT)
            if both and volume(both) > 1e-5:
                parent[root(ja)] = root(jb)
    comps = {}
    for k in keys:
        comps.setdefault(root(k), []).append(k)
    out = []
    for ks in comps.values():
        depth = max(pieces[k][1] for k in ks)
        pts = np.concatenate([pieces[k][2] for k in ks])
        out.append((ks, depth, pts))
    return out


def hugs(X, Y, comps):
    """Y e' una fascia/anello attorno a X (collare di una colonna, cornice): sottile lungo la direzione in
    cui X la attraversa e poco piu' larga di X tutt'attorno."""
    j = comps[0][0][0]
    n = Y.poly.normals[j]
    proj = Y.poly.verts @ n
    if proj.max() - proj.min() > 1.6:
        return False
    u, w = plane_basis(n)
    for axis in (u, w, (u + w) / math.sqrt(2), (u - w) / math.sqrt(2)):
        xa, ya = X.poly.verts @ axis, Y.poly.verts @ axis
        if ya.min() > xa.min() + 0.05 or ya.max() < xa.max() - 0.05:
            return False
        if ya.min() < xa.min() - 1.2 or ya.max() > xa.max() + 1.2:
            return False
    return True


def inner_points(faces):
    """Punti dentro un poliedro (centro, centri delle facce e punti verso i vertici): i soli vertici di una
    sovrapposizione lunga e sottile possono stare tutti dentro qualcos'altro."""
    verts = np.concatenate(faces)
    c = verts.mean(axis=0)
    fc = np.array([f.mean(axis=0) for f in faces])
    out = [c]
    for q in np.concatenate([verts, fc]):
        out.extend([c + (q - c) * 0.4, c + (q - c) * 0.85])
    return out


def window_points_for(g, which, faces):
    """Punti sulle cuciture delle finestre di quelle facce (appena fuori dalla parte attraversata)."""
    X = g.B if which == "B" else g.A
    win = g.winB if which == "B" else g.winA
    out = []
    for polys in win.values():
        for j, f in polys:
            if j in faces:
                n = X.poly.normals[j]
                c = f.mean(axis=0)
                out.append(c + n * 0.05)
                out.extend(v + (c - v) * 0.1 + n * 0.05 for v in f)
                out.extend(v + (c - v) * 0.5 + n * 0.05 for v in f)
    return out


def classify_static(g):
    """(codice, testo, gruppi di punti) di un difetto fra due parti ferme, oppure (None, motivo, None) se e'
    voluto o nascosto. Il difetto conta solo se si vede ogni gruppo di punti (es. tutti e due i lati di un
    palo che passa da parte a parte)."""
    A, B = g.A, g.B
    if A.piece and A.piece == B.piece:
        return None, "stesso elemento", None
    if g.fa > 0.995 and B.opaque:
        return None, "dentro un'altra parte", None
    if g.fb > 0.995 and A.opaque:
        return None, "dentro un'altra parte", None
    # cartelli: la faccia col testo tagliata o coperta
    for S, O, win, which in ((A, B, g.winA, "A"), (B, A, g.winB, "B")):
        if S.is_sign and O.visible:
            f = S.front_face()
            if f in win:
                area = sum(poly_area(q, S.poly.normals[j]) for j, q in win[f])
                return ("SG", f"{S.name} ha la faccia col testo tagliata da {O.name} ({area:.2f} stud²)",
                        [(window_points_for(g, which, {f}), {O.i})])
    a_see, b_see = A.tv >= SEE_THROUGH, B.tv >= SEE_THROUGH
    if a_see and b_see:
        if is_layer(A) and is_layer(B):
            return None, "strati sottili sovrapposti", None
        return ("TR", f"due parti trasparenti compenetrate ({g.vol:.2f} stud³): si vede una dentro l'altra",
                [(inner_points(g.I), {A.i, B.i})])
    if A.is_liquid or B.is_liquid:
        L, O = (A, B) if A.is_liquid else (B, A)
        if O.tv < SEE_THROUGH:
            return None, "esce dal liquido", None
    if same_look(A, B):
        return None, "stessa forma (stesso materiale e colore)", None
    if A.wall and B.wall:
        return None, "rocce delle sponde", None
    if is_layer(A) or is_layer(B):
        return None, "strato sottile appoggiato", None
    for X, Y, which in ((A, B, "B"), (B, A, "A")):
        comps = exit_components(X, Y)
        if len(comps) < 2:
            continue
        if is_rod(X):
            return None, "corda/asta che passa nei paletti", None
        if hugs(X, Y, comps):
            return None, "fascia/anello attorno a una colonna", None
        comps.sort(key=lambda c: c[1])
        groups = [(window_points_for(g, which, set(c[0])) or list(c[2]), {X.i}) for c in comps]
        see = "(trasparente) " if X.tv >= SEE_THROUGH else ""
        if comps[0][1] < SLIVER:
            return ("PK", f"{X.name} {see}spunta di {comps[0][1]:.2f} stud dall'altro lato di {Y.name}",
                    [groups[0]])
        code = "TR" if see else "XP"
        return (code, f"{X.name} {see}passa da parte a parte in {Y.name} (spunta di "
                + " e ".join(f"{c[1]:.1f}" for c in comps) + " stud)", groups)
    return None, "piantata o appoggiata", None


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


def posed(P, k):
    """Copia di una parte mobile nella sua posa k (per le stesse funzioni delle parti ferme)."""
    Q = copy.copy(P)
    Q.pos, Q.rot, tr = P.poses[k]
    Q.tv = Q.t = tr
    Q.poly = make_poly(P.local, Q.pos, Q.rot)
    Q.pose = k
    return Q


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
            f.groups = [(exposed, set())]
            if len(exposed) == 0:
                f.sev = "."
                f.extra = "coperte da altre parti"
            findings.append(f)
        # compenetrazioni
        g = pair_geometry(A, B)
        if not g:
            continue
        code, why, groups = classify_static(g)
        if code is None:
            ignored[why] = ignored.get(why, 0) + 1
            continue
        groups = [(np.atleast_2d(np.asarray(q, dtype=float)), ex) for q, ex in groups if len(q)]
        f = Finding(code, why, A, B, g.center, np.concatenate([q for q, _ in groups]) if groups else [], g.vol)
        f.groups = groups
        findings.append(f)


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
            P = posed(M, k)
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
        vertical = all(abs(q[0][0] - M.poses[0][0][0]) < 0.3 and abs(q[0][2] - M.poses[0][0][2]) < 0.3
                       and np.abs(q[1] - M.poses[0][1]).max() < 1e-3 for q in M.poses)
        for si, (vol, k, I, count) in worst.items():
            S = parts[si]
            pv = np.array(M.e.get("pv", M.pos), dtype=float)

            def ok(why):
                ignored[why] = ignored.get(why, 0) + 1

            if S.is_liquid:
                ok("mobile nel liquido")
                continue
            if is_layer(S):
                ok("mobile che passa in uno strato sottile (schiuma, vernice)")
                continue
            if M.kind in ("Swing", "Sweeper", "Spinner") and np.all(
                    S.poly.normals @ pv - S.poly.offsets <= 0.6):
                ok("perno/mozzo dell'elemento")
                continue
            P = posed(M, k)
            if M.kind == "Spinner":
                # gira su se' stesso: il volume spazzato e' la parte stessa, valgono le regole delle parti ferme
                code, why, _ = classify_static(PairGeom(P, S, I))
                if code is None:
                    ok(why)
                    continue
            if vertical:
                comps = exit_components(P, S)
                if len(comps) == 1 and all(S.poly.normals[j][1] > 0.7 for j in comps[0][0]):
                    ok("sale e scende dal fondo (piantato dall'alto)")
                    continue
            g = PairGeom(P, S, I)
            frac = k / len(M.poses)
            tr = M.poses[k][2]
            text = (f"{M.name} ({M.kind}{'/' + M.role if M.role else ''}) entra in {S.name} per {vol:.2f} stud³ "
                    f"in {count} pose su {len(M.poses)} (la peggiore a {frac:.0%} del periodo)")
            pts = g.window_points("A") + g.window_points("B") + inner_points(I)
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
            top = pts.copy()
            top[:, 1] = terrain_height(T, pts[:, 0], pts[:, 2]) + 0.1  # sulla superficie del terreno
            findings.append(Finding("TE", f"il terreno spunta sopra {P.name} fino a {worst:.1f} stud ({len(bad)} punti)",
                                    P, None, pts.mean(axis=0), top, float(worst)))


# --------------------------------------------------------------------------------------- rapporto
SEVERITY_RULES = {
    # codice: (minimo di punti di vista, distanza massima, misura minima) per "!!"
    "ZF": (3, 60, 0.5),
    "SG": (2, 60, 0.0),
    "TR": (3, 60, 0.1),
    "PK": (4, 40, 0.0),
    "XP": (3, 60, 0.0),
    "MV": (3, 80, 0.0),
    "TE": (1, 120, 0.5),
}


def grade(f, viewer):
    if f.sev == "." and f.extra:
        return
    both = {p.i for p in (f.A, f.B) if p is not None}
    groups = getattr(f, "groups", None) or [(f.points, both)]
    f.seen, f.dist = math.inf, math.inf
    for q, excl in groups:
        seen, dist = viewer.visible_from(q, exclude=excl) if len(q) else (0, math.inf)
        f.seen = min(f.seen, seen)
        f.dist = min(f.dist, dist) if seen else f.dist
    if f.seen == math.inf:
        f.seen = 0
    if f.seen == 0:
        f.sev = "."
        f.extra = f.extra or "non si vede dal percorso"
        return
    need, dmax, smin = SEVERITY_RULES.get(f.code, (3, 60, 0))
    strong = f.seen >= need and f.dist <= dmax and f.size >= smin
    if f.extra == "near" or (f.extra.startswith("trasparenza")):
        strong = False
    f.sev = "!!" if strong else "!"


def extent(P):
    """Ingombro della parte in coordinate di sezione (come gli argomenti di slab in Shared.Extreme)."""
    if P is None:
        return ""
    s, _, _, _ = local_coords(P.pos)
    x0 = SECTIONS[max(s, 1) - 1][2]
    lo, hi = P.poly.lo, P.poly.hi
    return (f"u {x0 - hi[0]:.1f}..{x0 - lo[0]:.1f}  v {lo[2] - COURSE_Z:+.1f}..{hi[2] - COURSE_Z:+.1f}  "
            f"y {lo[1]:.1f}..{hi[1]:.1f}")


def report(findings, args, ignored, stats):
    out = []
    shown = [f for f in findings if args.verbose or f.sev != "."]
    if args.section is not None:
        shown = [f for f in shown if section_of(f.center[0]) == args.section]
    if args.folder:
        shown = [f for f in shown if any(p is not None and p.folder == args.folder for p in (f.A, f.B))]
    shown.sort(key=lambda f: (section_of(f.center[0]) if section_of(f.center[0]) else 0.5, f.rank()))
    out.append(f"Percorso Estremo - controllo compenetrazioni: {stats}")
    last = None
    for f in shown:
        s = section_of(f.center[0])
        if s != last:
            out.append("")
            out.append(f"== {'Bivio e ingresso' if s == 0 else f'Sezione {s}: ' + SECTIONS[s - 1][1]}")
            last = s
        vis = f"visto da {f.seen} punti, il piu' vicino a {f.dist:.0f} stud" if f.seen else (f.extra or "nascosto")
        out.append(f"{f.sev:>2} {f.code} {fmt_where(f.center)}")
        out.append(f"      {f.text}  [{vis}]")
        for tag, P in (("A", f.A), ("B", f.B)):
            if P is not None:
                pose = f"  (posa {P.pose})" if hasattr(P, "pose") else ""
                out.append(f"      {tag}: {P.label()}  {extent(P)}{pose}")
        if f.extra and f.seen and f.extra != "near":
            out.append(f"      nota: {f.extra}")
    n2 = sum(1 for f in findings if f.sev == "!!")
    n1 = sum(1 for f in findings if f.sev == "!")
    n0 = sum(1 for f in findings if f.sev == ".")
    out.append("")
    out.append(f"Totale: {n2} chiaramente visibili (!!), {n1} visibili ma piccoli/lontani (!), "
               f"{n0} nascosti o minori (.)" + ("" if args.verbose else " - questi ultimi con --verbose"))
    if args.verbose:
        out.append("Casi voluti, non segnalati: " + ", ".join(f"{k} {v}" for k, v in sorted(ignored.items(), key=lambda kv: -kv[1])))
    return "\n".join(out), n2 + n1


def run_dump(path):
    cmd = [str(ROOT / ".tools/bin/lune"), "run", "tests/extreme_dump.luau", "--all", "--poses", "--terrain",
           "--out", str(path)]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stdout + res.stderr)
        sys.exit(2)
    for line in (res.stdout + res.stderr).splitlines():
        if not line.startswith("[extreme_dump]"):
            print(line)  # avvisi della costruzione (es. errori nei moduli d'arredo)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dump", help="dump gia' fatto (con --all --poses --terrain); senza, lo rifa'")
    ap.add_argument("--section", type=int, help="solo questa sezione (0 = bivio)")
    ap.add_argument("--folder", help="solo i problemi che toccano questa cartella (es. ExtremeDecorA)")
    ap.add_argument("--verbose", action="store_true", help="anche i casi minori, nascosti e voluti")
    ap.add_argument("--json", help="salva il rapporto completo in questo file")
    args = ap.parse_args()
    path = Path(args.dump) if args.dump else DEFAULT_DUMP
    if not args.dump:
        path.parent.mkdir(parents=True, exist_ok=True)
        run_dump(path)
    data, parts = load_parts(path)
    terrain = data.get("terrain")
    if terrain:
        terrain["_rows"] = np.array(terrain["rows"], dtype=float)
    if not any(p.poses for p in parts):
        print("attenzione: il dump non ha le pose degli elementi mobili (serve --poses): salto il controllo MV")
    viewer = Viewer(parts, terrain)
    findings, ignored = [], {}
    static_pass(parts, viewer, findings, ignored)
    mover_pass(parts, viewer, findings, ignored)
    terrain_pass(parts, terrain, findings)
    for f in findings:
        grade(f, viewer)
    stats = (f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}: {len(parts)} parti, "
             f"{sum(1 for p in parts if p.moving)} mobili, {len(viewer.spots)} punti di vista")
    text, bad = report(findings, args, ignored, stats)
    print(text)
    if args.json:
        Path(args.json).write_text(json.dumps({"findings": [f.as_dict() for f in findings], "ignored": ignored},
                                              indent=1, ensure_ascii=False))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
