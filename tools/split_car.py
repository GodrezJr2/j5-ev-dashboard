"""Stage 2 of the car model: cut the mid-poly car mesh (tools/car_prep.py) into the animated parts of web/car3d.js.

pipeline: nano-banana clay renders (front/left/back + mirrored left as right)
          -> Hunyuan3D-2mv gen_mv_seeds.py (res 512, seed 1 is the one in use)
          -> tools/car_prep.py out/mv4_r512_s1.glb build/car_t40_s1.glb --taubin 40
          -> this script -> web/car_parts.json
usage (needs trimesh, numpy, scipy, pymeshlab; the Hunyuan3D venv has them):
  python tools/split_car.py build/car_t40_s1.glb web/car_parts [--body 11000 --door 1800 --gate 2400]
  add --quick to skip every cut and preview a source mesh in seconds

Frame is car3d.js's: front +Z, car's left side +X, wheels on y=0, real size (4.38 x 1.86 x 1.65 m).
Parts: body, door0..3 (FL FR RL RR), gate (tailgate), sun (sunroof panel). A door, the gate and the sunroof are the
mesh intersected with a prism that follows the panel outline; the body is the mesh minus a slightly fatter prism, so
the gap reads as a panel line. The front doors carry the mirror (its own prism, unioned in) and a B-pillar strip stays
on the body. The body is then hollowed behind the openings so an open panel shows a cabin (car3d.js furnishes it).
Wheels are not cut out as parts: a drum is removed from the body and car3d.js builds the wheel in code.
Each part is decimated on its own budget (the body at 11k faces gives the faceted clay look of the references; more
faces melt it smooth). Faces the cuts create (not on the original skin) are written after the skin faces so the viewer
draws them as a second, dark material group. Per-vertex crease shading (cavity AO) is baked in. Output: positions as
int16 (1/8192 m, relative to each part's hinge pivot) + indices + ao, base64 in one JSON.
"""
import sys, json, argparse, time, base64
import numpy as np, trimesh, pymeshlab
from scipy.spatial import cKDTree

ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--body", type=int, default=11000); ap.add_argument("--door", type=int, default=1800)
ap.add_argument("--gate", type=int, default=2400)
ap.add_argument("--gap", type=float, default=.010)
ap.add_argument("--quick", action="store_true", help="no cuts: the whole mesh as the body, to judge a source mesh in seconds")
a = ap.parse_args()

# Outlines below were drawn on the first mesh, which was 4.5 m long and 1.85 m tall; the car is now real size.
SZ, SY = 4.38 / 4.5, 1.65 / 1.85
def tz(poly): return [(z * SZ, y * SY) for z, y in poly]

# ---- panel outlines in the side view, (z, y) --------------------------------------------------
# front door: hinge edge z=.865, B-pillar seam z=-.22. Rear door: seam -.22 .. -1.25, rear corner cut by the arch.
DOOR_POLY = {
    "front": [(.842, .294), (-.17, .294), (-.17, 1.534), (.15, 1.534), (.42, 1.38), (.842, 1.06)],   # real-size coords; keeps clear of the A-pillar
    "rear":  tz([(-.277, .33), (-.80, .33), (-1.02, .98), (-1.25, 1.02), (-1.25, 1.72), (-.277, 1.72)]),   # the B-pillar strip -.27 .. -.17 stays on the body
}
MIRROR_POLY = [(.70, 1.30), (.38, 1.30), (.38, 1.04), (.70, 1.04)]     # the mirror housing and stalk, a separate prism beyond x = .86
# slanted inner face of a door slab: x = X_IN0 + X_SLOPE * (y_old - .35)
X_IN0, X_SLOPE = .825, -.143                      # ~11 cm under the skin, which runs .905 low and .74 at the roof edge
x_in = lambda y: X_IN0 + X_SLOPE * (np.asarray(y) / SY - .35)
GATE_POLY = tz([(-2.45, .88), (-2.06, .88), (-1.66, 1.80), (-1.66, 2.05), (-2.45, 2.05)])   # inner face runs up the slope of the hatch
HATCH_PIVOT = (0, 1.80 * SY, -1.80 * SZ)
HINGE_Z = (.842, -.27)                                                               # front doors, rear doors
WING_POLY = {"front": tz([(.74, .45), (-.14, .45), (-.14, 1.52), (.15, 1.52), (.45, 1.18), (.74, .98)]),
             "rear":  tz([(-.30, .45), (-.76, .45), (-.95, 1.02), (-1.12, 1.04), (-1.12, 1.52), (-.30, 1.52)])}
