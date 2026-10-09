"""SDF -> mesh triangolare (marching cubes) con pulizia e normali dal gradiente."""
from __future__ import annotations

import numpy as np
from skimage import measure

from .sdf import SDF


def sample_grid(sdf: SDF, voxel: float, pad: float):
    lo = sdf.lo - pad
    hi = sdf.hi + pad
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    if np.prod(n) > 60_000_000:
        raise ValueError(f"Griglia troppo grande {n.tolist()} (voxel {voxel})")
    xs = lo[0] + np.arange(n[0], dtype=np.float32) * voxel
    ys = lo[1] + np.arange(n[1], dtype=np.float32) * voxel
    zs = lo[2] + np.arange(n[2], dtype=np.float32) * voxel
    vol = np.empty((n[0], n[1], n[2]), dtype=np.float32)
    # valuta a fette per contenere la memoria
    gy, gz = np.meshgrid(ys, zs, indexing="ij")
    plane = np.stack([np.zeros_like(gy), gy, gz], axis=-1).reshape(-1, 3)
    for i, x in enumerate(xs):
        plane[:, 0] = x
        vol[i] = sdf(plane).reshape(n[1], n[2])
    return vol, lo


def gradient(sdf: SDF, p: np.ndarray, eps: float = 1e-3) -> np.ndarray:
    g = np.zeros_like(p)
    for ax in range(3):
        d = np.zeros(3, dtype=np.float32)
        d[ax] = eps
        g[:, ax] = sdf(p + d) - sdf(p - d)
    n = np.linalg.norm(g, axis=1, keepdims=True)
    return g / np.maximum(n, 1e-9)


def mesh_sdf(sdf: SDF, voxel: float = 0.03, min_component_faces: int = 40):
    """Ritorna (vertici Nx3, facce Mx3, normali Nx3) della superficie zero dell'SDF."""
    pad = voxel * 3
    vol, lo = sample_grid(sdf, voxel, pad)
    if np.isnan(vol).any():
        raise ValueError("Il campo SDF contiene NaN (forma degenere, es. poligono con vertici ripetuti)")
    if vol.min() >= 0 or vol.max() <= 0:
        raise ValueError("La forma e' vuota o riempie tutta la griglia")
    verts, faces, _normals, _ = measure.marching_cubes(vol, level=0.0, spacing=(voxel, voxel, voxel))
    verts = verts.astype(np.float32) + lo
    faces = faces.astype(np.int64)
    verts, faces = _drop_small_components(verts, faces, min_component_faces)
    normals = gradient(sdf, verts, eps=voxel * 0.5)
    # orientazione delle facce coerente con le normali verso l'esterno
    tri = verts[faces]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    avg = normals[faces].mean(axis=1)
    if np.einsum("ij,ij->i", fn, avg).mean() < 0:
        faces = faces[:, ::-1].copy()
    return verts, faces, normals


def _drop_small_components(verts, faces, min_faces):
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components

    nv = len(verts)
    rows = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]])
    cols = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    graph = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(nv, nv))
    ncomp, labels = connected_components(graph, directed=False)
    if ncomp <= 1:
        return verts, faces
    face_label = labels[faces[:, 0]]
    counts = np.bincount(face_label, minlength=ncomp)
    keep_comp = counts >= min_faces
    dropped = int((~keep_comp).sum())
    if dropped:
        print(f"[mesher] scartati {dropped} pezzi con meno di {min_faces} facce (dettagli troppo fini per il voxel?)")
    keep_faces = keep_comp[face_label]
    faces = faces[keep_faces]
    used = np.unique(faces)
    remap = -np.ones(nv, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return verts[used], remap[faces]
