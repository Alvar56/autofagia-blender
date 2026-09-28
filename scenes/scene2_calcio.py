"""
Escena 2/3: la cascada de calcio viaja desde THE1 hacia el resto de la celula.
THE1 ya esta activado (brillo constante); protagonismo para las particulas de
calcio, los puntos de TCH3, y ZAC alejandose hacia el nucleo.

Uso:
  blender --background --python scene2_calcio.py -- --render
  blender --background --python scene2_calcio.py -- --render-still 60
"""

import sys
import os
import math
import random
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c

TOTAL_FRAMES = int(c.FPS * 4.5)

CALCIUM_BURST_START = int(c.FPS * 0.3)
CALCIUM_WAVE_DURATION = int(c.FPS * 2.2)

TCH3_PUNCTA_START = int(c.FPS * 1.2)
TCH3_PUNCTA_END = int(c.FPS * 2.0)

ZAC_START = int(c.FPS * 0.8)
ZAC_END = int(c.FPS * 3.6)

MCA1_LOCATION = (0.9, -0.2, c.Z_PLASMA_MEMBRANE - 0.1)

TCH3_POSITIONS = [
    (-2.3, 0.1, 1.6),
    (2.0, -0.6, 1.4),
    (-1.3, -1.3, 1.15),
]


def create_the1_static(mn):
    mat = c.make_material("Mat_THE1", (0.95, 0.42, 0.08), roughness=0.28, emission_strength=0.03, subsurface=0.35)
    mol = c.fetch_molecule(mn, c.UNIPROT_IDS["THE1"], "THE1", mat)
    obj = mol.object
    obj.location = (0, 0.5, c.Z_PLASMA_MEMBRANE - 0.2)
    obj.rotation_euler = (math.radians(15), math.radians(5), math.radians(20))
    obj.scale = (1.9, 1.9, 1.9)
    c.add_brownian_jitter(obj, TOTAL_FRAMES, seed=1, amplitude_deg=3, cycles=3)
    return obj


def create_plasma_membrane_strip():
    c.create_plasma_membrane()


def create_mca1(mn):
    """MCA1: canal de calcio mecanosensible, rio abajo de THE1 en la via CWI.
    Es el conducto real por el que entra el calcio, no THE1 directamente."""
    mat = c.make_material("Mat_MCA1", (0.25, 0.5, 0.9), roughness=0.3, emission_strength=0.05, subsurface=0.3)
    mol = c.fetch_molecule(mn, c.UNIPROT_IDS["MCA1"], "MCA1", mat)
    obj = mol.object
    obj.location = MCA1_LOCATION
    obj.rotation_euler = (math.radians(10), math.radians(70), math.radians(5))
    obj.scale = (1.6, 1.6, 1.6)
    c.add_brownian_jitter(obj, TOTAL_FRAMES, seed=5, amplitude_deg=3, cycles=2)
    return obj


def create_calcium_particles():
    rnd = random.Random(42)
    origin = (MCA1_LOCATION[0], MCA1_LOCATION[1], MCA1_LOCATION[2] - 0.6)
    mat = c.make_material("Mat_Calcio", (0.75, 0.95, 0.3), roughness=0.2, emission_strength=6.0)

    particles = []
    n = 14
    tch3_targets = 6  # las primeras convergen en TCH3, el resto se dispersan por el citosol
    for i in range(n):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=origin, segments=12, ring_count=6)
        p = bpy.context.active_object
        p.name = f"Calcio_{i+1}"
        p.data.materials.append(mat)
        bpy.ops.object.shade_smooth()

        if i < tch3_targets:
            tch3_pos = TCH3_POSITIONS[i % len(TCH3_POSITIONS)]
            target = (
                tch3_pos[0] + rnd.uniform(-0.15, 0.15),
                tch3_pos[1] + rnd.uniform(-0.15, 0.15),
                tch3_pos[2] + rnd.uniform(-0.1, 0.2),
            )
        else:
            angle = rnd.uniform(0, math.tau)
            radial = rnd.uniform(1.2, 3.4)
            target = (
                origin[0] + math.cos(angle) * radial,
                origin[1] + math.sin(angle) * radial * 0.6,
                origin[2] - rnd.uniform(0.8, 2.4),
            )

        start = CALCIUM_BURST_START + i * 2
        end = start + CALCIUM_WAVE_DURATION + rnd.randint(-6, 10)
        fade_end = end + int(c.FPS * 0.5)

        p.scale = (0.001, 0.001, 0.001)
        p.keyframe_insert(data_path="scale", frame=max(1, start - 3))
        p.scale = (1.0, 1.0, 1.0)
        p.keyframe_insert(data_path="scale", frame=start)

        p.location = origin
        p.keyframe_insert(data_path="location", frame=start)
        p.location = target
        p.keyframe_insert(data_path="location", frame=end)

        p.scale = (1.0, 1.0, 1.0)
        p.keyframe_insert(data_path="scale", frame=end)
        p.scale = (0.001, 0.001, 0.001)
        p.keyframe_insert(data_path="scale", frame=min(TOTAL_FRAMES, fade_end))

        particles.append(p)
    return particles