CABIN_LOW = tz([(.95, .50), (.95, 1.05), (.30, 1.25), (-1.90, 1.25), (-2.016, .98), (-2.02, .62)])   # rear edge lies on the hatch's inner face
CABIN_UP = tz([(.30, 1.20), (.12, 1.45), (-.40, 1.62), (-1.70, 1.70), (-2.016, .98)])               # head room, narrower so glass and roof edge stay shut


def ear_clip(poly):
    """triangulate a simple polygon (list of (a,b)), CCW or CW -> list of index triples"""
    P = np.array(poly, float); n = len(P)
    area = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n)) / 2
    idx = list(range(n)) if area > 0 else list(range(n))[::-1]
    tris = []
    def inside(p, a_, b_, c_):
        d = lambda p1, p2, p3: (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = d(p, a_, b_), d(p, b_, c_), d(p, c_, a_)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
    guard = 0
    while len(idx) > 3 and guard < 1000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            p0, p1, p2 = P[i0], P[i1], P[i2]
            if (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]) <= 1e-12: continue   # reflex
            if any(inside(P[j], p0, p1, p2) for j in idx if j not in (i0, i1, i2)): continue
            tris.append((i0, i1, i2)); idx.pop(k); break
    tris.append(tuple(idx))
    return tris


def prism(poly, x_in_, x_out, side, grow=0.0):
    """closed solid: polygon (z,y) extruded along x from the slanted inner face x_in_(y) to x_out, on the +side or -side.
    grow pushes every face out by that much."""
    P = np.array(poly, float)
    if grow:                                                    # offset the outline outwards by moving points off the centroid
        c = P.mean(0); d = P - c; P = P + d / np.linalg.norm(d, axis=1, keepdims=True) * grow
    n = len(P)
    V = [(side * (x_in_(y) - grow), y, z) for z, y in P] + [(side * x_out, y, z) for z, y in P]
    F = []
    for t in ear_clip([tuple(p) for p in P]):
        F.append(t); F.append(tuple(i + n for i in t[::-1]))
    for i in range(n):
        j = (i + 1) % n; F.append((i, j, j + n)); F.append((i, j + n, i + n))
    m = trimesh.Trimesh(np.array(V), np.array(F), process=True)
    m.fix_normals()
    if m.volume < 0: m.invert()
    return m


def door_solid(key, side, grow=0.0):
    base = prism(DOOR_POLY[key], x_in, 1.6 + grow, side, grow)
    if key == "front":                                       # front doors carry the mirror: union with its own prism
        return boolean("union", base, prism(MIRROR_POLY, lambda y: .86, 1.7 + grow, side, grow))
    return base


def gate_prism(grow):
    return prism(GATE_POLY, lambda y: -1.6, 1.6, 1, grow)


def cylinder_x(x0, x1, zc, yc, r):
    c = trimesh.creation.cylinder(radius=r, height=abs(x1 - x0), sections=48)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    c.apply_translation([(x0 + x1) / 2, yc, zc]); return c


def boolean(op, A, B):
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(np.asarray(A.vertices), np.asarray(A.faces)))
    ms.add_mesh(pymeshlab.Mesh(np.asarray(B.vertices), np.asarray(B.faces)))
    getattr(ms, "generate_boolean_" + op)(first_mesh=0, second_mesh=1)
    r = ms.current_mesh()
    return trimesh.Trimesh(r.vertex_matrix(), r.face_matrix(), process=True)


def decimate(m, n):
    if len(m.faces) <= n: return m
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(np.asarray(m.vertices), np.asarray(m.faces)))
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=n, preservenormal=True, planarquadric=True,
                                                 qualitythr=.6, preserveboundary=True)
    r = ms.current_mesh(); return trimesh.Trimesh(r.vertex_matrix(), r.face_matrix(), process=True)


