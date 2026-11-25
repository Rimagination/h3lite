# Indoor fight previz: 10 s, 3 shots, room geometry + knockable table prop.
# Route 3 (agent-driven Blender). Usage:
# blender -b --python whitemodel_indoor.py -- --outdir E:\Blender\wm_indoor --frames 240 --fps 24 --res 1344x768
import bpy, math, sys, os
from mathutils import Vector

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None):
    return ARGV[ARGV.index(k) + 1] if k in ARGV else d

OUTDIR = arg("--outdir", r"E:\Blender\wm_indoor")
W, H = [int(v) for v in (arg("--res", "1344x768").split("x"))]
FPS = int(arg("--fps", "24"))
FRAMES = int(arg("--frames", "240"))
os.makedirs(OUTDIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)

mat = bpy.data.materials.new("ClayGray")
mat.use_nodes = True
b = mat.node_tree.nodes.get("Principled BSDF")
b.inputs["Base Color"].default_value = (0.62, 0.62, 0.62, 1.0)
b.inputs["Roughness"].default_value = 0.9

def setmat(o):
    o.data.materials.clear(); o.data.materials.append(mat)

U = 1.70 / 7.5
upd_A, upd_D, upd_P = [], [], []   # attacker / defender / prop updaters
CUR = upd_A

def mk_sphere(loc, r, name, scale=(1, 1, 1), key=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=20, ring_count=12)
    o = bpy.context.object; o.name = name; o.scale = scale
    bpy.ops.object.shade_smooth(); setmat(o)
    if key:
        CUR.append(lambda j, o=o, key=key: setattr(o, "location", Vector(j[key])))
    return o

def mk_capsule(p1, p2, r, name, k1, k2):
    p1, p2 = Vector(p1), Vector(p2)
    L0 = max((p2 - p1).length, 1e-4)
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=L0, location=(p1 + p2) / 2, vertices=14)
    o = bpy.context.object; o.name = name
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = (p2 - p1).to_track_quat('Z', 'Y')
    bpy.ops.object.shade_smooth(); setmat(o)
    s1 = mk_sphere(p1, r, name + "_j1"); s2 = mk_sphere(p2, r, name + "_j2")
    def upd(j, o=o, s1=s1, s2=s2, k1=k1, k2=k2, L0=L0):
        a = Vector(j[k1]); bb = Vector(j[k2]); d = bb - a; L = max(d.length, 1e-4)
        o.location = (a + bb) / 2; o.scale = (1, 1, L / L0)
        o.rotation_quaternion = d.to_track_quat('Z', 'Y')
        s1.location = a; s2.location = bb
    CUR.append(upd)

def mk_foot(j, kk, ak, name):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(j[ak][0], j[ak][1] + 0.09, 0.045))
    o = bpy.context.object; o.name = name; o.scale = (0.09, 0.26, 0.09); setmat(o)
    def upd(j, o=o, kk=kk, ak=ak):
        a = Vector(j[ak]); k = Vector(j[kk]); d = a - k
        o.location = (a.x, a.y + 0.09, 0.045)
        o.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.pi / 2)
    CUR.append(upd)

def figure(j, name, ulist):
    global CUR
    CUR = ulist
    mk_sphere(j["head"], U * 0.50, name + "_head", scale=(0.88, 0.95, 1.08), key="head")
    mk_capsule(j["neck"], j["chest"], U * 0.16, name + "_neck", "neck", "chest")
    mk_sphere(j["chest"], U * 0.36, name + "_chest", scale=(1.25, 0.85, 1.1), key="chest")
    mk_capsule(j["chest"], j["pelvis"], U * 0.34, name + "_torso", "chest", "pelvis")
    mk_sphere(j["pelvis"], U * 0.32, name + "_pelvis", scale=(1.15, 0.9, 0.95), key="pelvis")
    for s in ("l", "r"):
        mk_sphere(j["sho_" + s], U * 0.18, name + "_sho" + s, key="sho_" + s)
        mk_capsule(j["chest"], j["sho_" + s], U * 0.15, name + "_clav" + s, "chest", "sho_" + s)
        mk_capsule(j["sho_" + s], j["elb_" + s], U * 0.16, name + "_uparm" + s, "sho_" + s, "elb_" + s)
        mk_capsule(j["elb_" + s], j["wri_" + s], U * 0.13, name + "_forearm" + s, "elb_" + s, "wri_" + s)
        mk_sphere(j["wri_" + s], U * 0.15, name + "_hand" + s, scale=(0.6, 1.0, 1.2), key="wri_" + s)
        mk_capsule(j["hip_" + s], j["knee_" + s], U * 0.24, name + "_thigh" + s, "hip_" + s, "knee_" + s)
        mk_sphere(j["knee_" + s], U * 0.19, name + "_knee" + s, key="knee_" + s)
        mk_capsule(j["knee_" + s], j["ank_" + s], U * 0.18, name + "_shin" + s, "knee_" + s, "ank_" + s)
        mk_foot(j, "knee_" + s, "ank_" + s, name + "_foot" + s)

