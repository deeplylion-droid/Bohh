"""Scrittore minimale di file .glb (glTF 2.0 binario) e di PNG, senza dipendenze.

Le mesh vengono costruite in coordinate Roblox (Y in alto, fronte = -Z). L'importatore di Roblox
ruota i modelli glTF di 180 gradi attorno a Y, quindi all'esportazione si applica (x, y, z) -> (-x, y, -z).
"""
import json
import math
import struct
import zlib


def png_bytes(width, height, rows):
    """rows: lista di bytearray RGBA lunghi width*4."""
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / length, v[1] / length, v[2] / length)


class Mesh:
    """Mesh con normali piatte o morbide e UV proiettate su una cella dell'atlante delle texture."""

    TILES = 4  # atlante 4x4
    MARGIN = 0.06

    def __init__(self, name, smooth=False, tex_scale=0.25):
        self.name = name
        self.smooth = smooth
        self.tex_scale = tex_scale
        self.tris = []  # (a, b, c, tile)

    def tri(self, a, b, c, tile):
        n = _cross(_sub(b, a), _sub(c, a))
        if n[0] * n[0] + n[1] * n[1] + n[2] * n[2] < 1e-12:
            return  # triangolo degenere
        self.tris.append((tuple(a), tuple(b), tuple(c), tile))

    def quad(self, a, b, c, d, tile):
        self.tri(a, b, c, tile)
        self.tri(a, c, d, tile)

    def merge(self, other):
        self.tris.extend(other.tris)

    def bounds(self):
        pts = [p for t in self.tris for p in t[:3]]
        lo = tuple(min(p[i] for p in pts) for i in range(3))
        hi = tuple(max(p[i] for p in pts) for i in range(3))
        return lo, hi

    def _uv(self, tri, normal):
        a, b, c, tile = tri
        ax = max(range(3), key=lambda i: abs(normal[i]))
        u_axis, v_axis = [(2, 1), (0, 2), (0, 1)][ax]
        s = self.tex_scale
        uvs = [(p[u_axis] * s, -p[v_axis] * s) for p in (a, b, c)]
        min_u = math.floor(min(u for u, _ in uvs))
        min_v = math.floor(min(v for _, v in uvs))
        uvs = [(u - min_u, v - min_v) for u, v in uvs]
        span = max(max(u for u, _ in uvs), max(v for _, v in uvs), 1.0)
        tx, ty = tile % self.TILES, tile // self.TILES
        m = self.MARGIN
        out = []
        for u, v in uvs:
            u, v = u / span, v / span
            out.append(((tx + m + u * (1 - 2 * m)) / self.TILES, (ty + m + v * (1 - 2 * m)) / self.TILES))
        return out

    def arrays(self):
        normals = [_norm(_cross(_sub(t[1], t[0]), _sub(t[2], t[0]))) for t in self.tris]
        if self.smooth:
            acc = {}
            for t, n in zip(self.tris, normals):
                for p in t[:3]:
                    key = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
                    s = acc.get(key, (0, 0, 0))
                    acc[key] = (s[0] + n[0], s[1] + n[1], s[2] + n[2])
        pos, nrm, uv, idx = [], [], [], []
        for t, n in zip(self.tris, normals):
            uvs = self._uv(t, n)
            for i, p in enumerate(t[:3]):
                vn = n
                if self.smooth:
                    sn = _norm(acc[(round(p[0], 3), round(p[1], 3), round(p[2], 3))])
                    # evita di ammorbidire spigoli troppo vivi
                    if sn[0] * n[0] + sn[1] * n[1] + sn[2] * n[2] > 0.5:
                        vn = sn
                pos.append((-p[0], p[1], -p[2]))
                nrm.append((-vn[0], vn[1], -vn[2]))
                uv.append(uvs[i])
                idx.append(len(idx))
        return pos, nrm, uv, idx


def write_glb(path, meshes, atlas_png):
    bin_data = bytearray()
    views, accessors, gltf_meshes, nodes = [], [], [], []

    def add_view(data, target=None):
        while len(bin_data) % 4:
            bin_data.append(0)
        view = {"buffer": 0, "byteOffset": len(bin_data), "byteLength": len(data)}
        if target:
            view["target"] = target
        bin_data.extend(data)
        views.append(view)
        return len(views) - 1

    def add_accessor(values, kind, comp=5126):
        flat = [c for v in values for c in (v if isinstance(v, tuple) else (v,))]
        fmt = "f" if comp == 5126 else "I"
        data = struct.pack("<%d%s" % (len(flat), fmt), *flat)
        acc = {"bufferView": add_view(data, 34963 if kind == "SCALAR" else 34962), "componentType": comp, "count": len(values), "type": kind}
        if kind == "VEC3":
            acc["min"] = [min(v[i] for v in values) for i in range(3)]
            acc["max"] = [max(v[i] for v in values) for i in range(3)]
        accessors.append(acc)
        return len(accessors) - 1

    image_view = add_view(atlas_png)
    for mesh in meshes:
        pos, nrm, uv, idx = mesh.arrays()
        attributes = {"POSITION": add_accessor(pos, "VEC3"), "NORMAL": add_accessor(nrm, "VEC3"), "TEXCOORD_0": add_accessor(uv, "VEC2")}
        gltf_meshes.append({
            "name": mesh.name,
            "primitives": [{"attributes": attributes, "indices": add_accessor(idx, "SCALAR", 5125), "material": 0}],
        })
        nodes.append({"name": mesh.name, "mesh": len(gltf_meshes) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "rake-meshgen"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": gltf_meshes,
        "materials": [{
            "name": "Atlas",
            "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0.0, "roughnessFactor": 0.9},
        }],
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
    total = 12 + 8 + len(js) + 8 + len(bin_data)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(bin_data), 0x004E4942) + bytes(bin_data))