def cavity_ao(V, N, r=.09):
    """per-vertex crease shading: where the skin around a vertex sits above it (a valley, a seam, an arch) the mean of the
    neighbours lies out along the normal. Returns 0..1 as uint8 over [0.4, 1.2] (1 = flat, below = darker)."""
    out = np.zeros(len(V))
    for i, nb in enumerate(skin_tree.query_ball_point(V, r, workers=-1)):
        if len(nb) >= 8: out[i] = np.dot(skin_pts[nb].mean(0) - V[i], N[i]) / r
    ao = np.clip(1 - 2.4 * out, .45, 1.15)
    return np.round((ao - .4) / .8 * 255).astype(np.uint8)


def find_wheels(mesh):
    """tyre centres (z) from the middle of each end's ground contact patches"""
    v = np.asarray(mesh.vertices); out = {}
    for end, sel in (("f", v[:, 2] > 0), ("r", v[:, 2] < 0)):
        pts = v[sel & (np.abs(v[:, 0]) > .55)]
        zs = pts[pts[:, 1] < .04][:, 2]
        zc = (zs.min() + zs.max()) / 2
        out[end] = (zc,)
    return out


t0 = time.time()
mesh = trimesh.load(a.src, force="mesh")
print("src", len(mesh.faces), "faces", np.round(mesh.bounds, 2).tolist(), "watertight", mesh.is_watertight)
wh = find_wheels(mesh)
WHEEL_Z = (wh["f"][0], wh["r"][0])
WHEEL_Y = .345                                  # 215/60 R17: 0.129 m sidewall + 0.216 m half rim (car3d.js TYRE_R)
WHEEL_R = WHEEL_Y * 1.24; WHEEL_X0 = .60
print(f"wheels z {WHEEL_Z[0]:.3f} / {WHEEL_Z[1]:.3f} (wheelbase {WHEEL_Z[0]-WHEEL_Z[1]:.3f} m, brochure 2.620)")

skin_pts = mesh.sample(1500000)                 # ~4 mm spacing: any skin face centre lands well inside the threshold below
skin_tree = cKDTree(skin_pts)

pieces = {}
body = mesh
g = a.gap
if a.quick:
    tiny = trimesh.Trimesh([[0, 0, 0], [.001, 0, 0], [0, .001, 0]], [[0, 1, 2]], process=False)
    for n_ in ("door0", "door1", "door2", "door3", "gate"): pieces[n_] = tiny
    pieces["body"] = mesh
    DOOR_POLY = {}
for i in range(0 if a.quick else 4):
    side = 1 if i % 2 == 0 else -1
    poly = DOOR_POLY["front" if i < 2 else "rear"]
    t = time.time()
    key = "front" if i < 2 else "rear"
    cut = door_solid(key, side)
    fat = door_solid(key, side, g)
    pieces["door%d" % i] = boolean("intersection", mesh, cut)
    body = boolean("difference", body, fat)
    print("door", i, len(pieces["door%d" % i].faces), "faces", f"{time.time()-t:.1f}s")

t = time.time()
if not a.quick: pieces["gate"] = boolean("intersection", mesh, gate_prism(0))     # tailgate: a prism over the full width, hinge across the top
if not a.quick: body = boolean("difference", body, gate_prism(g))
print("gate", len(pieces["gate"].faces), "faces", f"{time.time()-t:.1f}s")

# sunroof: a panel cut from the roof itself, so it fits its opening and slides back over the roof
v_ = np.asarray(mesh.vertices); roof_sel = (np.abs(v_[:, 0]) < .25) & (v_[:, 2] < -.2) & (v_[:, 2] > -1.0)
ROOF_Y = float(v_[roof_sel][:, 1].max()); SUN_PIVOT = (0, ROOF_Y, -.60)
SUN_POLY = [(-.12, ROOF_Y - .09), (-1.08, ROOF_Y - .09), (-1.08, ROOF_Y + .12), (-.12, ROOF_Y + .12)]
if not a.quick:
    pieces["sun"] = boolean("intersection", mesh, prism(SUN_POLY, lambda y: -.30, .30, 1))
    body = boolean("difference", body, prism(SUN_POLY, lambda y: -.30 - g, .30 + g, 1, g))