def mk_sword(jA):
    global CUR
    CUR = upd_A
    h1, h2 = Vector(jA["wri_l"]), Vector(jA["wri_r"])
    gm0 = (h1 + h2) / 2
    d0 = Vector(KEYS[0][3]) - gm0
    bpy.ops.mesh.primitive_cube_add(size=1, location=gm0 + d0.normalized() * (d0.length / 2))
    blade = bpy.context.object; blade.name = "Sword_blade"
    blade.rotation_mode = 'QUATERNION'
    blade.rotation_quaternion = d0.normalized().to_track_quat('Y', 'X')
    blade.scale = (0.032, max(d0.length, 1e-4), 0.11); setmat(blade)
    mk_capsule(jA["wri_l"], jA["wri_r"], 0.024, "Sword_grip", "wri_l", "wri_r")
    bpy.ops.mesh.primitive_cube_add(size=1, location=gm0)
    guard = bpy.context.object; guard.name = "Sword_guard"
    guard.scale = (0.16, 0.05, 0.035); setmat(guard)
    def upd(j, tip, blade=blade, guard=guard):
        a = Vector(j["wri_l"]); bb = Vector(j["wri_r"]); gm = (a + bb) / 2
        d = Vector(tip) - gm; L = max(d.length, 1e-4)
        blade.location = gm + d.normalized() * (L / 2)
        blade.scale = (0.032, L, 0.11)
        blade.rotation_quaternion = d.normalized().to_track_quat('Y', 'X')
        guard.location = gm
        guard.rotation_euler = (0, 0, math.atan2(d.y, d.x))
    return upd

def S(j, dx, dy):
    return {k: (v[0] + dx, v[1] + dy, v[2]) for k, v in j.items()}

def crouch(j, dz):
    out = {}
    for k, v in j.items():
        d = dz
        if k in ("pelvis", "hip_l", "hip_r"): d = dz * 0.6
        if k in ("knee_l", "knee_r"): d = dz * 0.3
        if k in ("ank_l", "ank_r"): d = 0.0
        out[k] = (v[0], v[1], v[2] - d)
    return out

def up(j, dy, dz):
    out = {}
    for k, v in j.items():
        dyk, dzk = dy, dz
        if k in ("pelvis", "hip_l", "hip_r"): dzk = dz * 0.5
        if k in ("knee_l", "knee_r", "ank_l", "ank_r"): dyk, dzk = 0.0, 0.0
        out[k] = (v[0], v[1] + dyk, v[2] + dzk)
    return out

def M(j1, j2, u):
    return {k: tuple(a + (b - a) * u for a, b in zip(j1[k], j2[k])) for k in j1}

def MT(p1, p2, u):
    return tuple(a + (b - a) * u for a, b in zip(p1, p2))

# ---------------- poses ----------------
A_GUARD = dict(
    head=(0.00, -0.05, 1.60), neck=(0.00, -0.06, 1.46), chest=(0.00, -0.08, 1.30), pelvis=(0.00, -0.10, 0.98),
    sho_l=(-0.22, -0.08, 1.42), sho_r=(0.22, -0.08, 1.42),
    elb_l=(-0.30, 0.10, 1.20), elb_r=(0.30, 0.10, 1.20),
    wri_l=(-0.10, 0.28, 1.12), wri_r=(0.10, 0.30, 1.14),
    hip_l=(-0.10, -0.10, 0.93), hip_r=(0.10, -0.10, 0.93),
    knee_l=(-0.14, 0.10, 0.52), knee_r=(0.14, 0.10, 0.52),
    ank_l=(-0.16, -0.30, 0.07), ank_r=(0.16, 0.30, 0.07))
