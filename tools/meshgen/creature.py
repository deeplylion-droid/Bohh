"""The Rake come mesh unica con scheletro (skinned mesh glTF): corpo scheletrico continuo, ~40 ossa
(colonna, collo, testa, mascella, braccia con quattro dita lunghe, gambe digitigrade).

Coordinate di progetto Roblox (Y in alto, fronte -Z, suolo a y=0). All'esportazione si applica la stessa
rotazione di 180 gradi degli altri modelli: le ossa importate risultano quindi ruotate di 180 gradi su Y.

Uso: python3 tools/meshgen/creature.py  ->  build/assets/RakeBody.glb e build/assets/rake_bones.json
"""
import io
import json
import math
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))

from PIL import Image  # noqa: E402

from atlas import T, TILE, TILES, build_atlas  # noqa: E402
from shapes import add, cross, dot, lerp, mul, norm, sub  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "build", "assets")

# ---------------------------------------------------------------------------------------------
# Scheletro: nome -> (genitore, posizione globale)

BONES = {}


def bone(name, parent, pos):
    BONES[name] = (parent, pos)


bone("Root", None, (0, 3.9, 0.15))
bone("Spine1", "Root", (0, 4.6, 0.12))
bone("Spine2", "Spine1", (0, 5.3, -0.12))
bone("Spine3", "Spine2", (0, 5.95, -0.55))
bone("Neck1", "Spine3", (0, 6.45, -1.0))
bone("Neck2", "Neck1", (0, 6.75, -1.35))
bone("Head", "Neck2", (0, 6.95, -1.6))
bone("Jaw", "Head", (0, 6.85, -1.72))
for side, s in (("L", -1), ("R", 1)):
    bone("Clav" + side, "Spine3", (s * 0.15, 6.2, -0.75))
    bone("Shoulder" + side, "Clav" + side, (s * 0.95, 6.12, -0.85))
    bone("Elbow" + side, "Shoulder" + side, (s * 1.18, 3.85, -1.0))
    bone("Wrist" + side, "Elbow" + side, (s * 1.12, 1.55, -1.42))
    for f in range(4):
        spread = (f - 1.5) * 0.11
        base = (s * (1.12 + spread * 0.9), 1.2, -1.5 - abs(spread) * 0.2)
        bone("Fing%d%sA" % (f, side), "Wrist" + side, base)
        bone("Fing%d%sB" % (f, side), "Fing%d%sA" % (f, side), (base[0] + s * spread * 0.6, 0.48, -1.72 - abs(spread) * 0.3))
    bone("Hip" + side, "Root", (s * 0.5, 3.75, 0.25))
    bone("Knee" + side, "Hip" + side, (s * 0.56, 2.05, -0.78))
    bone("Ankle" + side, "Knee" + side, (s * 0.56, 0.48, 0.36))
    bone("Toe" + side, "Ankle" + side, (s * 0.56, 0.12, -0.28))

NAMES = list(BONES.keys())
INDEX = {n: i for i, n in enumerate(NAMES)}


def P(name):
    return BONES[name][1]


# ---------------------------------------------------------------------------------------------
# Geometria pesata


class SkinMesh:
    def __init__(self):
        self.tris = []  # ((p, w), (p, w), (p, w), tile)  w = {bone: peso}

    def tri(self, a, b, c, tile):
        n = cross(sub(b[0], a[0]), sub(c[0], a[0]))
        if dot(n, n) < 1e-12:
            return
        self.tris.append((a, b, c, tile))

    def tri_out(self, a, b, c, ref, tile):
        n = cross(sub(b[0], a[0]), sub(c[0], a[0]))
        centroid = mul(add(add(a[0], b[0]), c[0]), 1 / 3)
        if dot(n, sub(centroid, ref)) < 0:
            b, c = c, b
        self.tri(a, b, c, tile)


def chain_weight(bones, k, t, blend=0.22):
    """Peso di un punto al parametro t del segmento k di una catena di ossa (k = osso di partenza)."""
    w = {bones[k]: 1.0}
    if t < blend:
        prev = bones[k - 1] if k > 0 else BONES[bones[k]][0]
        if prev:
            a = 0.5 * (1 - t / blend)
            w = {bones[k]: 1 - a, prev: a}
    elif t > 1 - blend and k + 1 < len(bones):
        a = 0.5 * (t - (1 - blend)) / blend
        w = {bones[k]: 1 - a, bones[k + 1]: a}
    return w


