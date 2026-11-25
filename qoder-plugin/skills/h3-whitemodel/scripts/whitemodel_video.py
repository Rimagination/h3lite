# Parametric white-model ANIMATION (blockout video) for H3 motion references.
# Route 3 (agent-driven Blender): keyframed joint dicts + animated camera, Workbench clay, PNG seq.
# Usage: blender --background --python whitemodel_video.py -- --outdir E:\Blender\wm_anim --res 1344x768 --fps 24 --frames 72
# Parts are built ONCE from pose keys, then transforms are updated per frame (no mesh rebuild).
import bpy, math, sys, os
from mathutils import Vector

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None):
    return ARGV[ARGV.index(k) + 1] if k in ARGV else d

OUTDIR = arg("--outdir", r"E:\Blender\wm_anim")
W, H = [int(v) for v in (arg("--res", "1344x768").split("x"))]
FPS = int(arg("--fps", "24"))
FRAMES = int(arg("--frames", "72"))
os.makedirs(OUTDIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)

mat = bpy.data.materials.new("ClayGray")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.62, 0.62, 0.62, 1.0)
bsdf.inputs["Roughness"].default_value = 0.9

def setmat(o):
    o.data.materials.clear()
    o.data.materials.append(mat)

U = 1.70 / 7.5
upd_A = []  # attacker joint-dict updaters
upd_D = []  # defender joint-dict updaters
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
        a = Vector(j[k1]); b = Vector(j[k2]); d = b - a; L = max(d.length, 1e-4)
        o.location = (a + b) / 2
        o.scale = (1, 1, L / L0)
        o.rotation_quaternion = d.to_track_quat('Z', 'Y')
        s1.location = a; s2.location = b
    CUR.append(upd)
    return o

def mk_foot(j, knee_key, ank_key, name):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(j[ank_key][0], j[ank_key][1] + 0.09, 0.045))
    o = bpy.context.object; o.name = name
    o.scale = (0.09, 0.26, 0.09)
    setmat(o)
    def upd(j, o=o, knee_key=knee_key, ank_key=ank_key):
        a = Vector(j[ank_key]); k = Vector(j[knee_key])
        d = a - k
        yaw = math.atan2(d.y, d.x) - math.pi / 2
        o.location = (a.x, a.y + 0.09, 0.045)
        o.rotation_euler = (0, 0, yaw)
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

def mk_sword(jA, name):
    global CUR
    CUR = upd_A
    h1, h2 = Vector(jA["wri_l"]), Vector(jA["wri_r"])
    grip_mid = (h1 + h2) / 2
    tip0 = Vector(KEY_TIP_DEFAULT)
    d0 = tip0 - grip_mid
    bpy.ops.mesh.primitive_cube_add(size=1, location=grip_mid + d0.normalized() * (d0.length / 2))
    blade = bpy.context.object; blade.name = name + "_blade"
    blade.rotation_mode = 'QUATERNION'
    blade.rotation_quaternion = d0.normalized().to_track_quat('Y', 'X')
    blade.scale = (0.032, max(d0.length, 1e-4), 0.11)
    setmat(blade)
    mk_capsule(jA["wri_l"], jA["wri_r"], 0.024, name + "_grip", "wri_l", "wri_r")
    bpy.ops.mesh.primitive_cube_add(size=1, location=grip_mid)
    guard = bpy.context.object; guard.name = name + "_guard"
    guard.scale = (0.16, 0.05, 0.035)
    setmat(guard)
    def upd(j, tip, blade=blade, guard=guard):
        a = Vector(j["wri_l"]); b = Vector(j["wri_r"])
        gm = (a + b) / 2
        d = Vector(tip) - gm
        L = max(d.length, 1e-4)
        blade.location = gm + d.normalized() * (L / 2)
        blade.scale = (0.032, L, 0.11)
        blade.rotation_quaternion = d.normalized().to_track_quat('Y', 'X')
        guard.location = gm
        guard.rotation_euler = (0, 0, math.atan2(d.y, d.x))
    sword_upd = upd
    return sword_upd

# ---------------- keyframe poses ----------------
def shift(j, dy):
    return {k: (v[0], v[1] + dy, v[2]) for k, v in j.items()}

