"""
Escena 3/3: ATG8ilacion en el tonoplasto. ATG16 llega primero y se anclan en la
membrana vacuolar; ATG8 se lipida despues junto a el; uno de los ATG16 termina
internalizado en el lumen vacuolar (visto por microscopia electronica en la tesis).

Uso:
  blender --background --python scene3_atg8ilacion.py -- --render
  blender --background --python scene3_atg8ilacion.py -- --render-still 90
"""

import sys
import os
import math
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c

TOTAL_FRAMES = int(c.FPS * 5.5)

ATG16_START_FRAME = int(c.FPS * 0.5)
ATG16_TRAVEL_FRAMES = int(c.FPS * 1.0)

ATG8_START_FRAME = int(c.FPS * 2.4)
ATG8_TRAVEL_FRAMES = int(c.FPS * 1.0)

ATG16_INTERNALIZE_START = int(c.FPS * 4.3)
ATG16_INTERNALIZE_END = int(c.FPS * 5.3)


VHA_H_LOCATION = (-0.35, 0.65, 0.5)
ATG16_VHA_CONTACT_FRAME = ATG16_START_FRAME + ATG16_TRAVEL_FRAMES


def create_vha_h(mn):
    """VHA-H: subunidad periferica (citosolica) del dominio V1 de la V-ATPasa,
    acoplada al dominio V0 en el tonoplasto. En la tesis, el docking
    HADDOCK entre VHA-H y el dominio WD40 de ATG16 es la interaccion
    candidata que reclutaria ATG16 al tonoplasto. Posicionada pegada al primer
    ATG16 y centrada en el encuadre para que la interaccion sea el foco visual
    de la escena, con un pulso de brillo en el momento del contacto."""
    mat = c.make_material("Mat_VHA_H", (0.9, 0.75, 0.15), roughness=0.3, emission_strength=0.05, subsurface=0.3)
    mol = c.fetch_molecule(mn, c.UNIPROT_IDS["VHA_H"], "VHA_H", mat)
    obj = mol.object
    obj.location = VHA_H_LOCATION
    obj.rotation_euler = (math.radians(25), math.radians(-15), math.radians(40))
    obj.scale = (1.6, 1.6, 1.6)
    c.add_brownian_jitter(obj, TOTAL_FRAMES, seed=40, amplitude_deg=4, cycles=2)

    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    emission_input = bsdf.inputs["Emission Strength"]
    emission_input.default_value = 0.05
    emission_input.keyframe_insert(data_path="default_value", frame=ATG16_VHA_CONTACT_FRAME - 4)
    emission_input.default_value = 0.6
    emission_input.keyframe_insert(data_path="default_value", frame=ATG16_VHA_CONTACT_FRAME + 4)
    emission_input.default_value = 0.15
    emission_input.keyframe_insert(data_path="default_value", frame=ATG16_VHA_CONTACT_FRAME + int(c.FPS * 0.6))

    return obj, mat


def create_atg16_molecules(mn):
    mat = c.make_material("Mat_ATG16", (0.1, 0.65, 0.7), roughness=0.28, emission_strength=0.05, subsurface=0.35)
    mol = c.fetch_molecule(mn, c.UNIPROT_IDS["ATG16"], "ATG16_1", mat)
    base = mol.object

    cytosol_positions = [
        (-1.6, 1.1, 2.3),
        (1.5, -1.3, 2.1),
        (-0.9, -1.7, 2.4),
    ]
    anchor_positions = [
        (-0.65, 0.95, 0.35),
        (1.1, -0.5, 0.35),
        (-0.5, -0.9, 0.35),
    ]

    objs = [base]
    for i in range(1, 3):
        objs.append(c.duplicate_object(base, f"ATG16_{i+1}"))

    for i, (obj, start, anchor) in enumerate(zip(objs, cytosol_positions, anchor_positions)):
        obj.scale = (1.7, 1.7, 1.7)
        obj.rotation_euler = (math.radians(10 * i), math.radians(20 * i), math.radians(15 * i))

        travel_start = ATG16_START_FRAME + i * 5
        travel_end = travel_start + ATG16_TRAVEL_FRAMES

        obj.location = start
        obj.keyframe_insert(data_path="location", frame=travel_start)
        obj.location = anchor
        obj.keyframe_insert(data_path="location", frame=travel_end)

        c.add_brownian_jitter(obj, travel_end, seed=20 + i, amplitude_deg=6, cycles=2)

        if i == 0:
            deep = (anchor[0], anchor[1], -2.2)
            obj.keyframe_insert(data_path="location", frame=ATG16_INTERNALIZE_START)
            obj.location = deep
            obj.keyframe_insert(data_path="location", frame=ATG16_INTERNALIZE_END)

    return objs


