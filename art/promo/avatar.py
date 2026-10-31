"""Avatar "Bacon Hair" in stile Roblox classico (R6) per le copertine: costruito da zero in Blender (niente
asset scaricati), con parti separate e perni nelle articolazioni per metterlo in posa.

Proporzioni R6 in stud (1 unita' Blender = 1 stud, Z in alto, guarda verso -Y come i pet):
- gambe 1 x 1 x 2, busto 2 x 1 x 2, braccia 1 x 1 x 2, testa "classica" (cilindro con i bordi molto
  arrotondati) larga 1,2; altezza totale circa 5,1;
- spigoli smussati (scatole arrotondate esatte, nessun artefatto di ombreggiatura sulle facce piatte);
- faccia "Smile" di default: due ovali neri verticali e il sorriso ad arco, decalcomanie sottili che
  seguono la curvatura della testa;
- capelli "bacon": calotta marrone + ciocche a nastro ondulate (come strisce di pancetta) con strisce
  chiare color cuoio lungo la lunghezza, ciuffo che spazza la fronte e punte che sporgono;
- maglietta a maniche corte di colore acceso, avambracci color pelle, pantaloni e scarpe.

Gerarchia dei perni (empty): Root (bacino, z = 2) -> HipR/HipL -> gambe; Root -> Waist -> busto,
Neck -> testa/faccia/capelli, ShoulderR/ShoulderL -> braccia. Il lato destro del personaggio e' -X.
Rotazioni in gradi (Euler XYZ, locali al perno): per braccia e gambe X negativo = avanti, -180 = in alto.

Uso come modulo (vedi promo/covers.py):
    import avatar
    rig = avatar.build("Bacon", shirt="#2fd24a")
    avatar.pose(rig, "run_carry")            # oppure un dizionario {perno: (rx, ry, rz)}
    rig.root.location = (x, y, z); rig.root.rotation_euler.z = ...

Anteprima (dalla cartella art/): nice -n 10 ../.tools/venv/bin/python promo/avatar.py pose 960 48
-> art/out/promo/covers/work/avatar_preview.png (quattro pose); con 'head' come primo argomento\navatar_head.png (la testa da tre angolazioni). Argomenti: [pose|head] [res] [samples].
"""
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_scenes as S  # noqa: E402

ART = Path(__file__).resolve().parents[1]
WORK = ART / "out" / "promo" / "covers" / "work"

# colori predefiniti (sRGB)
SKIN = "#f5c08f"
SHIRT = "#2fd24a"
PANTS = "#2a55b8"
SHOES = "#2a2a35"
HAIR_DARK = "#4a2412"
HAIR_BASE = "#7b3f1d"
HAIR_LIGHT = "#d39a5c"

HEAD_R = 0.6      # raggio della testa
HEAD_H = 0.6      # meta' altezza
HEAD_RR = 0.27    # raggio degli arrotondamenti sopra e sotto


# =================================================================================== mesh di base
def _mesh_object(name, verts, faces, mat=None, smooth=True, uvs=None, parent=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(map(int, f)) for f in faces])
    me.validate()
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        loop_uv = np.zeros((len(me.loops), 2), dtype=np.float32)
        vi = np.zeros(len(me.loops), dtype=np.int64)
        me.loops.foreach_get("vertex_index", vi)
        loop_uv[:] = np.asarray(uvs, dtype=np.float32)[vi]
        uvl.data.foreach_set("uv", loop_uv.ravel())
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        ob.data.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    return ob