TIP_GUARD = (0.20, 1.05, 1.35)
A_WINDUP = dict(
    head=(-0.02, -0.15, 1.58), neck=(-0.01, -0.17, 1.44), chest=(0.00, -0.20, 1.28), pelvis=(0.01, -0.22, 0.96),
    sho_l=(-0.22, -0.20, 1.40), sho_r=(0.24, -0.18, 1.40),
    elb_l=(-0.32, -0.42, 1.58), elb_r=(0.18, -0.45, 1.66),
    wri_l=(-0.12, -0.52, 1.78), wri_r=(0.10, -0.58, 1.82),
    hip_l=(-0.10, -0.22, 0.91), hip_r=(0.11, -0.22, 0.91),
    knee_l=(-0.22, -0.55, 0.52), knee_r=(0.18, 0.10, 0.52),
    ank_l=(-0.24, -1.05, 0.07), ank_r=(0.34, 0.45, 0.07))
TIP_WINDUP = (-0.30, -1.20, 1.60)
A_STRIKE = dict(
    head=(0.09, -0.26, 1.56), neck=(0.07, -0.28, 1.42), chest=(0.05, -0.30, 1.25), pelvis=(0.00, -0.35, 0.95),
    sho_l=(-0.18, -0.32, 1.38), sho_r=(0.28, -0.28, 1.38),
    elb_l=(-0.12, -0.06, 1.14), elb_r=(0.44, -0.06, 1.20),
    wri_l=(0.10, 0.16, 1.04), wri_r=(0.24, 0.20, 1.08),
    hip_l=(-0.11, -0.35, 0.90), hip_r=(0.11, -0.35, 0.90),
    knee_l=(-0.20, -0.75, 0.50), knee_r=(0.22, 0.05, 0.48),
    ank_l=(-0.24, -1.05, 0.07), ank_r=(0.34, 0.45, 0.07))
TIP_STRIKE = (1.05, 0.70, 1.30)
A_CLINCH = dict(
    head=(0.05, 0.20, 1.52), neck=(0.04, 0.22, 1.40), chest=(0.03, 0.25, 1.24), pelvis=(0.00, 0.30, 0.94),
    sho_l=(-0.19, 0.26, 1.36), sho_r=(0.25, 0.28, 1.36),
    elb_l=(-0.28, 0.42, 1.28), elb_r=(0.34, 0.44, 1.30),
    wri_l=(-0.06, 0.55, 1.42), wri_r=(0.14, 0.56, 1.44),
    hip_l=(-0.11, 0.30, 0.89), hip_r=(0.11, 0.30, 0.89),
    knee_l=(-0.18, 0.02, 0.50), knee_r=(0.20, 0.55, 0.50),
    ank_l=(-0.22, -0.30, 0.07), ank_r=(0.30, 0.85, 0.07))
TIP_CLINCH = (-0.45, 0.15, 1.95)
A_DOWN = dict(
    head=(0.05, 0.10, 1.05), neck=(0.04, 0.12, 0.94), chest=(0.03, 0.15, 0.82), pelvis=(0.00, 0.18, 0.55),
    sho_l=(-0.19, 0.16, 0.92), sho_r=(0.25, 0.18, 0.92),
    elb_l=(-0.24, 0.30, 0.55), elb_r=(0.30, 0.28, 0.55),
    wri_l=(-0.08, 0.44, 0.32), wri_r=(0.06, 0.48, 0.30),
    hip_l=(-0.11, 0.18, 0.50), hip_r=(0.11, 0.18, 0.50),
    knee_l=(-0.20, 0.48, 0.46), knee_r=(0.14, 0.10, 0.10),
    ank_l=(-0.24, 0.60, 0.07), ank_r=(0.20, -0.25, 0.06))
TIP_DOWN = (0.90, 0.90, 0.10)

