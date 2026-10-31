"""Stage 1b of the car model: turn an open image-to-3D shell into a watertight solid, keeping the surface detail.

tools/split_car.py cuts panels with mesh booleans, which need a closed mesh. Hunyuan3D marching-cubes output is closed;
TRELLIS.2 output is an open shell (holes under the car and in the arches) and hole filling does not fix it.
Here: sample the surface into a voxel grid, call a voxel inside when it lies between surface hits along all three
axes (works on an open shell), marching cubes, then snap each vertex back onto the source surface (point-to-plane on
the nearest of 4M surface samples) so the voxel steps disappear. Vertices with no surface within 3 cm (filled holes)
stay where marching cubes put them.

pipeline for the TRELLIS.2 model now in web/car_parts.json:
  trellis-cli j5.png raw.glb --res 1024 --seed 42 -> tools/car_mirror.py raw.glb trm   (keep trm_L)
  -> tools/car_prep.py trm_L.glb prep.glb --mid 120000 --taubin 6 -> this script prep.glb solid.glb
  -> tools/split_car.py solid.glb web/car_parts --body 30000 --door 4000 --gate 5000
usage (Hunyuan3D venv: trimesh, numpy, scipy, scikit-image, pymeshlab):
  python tools/car_solid.py prep.glb solid.glb [--pitch .008 --faces 150000]
"""
import argparse
import numpy as np, trimesh, pymeshlab
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure

ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--pitch", type=float, default=.008, help="voxel size in m")
ap.add_argument("--close", type=int, default=2, help="dilate/erode steps that bridge small cracks")
ap.add_argument("--faces", type=int, default=150000)
a = ap.parse_args()
P, R, F = a.pitch, a.close, a.faces

m = trimesh.load(a.src, force="mesh", process=True)
lo = m.bounds[0] - 4 * P
pts, _ = trimesh.sample.sample_surface(m, int(m.area / (P * P * .15)))
idx = np.floor((pts - lo) / P).astype(int)
g = np.zeros(idx.max(0) + 5, bool); g[tuple(idx.T)] = True
st = ndimage.generate_binary_structure(3, 1)
g = ndimage.binary_dilation(g, st, iterations=R)


def between(g, ax):                      # true between the first and last surface voxel on each scanline
    c = np.cumsum(g, ax); tot = np.take(c, [-1], ax)
    return (c > 0) & (c < tot) | g


g = between(g, 0) & between(g, 1) & between(g, 2)
g = ndimage.binary_fill_holes(g)
g = ndimage.binary_erosion(g, st, iterations=R)
lab, n = ndimage.label(g); sz = np.bincount(lab.ravel()); sz[0] = 0; g = lab == sz.argmax()
print("grid", g.shape, "components", n, "fill", round(float(g.mean()), 3))

v, f, _, _ = measure.marching_cubes(np.pad(g, 1).astype(np.float32), .5)
v = (v - 1) * P + lo + P / 2
ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(v, f[:, ::-1]))
ms.apply_coord_taubin_smoothing(stepsmoothnum=10)
ms.meshing_decimation_quadric_edge_collapse(targetfacenum=F * 3, preservetopology=True, preservenormal=True)

SP, fi = trimesh.sample.sample_surface(m, 4_000_000); SN = m.face_normals[fi]; KD = cKDTree(SP)
for it in range(2):
    cm = ms.current_mesh(); vv = cm.vertex_matrix().copy(); ff = cm.face_matrix()
    nb = KD.query(vv)[1]; p, nrm = SP[nb], SN[nb]
    cp = vv - ((vv - p) * nrm).sum(1, keepdims=True) * nrm
    near = np.linalg.norm(p - vv, axis=1) < .03
    vv[near] = cp[near]
    print("snap", it, "snapped", round(float(near.mean()), 3))
    ms.clear(); ms.add_mesh(pymeshlab.Mesh(vv, ff))
    if it == 0:
        ms.apply_coord_laplacian_smoothing(stepsmoothnum=1, cotangentweight=False)
ms.meshing_decimation_quadric_edge_collapse(targetfacenum=F, preservetopology=True, preservenormal=True)
ms.meshing_repair_non_manifold_edges(); ms.meshing_repair_non_manifold_vertices(); ms.meshing_close_holes(maxholesize=1000)

cm = ms.current_mesh(); o = trimesh.Trimesh(cm.vertex_matrix(), cm.face_matrix(), process=True)
if o.volume < 0:
    o.invert()
print("watertight", o.is_watertight, "volume", round(o.volume, 3), "m3, faces", len(o.faces), "extents", o.extents.round(3))
o.export(a.dst)