def frame(tangent):
    side = (1, 0, 0) if abs(tangent[0]) < 0.9 else (0, 0, 1)
    x = norm(sub(side, mul(tangent, dot(side, tangent))))
    y = cross(tangent, x)
    return x, y


def limb(mesh, points, bones, radii, tile, segments=10, profile=None, cap_end=True, sub_steps=3, rnd=None):
    """Tubo lungo una catena di punti; bones[k] guida il segmento points[k]->points[k+1].
    radii: (rx, rz) o raggio per ogni punto; profile(angle, s) modula il raggio (s = 0..1 lungo il tubo)."""
    rnd = rnd or random.Random(len(points))
    rings, centers = [], []
    n = len(points)
    total = (n - 1) * sub_steps
    for k in range(n - 1):
        for st in range(sub_steps + (1 if k == n - 2 else 0)):
            t = st / sub_steps
            c = lerp(points[k], points[k + 1], t)
            r0 = radii[k] if isinstance(radii[k], tuple) else (radii[k], radii[k])
            r1 = radii[k + 1] if isinstance(radii[k + 1], tuple) else (radii[k + 1], radii[k + 1])
            rx, rz = r0[0] + (r1[0] - r0[0]) * t, r0[1] + (r1[1] - r0[1]) * t
            tangent = norm(sub(points[k + 1], points[k]))
            if k > 0 and t < 0.5:
                prev = norm(sub(points[k], points[k - 1]))
                tangent = norm(lerp(prev, tangent, 0.5 + t))
            fx, fy = frame(tangent)
            s = (k * sub_steps + st) / total
            w = chain_weight(bones, k, t)
            ring = []
            for j in range(segments):
                ang = 2 * math.pi * j / segments
                m = profile(ang, s) if profile else 1.0
                m *= 1 + rnd.uniform(-0.04, 0.04)
                p = add(c, add(mul(fx, math.cos(ang) * rx * m), mul(fy, math.sin(ang) * rz * m)))
                ring.append((p, w))
            rings.append(ring)
            centers.append(c)
    for i in range(len(rings) - 1):
        ref = lerp(centers[i], centers[i + 1], 0.5)
        for j in range(segments):
            k2 = (j + 1) % segments
            a, b, c, d = rings[i][j], rings[i][k2], rings[i + 1][k2], rings[i + 1][j]
            mesh.tri_out(a, b, c, ref, tile)
            mesh.tri_out(a, c, d, ref, tile)
    for idx, ref_dir in ((0, -1), (len(rings) - 1, 1)):
        if idx == len(rings) - 1 and not cap_end:
            continue
        center = centers[idx]
        w = rings[idx][0][1]
        nxt = centers[idx + ref_dir] if 0 <= idx + ref_dir < len(centers) else center
        ref = nxt
        for j in range(segments):
            mesh.tri_out((center, w), rings[idx][j], rings[idx][(j + 1) % segments], ref, tile)


def ellipsoid(mesh, center, radii, weights, tile, subdiv=2, deform=None, seed=0):
    from shapes import icosphere
    verts, faces = icosphere(subdiv)
    rnd = random.Random(seed)
    pts = []
    for v in verts:
        p = (v[0] * radii[0], v[1] * radii[1], v[2] * radii[2])
        if deform:
            p = deform(v, p)
        p = mul(p, 1 + rnd.uniform(-0.03, 0.03))
        pts.append((add(center, p), weights))
    for a, b, c in faces:
        mesh.tri_out(pts[a], pts[b], pts[c], center, tile)


def spike(mesh, base, tip, width, weights, tile):
    """Cono sottile a tre facce (denti, artigli)."""
    d = norm(sub(tip, base))
    fx, fy = frame(d)
    ring = [add(base, add(mul(fx, math.cos(a) * width), mul(fy, math.sin(a) * width))) for a in (0, 2.1, 4.2)]
    for i in range(3):
        mesh.tri_out((ring[i], weights), (ring[(i + 1) % 3], weights), (tip, weights), base, tile)