# Attacker guard (upright, two-hand sword forward)
A_GUARD = dict(
    head=(0.00, -0.05, 1.60), neck=(0.00, -0.06, 1.46), chest=(0.00, -0.08, 1.30),
    pelvis=(0.00, -0.10, 0.98),
    sho_l=(-0.22, -0.08, 1.42), sho_r=(0.22, -0.08, 1.42),
    elb_l=(-0.30, 0.10, 1.20), elb_r=(0.30, 0.10, 1.20),
    wri_l=(-0.10, 0.28, 1.12), wri_r=(0.10, 0.30, 1.14),
    hip_l=(-0.10, -0.10, 0.93), hip_r=(0.10, -0.10, 0.93),
    knee_l=(-0.14, 0.10, 0.52), knee_r=(0.14, 0.10, 0.52),
    ank_l=(-0.16, -0.30, 0.07), ank_r=(0.16, 0.30, 0.07),
)
TIP_GUARD = (0.20, 1.05, 1.35)

# Attacker windup (sword overhead-back, weight on rear leg)
A_WINDUP = dict(
    head=(-0.02, -0.15, 1.58), neck=(-0.01, -0.17, 1.44), chest=(0.00, -0.20, 1.28),
    pelvis=(0.01, -0.22, 0.96),
    sho_l=(-0.22, -0.20, 1.40), sho_r=(0.24, -0.18, 1.40),
    elb_l=(-0.32, -0.42, 1.58), elb_r=(0.18, -0.45, 1.66),
    wri_l=(-0.12, -0.52, 1.78), wri_r=(0.10, -0.58, 1.82),
    hip_l=(-0.10, -0.22, 0.91), hip_r=(0.11, -0.22, 0.91),
    knee_l=(-0.22, -0.55, 0.52), knee_r=(0.18, 0.10, 0.52),
    ank_l=(-0.28, -0.95, 0.07), ank_r=(0.22, 0.35, 0.07),
)
TIP_WINDUP = (-0.30, -1.20, 1.60)

# Attacker strike = accepted still-pose from v4
A_STRIKE = dict(
    head=(0.09, -0.26, 1.56), neck=(0.07, -0.28, 1.42), chest=(0.05, -0.30, 1.25),
    pelvis=(0.00, -0.35, 0.95),
    sho_l=(-0.18, -0.32, 1.38), sho_r=(0.28, -0.28, 1.38),
    elb_l=(-0.12, -0.06, 1.14), elb_r=(0.44, -0.06, 1.20),
    wri_l=(0.10, 0.16, 1.04), wri_r=(0.24, 0.20, 1.08),
    hip_l=(-0.11, -0.35, 0.90), hip_r=(0.11, -0.35, 0.90),
    knee_l=(-0.20, -0.75, 0.50), knee_r=(0.22, 0.05, 0.48),
    ank_l=(-0.24, -1.05, 0.07), ank_r=(0.34, 0.45, 0.07),
)
TIP_STRIKE = (1.05, 0.70, 1.30)

# Defender guard / brace / parry
D_GUARD = dict(
    head=(0.00, 1.25, 1.60), neck=(0.00, 1.26, 1.46), chest=(0.00, 1.27, 1.30),
    pelvis=(0.00, 1.28, 0.98),
    sho_l=(-0.22, 1.27, 1.42), sho_r=(0.22, 1.27, 1.42),
    elb_l=(-0.30, 1.10, 1.20), elb_r=(0.30, 1.10, 1.20),
    wri_l=(-0.16, 0.92, 1.15), wri_r=(0.16, 0.92, 1.15),
    hip_l=(-0.10, 1.28, 0.93), hip_r=(0.10, 1.28, 0.93),
    knee_l=(-0.14, 1.10, 0.52), knee_r=(0.14, 1.10, 0.52),
    ank_l=(-0.16, 0.90, 0.07), ank_r=(0.16, 1.50, 0.07),
)
D_BRACE = dict(
    head=(0.00, 1.32, 1.59), neck=(0.00, 1.33, 1.45), chest=(0.00, 1.34, 1.29),
    pelvis=(0.00, 1.35, 0.97),
    sho_l=(-0.22, 1.34, 1.41), sho_r=(0.22, 1.34, 1.41),
    elb_l=(-0.32, 1.15, 1.30), elb_r=(0.30, 1.15, 1.18),
    wri_l=(-0.28, 0.95, 1.45), wri_r=(0.18, 0.98, 1.12),
    hip_l=(-0.10, 1.35, 0.92), hip_r=(0.10, 1.35, 0.92),
    knee_l=(-0.14, 1.15, 0.52), knee_r=(0.14, 1.15, 0.52),
    ank_l=(-0.16, 0.95, 0.07), ank_r=(0.16, 1.60, 0.07),
)
D_PARRY = dict(
    head=(-0.05, 1.20, 1.56), neck=(-0.04, 1.21, 1.42), chest=(-0.03, 1.22, 1.25),
    pelvis=(0.00, 1.25, 0.95),
    sho_l=(-0.26, 1.23, 1.38), sho_r=(0.20, 1.27, 1.38),
    elb_l=(-0.34, 1.00, 1.20), elb_r=(0.40, 1.32, 1.24),
    wri_l=(-0.26, 0.68, 1.10), wri_r=(0.56, 1.46, 1.44),
    hip_l=(-0.11, 1.25, 0.90), hip_r=(0.11, 1.25, 0.90),
    knee_l=(-0.18, 0.95, 0.50), knee_r=(0.20, 1.55, 0.50),
    ank_l=(-0.22, 0.70, 0.07), ank_r=(0.28, 1.85, 0.07),
)