def rounded_box(name, size, r, center=(0, 0, 0), mat=None, parent=None, k=5, m=3):
    """Scatola con spigoli arrotondati di raggio r (somma di Minkowski scatola + sfera), griglia fitta vicino
    agli spigoli cosi' le facce piatte restano piatte anche con l'ombreggiatura morbida."""
    hs = np.array(size, dtype=float) / 2.0

    def coords(h):
        band = (h - r) + r * np.linspace(0, 1, k + 1)
        inner = np.linspace(-(h - r), h - r, m + 1)
        # una linea in piu' appena prima dell'arrotondamento: la sfumatura delle normali resta in una fascia stretta
        guard = min(0.02, (h - r) * 0.2)
        inner = np.concatenate([[-(h - r) + guard], inner[1:-1], [(h - r) - guard]])
        return np.concatenate([-band[::-1], inner, band])

    cx, cy, cz = coords(hs[0]), coords(hs[1]), coords(hs[2])
    bm = bmesh.new()
    lim = hs - r

    def add_face(axis, sign):
        a1, a2 = [a for a in range(3) if a != axis]
        c1 = (cx, cy, cz)[a1]
        c2 = (cx, cy, cz)[a2]
        grid = []
        for i, u in enumerate(c1):
            row = []
            for j, v in enumerate(c2):
                p = np.zeros(3)
                p[axis] = sign * hs[axis]
                p[a1] = u
                p[a2] = v
                q = np.clip(p, -lim, lim)
                d = p - q
                n = np.linalg.norm(d)
                pos = q + d / n * r
                row.append(bm.verts.new(tuple(pos + np.array(center))))
            grid.append(row)
        for i in range(len(c1) - 1):
            for j in range(len(c2) - 1):
                quad = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
                # orientamento verso l'esterno
                if (sign > 0) != ((axis == 1)):
                    quad = quad[::-1]
                bm.faces.new(quad)

    for axis in range(3):
        for sign in (-1, 1):
            add_face(axis, sign)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        ob.data.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    return ob