def create_atg8_molecules(mn):
    mat = c.make_material("Mat_ATG8A", (0.15, 0.78, 0.28), roughness=0.25, emission_strength=0.05, subsurface=0.35)
    mol = c.fetch_molecule(mn, c.UNIPROT_IDS["ATG8A"], "ATG8A_1", mat)
    base = mol.object

    cytosol_positions = [
        (-1.9, 1.7, 2.5),
        (0.6, 1.9, 2.2),
        (1.9, 1.2, 2.6),
    ]
    anchor_positions = [
        (-1.5, 1.3, 0.4),
        (0.4, 1.4, 0.4),
        (1.5, 0.9, 0.4),
    ]

    objs = [base]
    for i in range(1, 3):
        objs.append(c.duplicate_object(base, f"ATG8A_{i+1}"))

    for i, (obj, start, anchor) in enumerate(zip(objs, cytosol_positions, anchor_positions)):
        obj.scale = (1.9, 1.9, 1.9)
        obj.rotation_euler = (math.radians(30 * i), math.radians(5 * i), math.radians(50 * i))

        travel_start = ATG8_START_FRAME + i * 5
        travel_end = travel_start + ATG8_TRAVEL_FRAMES

        obj.location = start
        obj.keyframe_insert(data_path="location", frame=travel_start)
        obj.location = anchor
        obj.keyframe_insert(data_path="location", frame=travel_end)

        c.add_brownian_jitter(obj, TOTAL_FRAMES, seed=30 + i, amplitude_deg=6, cycles=2)

    return objs


def create_camera_and_lights():
    bpy.ops.object.camera_add(location=(0.3, -7.0, 1.4), rotation=(math.radians(84), 0, math.radians(-6)))
    camera = bpy.context.active_object
    camera.name = "Camara"
    camera.data.lens = 42
    bpy.context.scene.camera = camera

    camera.data.dof.use_dof = True
    camera.data.dof.aperture_fstop = 2.4
    camera.data.dof.focus_distance = 7.0

    camera.location = (0.3, -7.0, 1.4)
    camera.keyframe_insert(data_path="location", frame=1)
    camera.location = (-0.2, -4.8, 0.5)
    camera.keyframe_insert(data_path="location", frame=TOTAL_FRAMES)

    c.add_wehi_lighting(key_loc=(2.0, -2.8, 3.2), target=(-0.4, 0.7, 0.5), key_energy=320, key_size=2.5)

    bpy.ops.object.light_add(type="AREA", location=(0, 1, -3.5))
    below = bpy.context.active_object
    below.name = "LuzVacuola"
    below.data.energy = 45
    below.data.size = 6
    below.data.color = (0.6, 0.35, 0.9)
    below.rotation_euler = (math.radians(180), 0, 0)

    return camera


def build_scene():
    c.clear_scene()
    c.setup_world_dark()
    mn = c.enable_molecular_nodes()

    c.create_vacuole()
    c.create_tonoplast()

    create_vha_h(mn)
    create_atg16_molecules(mn)
    # NOTA: VHA-H y el primer ATG16 quedan pegados y centrados en el encuadre
    # (ver ATG16_VHA_CONTACT_FRAME) para que la interaccion ATG16-VATPasa sea
    # el foco visual, con un pulso de brillo en VHA-H en el momento del contacto.
    create_atg8_molecules(mn)

    c.create_crowding_proteins(
        bounds=((-3.5, 3.5), (-3, 3), (0.6, 2.4)),
        count=26,
        seed=300,
        total_frames=TOTAL_FRAMES,
    )

    create_camera_and_lights()
    c.setup_render_settings(TOTAL_FRAMES, "escena3_atg8ilacion")
    bpy.context.scene.frame_set(1)


if __name__ == "__main__":
    build_scene()

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--render-still" in args:
        frame_arg = int(c.FPS * 3.0)
        if len(args) > 1 and args[-1].isdigit():
            frame_arg = int(args[-1])
        if "--workbench" in args:
            bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        c.render_still(frame_arg, "escena3_preview.png")
    elif "--render" in args:
        c.render_animation("escena3_atg8ilacion.mp4")
    elif "--render-frames" in args:
        i = args.index("--render-frames")
        start, end = int(args[i + 1]), int(args[i + 2])
        c.render_frame_range(start, end, "escena3")
    elif "--encode" in args:
        c.encode_png_sequence("escena3", 1, TOTAL_FRAMES, c.FPS, "escena3_atg8ilacion.mp4")