KEY_TIP_DEFAULT = TIP_GUARD

# timeline: (t, A, D, tip)  t in [0,1]
KEYS = [
    (0.00, A_GUARD,  D_GUARD, TIP_GUARD),
    (0.30, A_WINDUP, D_BRACE, TIP_WINDUP),
    (0.52, A_STRIKE, D_PARRY, TIP_STRIKE),
    (0.62, A_STRIKE, D_PARRY, TIP_STRIKE),          # impact hold
    (0.85, shift(A_GUARD, 0.35), D_GUARD, (TIP_GUARD[0], TIP_GUARD[1] + 0.35, TIP_GUARD[2])),
    (1.00, shift(A_GUARD, 0.35), D_GUARD, (TIP_GUARD[0], TIP_GUARD[1] + 0.35, TIP_GUARD[2])),
]

def smooth(u):
    return u * u * (3 - 2 * u)

def sample(t):
    for i in range(len(KEYS) - 1):
        t0, A0, D0, P0 = KEYS[i]
        t1, A1, D1, P1 = KEYS[i + 1]
        if t <= t1 or i == len(KEYS) - 2:
            u = 0.0 if t1 == t0 else min(max((t - t0) / (t1 - t0), 0), 1)
            s = smooth(u)
            A = {k: tuple(a + (b - a) * s for a, b in zip(A0[k], A1[k])) for k in A0}
            D = {k: tuple(a + (b - a) * s for a, b in zip(D0[k], D1[k])) for k in D0}
            P = tuple(a + (b - a) * s for a, b in zip(P0, P1))
            return A, D, P
    return KEYS[-1][1], KEYS[-1][2], KEYS[-1][3]

# ---------------- build scene from first key ----------------
A0, D0, P0 = sample(0.0)
figure(A0, "Attacker", upd_A)
figure(D0, "Defender", upd_D)
sword_update = mk_sword(A0, "AttackerSword")

# ---------------- ground / world / sun ----------------
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
g = bpy.context.object; g.name = "Ground"
gmat = bpy.data.materials.new("GroundGray"); gmat.use_nodes = True
gb = gmat.node_tree.nodes.get("Principled BSDF")
gb.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1.0)
gb.inputs["Roughness"].default_value = 1.0
g.data.materials.append(gmat)

world = bpy.data.worlds.new("W"); bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.85, 0.85, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
bpy.ops.object.light_add(type='SUN', location=(4, -3, 8))
sun = bpy.context.object; sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), math.radians(-8), math.radians(35))

# ---------------- camera rig: slow arc + impact push-in ----------------
strike_pts = [Vector(p) for p in A_STRIKE.values()] + [Vector(p) for p in D_PARRY.values()]
c = sum(strike_pts, Vector()) / len(strike_pts)
c.z = 1.05
r = max((p - c).length for p in strike_pts) + 0.55
DIST = r * 2.14
AZ0 = math.radians(-55.0); AZ1 = math.radians(-18.0)
EL0 = math.radians(13.0); EL1 = math.radians(18.0)

cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.rotation_mode = 'QUATERNION'
bpy.context.scene.camera = cam

def place_camera(t):
    az = AZ0 + (AZ1 - AZ0) * t
    el = EL0 + (EL1 - EL0) * t
    dist = DIST * (1.0 - 0.10 * math.exp(-((t - 0.57) ** 2) / (2 * 0.07 ** 2)))  # impact push-in
    cam.location = (c.x + dist * math.cos(el) * math.cos(az),
                    c.y + dist * math.cos(el) * math.sin(az),
                    c.z + dist * math.sin(el))
    cam.rotation_quaternion = (c - cam.location).to_track_quat('-Z', 'Y')

# ---------------- render settings ----------------
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
    A, D, tip = sample(t)
    for upd in upd_A:
        upd(A)
    for upd in upd_D:
        upd(D)
    sword_update(A, tip)
    place_camera(t)
    sc.render.filepath = os.path.join(OUTDIR, "frame_%04d.png" % f)
    bpy.ops.render.render(write_still=True)
    if f % 12 == 0:
        print("WMV frame", f, flush=True)

print("WHITEMODEL_VIDEO_OK", OUTDIR, FRAMES, FPS, W, H)
