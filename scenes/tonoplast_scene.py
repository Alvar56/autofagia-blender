"""
Escena 3D: autofagia no canonica (VQC) en Arabidopsis thaliana bajo dano de pared celular.
Modelo basado en la tesis de master del usuario (Pascual Garcia, BOKU 2026):
  pared celular danada -> THE1 (receptor quinasa, membrana plasmatica) -> senal rio abajo
  -> tonoplasto: ATG16 llega primero (~40min), luego se lipida ATG8 (~1h) -> ATG16 se
  internaliza en el lumen vacuolar. En paralelo: TCH3 forma puntos transitorios en la
  periferia celular (especifico de ES20-1) y ZAC se transloca al nucleo via su dominio C2.

Usa Molecular Nodes (github.com/BradyAJohnston/MolecularNodes) para traer las estructuras
AlphaFold reales citadas en la tesis (Img. 1): THE1, TOUCH3/CML12, ZAC/AGD12, ATG16, y
ATG8A, en vez de primitivas geometricas.

Se ejecuta dentro de Blender (bpy no existe fuera de Blender).

Uso headless (sin interfaz, renderiza y sale):
  blender --background --python tonoplast_scene.py -- --render

Uso interactivo (abre Blender con la escena ya construida):
  blender --python tonoplast_scene.py
"""

import sys
import os
import math
import bpy

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")

FPS = 24
DURATION_SECONDS = 6
TOTAL_FRAMES = FPS * DURATION_SECONDS

# Alturas (Z) de cada compartimento, de arriba a abajo
Z_CELL_WALL = 5.0
Z_PLASMA_MEMBRANE = 3.0
Z_TONOPLAST = 0.0
Z_VACUOLE_CENTER = -7.0

WALL_DAMAGE_START = 1
WALL_DAMAGE_END = int(FPS * 1.6)

THE1_ACTIVATION_START = int(FPS * 1.2)
THE1_ACTIVATION_END = int(FPS * 2.0)

ATG16_START_FRAME = int(FPS * 2.2)
ATG16_TRAVEL_FRAMES = int(FPS * 1.0)

ATG8_START_FRAME = int(FPS * 4.0)
ATG8_TRAVEL_FRAMES = int(FPS * 1.0)

ATG16_INTERNALIZE_START = int(FPS * 4.8)
ATG16_INTERNALIZE_END = int(FPS * 5.8)

TCH3_PUNCTA_START = int(FPS * 1.8)
TCH3_PUNCTA_END = int(FPS * 2.6)

ZAC_TRANSLOCATION_START = int(FPS * 1.6)
ZAC_TRANSLOCATION_END = int(FPS * 3.6)

NUCLEUS_LOCATION = (4.3, -3.2, 1.4)
NUCLEUS_RADIUS = 1.1

# UniProt de Arabidopsis thaliana citados en la tesis (Img. 1) + ATG8A
UNIPROT_IDS = {
    "THE1": "Q9LK35",
    "ZAC": "Q9FVJ3",
    "ATG16": "Q6NNP0",
    "ATG8A": "Q8LEM4",
}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_collection in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(block_collection):
            if block.users == 0:
                block_collection.remove(block)


def enable_molecular_nodes():
    bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.molecularnodes")
    import bl_ext.blender_org.molecularnodes as mn
    return mn