D_GUARD = dict(
    head=(0.00, 1.25, 1.60), neck=(0.00, 1.26, 1.46), chest=(0.00, 1.27, 1.30), pelvis=(0.00, 1.28, 0.98),
    sho_l=(-0.22, 1.27, 1.42), sho_r=(0.22, 1.27, 1.42),
    elb_l=(-0.30, 1.10, 1.20), elb_r=(0.30, 1.10, 1.20),
    wri_l=(-0.16, 0.92, 1.15), wri_r=(0.16, 0.92, 1.15),
    hip_l=(-0.10, 1.28, 0.93), hip_r=(0.10, 1.28, 0.93),
    knee_l=(-0.14, 1.10, 0.52), knee_r=(0.14, 1.10, 0.52),
    ank_l=(-0.16, 0.90, 0.07), ank_r=(0.16, 1.50, 0.07))
D_BRACE = dict(
    head=(0.00, 1.32, 1.59), neck=(0.00, 1.33, 1.45), chest=(0.00, 1.34, 1.29), pelvis=(0.00, 1.35, 0.97),
    sho_l=(-0.22, 1.34, 1.41), sho_r=(0.22, 1.34, 1.41),
    elb_l=(-0.32, 1.15, 1.30), elb_r=(0.30, 1.15, 1.18),
    wri_l=(-0.28, 0.95, 1.45), wri_r=(0.18, 0.98, 1.12),
    hip_l=(-0.10, 1.35, 0.92), hip_r=(0.10, 1.35, 0.92),
    knee_l=(-0.14, 1.15, 0.52), knee_r=(0.14, 1.15, 0.52),
    ank_l=(-0.22, 0.70, 0.07), ank_r=(0.28, 1.85, 0.07))
D_PARRY = dict(
    head=(-0.05, 1.20, 1.56), neck=(-0.04, 1.21, 1.42), chest=(-0.03, 1.22, 1.25), pelvis=(0.00, 1.25, 0.95),
    sho_l=(-0.26, 1.23, 1.38), sho_r=(0.20, 1.27, 1.38),
    elb_l=(-0.34, 1.00, 1.20), elb_r=(0.40, 1.32, 1.24),
    wri_l=(-0.26, 0.68, 1.10), wri_r=(0.56, 1.46, 1.44),
    hip_l=(-0.11, 1.25, 0.90), hip_r=(0.11, 1.25, 0.90),
    knee_l=(-0.18, 0.95, 0.50), knee_r=(0.20, 1.55, 0.50),
    ank_l=(-0.22, 0.70, 0.07), ank_r=(0.28, 1.85, 0.07))
D_CLINCH = dict(
    head=(-0.02, 1.05, 1.54), neck=(-0.01, 1.06, 1.41), chest=(0.00, 1.08, 1.25), pelvis=(0.00, 1.12, 0.95),
    sho_l=(-0.24, 1.09, 1.37), sho_r=(0.22, 1.10, 1.37),
    elb_l=(-0.34, 0.90, 1.30), elb_r=(0.32, 0.92, 1.28),
    wri_l=(-0.10, 0.60, 1.44), wri_r=(0.16, 0.60, 1.42),
    hip_l=(-0.11, 1.12, 0.90), hip_r=(0.11, 1.12, 0.90),
    knee_l=(-0.18, 0.85, 0.50), knee_r=(0.18, 1.40, 0.50),
    ank_l=(-0.22, 0.60, 0.07), ank_r=(0.26, 1.70, 0.07))
D_PIN = dict(
    head=(0.00, 0.75, 1.45), neck=(0.00, 0.78, 1.33), chest=(0.00, 0.82, 1.18), pelvis=(0.00, 0.95, 0.92),
    sho_l=(-0.22, 0.83, 1.30), sho_r=(0.22, 0.84, 1.30),
    elb_l=(-0.26, 0.62, 1.00), elb_r=(0.30, 1.00, 1.20),
    wri_l=(-0.06, 0.46, 0.36), wri_r=(0.34, 1.15, 1.35),
    hip_l=(-0.10, 0.95, 0.88), hip_r=(0.10, 0.95, 0.88),
    knee_l=(-0.16, 0.70, 0.50), knee_r=(0.16, 1.25, 0.50),
    ank_l=(-0.20, 0.45, 0.07), ank_r=(0.22, 1.60, 0.07))