def head_profile(n=40):
    """Profilo (rho, z) della testa classica dal polo sud al polo nord (cilindro con bordi arrotondati)."""
    R, H, rr = HEAD_R, HEAD_H, HEAD_RR
    pts = [(0.0, -H)]
    for t in np.linspace(0, 1, 6)[1:]:
        pts.append(((R - rr) * t, -H))
    for a in np.linspace(-math.pi / 2, 0, n // 4 + 2)[1:]:
        pts.append((R - rr + rr * math.cos(a), -H + rr + rr * math.sin(a)))
    for z in np.linspace(-H + rr, H - rr, 9)[1:-1]:
        pts.append((R, z))
    for a in np.linspace(0, math.pi / 2, n // 4 + 2):
        pts.append((R - rr + rr * math.cos(a), H - rr + rr * math.sin(a)))
    for t in np.linspace(1, 0, 6)[1:]:
        pts.append(((R - rr) * t, H))
    # togli duplicati consecutivi
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return np.array(out)


def revolve(name, profile, seg=64, mat=None, parent=None, center=(0, 0, 0)):
    prof = np.asarray(profile)
    verts, faces = [], []
    n = len(prof)
    for s in range(seg):
        a = 2 * math.pi * s / seg
        ca, sa = math.cos(a), math.sin(a)
        for rho, z in prof:
            verts.append((center[0] + rho * ca, center[1] + rho * sa, center[2] + z))
    for s in range(seg):
        s2 = (s + 1) % seg
        for i in range(n - 1):
            faces.append((s * n + i, s * n + i + 1, s2 * n + i + 1, s2 * n + i))
    ob = _mesh_object(name, verts, faces, mat, parent=parent)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def head_sdf(p):
    """Distanza con segno dalla testa (coordinate locali al centro della testa), vettoriale."""
    p = np.atleast_2d(p)
    R, H, rr = HEAD_R, HEAD_H, HEAD_RR
    qx = np.hypot(p[:, 0], p[:, 1]) - (R - rr)
    qz = np.abs(p[:, 2]) - (H - rr)
    out = np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - rr
    return out


def surface_dist(dirs):
    """Distanza dal centro della testa alla superficie lungo le direzioni (N x 3, normalizzate)."""
    dirs = np.atleast_2d(dirs)
    lo = np.zeros(len(dirs))
    hi = np.full(len(dirs), 1.2)
    for _ in range(40):
        mid = (lo + hi) / 2
        inside = head_sdf(dirs * mid[:, None]) < 0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    return (lo + hi) / 2


def head_normal(p, eps=1e-3):
    p = np.atleast_2d(p)
    g = np.zeros_like(p)
    for i in range(3):
        d = np.zeros(3)
        d[i] = eps
        g[:, i] = head_sdf(p + d) - head_sdf(p - d)
    return g / np.linalg.norm(g, axis=1, keepdims=True)


# =================================================================================== materiali
def plastic(name, color, rough=0.42, coat=0.25, sss=0.0):
    mat, nt, out = S.new_material(name)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = S.lin(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.12
    if sss > 0:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.3)
        b.inputs["Subsurface Scale"].default_value = 0.05
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return mat


def hair_material(name="BaconHair", dark=HAIR_DARK, base=HAIR_BASE, light=HAIR_LIGHT):
    """Strisce lungo la ciocca (coordinata UV v di traverso): bordo scuro, carne marrone-rossiccia, grasso chiaro."""
    mat, nt, out = S.new_material(name)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    nz = S.node(nt, "ShaderNodeTexNoise", Scale=3.0, Detail=2.0)
    nt.links.new(uv.outputs["UV"], nz.inputs["Vector"])
    v = S.math_node(nt, "ADD", sep.outputs["Y"], S.math_node(nt, "MULTIPLY", S.math_node(nt, "SUBTRACT", nz.outputs["Fac"], 0.5), 0.16))
    d, b_, l_ = S.lin(dark), S.lin(base), S.lin(light)
    mid = tuple((a + c) / 2 for a, c in zip(b_[:3], l_[:3])) + (1,)
    col = S.ramp(nt, v, [(0.0, d), (0.1, d), (0.17, b_), (0.3, b_), (0.36, l_), (0.46, l_), (0.52, b_), (0.66, b_),
                         (0.71, mid), (0.77, mid), (0.83, b_), (0.9, d), (1.0, d)])
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Coat Weight"].default_value = 0.2
    b.inputs["Coat Roughness"].default_value = 0.2
    b.inputs["Sheen Weight"].default_value = 0.3
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    return mat


# =================================================================================== faccia
def face_decals(parent, mat, eye_sep=0.2, eye_z=0.08, eye_w=0.07, eye_h=0.14, smile_r=0.34, smile_z=0.12,
                smile_a=(-132, -48), smile_w=0.05, eps=0.004):
    """Faccia "Smile": i punti (u = arco orizzontale dal centro, v = quota) si avvolgono sulla testa."""

    def wrap(u, v):
        a = u / HEAD_R
        d = np.array([[math.sin(a), -math.cos(a), 0.0]])
        # raggio della superficie a quella quota (la testa e' un cilindro con il bordo arrotondato)
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) / 2
            p = np.array([[mid * d[0, 0], mid * d[0, 1], v]])
            if head_sdf(p)[0] < 0:
                lo = mid
            else:
                hi = mid
        rho = (lo + hi) / 2 + eps
        return (rho * d[0, 0], rho * d[0, 1], v)

    verts, faces = [], []

    def ellipse(cu, cv, a, b, n=40):
        base = len(verts)
        verts.append(wrap(cu, cv))
        for i in range(n):
            t = 2 * math.pi * i / n
            verts.append(wrap(cu + a * math.cos(t), cv + b * math.sin(t)))
        for i in range(n):
            faces.append((base, base + 1 + i, base + 1 + (i + 1) % n))

    ellipse(-eye_sep, eye_z, eye_w, eye_h)
    ellipse(eye_sep, eye_z, eye_w, eye_h)
    # sorriso: arco spesso con le estremita' arrotondate
    a0, a1 = map(math.radians, smile_a)
    n = 36
    base = len(verts)
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        for rr in (smile_r - smile_w / 2, smile_r + smile_w / 2):
            verts.append(wrap(rr * math.cos(t), smile_z + rr * math.sin(t)))
    for i in range(n):
        a, b = base + 2 * i, base + 2 * i + 1
        c, d = base + 2 * (i + 1) + 1, base + 2 * (i + 1)
        faces.append((a, d, c, b))
    for t in (a0, a1):
        ellipse(smile_r * math.cos(t), smile_z + smile_r * math.sin(t), smile_w / 2, smile_w / 2, n=16)
    ob = _mesh_object("Face", verts, faces, mat, parent=parent)
    # le decalcomanie sono rivolte verso l'esterno
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for f in bm.faces:
        c = f.calc_center_median()
        if f.normal.dot(Vector((c.x, c.y, 0))) < 0:
            f.normal_flip()
    bm.to_mesh(ob.data)
    bm.free()
    return ob


# =================================================================================== capelli "bacon"
def _frame(points):
    t = np.gradient(points, axis=0)
    return t / np.linalg.norm(t, axis=1, keepdims=True)


def lock(name, centers, normals, widths, thick, mat, parent, ripple=0.03, freq=2.2, phase=0.0, nr=14, v_shift=0.0):
    """Ciocca 'a pancetta': tubo a sezione ellittica schiacciata (larghezza widths, spessore thick) lungo la linea
    centrale, ondulata lungo la lunghezza, chiusa a punta. UV: u lungo la ciocca, v di traverso (strisce chiare)."""
    c = np.asarray(centers, float)
    nrm = np.asarray(normals, float)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    tan = _frame(c)
    side = np.cross(tan, nrm)
    side /= np.linalg.norm(side, axis=1, keepdims=True)
    nrm = np.cross(side, tan)
    n = len(c)
    verts, uvs, faces = [], [], []
    for i in range(n):
        t = i / (n - 1)
        wave = ripple * math.sin(2 * math.pi * freq * t + phase) * min(1.0, 4 * t)
        for j in range(nr):
            phi = 2 * math.pi * j / nr
            cs, sn = math.cos(phi), math.sin(phi)
            # increspatura di traverso: i bordi ondeggiano piu' del centro
            edge = ripple * 0.7 * math.sin(2 * math.pi * freq * t + phase + 1.7 * cs) * abs(cs)
            p = (c[i] + side[i] * (widths[i] / 2) * cs + nrm[i] * ((thick[i] / 2) * sn + wave + edge)
                 + nrm[i] * 0.25 * thick[i] * (1 - cs * cs))  # dorso un po' bombato
            verts.append(p)
            uvs.append((t, (cs + 1) / 2 * 0.86 + 0.07 + v_shift))
    tip = len(verts)
    verts.append(c[-1] + tan[-1] * 0.02)
    uvs.append((1.0, 0.5))
    root = len(verts)
    verts.append(c[0] - tan[0] * 0.01)
    uvs.append((0.0, 0.5))
    for i in range(n - 1):
        for j in range(nr):
            a = i * nr + j
            b = i * nr + (j + 1) % nr
            faces.append((a, b, b + nr, a + nr))
    for j in range(nr):
        faces.append(((n - 1) * nr + j, (n - 1) * nr + (j + 1) % nr, tip))
        faces.append((root, (j + 1) % nr, j))
    ob = _mesh_object(name, verts, faces, mat, uvs=uvs, parent=parent)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def strand_path(start_dir, end_dir, n=24, lift0=0.03, lift1=0.16, lift_pow=2.2, bulge=0.0, tip_out=0.0, tip_turn=None):
    """Linea centrale di una ciocca che segue la testa (da start_dir a end_dir, interpolazione sferica),
    staccandosi sempre di piu' verso la punta."""
    a = np.asarray(start_dir, float)
    b = np.asarray(end_dir, float)
    a /= np.linalg.norm(a)
    b /= np.linalg.norm(b)
    om = math.acos(np.clip(a @ b, -1, 1))
    ts = np.linspace(0, 1, n)
    dirs = []
    for t in ts:
        if om < 1e-4:
            d = a
        else:
            d = (math.sin((1 - t) * om) * a + math.sin(t * om) * b) / math.sin(om)
        dirs.append(d / np.linalg.norm(d))
    dirs = np.array(dirs)
    rad = surface_dist(dirs)
    lift = lift0 + (lift1 - lift0) * ts ** lift_pow + bulge * np.sin(ts * math.pi)
    pts = dirs * (rad + lift)[:, None]
    nrm = head_normal(dirs * rad[:, None])
    if tip_out:
        # la punta si allontana dalla testa (ciuffo che sporge)
        k = np.clip((ts - 0.55) / 0.45, 0, 1) ** 2
        pts += nrm * (tip_out * k)[:, None]
    if tip_turn is not None:
        k = np.clip((ts - 0.5) / 0.5, 0, 1) ** 2
        pts += np.outer(k, np.asarray(tip_turn, float))
    return pts, nrm


def sph(az, el):
    """Direzione dal centro della testa: az = azimut in gradi da davanti (-Y) verso la sinistra del personaggio (+X),
    el = elevazione in gradi."""
    a, e = math.radians(az), math.radians(el)
    return np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])