def make_material(name, base_color, roughness=0.4, transmission=0.0, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    if emission_strength > 0:
        bsdf.inputs["Emission Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def fetch_molecule(mn, code, name, material):
    mol = mn.Molecule.fetch(code, format="cif", database="alphafold", centre="centroid")
    mol.object.name = name
    mol.add_style("cartoon", material=material, color=None)
    return mol


def duplicate_object(source_obj, new_name):
    bpy.ops.object.select_all(action="DESELECT")
    source_obj.select_set(True)
    bpy.context.view_layer.objects.active = source_obj
    bpy.ops.object.duplicate(linked=True)
    dup = bpy.context.active_object
    dup.name = new_name
    return dup


def create_vacuole():
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=6, location=(0, 0, Z_VACUOLE_CENTER), segments=48, ring_count=24
    )
    vacuole = bpy.context.active_object
    vacuole.name = "Vacuola"
    vacuole.data.materials.append(
        make_material("Mat_Vacuola", (0.55, 0.35, 0.85), roughness=0.1, transmission=0.65)
    )
    bpy.ops.object.shade_smooth()
    return vacuole


def create_tonoplast():
    bpy.ops.mesh.primitive_grid_add(
        size=14, x_subdivisions=64, y_subdivisions=64, location=(0, 0, Z_TONOPLAST)
    )
    membrane = bpy.context.active_object
    membrane.name = "Tonoplasto"

    displace_mod = membrane.modifiers.new("Ondulacion", "DISPLACE")
    tex = bpy.data.textures.new("TonoplastoNoise", type="CLOUDS")
    tex.noise_scale = 0.15
    displace_mod.texture = tex
    displace_mod.strength = 0.1
    displace_mod.mid_level = 0.5

    solidify_mod = membrane.modifiers.new("Grosor", "SOLIDIFY")
    solidify_mod.thickness = 0.25

    membrane.data.materials.append(
        make_material("Mat_Tonoplasto", (0.25, 0.1, 0.5), roughness=0.2, transmission=0.25)
    )
    bpy.ops.object.shade_smooth()
    return membrane


def create_cell_wall_damage_cutter():
    bpy.ops.mesh.primitive_cylinder_add(
        radius=1.0, depth=3.0, location=(0, 0, Z_CELL_WALL)
    )
    cutter = bpy.context.active_object
    cutter.name = "CorteDanoParedCelular"
    cutter.hide_render = True
    cutter.hide_viewport = True

    cutter.scale = (0.001, 0.001, 1.0)
    cutter.keyframe_insert(data_path="scale", frame=WALL_DAMAGE_START)

    cutter.scale = (2.3, 2.3, 1.0)
    cutter.keyframe_insert(data_path="scale", frame=WALL_DAMAGE_END)

    return cutter


def create_cell_wall(cutter):
    bpy.ops.mesh.primitive_grid_add(
        size=14, x_subdivisions=48, y_subdivisions=48, location=(0, 0, Z_CELL_WALL)
    )
    wall = bpy.context.active_object
    wall.name = "ParedCelular"

    displace_mod = wall.modifiers.new("Fibras", "DISPLACE")
    tex = bpy.data.textures.new("ParedCelularNoise", type="CLOUDS")
    tex.noise_scale = 0.1
    displace_mod.texture = tex
    displace_mod.strength = 0.15

    boolean_mod = wall.modifiers.new("Dano", "BOOLEAN")
    boolean_mod.operation = "DIFFERENCE"
    boolean_mod.object = cutter

    solidify_mod = wall.modifiers.new("Grosor", "SOLIDIFY")
    solidify_mod.thickness = 0.4

    wall.data.materials.append(
        make_material("Mat_ParedCelular", (0.75, 0.65, 0.4), roughness=0.75, transmission=0.0)
    )
    bpy.ops.object.shade_smooth()
    return wall


def create_plasma_membrane():
    bpy.ops.mesh.primitive_grid_add(
        size=14, x_subdivisions=48, y_subdivisions=48, location=(0, 0, Z_PLASMA_MEMBRANE)
    )
    membrane = bpy.context.active_object
    membrane.name = "MembranaPlasmatica"

    displace_mod = membrane.modifiers.new("Ondulacion", "DISPLACE")
    tex = bpy.data.textures.new("MembranaPMNoise", type="CLOUDS")
    tex.noise_scale = 0.15
    displace_mod.texture = tex
    displace_mod.strength = 0.08

    solidify_mod = membrane.modifiers.new("Grosor", "SOLIDIFY")
    solidify_mod.thickness = 0.15

    membrane.data.materials.append(
        make_material("Mat_MembranaPM", (0.9, 0.7, 0.7), roughness=0.25, transmission=0.35)
    )
    bpy.ops.object.shade_smooth()
    return membrane


def create_the1_receptor(mn):
    """THE1: receptor quinasa real (AlphaFold Q9LK35), en la membrana plasmatica.
    Se activa (brillo) cuando el dano de la pared crece por encima de el."""
    mat = make_material("Mat_THE1", (0.95, 0.45, 0.1), roughness=0.3, emission_strength=0.0)
    mol = fetch_molecule(mn, UNIPROT_IDS["THE1"], "THE1", mat)
    obj = mol.object
    obj.location = (0, 0, Z_PLASMA_MEMBRANE - 0.3)
    obj.rotation_euler = (math.radians(20), math.radians(8), math.radians(35))
    obj.scale = (1.5, 1.5, 1.5)

    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    emission_input = bsdf.inputs["Emission Strength"]
    emission_input.default_value = 0.0
    emission_input.keyframe_insert(data_path="default_value", frame=THE1_ACTIVATION_START)
    emission_input.default_value = 0.45
    emission_input.keyframe_insert(data_path="default_value", frame=THE1_ACTIVATION_END)

    return obj


def create_atg16_molecules(mn):
    mat = make_material("Mat_ATG16", (0.1, 0.6, 0.65), roughness=0.3, emission_strength=0.25)
    mol = fetch_molecule(mn, UNIPROT_IDS["ATG16"], "ATG16_1", mat)
    base = mol.object

    cytosol_positions = [
        (-2.5, 1.5, 1.6),
        (2.2, -1.8, 1.4),
        (-1.2, -2.3, 1.8),
        (1.8, 1.9, 1.5),
    ]
    anchor_positions = [
        (-1.8, 0.9, 0.4),
        (1.9, -0.7, 0.4),
        (-0.9, -1.4, 0.4),
        (1.1, 1.1, 0.4),
    ]

    objs = [base]
    for i in range(1, 4):
        objs.append(duplicate_object(base, f"ATG16_{i+1}"))

    for i, (obj, start, anchor) in enumerate(zip(objs, cytosol_positions, anchor_positions)):
        obj.rotation_euler = (math.radians(10 * i), math.radians(20 * i), math.radians(15 * i))
        obj.scale = (1.4, 1.4, 1.4)

        travel_start = ATG16_START_FRAME + i * 4
        travel_end = travel_start + ATG16_TRAVEL_FRAMES

        obj.location = start
        obj.keyframe_insert(data_path="location", frame=travel_start)

        obj.location = anchor
        obj.keyframe_insert(data_path="location", frame=travel_end)

        # El primer ATG16 en llegar es el que luego se internaliza en la vacuola
        if i == 0:
            deep_position = (anchor[0], anchor[1], -2.5)
            obj.keyframe_insert(data_path="location", frame=ATG16_INTERNALIZE_START)
            obj.location = deep_position
            obj.keyframe_insert(data_path="location", frame=ATG16_INTERNALIZE_END)

    return objs


def create_atg8_molecules(mn):
    mat = make_material("Mat_ATG8A", (0.15, 0.75, 0.25), roughness=0.25, emission_strength=0.2)
    mol = fetch_molecule(mn, UNIPROT_IDS["ATG8A"], "ATG8A_1", mat)
    base = mol.object

    cytosol_positions = [
        (-2.8, 2.0, 1.8),
        (-1.0, -2.6, 2.0),
        (2.6, 2.2, 1.7),
        (2.0, -1.2, 1.9),
    ]
    anchor_positions = [
        (-1.3, 1.4, 0.5),
        (-0.4, -1.9, 0.5),
        (1.4, 1.6, 0.5),
        (1.5, -0.3, 0.5),
    ]

    objs = [base]
    for i in range(1, 4):
        objs.append(duplicate_object(base, f"ATG8A_{i+1}"))

    for i, (obj, start, anchor) in enumerate(zip(objs, cytosol_positions, anchor_positions)):
        obj.rotation_euler = (math.radians(30 * i), math.radians(5 * i), math.radians(50 * i))
        obj.scale = (1.6, 1.6, 1.6)

        travel_start = ATG8_START_FRAME + i * 4
        travel_end = travel_start + ATG8_TRAVEL_FRAMES

        obj.location = start
        obj.keyframe_insert(data_path="location", frame=travel_start)

        obj.location = anchor
        obj.keyframe_insert(data_path="location", frame=travel_end)

    return objs


def create_nucleus():
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=NUCLEUS_RADIUS, location=NUCLEUS_LOCATION, segments=32, ring_count=16
    )
    nucleus = bpy.context.active_object
    nucleus.name = "Nucleo"
    nucleus.data.materials.append(
        make_material("Mat_Nucleo", (0.5, 0.45, 0.75), roughness=0.2, transmission=0.4)
    )
    bpy.ops.object.shade_smooth()
    return nucleus