# timeline (t in [0,1] over 10 s) — pose-to-pose with anticipation / breakdown /
# overshoot / settle keys, and foot-plant contact keys (shared ankle values).
TG0 = (TIP_GUARD[0] - 0.4, TIP_GUARD[1] - 0.5, TIP_GUARD[2])
TG1 = (TIP_GUARD[0] + 0.5, TIP_GUARD[1] - 0.4, TIP_GUARD[2])
A_G0 = S(A_GUARD, -0.4, -0.5); D_G0 = S(D_GUARD, 0.3, 0.3)
A_G1 = S(A_GUARD, 0.5, -0.4);  D_G1 = S(D_GUARD, -0.4, 0.3)
A_DIP = crouch(S(A_GUARD, 0.15, -0.10), 0.05)
TIP_DIP = (0.35, 0.95, 1.30)
A_MID = M(A_WINDUP, A_STRIKE, 0.55)
D_MID = M(D_BRACE, D_PARRY, 0.5)
TIP_MID = MT(TIP_WINDUP, TIP_STRIKE, 0.5)
A_OVER = up(A_STRIKE, 0.07, -0.04)
TIP_OVER = (1.28, 0.88, 1.16)
KEYS = [
    (0.00, A_G0, D_G0, TG0),
    (0.08, crouch(A_G0, 0.02), crouch(D_G0, 0.02), (TG0[0], TG0[1], TG0[2] - 0.02)),   # breath
    (0.16, A_G1, D_G1, TG1),                                                          # circle step
    (0.26, A_DIP, crouch(D_G1, 0.04), TIP_DIP),                                       # anticipation dip
    (0.32, A_WINDUP, D_BRACE, TIP_WINDUP),                                            # feet plant here
    (0.40, A_MID, D_MID, TIP_MID),                                                    # swing breakdown
    (0.44, A_STRIKE, D_PARRY, TIP_STRIKE),                                            # contact
    (0.48, A_OVER, up(D_PARRY, 0.0, -0.02), TIP_OVER),                                # overshoot / recoil
    (0.56, A_CLINCH, D_CLINCH, TIP_CLINCH),
    (0.70, A_DOWN, D_PIN, TIP_DOWN),
    (0.84, up(A_DOWN, 0.0, 0.015), up(D_PIN, 0.0, 0.015), TIP_DOWN),                  # settle
    (1.00, A_DOWN, D_PIN, TIP_DOWN),
]

def smooth(u):
    return u * u * (3 - 2 * u)

# Catmull-Rom through keys: C1-continuous velocity + natural arcs
def cr_at(t):
    ts = [k[0] for k in KEYS]
    i = 0
    for n in range(len(ts) - 1):
        if t <= ts[n + 1] or n == len(ts) - 2:
            i = n
            break
    span = ts[i + 1] - ts[i]
    u = 0.0 if span == 0 else min(max((t - ts[i]) / span, 0.0), 1.0)
    def pick(idx):
        return KEYS[min(max(idx, 0), len(KEYS) - 1)]
    def val(get):
        p0, p1, p2, p3 = (get(pick(i - 1)), get(pick(i)), get(pick(i + 1)), get(pick(i + 2)))
        return tuple(0.5 * (2 * a + (-b + c) * u + (2 * b - 5 * a + 4 * c - d) * u * u
                            + (-b + 3 * a - 3 * c + d) * u * u * u)
                     for a, b, c, d in zip(p1, p0, p2, p3))
    A = {k: val(lambda P, k=k: P[1][k]) for k in KEYS[0][1]}
    D = {k: val(lambda P, k=k: P[2][k]) for k in KEYS[0][2]}
    P = val(lambda P: P[3])
    return A, D, P

PRE = [cr_at(f / max(FRAMES - 1, 1)) for f in range(FRAMES)]

# secondary motion: ~1.5-frame lag on heads (overlap / follow-through)
for arr in (0, 1):
    prev = None
    for fr in PRE:
        j = fr[arr]
        v = j["head"]
        if prev is None:
            prev = v
        else:
            prev = tuple(p + (c - p) * 0.5 for p, c in zip(prev, v))
        j["head"] = prev

A0, D0, P0 = PRE[0]
figure(A0, "Attacker", upd_A)
figure(D0, "Defender", upd_D)
sword_update = mk_sword(A0)