def hairline(az):
    """Quota dell'attaccatura dei capelli (coordinate della testa) in funzione dell'azimut: alta sulla fronte,
    all'altezza degli occhi ai lati, bassa sulla nuca."""
    front = math.cos(math.radians(az))
    return 0.36 * max(front, 0) ** 1.6 + 0.06 - 0.44 * max(-front, 0) ** 1.3 - 0.02 * (1 - abs(front))


def hair_cap(parent, mat, seg=96, nv=28, off=0.03):
    """Calotta: la superficie della testa (gonfiata di off) dal polo nord fino all'attaccatura, bordo liscio."""
    prof = head_profile(64)
    # parametrizza il profilo dal polo nord verso il basso per lunghezza d'arco
    pr = prof[::-1]
    seglen = np.hypot(np.diff(pr[:, 0]), np.diff(pr[:, 1]))
    s_acc = np.concatenate([[0], np.cumsum(seglen)])
    verts, uvs, faces = [], [], []
    for k in range(seg):
        az = 360.0 * k / seg
        zc = hairline(az)
        # lunghezza d'arco dove il profilo scende a quota zc
        idx = np.nonzero(pr[:, 1] <= zc)[0]
        i1 = idx[0] if len(idx) else len(pr) - 1
        i0 = max(i1 - 1, 0)
        f = 0.0 if pr[i0, 1] == pr[i1, 1] else (pr[i0, 1] - zc) / (pr[i0, 1] - pr[i1, 1])
        s_end = s_acc[i0] + f * (s_acc[i1] - s_acc[i0])
        a = math.radians(az)
        tri = abs(((k / seg) * 12.0) % 2.0 - 1.0)
        for j in range(nv + 1):
            s = s_end * j / nv
            rho = np.interp(s, s_acc, pr[:, 0])
            z = np.interp(s, s_acc, pr[:, 1])
            d = np.array([rho * math.sin(a), -rho * math.cos(a), z])
            nn = head_normal(d)[0]
            # il bordo si assottiglia verso l'attaccatura
            verts.append(d + nn * off * (1.0 - 0.6 * (j / nv) ** 6))
            uvs.append((j / nv, tri))
    verts.append((0.0, 0.0, HEAD_H + off))
    uvs.append((0.0, 0.5))
    pole = len(verts) - 1
    for k in range(seg):
        k2 = (k + 1) % seg
        for j in range(nv):
            a0, a1 = k * (nv + 1) + j, k2 * (nv + 1) + j
            faces.append((a0, a1, a1 + 1, a0 + 1))
    ob = _mesh_object("HairCap", verts, faces, mat, uvs=uvs, parent=parent)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    for p in ob.data.polygons:
        p.use_smooth = True
    sol = ob.modifiers.new("spessore", "SOLIDIFY")
    sol.thickness = 0.03
    sol.offset = -1.0
    return ob


