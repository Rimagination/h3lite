# Parametric white-model (clay blockout) generator for H3 reference images.
# Usage: blender --background --python whitemodel.py -- --out OUT.png --res 1344x768 --pose fight_pair
# Community-standard blockout: joint-point dict + capsule limbs, no rig, Workbench clay render.
import bpy, bmesh, math, sys, json
from mathutils import Vector

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None):
    return ARGV[ARGV.index(k) + 1] if k in ARGV else d

OUT = arg("--out", r"E:\Blender\whitemodel_out.png")
W, H = [int(v) for v in (arg("--res", "1344x768").split("x"))]
POSE = arg("--pose", "fight_pair")

# ---------- clean scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------- clay material ----------
mat = bpy.data.materials.new("ClayGray")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.62, 0.62, 0.62, 1.0)
bsdf.inputs["Roughness"].default_value = 0.9

# ---------- helpers ----------
def setmat(o):
    o.data.materials.clear()
    o.data.materials.append(mat)

def sphere(loc, r, name, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=24, ring_count=16)
    o = bpy.context.object; o.name = name; o.scale = scale
    bpy.ops.object.shade_smooth(); setmat(o); return o

def capsule(p1, p2, r, name):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    L = d.length
    if L < 1e-6:
        return sphere(p1, r, name)
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=L, location=(p1 + p2) / 2, vertices=16)
    o = bpy.context.object; o.name = name
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    bpy.ops.object.shade_smooth(); setmat(o)
    sphere(p1, r, name + "_j1"); sphere(p2, r, name + "_j2")
    return o