# ---------------- room: 6-tatami Showa interior, blockout ----------------
def wall(loc, size, name):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = size; setmat(o); return o

bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
fl = bpy.context.object; fl.name = "Floor"; setmat(fl)
wall((0, 2.75, 1.30), (6.0, 0.10, 2.60), "WallBack")
wall((-2.95, 0, 1.30), (0.10, 5.6, 2.60), "WallLeft")
wall((2.95, 0, 1.30), (0.10, 5.6, 2.60), "WallRight")
# tokonoma shelf against back-left
wall((-2.45, 2.30, 0.90), (0.50, 0.90, 1.80), "Shelf")
# zabuton x2
wall((-1.2, 0.2, 0.03), (0.60, 0.60, 0.06), "Zabuton1")
wall((0.9, -1.4, 0.03), (0.60, 0.60, 0.06), "Zabuton2")
# hanging paper lamp
bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.5, location=(0.0, 0.7, 2.35), vertices=8)
cord = bpy.context.object; cord.name = "LampCord"; setmat(cord)
mk_sphere((0.0, 0.7, 2.05), 0.22, "Lamp")
# chabudai (low round table), knockable between t=0.50..0.62
bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=0.30, location=(1.5, 0.9, 0.15), vertices=20)
table = bpy.context.object; table.name = "Chabudai"; setmat(table)
def table_upd(t, table=table):
    t0, t1 = 0.50, 0.62
    s = smooth(min(max((t - t0) / (t1 - t0), 0), 1))
    table.rotation_euler = (math.radians(95) * s, 0, 0)
    table.location = (1.5, 0.9 + 0.35 * s, 0.15 + 0.30 * s)
upd_P.append(table_upd)

world = bpy.data.worlds.new("W"); bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.85, 0.85, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
bpy.ops.object.light_add(type='SUN', location=(2, -2, 6))
sun = bpy.context.object; sun.data.energy = 3.0
sun.rotation_euler = (math.radians(45), math.radians(-6), math.radians(20))

# ---------------- camera: 3 shots, live chest-midpoint targeting ----------------
cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = 35
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.rotation_mode = 'QUATERNION'
bpy.context.scene.camera = cam

SHOTS = [
    # (f_start, f_end, pos0, pos1, lens, target_dz)
    (0,   83,  (-1.9, -2.6, 1.65), (-1.5, -2.4, 1.55), 35, 0.05),   # wide: standoff + circling
    (84,  167, (2.7, -1.4, 1.40),  (2.3, 0.9, 1.25),   50, 0.00),   # medium: slash -> clinch
    (168, 239, (1.9, -1.9, 1.25),  (1.5, -1.3, 1.05), 50, -0.10), # low close: sweep + pin
]
def place_camera(f, A, D):
    for (f0, f1, p0, p1, lens, dz) in SHOTS:
        if f0 <= f <= f1:
            u = (f - f0) / max(f1 - f0, 1)
            p = Vector(p0).lerp(Vector(p1), u)
            cam.location = p
            cam_data.lens = lens
            tgt = (Vector(A["chest"]) + Vector(D["chest"])) / 2
            tgt = Vector((tgt.x, tgt.y, tgt.z + dz))
            cam.rotation_quaternion = (tgt - p).to_track_quat('-Z', 'Y')
            return

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'SINGLE'
sc.display.shading.single_color = (0.68, 0.68, 0.68)
sc.display.shading.show_cavity = True
sc.render.resolution_x = W
sc.render.resolution_y = H
sc.render.image_settings.file_format = 'PNG'

for f in range(FRAMES):
    t = f / max(FRAMES - 1, 1)
    A, D, tip = PRE[f]
    for upd in upd_A: upd(A)
    for upd in upd_D: upd(D)
    for upd in upd_P: upd(t)
    sword_update(A, tip)
    place_camera(f, A, D)
    sc.render.filepath = os.path.join(OUTDIR, "frame_%04d.png" % f)
    bpy.ops.render.render(write_still=True)
    if f % 40 == 0:
        print("WMI frame", f, flush=True)

print("WHITEMODEL_INDOOR_OK", OUTDIR, FRAMES, FPS, W, H)