def taper(n, w0, w_mid, start=0.12, power=0.7):
    t = np.linspace(0, 1, n)
    return w0 + (w_mid - w0) * np.sin(np.clip(t + start, 0, 1) * math.pi * 0.5 / (1 - start * 0.5)) ** 0.3 * (1 - t) ** power


def path_waypoints(wps, n=32, lift=(0.06, 0.1), bulge=0.05, tip_out=0.0, tip_turn=None):
    """Linea centrale da una lista di tappe (azimut, elevazione) in gradi, interpolate con Catmull-Rom sulla
    superficie della testa; la ciocca si stacca di lift[0] alla radice e lift[1] alla punta (+ bulge a meta')."""
    w = np.asarray(wps, float)
    # Catmull-Rom con estremi duplicati
    P = np.vstack([w[0] * 2 - w[1], w, w[-1] * 2 - w[-2]])
    segs = len(w) - 1
    out = []
    for k in range(n):
        u = k / (n - 1) * segs
        i = min(int(u), segs - 1)
        t = u - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        t2, t3 = t * t, t * t * t
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    ae = np.array(out)
    dirs = np.array([sph(a, e) for a, e in ae])
    rad = surface_dist(dirs)
    ts = np.linspace(0, 1, n)
    lf = lift[0] + (lift[1] - lift[0]) * ts ** 2 + bulge * np.sin(ts * math.pi)
    pts = dirs * (rad + lf)[:, None]
    nrm = head_normal(dirs * rad[:, None])
    if tip_out:
        k = np.clip((ts - 0.6) / 0.4, 0, 1) ** 2
        pts += nrm * (tip_out * k)[:, None]
    if tip_turn is not None:
        k = np.clip((ts - 0.55) / 0.45, 0, 1) ** 2
        pts += np.outer(k, np.asarray(tip_turn, float))
    return pts, nrm