def create_tch3_puncta():
    """TCH3: sensor de calcio citosolico. En microscopia confocal real aparece
    como puntos (puncta) al limite de difraccion, no como estructuras resueltas,
    asi que se representan como esferas emisivas en vez de una proteina completa."""
    peripheral_positions = [
        (-4.6, 0.5, 2.6),
        (-4.2, -2.2, 2.5),
        (4.4, 1.8, 2.7),
        (3.9, -0.5, 2.4),
        (-3.8, 3.0, 2.6),
    ]

    puncta = []
    for i, pos in enumerate(peripheral_positions):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=pos, segments=16, ring_count=8)
        dot = bpy.context.active_object
        dot.name = f"TCH3_{i+1}"
        mat = make_material(f"Mat_TCH3_{i+1}", (0.85, 0.2, 0.55), roughness=0.3, emission_strength=0.0)
        dot.data.materials.append(mat)
        bpy.ops.object.shade_smooth()

        dot.scale = (0.3, 0.3, 0.3)
        dot.keyframe_insert(data_path="scale", frame=TCH3_PUNCTA_START)
        dot.scale = (1.2, 1.2, 1.2)
        dot.keyframe_insert(data_path="scale", frame=TCH3_PUNCTA_START + int(FPS * 0.3))
        dot.scale = (1.0, 1.0, 1.0)
        dot.keyframe_insert(data_path="scale", frame=TCH3_PUNCTA_END)

        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        emission_input = bsdf.inputs["Emission Strength"]
        emission_input.default_value = 0.0
        emission_input.keyframe_insert(data_path="default_value", frame=TCH3_PUNCTA_START)
        emission_input.default_value = 0.9
        emission_input.keyframe_insert(data_path="default_value", frame=TCH3_PUNCTA_END)

        puncta.append(dot)
    return puncta


