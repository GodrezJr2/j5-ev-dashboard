"""Stage 0 of the car model (optional): make a single-view image-to-3D car symmetric.

A single photo shows one side of the car; the generator invents the other, usually worse. A car is mirror-symmetric,
so keep the half the photo saw and reflect it. Runs before tools/car_prep.py.

usage (Hunyuan3D venv: trimesh, numpy, pymeshlab):
  python tools/car_mirror.py raw.glb out_prefix
writes out_prefix_L.glb and out_prefix_R.glb (each built from one half); look at both and pass the better one on.

Expects Y up (TRELLIS.2 and Hunyuan3D GLBs load that way). The width axis is the shorter horizontal extent; the
mirror plane is the middle of the body below the mirrors (mirrors and stray fins would bias a plain bounding box).
"""
import sys
import numpy as np, trimesh, pymeshlab

src, prefix = sys.argv[1:3]
m = trimesh.load(src, force="mesh", process=False)
m = trimesh.Trimesh(m.vertices, m.faces, process=True)        # weld; drop UVs and the baked texture
v = m.vertices
ext = v.max(0) - v.min(0)
W_ax = 0 if ext[0] < ext[2] else 2
low = v[:, 1] < v[:, 1].min() + .45 * ext[1]                   # body sides, below the mirrors
lo, hi = np.percentile(v[low, W_ax], [.5, 99.5])               # percentiles: ignore a stray shard
mid = (lo + hi) / 2
print("faces", len(m.faces), "width axis", "xz"[W_ax // 2], "plane", round(mid, 4))

cent = m.triangles_center[:, W_ax] - mid
for name, keep in (("L", cent > 0), ("R", cent < 0)):
    half = m.submesh([np.where(keep)[0]], append=True)
    hv = half.vertices.copy(); hv[:, W_ax] = np.where(np.abs(hv[:, W_ax] - mid) < 1e-4, mid, hv[:, W_ax])
    mv = hv.copy(); mv[:, W_ax] = 2 * mid - mv[:, W_ax]
    both = trimesh.Trimesh(np.vstack([hv, mv]),
                           np.vstack([half.faces, half.faces[:, ::-1] + len(hv)]), process=False)
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(both.vertices, both.faces))
    ms.meshing_merge_close_vertices(threshold=pymeshlab.PercentageValue(.02))     # stitch the seam on the plane
    ms.meshing_remove_duplicate_faces(); ms.meshing_remove_null_faces()
    cm = ms.current_mesh()
    out = trimesh.Trimesh(cm.vertex_matrix(), cm.face_matrix(), process=False)
    out.export(f"{prefix}_{name}.glb")
    print(name, len(out.faces), "faces ->", f"{prefix}_{name}.glb")