def box(loc, size, name, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object; o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    o.rotation_euler = rot
    setmat(o); return o

# 7.5-head proportion template, height 1.70 m -> head unit u
U = 1.70 / 7.5

def figure(j, name):
    """j: dict of joint points in world space (meters)."""
    parts = []
    parts.append(sphere(j["head"], U * 0.50, name + "_head", scale=(0.88, 0.95, 1.08)))
    parts.append(capsule(j["neck"], j["chest"], U * 0.16, name + "_neck"))
    parts.append(sphere(j["chest"], U * 0.36, name + "_chest", scale=(1.25, 0.85, 1.1)))
    parts.append(capsule(j["chest"], j["pelvis"], U * 0.34, name + "_torso"))
    parts.append(sphere(j["pelvis"], U * 0.32, name + "_pelvis", scale=(1.15, 0.9, 0.95)))
    for s in ("l", "r"):
        parts.append(sphere(j["sho_" + s], U * 0.18, name + "_sho" + s))
        parts.append(capsule(j["chest"], j["sho_" + s], U * 0.15, name + "_clav" + s))
        parts.append(capsule(j["sho_" + s], j["elb_" + s], U * 0.16, name + "_uparm" + s))
        parts.append(capsule(j["elb_" + s], j["wri_" + s], U * 0.13, name + "_forearm" + s))
        parts.append(sphere(j["wri_" + s], U * 0.15, name + "_hand" + s, scale=(0.6, 1.0, 1.2)))
        parts.append(capsule(j["hip_" + s], j["knee_" + s], U * 0.24, name + "_thigh" + s))
        parts.append(sphere(j["knee_" + s], U * 0.19, name + "_knee" + s))
        parts.append(capsule(j["knee_" + s], j["ank_" + s], U * 0.18, name + "_shin" + s))
        parts.append(box((j["ank_" + s][0], j["ank_" + s][1] + 0.09, 0.045), (0.09, 0.26, 0.09), name + "_foot" + s))
    return parts

def sword(hand1, hand2, tip, name):
    h1, h2, tp = Vector(hand1), Vector(hand2), Vector(tip)
    grip_mid = (h1 + h2) / 2
    blade_dir = (tp - grip_mid).normalized()
    blade_len = (tp - grip_mid).length
    bpy.ops.mesh.primitive_cube_add(location=grip_mid + blade_dir * (blade_len / 2))
    b = bpy.context.object; b.name = name + "_blade"
    b.scale = (0.016, blade_len / 2, 0.055)
    b.rotation_mode = 'QUATERNION'
    b.rotation_quaternion = blade_dir.to_track_quat('Y', 'X')
    setmat(b)
    capsule(h1, h2, 0.024, name + "_grip")
    gmid = grip_mid
    box((gmid.x, gmid.y, gmid.z), (0.16, 0.05, 0.035), name + "_guard",
        rot=(0, 0, math.atan2(blade_dir.y, blade_dir.x)))
    return b

# ---------- pose: two-figure sword fight (matches PoseMy.Art ref v1 blocking) ----------
def pose_fight_pair():
    # Attacker: deep lunge toward +Y, two-hand grip swinging blade up-forward
    A = dict(
        head=(0.09, -0.26, 1.56), neck=(0.07, -0.28, 1.42), chest=(0.05, -0.30, 1.25),
        pelvis=(0.00, -0.35, 0.95),
        sho_l=(-0.18, -0.32, 1.38), sho_r=(0.28, -0.28, 1.38),
        elb_l=(-0.12, -0.06, 1.14), elb_r=(0.44, -0.06, 1.20),
        wri_l=(0.10, 0.16, 1.04), wri_r=(0.24, 0.20, 1.08),
        hip_l=(-0.11, -0.35, 0.90), hip_r=(0.11, -0.35, 0.90),
        knee_l=(-0.20, -0.75, 0.50), knee_r=(0.22, 0.05, 0.48),
        ank_l=(-0.24, -1.05, 0.07), ank_r=(0.34, 0.45, 0.07),
    )
    # Defender: at +Y facing -Y, lead hand parrying, rear arm cocked back
    D = dict(
        head=(-0.05, 1.20, 1.56), neck=(-0.04, 1.21, 1.42), chest=(-0.03, 1.22, 1.25),
        pelvis=(0.00, 1.25, 0.95),
        sho_l=(-0.26, 1.23, 1.38), sho_r=(0.20, 1.27, 1.38),
        elb_l=(-0.34, 1.00, 1.20), elb_r=(0.40, 1.32, 1.24),
        wri_l=(-0.26, 0.68, 1.10), wri_r=(0.56, 1.46, 1.44),
        hip_l=(-0.11, 1.25, 0.90), hip_r=(0.11, 1.25, 0.90),
        knee_l=(-0.18, 0.95, 0.50), knee_r=(0.20, 1.55, 0.50),
        ank_l=(-0.22, 0.70, 0.07), ank_r=(0.28, 1.85, 0.07),
    )
    figure(A, "Attacker")
    figure(D, "Defender")
    sword(A["wri_l"], A["wri_r"], (1.05, 0.70, 1.30), "AttackerSword")
    return [A, D]

POSES = {"fight_pair": pose_fight_pair}
joints_all = POSES[POSE]()

# ---------- ground ----------
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
g = bpy.context.object; g.name = "Ground"
gmat = bpy.data.materials.new("GroundGray"); gmat.use_nodes = True
gb = gmat.node_tree.nodes.get("Principled BSDF")
gb.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1.0)
gb.inputs["Roughness"].default_value = 1.0
g.data.materials.append(gmat)

# ---------- world + sun ----------
world = bpy.data.worlds.new("W"); bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.85, 0.85, 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
bpy.ops.object.light_add(type='SUN', location=(4, -3, 8))
sun = bpy.context.object; sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), math.radians(-8), math.radians(35))

# ---------- camera: auto-frame the joint cloud ----------
pts = [Vector(p) for j in joints_all for p in j.values()]
c = sum(pts, Vector()) / len(pts)
r = max((p - c).length for p in pts) + 0.55
cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (c.x + r * 1.20, c.y - r * 1.70, c.z + r * 0.50)
direc = c - cam.location
cam.rotation_mode = 'QUATERNION'
cam.rotation_quaternion = direc.to_track_quat('-Z', 'Y')
bpy.context.scene.camera = cam

# ---------- render: Workbench clay ----------
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'SINGLE'
sc.display.shading.single_color = (0.68, 0.68, 0.68)
sc.display.shading.show_cavity = True
sc.render.resolution_x = W
sc.render.resolution_y = H
sc.render.filepath = OUT
sc.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print("WHITEMODEL_OK", OUT, W, H, POSE)