def create_zac_translocation(mn):
    """ZAC: ARF-GAP real (AlphaFold Q9FVJ3) que, bajo dano de pared, se transloca
    progresivamente al nucleo a traves de su dominio C2. Rama secundaria/paralela,
    no forma parte del eje THE1->ATG16->ATG8."""
    mat = make_material("Mat_ZAC", (0.55, 0.25, 0.7), roughness=0.3, emission_strength=0.2)
    mol = fetch_molecule(mn, UNIPROT_IDS["ZAC"], "ZAC_1", mat)
    base = mol.object

    start_positions = [
        (2.0, -2.4, 2.3),
        (2.8, -1.5, 2.0),
        (1.6, -3.0, 1.9),
    ]

    objs = [base]
    for i in range(1, 3):
        objs.append(duplicate_object(base, f"ZAC_{i+1}"))

    for i, (obj, start) in enumerate(zip(objs, start_positions)):
        obj.rotation_euler = (math.radians(40 * i), math.radians(15 * i), math.radians(60 * i))
        obj.scale = (1.4, 1.4, 1.4)

        travel_start = ZAC_TRANSLOCATION_START + i * 6
        travel_end = ZAC_TRANSLOCATION_END + i * 6

        direction_x = NUCLEUS_LOCATION[0] - start[0]
        direction_y = NUCLEUS_LOCATION[1] - start[1]
        direction_z = NUCLEUS_LOCATION[2] - start[2]
        length = math.sqrt(direction_x**2 + direction_y**2 + direction_z**2)
        surface_point = (
            NUCLEUS_LOCATION[0] - direction_x / length * NUCLEUS_RADIUS,
            NUCLEUS_LOCATION[1] - direction_y / length * NUCLEUS_RADIUS,
            NUCLEUS_LOCATION[2] - direction_z / length * NUCLEUS_RADIUS,
        )

        obj.location = start
        obj.keyframe_insert(data_path="location", frame=travel_start)

        obj.location = surface_point
        obj.keyframe_insert(data_path="location", frame=travel_end)

    return objs