def build():
    mesh = SkinMesh()
    skin, claw, bone_t = T["skin"], T["rubber"], T["bark_birch"]
    rnd = random.Random(42)

    # Tronco: bacino, vita sottile, gabbia toracica con costole, spalle
    pelvis_bottom = (0, 3.45, 0.2)
    top = (0, 6.25, -0.85)
    spine_pts = [pelvis_bottom, P("Root"), P("Spine1"), P("Spine2"), P("Spine3"), top]
    spine_bones = ["Root", "Root", "Spine1", "Spine2", "Spine3"]
    radii = [(0.42, 0.3), (0.55, 0.36), (0.33, 0.26), (0.6, 0.46), (0.66, 0.44), (0.38, 0.3)]

    def torso_profile(ang, s):
        m = 1.0
        if 0.42 < s < 0.86:  # costole sul davanti e sui fianchi
            front = max(0.0, -math.sin(ang))
            m += 0.07 * front * max(0.0, math.sin((s - 0.42) / 0.44 * math.pi * 6))
            m -= 0.05 * front
        back = max(0.0, math.sin(ang))  # cresta della colonna
        m += 0.12 * back ** 12
        return m

    limb(mesh, spine_pts, spine_bones, radii, skin, segments=16, profile=torso_profile, sub_steps=5, rnd=rnd)
    # creste delle anche e scapole
    for s in (-1, 1):
        ellipsoid(mesh, (s * 0.42, 3.95, 0.05), (0.18, 0.2, 0.25), {"Root": 1}, skin, 1, seed=s)
        ellipsoid(mesh, (s * 0.42, 5.95, -0.2), (0.3, 0.32, 0.12), {"Spine3": 1}, skin, 1, seed=s + 5)
    # vertebre sporgenti
    for i in range(9):
        t = i / 8
        p = lerp(P("Spine1"), top, t)
        b = "Spine1" if t < 0.3 else ("Spine2" if t < 0.65 else "Spine3")
        ellipsoid(mesh, add(p, (0, 0, 0.36 + 0.06 * math.sin(t * 3))), (0.08, 0.06, 0.1), {b: 1}, bone_t, 1)

    # Collo lungo e testa
    limb(mesh, [top, P("Neck1"), P("Neck2"), P("Head")], ["Spine3", "Neck1", "Neck2"], [0.2, 0.15, 0.13, 0.15], skin, segments=9,
         profile=lambda a, s: 1 + 0.15 * max(0.0, math.cos(a * 2)) ** 4, rnd=rnd)
    head = P("Head")
    skull_c = add(head, (0, 0.28, -0.25))

    def skull_deform(v, p):
        # orbite incavate e zigomi
        for sx in (-1, 1):
            eye = norm((sx * 0.45, 0.15, -0.88))
            d = dot(v, eye)
            if d > 0.9:
                p = mul(p, 1 - (d - 0.9) * 2.2)
        if v[2] < -0.6 and v[1] < 0:
            p = (p[0] * 0.8, p[1], p[2])
        return p

    ellipsoid(mesh, skull_c, (0.36, 0.42, 0.58), {"Head": 1}, skin, 3, deform=skull_deform, seed=7)
    ellipsoid(mesh, add(head, (0, 0.45, 0.15)), (0.3, 0.3, 0.36), {"Head": 1}, skin, 2, seed=8)
    # muso superiore e denti
    snout = add(head, (0, 0.08, -0.72))
    ellipsoid(mesh, snout, (0.24, 0.16, 0.36), {"Head": 1}, skin, 2, seed=9)
    for i in range(13):
        a = -1.2 + i * 0.2
        base = add(snout, (math.sin(a) * 0.2, -0.1, -math.cos(a) * 0.3 + 0.05))
        spike(mesh, base, add(base, (0, -0.2 - 0.06 * (i % 2), -0.02)), 0.025, {"Head": 1}, bone_t)
    # mascella inferiore (osso Jaw) con denti
    jaw = P("Jaw")
    ellipsoid(mesh, add(jaw, (0, -0.16, -0.38)), (0.22, 0.1, 0.42), {"Jaw": 1}, skin, 2, seed=10)
    for i in range(11):
        a = -1.0 + i * 0.2
        base = add(jaw, (math.sin(a) * 0.18, -0.08, -0.4 - math.cos(a) * 0.3 + 0.08))
        spike(mesh, base, add(base, (0, 0.2 + 0.05 * (i % 2), 0)), 0.022, {"Jaw": 1}, bone_t)

    for side, s in (("L", -1), ("R", 1)):
        # clavicola, braccio, avambraccio
        limb(mesh, [P("Clav" + side), P("Shoulder" + side)], ["Clav" + side], [0.1, 0.12], skin, segments=7, rnd=rnd)
        ellipsoid(mesh, P("Shoulder" + side), (0.2, 0.2, 0.2), {"Shoulder" + side: 1}, skin, 1)
        limb(mesh, [P("Shoulder" + side), P("Elbow" + side), P("Wrist" + side)], ["Shoulder" + side, "Elbow" + side],
             [0.17, 0.11, 0.08], skin, segments=9, sub_steps=4,
             profile=lambda a, sp: 1 + 0.25 * math.exp(-((sp - 0.5) / 0.06) ** 2), rnd=rnd)
        ellipsoid(mesh, add(P("Wrist" + side), (0, -0.15, -0.05)), (0.13, 0.2, 0.08), {"Wrist" + side: 1}, skin, 1)
        for f in range(4):
            a, b = "Fing%d%sA" % (f, side), "Fing%d%sB" % (f, side)
            pa, pb = P(a), P(b)
            tip = add(pb, mul(norm(sub(pb, pa)), 0.55))
            limb(mesh, [pa, pb, tip], [a, b], [0.05, 0.04, 0.025], skin, segments=6, sub_steps=2, cap_end=False, rnd=rnd)
            spike(mesh, tip, add(tip, add(mul(norm(sub(tip, pb)), 0.45), (0, -0.05, -0.12))), 0.03, {b: 1}, claw)
            limb(mesh, [P("Wrist" + side), pa], ["Wrist" + side], [0.05, 0.05], skin, segments=5, sub_steps=1, rnd=rnd)
        # gambe digitigrade
        limb(mesh, [P("Hip" + side), P("Knee" + side), P("Ankle" + side), P("Toe" + side)], ["Hip" + side, "Knee" + side, "Ankle" + side],
             [0.25, 0.13, 0.08, 0.07], skin, segments=9, sub_steps=4,
             profile=lambda a, sp: 1 + 0.3 * math.exp(-((sp - 0.33) / 0.05) ** 2), rnd=rnd)
        for t in range(3):
            off = (t - 1) * 0.12
            base = add(P("Toe" + side), (off, 0, 0))
            tip = add(base, (off * 0.8, -0.05, -0.55))
            limb(mesh, [P("Ankle" + side), base, tip], ["Ankle" + side, "Toe" + side], [0.05, 0.045, 0.02], skin, segments=5, sub_steps=2, cap_end=False, rnd=rnd)
            spike(mesh, tip, add(tip, (0, -0.06, -0.3)), 0.03, {"Toe" + side: 1}, claw)
    return mesh