def create_tch3_molecules(mn):
    """TCH3: sensor de calcio tipo calmodulina (6 motivos EF-hand). Al llegar
    el calcio, las EF-hand cambian de conformacion y reclutan a otras
    proteinas; aqui se representa con un pulso de escala + brillo en el
    momento en que las particulas de calcio la alcanzan."""
    mat = c.make_material("Mat_TCH3", (0.9, 0.2, 0.55), roughness=0.3, emission_strength=0.0, subsurface=0.4)
    mol = c.fetch_molecule(mn, c.UNIPROT_IDS["TCH3"], "TCH3_1", mat)
    base = mol.object

    objs = [base]
    for i in range(1, len(TCH3_POSITIONS)):
        objs.append(c.duplicate_object(base, f"TCH3_{i+1}"))

    for i, (obj, pos) in enumerate(zip(objs, TCH3_POSITIONS)):
        obj.location = pos
        obj.rotation_euler = (math.radians(20 * i), math.radians(35 * i), math.radians(10 * i))

        start = TCH3_PUNCTA_START + i * 5
        peak = start + int(c.FPS * 0.2)
        end = TCH3_PUNCTA_END + i * 5

        obj.scale = (1.1, 1.1, 1.1)
        obj.keyframe_insert(data_path="scale", frame=start)
        obj.scale = (1.45, 1.35, 1.45)
        obj.keyframe_insert(data_path="scale", frame=peak)
        obj.scale = (1.25, 1.25, 1.25)
        obj.keyframe_insert(data_path="scale", frame=end)

    return objs


def create_zac(mn):
    mat = c.make_material("Mat_ZAC", (0.55, 0.25, 0.7), roughness=0.3, emission_strength=0.06, subsurface=0.3)
    mol = c.fetch_molecule(mn, c.UNIPROT_IDS["ZAC"], "ZAC_1", mat)
    base = mol.object

    start_positions = [
        (1.6, -1.6, 1.9),
        (2.0, -1.0, 1.6),
    ]

    objs = [base]
    objs.append(c.duplicate_object(base, "ZAC_2"))

    for i, (obj, start) in enumerate(zip(objs, start_positions)):
        obj.scale = (1.5, 1.5, 1.5)
        c.add_brownian_jitter(obj, TOTAL_FRAMES, seed=10 + i, amplitude_deg=8, cycles=2)

        direction_x = c.NUCLEUS_LOCATION[0] - start[0]
        direction_y = c.NUCLEUS_LOCATION[1] - start[1]
        direction_z = c.NUCLEUS_LOCATION[2] - start[2]
        length = math.sqrt(direction_x**2 + direction_y**2 + direction_z**2)
        surface_point = (
            c.NUCLEUS_LOCATION[0] - direction_x / length * c.NUCLEUS_RADIUS,
            c.NUCLEUS_LOCATION[1] - direction_y / length * c.NUCLEUS_RADIUS,
            c.NUCLEUS_LOCATION[2] - direction_z / length * c.NUCLEUS_RADIUS,
        )

        travel_start = ZAC_START + i * 8
        travel_end = ZAC_END + i * 8

        obj.location = start
        obj.keyframe_insert(data_path="location", frame=travel_start)
        obj.location = surface_point
        obj.keyframe_insert(data_path="location", frame=travel_end)

    return objs


def create_camera_and_lights():
    bpy.ops.object.camera_add(location=(-1.0, -8.5, 1.9), rotation=(math.radians(87), 0, math.radians(-8)))
    camera = bpy.context.active_object
    camera.name = "Camara"
    camera.data.lens = 40
    bpy.context.scene.camera = camera

    camera.data.dof.use_dof = True
    camera.data.dof.aperture_fstop = 2.8
    camera.data.dof.focus_distance = 8.5

    camera.location = (-1.0, -8.5, 1.9)
    camera.keyframe_insert(data_path="location", frame=1)
    camera.location = (0.6, -6.5, 1.3)
    camera.keyframe_insert(data_path="location", frame=TOTAL_FRAMES)

    c.add_wehi_lighting(key_loc=(2.2, -3.8, 3.8), target=(0, 0, 1.6), key_energy=340, key_size=2.5)

    bpy.ops.object.light_add(type="AREA", location=(2, -1, -0.5))
    under = bpy.context.active_object
    under.name = "LuzTonoplasto"
    under.data.energy = 30
    under.data.size = 5
    under.data.color = (0.6, 0.4, 0.9)
    under.rotation_euler = (math.radians(180), 0, 0)

    return camera


def build_scene():
    c.clear_scene()
    c.setup_world_dark()
    mn = c.enable_molecular_nodes()

    create_plasma_membrane_strip()
    create_the1_static(mn)
    create_mca1(mn)
    create_calcium_particles()
    create_tch3_molecules(mn)
    create_zac(mn)
    c.create_nucleus()

    c.create_crowding_proteins(
        bounds=((-4.5, 4.5), (-4, 1.5), (0.3, 2.7)),
        count=30,
        seed=200,
        total_frames=TOTAL_FRAMES,
    )

    create_camera_and_lights()
    c.setup_render_settings(TOTAL_FRAMES, "escena2_calcio")
    bpy.context.scene.frame_set(1)


if __name__ == "__main__":
    build_scene()

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--render-still" in args:
        frame_arg = int(c.FPS * 1.5)
        if len(args) > 1 and args[-1].isdigit():
            frame_arg = int(args[-1])
        if "--workbench" in args:
            bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        c.render_still(frame_arg, "escena2_preview.png")
    elif "--render" in args:
        c.render_animation("escena2_calcio.mp4")
    elif "--render-frames" in args:
        i = args.index("--render-frames")
        start, end = int(args[i + 1]), int(args[i + 2])
        c.render_frame_range(start, end, "escena2")
    elif "--encode" in args:
        c.encode_png_sequence("escena2", 1, TOTAL_FRAMES, c.FPS, "escena2_calcio.mp4")