def create_camera_and_lights():
    bpy.ops.object.camera_add(location=(0, -20, 2.0), rotation=(math.radians(87), 0, 0))
    camera = bpy.context.active_object
    camera.name = "CamaraPrincipal"
    camera.data.lens = 32
    bpy.context.scene.camera = camera

    camera.data.dof.use_dof = True
    camera.data.dof.aperture_fstop = 4.0
    camera.data.dof.focus_distance = 20.0

    # Dolly cinematografico lento: de vista general a plano cercano del tonoplasto
    camera.location = (0, -20, 2.0)
    camera.keyframe_insert(data_path="location", frame=1)
    camera.data.dof.focus_distance = 20.0
    camera.data.dof.keyframe_insert(data_path="focus_distance", frame=1)

    camera.location = (0, -14, 0.6)
    camera.keyframe_insert(data_path="location", frame=TOTAL_FRAMES)
    camera.data.dof.focus_distance = 14.0
    camera.data.dof.keyframe_insert(data_path="focus_distance", frame=TOTAL_FRAMES)

    bpy.ops.object.light_add(type="SUN", location=(4, -6, 12))
    sun = bpy.context.active_object
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(45), 0, math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-6, -6, 8))
    fill = bpy.context.active_object
    fill.data.energy = 400
    fill.data.size = 8

    bpy.ops.object.light_add(type="AREA", location=(0, 6, -1))
    rim = bpy.context.active_object
    rim.data.energy = 250
    rim.data.size = 10
    rim.data.color = (0.75, 0.8, 1.0)
    rim.rotation_euler = (math.radians(-100), 0, 0)

    return camera


def setup_world():
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("Mundo")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.85, 0.9, 0.95, 1.0)
    bg.inputs["Strength"].default_value = 1.0


def setup_render_settings():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = TOTAL_FRAMES
    scene.render.fps = FPS
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100

    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.use_raytracing = True
    scene.eevee.taa_render_samples = 64
    scene.eevee.use_shadows = True

    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.4

    scene.render.filepath = os.path.join(OUTPUT_DIR, "tonoplast_")
    scene.render.image_settings.file_format = "PNG"


def build_scene():
    clear_scene()
    setup_world()
    mn = enable_molecular_nodes()

    create_vacuole()
    create_tonoplast()

    cutter = create_cell_wall_damage_cutter()
    create_cell_wall(cutter)
    create_plasma_membrane()
    create_the1_receptor(mn)

    create_atg16_molecules(mn)
    create_atg8_molecules(mn)

    create_nucleus()
    create_tch3_puncta()
    create_zac_translocation(mn)

    create_camera_and_lights()
    setup_render_settings()
    bpy.context.scene.frame_set(1)


def render_still(frame=None):
    scene = bpy.context.scene
    if frame is not None:
        scene.frame_set(frame)
    scene.render.filepath = os.path.join(OUTPUT_DIR, "tonoplast_preview.png")
    bpy.ops.render.render(write_still=True)


def render_animation():
    scene = bpy.context.scene
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.filepath = os.path.join(OUTPUT_DIR, "tonoplast_autofagia.mp4")
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    build_scene()

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--render-still" in args:
        frame_arg = int(FPS * 4.5)
        if len(args) > 1 and args[-1].isdigit():
            frame_arg = int(args[-1])
        render_still(frame=frame_arg)
    elif "--render" in args:
        render_animation()

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCRIPT_DIR, "tonoplast_scene.blend"))