def bacon_hair(parent, mat, seed=3):
    """Capelli 'bacon': calotta + ciocche voluminose ondulate. Fronte = -Y, sinistra del personaggio = +X.
    Ogni ciocca e' una lista di tappe (azimut, elevazione) sulla testa."""
    rng = np.random.default_rng(seed)
    objs = [hair_cap(parent, mat)]

    def add(name, wps, w, th, lift=(0.06, 0.1), bulge=0.05, tip_out=0.0, tip_turn=None, n=34, ripple=0.026, freq=1.6,
            vs=0.0, tip_start=0.62):
        pts, nrm = path_waypoints(wps, n=n, lift=lift, bulge=bulge, tip_out=tip_out, tip_turn=tip_turn)
        t = np.linspace(0, 1, n)
        # larga quasi fino in fondo, poi punta arrotondata
        body = np.clip(t * 6, 0, 1) ** 0.5 * 0.3 + 0.7
        tipk = 1 - np.clip((t - tip_start) / (1 - tip_start), 0, 1) ** 1.6
        width = w * body * tipk + 0.02
        thick = th * body * tipk ** 0.7 + 0.015
        objs.append(lock(name, pts, nrm, width, thick, mat, parent, ripple=ripple, freq=freq,
                         phase=rng.uniform(0, 6.28), v_shift=vs))

    # nuca e lati (strato basso): dal vertice all'attaccatura, punte appena in fuori
    for i, az in enumerate(np.linspace(70, 290, 9)):
        front = math.cos(math.radians(az))
        zc = hairline(az)
        el_end = math.degrees(math.asin(np.clip((zc + 0.02) / 0.64, -1, 1)))
        a0 = az + 14 + rng.uniform(-5, 5)
        add(f"HairBack{i}", [(a0, 80), (az + 6, 50), (az + rng.uniform(-5, 5), el_end)],
            w=0.6 + rng.uniform(-0.04, 0.04), th=0.1, lift=(0.05, 0.07), bulge=0.05,
            tip_out=0.06 + 0.05 * max(-front, 0) + rng.uniform(0, 0.03), ripple=0.04, freq=2.2 + rng.uniform(0, 0.6),
            vs=rng.uniform(-0.05, 0.05))
    # vertice: volume
    for i, wps in enumerate(([(190, 62), (120, 70), (60, 64)], [(160, 55), (220, 70), (290, 58)],
                             [(130, 50), (90, 64), (40, 70)], [(230, 48), (280, 64), (330, 66)])):
        add(f"HairTop{i}", wps, w=0.62, th=0.1, lift=(0.08, 0.1), bulge=0.05, tip_out=0.0, ripple=0.04, freq=2.0,
            tip_start=0.5)
    # ciuffo: tre ciocche separate che spazzano la fronte da destra (-X) a sinistra (+X), punte verso la tempia
    # sinistra (in basso, di lato, in alto)
    add("HairFringe0", [(-70, 64), (-35, 50), (0, 43), (35, 37), (58, 26)], w=0.52, th=0.1, lift=(0.08, 0.1),
        bulge=0.05, tip_turn=(0.06, -0.06, -0.04), ripple=0.045, freq=2.4, tip_start=0.6)
    add("HairFringe1", [(-110, 68), (-60, 60), (-15, 55), (30, 50), (66, 44)], w=0.52, th=0.1, lift=(0.11, 0.13),
        bulge=0.05, tip_turn=(0.12, 0.0, 0.05), ripple=0.045, freq=2.4, vs=0.05, tip_start=0.6)
    add("HairFringe2", [(-150, 66), (-100, 66), (-50, 68), (0, 67), (45, 64)], w=0.52, th=0.1, lift=(0.13, 0.16),
        bulge=0.05, tip_turn=(0.12, 0.0, 0.1), ripple=0.045, freq=2.4, vs=-0.04, tip_start=0.62)
    # ciocca davanti all'orecchio destro, punta in giu'
    add("HairSideR", [(-60, 66), (-72, 44), (-80, 22), (-84, 8)], w=0.46, th=0.1, lift=(0.07, 0.07), bulge=0.04,
        tip_out=0.05, ripple=0.04, freq=2.0, tip_start=0.55)
    return objs


