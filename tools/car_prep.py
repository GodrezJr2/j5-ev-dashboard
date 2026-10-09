"""Stage 1 of the car model: raw Hunyuan3D shape -> clean, oriented, real-size, denoised dense mesh.

usage (needs trimesh, numpy, pymeshlab; the Hunyuan3D venv has them):
  python tools/car_prep.py "D:/Llm Studio/Hunyuan3D/out/mv4_r512_s1.glb" build/car_t40_s1.glb --taubin 40
then:  python tools/split_car.py build/car_t40_s1.glb web/car_parts

The mesh is scaled to the Jaecoo J5 EV brochure size from MODEL_SPECS in tools/server.py (length 4380, width 1860,
height 1650 mm), because an image-to-3D shape has no real scale and the clay renders are drawn a little tall. Width
is the widest point of the body below the mirrors. Frame out: front +Z, wheels on y=0, centred on x and z.
The generator's marching-cubes noise is removed by decimating first (QEM averages it) and then Taubin smoothing at the
mesh's own scale; the two-step normal denoise (--denoise) was tried and eats handles and mirrors.
"""
import argparse, numpy as np, trimesh, pymeshlab

ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--dense", type=int, default=220000, help="face count of the first working mesh")
ap.add_argument("--mid", type=int, default=45000, help="face count after QEM decimation (averages the generator's noise)")
ap.add_argument("--taubin", type=int, default=12, help="volume-preserving smoothing passes on the mid mesh")
ap.add_argument("--denoise", type=int, default=0, help="two-step smoothing passes (0 = off; it eats handles and mirrors)")
ap.add_argument("--normthr", type=float, default=55.0, help="two-step smoothing: normal angle that counts as a crease")
a = ap.parse_args()
L, W, H = 4.38, 1.86, 1.65                                    # metres, MODEL_SPECS["jaecoo j5 ev"]

m = trimesh.load(a.src, force="mesh")
print("in", len(m.vertices), "v", len(m.faces), "f", np.round(m.bounds, 2).tolist())
parts = m.split(only_watertight=False)
big = max(len(p.faces) for p in parts)
m = trimesh.util.concatenate([p for p in parts if len(p.faces) > 0.02 * big])      # drop floaters
print("components", len(parts), "->", len(m.faces), "faces kept")

ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(m.vertices, m.faces))
ms.meshing_remove_duplicate_vertices(); ms.meshing_remove_duplicate_faces(); ms.meshing_remove_null_faces()
ms.meshing_repair_non_manifold_edges(); ms.meshing_repair_non_manifold_vertices()
ms.meshing_close_holes(maxholesize=400)
if ms.current_mesh().face_number() > a.dense:
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=a.dense, preservenormal=True, qualitythr=.6)
cm = ms.current_mesh(); m = trimesh.Trimesh(cm.vertex_matrix(), cm.face_matrix(), process=False)
print("dense", len(m.faces), "faces, watertight", m.is_watertight)

# ---- orient: Y up, longest horizontal axis = length, front = the lower end -----------------------
v = m.vertices.copy(); up = 1
ext = v.max(0) - v.min(0)
horiz = [i for i in range(3) if i != up]
L_ax = horiz[0] if ext[horiz[0]] >= ext[horiz[1]] else horiz[1]
W_ax = [i for i in horiz if i != L_ax][0]
lo, hi = v[:, L_ax].min(), v[:, L_ax].max(); span = hi - lo
h_lo = v[v[:, L_ax] < lo + .12 * span][:, up].max(); h_hi = v[v[:, L_ax] > hi - .12 * span][:, up].max()
front_is_high = h_hi < h_lo                                   # the hatch end is taller, the bonnet end is lower
print("front at", "max" if front_is_high else "min")
Z = (v[:, L_ax] - (lo + hi) / 2) * (1 if front_is_high else -1)
X = v[:, W_ax] - (v[:, W_ax].min() + v[:, W_ax].max()) / 2
Y = v[:, up] - v[:, up].min()
s = L / span
Z, X, Y = Z * s, X * s, Y * s                                  # uniform first, then fit height and width to the brochure
Y *= H / Y.max()
body = Y < .50 * Y.max()                                       # below the mirrors and glass
X *= (W / 2) / np.abs(X[body]).max()
out = trimesh.Trimesh(np.stack([X, Y, Z], 1), m.faces.copy(), process=False)
if out.volume < 0: out.invert()
print("final extents", np.round(out.extents, 3).tolist(), "(incl. mirrors)")

# ---- denoise: normals first, then vertices follow them, so flat panels flatten and creases survive -----
if a.denoise:
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(out.vertices, out.faces))
    ms.apply_coord_two_steps_smoothing(stepsmoothnum=a.denoise, normalthr=a.normthr, stepnormalnum=20, stepfitnum=20)
    cm = ms.current_mesh(); out = trimesh.Trimesh(cm.vertex_matrix(), cm.face_matrix(), process=False)
    # smoothing drifts the ground contact by a hair
    out.apply_translation([0, -out.bounds[0][1], 0])
if a.mid and len(out.faces) > a.mid:                           # decimate first: QEM averages the marching-cubes noise
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(out.vertices, out.faces))
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=a.mid, preservenormal=True, qualitythr=.6)
    cm = ms.current_mesh(); out = trimesh.Trimesh(cm.vertex_matrix(), cm.face_matrix(), process=False)
if a.taubin:                                                   # then smooth at the scale the mesh now has
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(out.vertices, out.faces))
    ms.apply_coord_taubin_smoothing(lambda_=.5, mu=-.53, stepsmoothnum=a.taubin)
    cm = ms.current_mesh(); out = trimesh.Trimesh(cm.vertex_matrix(), cm.face_matrix(), process=False)
    out.apply_translation([0, -out.bounds[0][1], 0])
import os; os.makedirs(os.path.dirname(os.path.abspath(a.dst)), exist_ok=True)
out.export(a.dst); print("WROTE", a.dst, len(out.faces), "faces", np.round(out.bounds, 3).tolist())