else: pieces["sun"] = tiny
print("sunroof", len(pieces["sun"].faces), "faces, roof y", round(ROOF_Y, 3))

# wheels: a drum around each tyre is cut out of the body; car3d.js builds the wheel itself and drops it in
for i in range(0 if a.quick else 4):
    side = 1 if i % 2 == 0 else -1; zc = WHEEL_Z[i // 2]
    x0, x1 = (WHEEL_X0, 1.3) if side > 0 else (-1.3, -WHEEL_X0)
    body = boolean("difference", body, cylinder_x(x0, x1, zc, WHEEL_Y, WHEEL_R + g))

# cabin: hollow the body out behind the door and hatch openings. Two central blocks keep roof and pillar thickness,
# and a wing behind each door reaches that door's inner face.
t = time.time()
for c_ in ([] if a.quick else (prism(CABIN_LOW, lambda y: -.58, .58, 1), prism(CABIN_UP, lambda y: -.44, .44, 1))):
    body = boolean("difference", body, c_)
for side in (() if a.quick else (1, -1)):
    for key in ("front", "rear"):
        w = prism(WING_POLY[key], lambda y: 0.0, 1.0, side)
        w.vertices[:, 0] = np.where(np.abs(w.vertices[:, 0]) > .5, side * (x_in(w.vertices[:, 1]) + .03), w.vertices[:, 0])
        body = boolean("difference", body, w)
print("cabin hollowed", len(body.faces), "faces", f"{time.time()-t:.1f}s")
if not a.quick: pieces["body"] = body

# ---- decimate each part on its own budget, then pack -----------------------------------------------
PIVOT = {"door0": (0, 0, HINGE_Z[0]), "door1": (0, 0, HINGE_Z[0]), "door2": (0, 0, HINGE_Z[1]), "door3": (0, 0, HINGE_Z[1]), "gate": HATCH_PIVOT, "sun": SUN_PIVOT}
BUDGET = {"body": a.body, "gate": a.gate, "sun": 700}
for i in range(4): BUDGET["door%d" % i] = a.door
order = ["body", "door0", "door1", "door2", "door3", "gate", "sun"]          # wheels are built in code by car3d.js
Q = 8192.0                                                 # positions are int16 in 1/8192 m, relative to the part's pivot
meta = []; total = 0
for name in order:
    m = decimate(pieces[name], BUDGET[name]); m.remove_unreferenced_vertices()
    V = np.asarray(m.vertices, np.float64); F = np.asarray(m.faces, np.int64)
    pv = np.array(PIVOT.get(name, (0, 0, 0)), np.float64)
    # skin faces first, then the faces the cut made (distance of the face centre to the skin samples), so the
    # viewer can draw them as two groups: clay, then dark cabin
    fc = V[F].mean(1); dist, _ = skin_tree.query(fc)
    skin_f = dist < .02
    F = np.concatenate([F[skin_f], F[~skin_f]])
    ao = cavity_ao(V, np.asarray(m.vertex_normals))
    q = np.round((V - pv) * Q)
    assert np.abs(q).max() < 32767, name
    idx = F.astype(np.uint16 if len(V) < 65536 else np.uint32).ravel()
    meta.append({"name": name, "pivot": pv.round(4).tolist(), "nv": len(V), "nskin": int(skin_f.sum()) * 3,
                 "pos": base64.b64encode(q.astype("<i2").tobytes()).decode(), "ao": base64.b64encode(ao.tobytes()).decode(),
                 "idx": base64.b64encode(idx.astype(idx.dtype.newbyteorder("<")).tobytes()).decode(), "idx32": len(V) >= 65536})
    total += len(meta[-1]["pos"]) + len(meta[-1]["idx"])
    print(f"{name:7s} {len(F):6d} faces  {len(V):6d} verts  cut faces {int((~skin_f).sum())}")
json.dump({"q": Q, "parts": meta, "wheelZ": WHEEL_Z, "wheelY": WHEEL_Y, "hingeX": .76}, open(a.dst + ".json", "w"), separators=(",", ":"))
print("WROTE", a.dst + ".json", f"{total/1024:.0f} KB, {time.time()-t0:.0f}s total")