# ---------------------------------------------------------------------------------------------
# Esportazione glTF con skin


def flip(p):
    return (-p[0], p[1], -p[2])


def export(mesh, atlas_png, path):
    # normali morbide per posizione
    acc = {}
    tri_normals = []
    for a, b, c, _ in mesh.tris:
        n = norm(cross(sub(b[0], a[0]), sub(c[0], a[0])))
        tri_normals.append(n)
        for v in (a, b, c):
            key = tuple(round(x, 3) for x in v[0])
            s = acc.get(key, (0, 0, 0))
            acc[key] = (s[0] + n[0], s[1] + n[1], s[2] + n[2])
    pos, nrm, uv, joints, weights, idx = [], [], [], [], [], []
    for (a, b, c, tile), n in zip(mesh.tris, tri_normals):
        ax = max(range(3), key=lambda i: abs(n[i]))
        ua, va = [(2, 1), (0, 2), (0, 1)][ax]
        uvs = [(v[0][ua] * 1.2, -v[0][va] * 1.2) for v in (a, b, c)]
        mu, mv = math.floor(min(u for u, _ in uvs)), math.floor(min(v for _, v in uvs))
        uvs = [(u - mu, v - mv) for u, v in uvs]
        span = max(max(u for u, _ in uvs), max(v for _, v in uvs), 1.0)
        tx, ty = tile % TILES, tile // TILES
        for i, v in enumerate((a, b, c)):
            p, w = v
            sn = norm(acc[tuple(round(x, 3) for x in p)])
            vn = sn if dot(sn, n) > 0.3 else n
            pos.append(flip(p))
            nrm.append(flip(vn))
            u0, v0 = uvs[i]
            uv.append(((tx + 0.06 + u0 / span * 0.88) / TILES, (ty + 0.06 + v0 / span * 0.88) / TILES))
            items = sorted(w.items(), key=lambda kv: -kv[1])[:4]
            total = sum(x for _, x in items)
            j4 = [INDEX[k] for k, _ in items] + [0] * (4 - len(items))
            w4 = [x / total for _, x in items] + [0.0] * (4 - len(items))
            joints.append(tuple(j4))
            weights.append(tuple(w4))
            idx.append(len(idx))

    bin_data = bytearray()
    views, accessors = [], []

    def view(data):
        while len(bin_data) % 4:
            bin_data.append(0)
        views.append({"buffer": 0, "byteOffset": len(bin_data), "byteLength": len(data)})
        bin_data.extend(data)
        return len(views) - 1

    def accessor(values, kind, comp, fmt, minmax=False):
        flat = [c for v in values for c in (v if isinstance(v, tuple) else (v,))]
        a = {"bufferView": view(struct.pack("<%d%s" % (len(flat), fmt), *flat)), "componentType": comp, "count": len(values), "type": kind}
        if minmax:
            a["min"] = [min(v[i] for v in values) for i in range(3)]
            a["max"] = [max(v[i] for v in values) for i in range(3)]
        accessors.append(a)
        return len(accessors) - 1

    image_view = view(atlas_png)
    attrs = {
        "POSITION": accessor(pos, "VEC3", 5126, "f", True),
        "NORMAL": accessor(nrm, "VEC3", 5126, "f"),
        "TEXCOORD_0": accessor(uv, "VEC2", 5126, "f"),
        "JOINTS_0": accessor(joints, "VEC4", 5123, "H"),
        "WEIGHTS_0": accessor(weights, "VEC4", 5126, "f"),
    }
    indices = accessor(idx, "SCALAR", 5125, "I")

    nodes = []
    for name in NAMES:
        parent, p = BONES[name]
        local = sub(p, BONES[parent][1]) if parent else p
        nodes.append({"name": name, "translation": list(flip(local))})
    for name in NAMES:
        parent = BONES[name][0]
        if parent:
            nodes[INDEX[parent]].setdefault("children", []).append(INDEX[name])
    mats = []
    for name in NAMES:
        g = flip(BONES[name][1])
        mats += [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -g[0], -g[1], -g[2], 1]
    ibm = accessors.append({"bufferView": view(struct.pack("<%df" % len(mats), *mats)), "componentType": 5126, "count": len(NAMES), "type": "MAT4"})
    ibm = len(accessors) - 1
    mesh_node = len(nodes)
    nodes.append({"name": "Rake_Body", "mesh": 0, "skin": 0})
    gltf = {
        "asset": {"version": "2.0", "generator": "rake-meshgen"},
        "scene": 0,
        "scenes": [{"nodes": [INDEX["Root"], mesh_node]}],
        "nodes": nodes,
        "skins": [{"joints": list(range(len(NAMES))), "inverseBindMatrices": ibm, "skeleton": INDEX["Root"]}],
        "meshes": [{"name": "Rake_Body", "primitives": [{"attributes": attrs, "indices": indices, "material": 0}]}],
        "materials": [{"name": "Pelle", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 0.7}}],
        "images": [{"bufferView": image_view, "mimeType": "image/png"}],
        "textures": [{"source": 0}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(bin_data)}],
    }
    while len(bin_data) % 4:
        bin_data.append(0)
    js = json.dumps(gltf).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_data)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(bin_data), 0x004E4942) + bytes(bin_data))
    lo = [min(p[i] for p in pos) for i in range(3)]
    hi = [max(p[i] for p in pos) for i in range(3)]
    # centro e dimensioni in coordinate di progetto (annulla la rotazione)
    center = flip(tuple((lo[i] + hi[i]) / 2 for i in range(3)))
    size = tuple(hi[i] - lo[i] for i in range(3))
    return len(idx) // 3, center, size


def main():
    os.makedirs(OUT, exist_ok=True)
    atlas = build_atlas()
    buf = io.BytesIO()
    Image.fromarray(atlas, "RGBA").save(buf, format="PNG", optimize=True)
    mesh = build()
    tris, center, size = export(mesh, buf.getvalue(), os.path.join(OUT, "RakeBody.glb"))
    info = {"tris": tris, "center": [round(c, 4) for c in center], "size": [round(s, 4) for s in size],
            "bones": {n: list(BONES[n][1]) for n in NAMES}}
    json.dump(info, open(os.path.join(OUT, "rake_bones.json"), "w"), indent=1)
    print("Rake_Body: %d triangoli, %d ossa, centro %s, dimensioni %s" % (tris, len(NAMES), info["center"], info["size"]))
    return mesh


if __name__ == "__main__":
    main()