# =================================================================================== personaggio
@dataclass
class Rig:
    root: object
    joints: dict = field(default_factory=dict)
    parts: dict = field(default_factory=dict)
    objects: list = field(default_factory=list)


def _empty(name, loc, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_size = 0.3
    if parent is not None:
        e.parent = parent
    e.location = loc
    return e


def build(name="Bacon", skin=SKIN, shirt=SHIRT, pants=PANTS, shoes=SHOES, hair=True, seed=3, edge=0.09) -> Rig:
    m_skin = plastic(f"{name}Skin", skin, rough=0.45, coat=0.15, sss=0.15)
    m_shirt = plastic(f"{name}Shirt", shirt, rough=0.55, coat=0.1)
    m_pants = plastic(f"{name}Pants", pants, rough=0.6, coat=0.05)
    m_shoes = plastic(f"{name}Shoes", shoes, rough=0.5, coat=0.2)
    m_face = plastic(f"{name}Face", "#141018", rough=0.35, coat=0.3)
    m_hair = hair_material(f"{name}Hair")

    root = _empty(name, (0, 0, 2.0))
    rig = Rig(root)
    J = rig.joints
    J["Root"] = root
    J["Waist"] = _empty(f"{name}_Waist", (0, 0, 0), root)
    J["Neck"] = _empty(f"{name}_Neck", (0, 0, 2.0), J["Waist"])
    J["ShoulderR"] = _empty(f"{name}_ShoulderR", (-1.5, 0, 1.5), J["Waist"])
    J["ShoulderL"] = _empty(f"{name}_ShoulderL", (1.5, 0, 1.5), J["Waist"])
    J["HipR"] = _empty(f"{name}_HipR", (-0.5, 0, 0), root)
    J["HipL"] = _empty(f"{name}_HipL", (0.5, 0, 0), root)
    P = rig.parts
    e = edge
    # busto: maglietta + fascia dei pantaloni in basso
    P["Torso"] = rounded_box(f"{name}_Torso", (2, 1, 1.72), e, (0, 0, 1.14), m_shirt, J["Waist"])
    P["Belt"] = rounded_box(f"{name}_Belt", (2.0, 1.0, 0.36), e * 0.8, (0, 0, 0.18), m_pants, J["Waist"])
    # braccia: manica corta + avambraccio color pelle (il perno e' 0,5 sotto la cima del braccio)
    for side, sx in (("R", -1), ("L", 1)):
        sh = J[f"Shoulder{side}"]
        P[f"Sleeve{side}"] = rounded_box(f"{name}_Sleeve{side}", (1.0, 1.0, 0.82), e, (0, 0, 0.09), m_shirt, sh)
        P[f"Arm{side}"] = rounded_box(f"{name}_Arm{side}", (0.96, 0.96, 1.3), e, (0, 0, -0.84), m_skin, sh)
        hp = J[f"Hip{side}"]
        P[f"Leg{side}"] = rounded_box(f"{name}_Leg{side}", (1.0, 1.0, 1.66), e, (0, 0, -0.83), m_pants, hp)
        P[f"Shoe{side}"] = rounded_box(f"{name}_Shoe{side}", (1.02, 1.04, 0.36), e, (0, -0.01, -1.82), m_shoes, hp)
    # testa (centro 0,5 sopra il collo: la base affonda di 0,1 nel busto come in R6)
    head_c = _empty(f"{name}_HeadCenter", (0, 0, 0.5), J["Neck"])
    J["HeadCenter"] = head_c
    P["Head"] = revolve(f"{name}_Head", head_profile(), 72, m_skin, head_c)
    P["Face"] = face_decals(head_c, m_face)
    if hair:
        for o in bacon_hair(head_c, m_hair, seed=seed):
            P[o.name] = o
    rig.objects = [o for o in P.values()]
    bpy.context.view_layer.update()
    return rig


POSES = {
    # braccia dritte in alto a reggere l'uovo, falcata di corsa, busto un po' in avanti
    "run_carry": {"Root": (8, 0, 0), "Waist": (0, 0, 0), "Neck": (-6, 0, 0),
                  "ShoulderR": (-172, 8, 0), "ShoulderL": (-168, -8, 0), "HipR": (-42, 0, 0), "HipL": (38, 0, 0)},
    # salto: gambe divaricate avanti/indietro, braccia in alto e in fuori
    "leap": {"Root": (-6, 0, 0), "Waist": (0, 0, 0), "Neck": (-8, 0, 0),
             "ShoulderR": (-150, 30, 0), "ShoulderL": (-160, -26, 0), "HipR": (-62, 0, 0), "HipL": (44, 0, 0)},
    # corsa normale (braccia che oscillano)
    "run": {"Root": (10, 0, 0), "Neck": (-6, 0, 0), "ShoulderR": (50, 0, 0), "ShoulderL": (-60, 0, 0),
            "HipR": (-45, 0, 0), "HipL": (40, 0, 0)},
    "idle": {},
}


def pose(rig: Rig, p):
    angles = POSES[p] if isinstance(p, str) else p
    for name, j in rig.joints.items():
        if name in ("HeadCenter",):
            continue
        rx, ry, rz = angles.get(name, (0, 0, 0))
        j.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    bpy.context.view_layer.update()


def world_bounds(rig: Rig):
    return S.bounds([o for o in rig.objects if o.type == "MESH"])


# =================================================================================== anteprima
def preview(res=960, samples=48):
    S.reset()
    sc = S.setup_render(res, samples)
    sc.render.resolution_x, sc.render.resolution_y = res, res * 9 // 16
    S.world_sky([(0.0, S.lin("#d9ecff")), (0.5, S.lin("#7fb4ff")), (1.0, S.lin("#3d78e6"))], light_color=S.lin("#cfe2ff"),
                light_strength=0.9)
    xs = [-7.5, -2.5, 2.5, 7.5]
    for x, ps in zip(xs, ["idle", "run_carry", "leap", "run"]):
        rig = build(f"B{ps}")
        pose(rig, ps)
        rig.root.location = (x, 0, 2.0 + (0.6 if ps == "leap" else 0))
        rig.root.rotation_euler.z = math.radians(-25)
    ground = S.grid_object("Ground", -30, 30, -20, 30, 4, 4, lambda gx, gy: gx * 0)
    ground.data.materials.append(plastic("GroundM", "#e8eef8", rough=0.8, coat=0))
    S.sun_light("Sun", (-0.6, -0.8, 0.9), 3.5, (1, 0.96, 0.9), angle=3)
    S.area_light("Rim", (4, 8, 7), (0, 0, 3), 1500, 8, (0.8, 0.9, 1))
    S.camera((2.0, -21, 4.2), (0, 0, 2.8), lens=45)
    out = S.render_to(WORK / "avatar_preview.png")
    print(f"[avatar] {out}")


def preview_head(res=640, samples=32):
    """Primi piani della testa (tre angolazioni affiancate) per rifinire capelli e faccia."""
    from PIL import Image
    tiles = []
    for i, (az, el) in enumerate(((-28, 8), (35, 18), (150, 25))):
        S.reset()
        sc = S.setup_render(res, samples)
        S.world_sky([(0.0, S.lin("#d9ecff")), (1.0, S.lin("#5f94ea"))], light_color=S.lin("#cfe2ff"), light_strength=0.9)
        rig = build("BHead")
        hc = Vector(rig.joints["HeadCenter"].matrix_world.translation)
        S.sun_light("Sun", (-0.6, -0.8, 0.9), 3.5, (1, 0.96, 0.9), angle=3)
        S.area_light("Rim", (4, 8, 7), tuple(hc), 900, 6, (0.8, 0.9, 1))
        a, e = math.radians(az), math.radians(el)
        d = 5.0
        cam = hc + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * d
        S.camera(tuple(cam), tuple(hc + Vector((0, 0, 0.15))), lens=85)
        tiles.append(S.render_to(WORK / f"avatar_head_{i}.png"))
    ims = [Image.open(t) for t in tiles]
    sheet = Image.new("RGB", (res * len(ims), res))
    for i, im in enumerate(ims):
        sheet.paste(im, (i * res, 0))
    sheet.save(WORK / "avatar_head.png")
    print(f"[avatar] {WORK / 'avatar_head.png'}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "pose"
    r = int(sys.argv[2]) if len(sys.argv) > 2 else 960
    s = int(sys.argv[3]) if len(sys.argv) > 3 else 48
    (preview_head if mode == "head" else preview)(r, s)
