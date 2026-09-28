"""
Escena 1/3: la pared celular se rompe y THE1 lo detecta.
Plano cerrado, un solo protagonista (THE1), sin distraer con el resto de la celula.

Uso:
  blender --background --python scene1_pared_celular.py -- --render
  blender --background --python scene1_pared_celular.py -- --render-still 60
"""

import sys
import os
import math
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c

TOTAL_FRAMES = int(c.FPS * 4.5)

WALL_DAMAGE_START = int(c.FPS * 0.6)
WALL_DAMAGE_END = int(c.FPS * 2.6)

THE1_ACTIVATION_START = int(c.FPS * 2.0)
THE1_ACTIVATION_END = int(c.FPS * 3.0)

DAMAGE_MOLECULES_START = int(c.FPS * 1.6)
DAMAGE_MOLECULES_ARRIVE = THE1_ACTIVATION_START

PHOSPHO_SPARK_START = THE1_ACTIVATION_END
PHOSPHO_SPARK_END = TOTAL_FRAMES

THE1_ECTO_Z = c.Z_PLASMA_MEMBRANE + 0.5
THE1_KINASE_Z = c.Z_PLASMA_MEMBRANE - 0.9

MCA1_LOCATION = (1.3, -0.7, c.Z_PLASMA_MEMBRANE - 0.15)


def create_damage_molecules():
    """Oligogalacturonidos (OGs): fragmentos de pectina liberados cuando se
    degrada la pared, el DAMP que de hecho activa THE1. Cadenas cortas de
    2-3 unidades de azucar que viajan desde la grieta hasta el ectodominio."""
    bpy.ops.mesh.primitive_torus_add(major_radius=0.16, minor_radius=0.05, major_segments=10, minor_segments=8)
    unit = bpy.context.active_object
    unit.data.materials.append(
        c.make_material("Mat_OG", (0.95, 0.6, 0.15), roughness=0.35, emission_strength=0.6, subsurface=0.2)
    )
    bpy.ops.object.shade_smooth()

    ogs = []
    rnd_positions = [
        ((-0.9, 0.5, c.Z_CELL_WALL - 0.3), (-0.3, 0.15, THE1_ECTO_Z + 1.3)),
        ((0.8, -0.6, c.Z_CELL_WALL - 0.3), (0.35, -0.15, THE1_ECTO_Z + 1.1)),
        ((0.3, 0.9, c.Z_CELL_WALL - 0.4), (0.1, 0.35, THE1_ECTO_Z + 1.5)),
    ]
    for i, (start, end) in enumerate(rnd_positions):
        base = unit if i == 0 else c.duplicate_object(unit, f"OG_{i+1}")
        base.name = f"OG_{i+1}"
        offset = (i * 0.12, i * 0.08, i * 0.05)
        second = c.duplicate_object(base, f"OG_{i+1}_b")
        second.location = (offset[0], offset[1], offset[2] - 0.14)

        for obj in (base, second):
            obj.location = start
            obj.keyframe_insert(data_path="location", frame=DAMAGE_MOLECULES_START)
            target = (end[0] + (obj.location[0] - start[0]), end[1] + (obj.location[1] - start[1]), end[2])
            obj.location = target
            obj.keyframe_insert(data_path="location", frame=DAMAGE_MOLECULES_ARRIVE)
            c.add_brownian_jitter(obj, DAMAGE_MOLECULES_ARRIVE, seed=50 + i, amplitude_deg=25, cycles=2)
        ogs.append(base)
        ogs.append(second)
    return ogs


def create_phospho_spark():
    """Chispa de fosforilacion: tras activarse, THE1 dispara una senal desde
    su dominio quinasa (citoplasmico) hacia el resto del citosol -- el
    gancho visual hacia la cascada de calcio (escena 2)."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.09, location=(0, 0, THE1_KINASE_Z), segments=12, ring_count=8)
    spark = bpy.context.active_object
    spark.name = "ChispaFosforilacion"
    mat = c.make_material("Mat_Chispa", (0.95, 0.85, 0.3), roughness=0.2, emission_strength=0.0)
    spark.data.materials.append(mat)
    bpy.ops.object.shade_smooth()

    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    emission_input = bsdf.inputs["Emission Strength"]

    spark.scale = (0.001, 0.001, 0.001)
    spark.keyframe_insert(data_path="scale", frame=PHOSPHO_SPARK_START)
    emission_input.default_value = 0.0
    emission_input.keyframe_insert(data_path="default_value", frame=PHOSPHO_SPARK_START)

    spark.scale = (1.0, 1.0, 1.0)
    spark.keyframe_insert(data_path="scale", frame=PHOSPHO_SPARK_START + 5)
    emission_input.default_value = 4.0
    emission_input.keyframe_insert(data_path="default_value", frame=PHOSPHO_SPARK_START + 5)

    spark.location = (0, 0, THE1_KINASE_Z)
    spark.keyframe_insert(data_path="location", frame=PHOSPHO_SPARK_START + 5)
    spark.location = MCA1_LOCATION
    spark.keyframe_insert(data_path="location", frame=PHOSPHO_SPARK_END)

    spark.scale = (0.3, 0.3, 0.3)
    spark.keyframe_insert(data_path="scale", frame=PHOSPHO_SPARK_END)

    return spark


def create_mca1_partner(mn):
    """MCA1: canal de calcio mecanosensible. Segun Nakagawa et al. y Yamanaka
    et al. (JBC 2021; PLOS ONE 2014), MCA1 es una proteina de membrana de
    paso unico (N-term extracelular, C-term citoplasmico) que se ensambla en
    HOMOTETRAMEROS -- 4 copias en anillo con un poro central -- para formar
    el canal funcional. Se representa como 4 copias reales en anillo, no una
    proteina suelta, con un pulso de brillo compartido cuando llega la
    chispa de fosforilacion desde THE1."""
    materials = []
    objs = []
    ring_radius = 0.34
    for i in range(4):
        angle = math.radians(90 * i)
        mat = c.make_material(f"Mat_MCA1_{i+1}", (0.15, 0.6, 0.75), roughness=0.3, emission_strength=0.04, subsurface=0.35, use_cpk=True)
        mol = c.fetch_molecule(mn, c.UNIPROT_IDS["MCA1"], f"MCA1_{i+1}", mat)
        obj = mol.object
        obj.location = (
            MCA1_LOCATION[0] + math.cos(angle) * ring_radius,
            MCA1_LOCATION[1] + math.sin(angle) * ring_radius,
            MCA1_LOCATION[2],
        )
        obj.rotation_euler = (math.radians(8), math.radians(55), angle)
        obj.scale = (1.15, 1.15, 1.15)
        c.add_brownian_jitter(obj, TOTAL_FRAMES, seed=6 + i, amplitude_deg=3, cycles=2)
        materials.append(mat)
        objs.append(obj)

    for mat in materials:
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        emission_input = bsdf.inputs["Emission Strength"]
        emission_input.default_value = 0.04
        emission_input.keyframe_insert(data_path="default_value", frame=PHOSPHO_SPARK_END - 4)
        emission_input.default_value = 0.7
        emission_input.keyframe_insert(data_path="default_value", frame=PHOSPHO_SPARK_END + 3)
        emission_input.default_value = 0.2
        emission_input.keyframe_insert(
            data_path="default_value", frame=min(TOTAL_FRAMES, PHOSPHO_SPARK_END + int(c.FPS * 0.4))
        )

    return objs


def create_the1(mn):
    """THE1 es una quinasa receptora transmembrana: ectodominio extracelular
    (hacia la pared), una helice transmembrana, y el dominio quinasa
    citoplasmatico (hacia el citosol, el que responde al dano). Dos tonos
    (ectodominio vs quinasa) para dar textura/variacion en vez de un bloque
    de un solo color uniforme."""
    base_mat = c.make_material("Mat_THE1_ecto", (0.65, 0.32, 0.1), roughness=0.35, emission_strength=0.0, subsurface=0.3, use_cpk=True)
    kinase_mat = c.make_material("Mat_THE1_kinasa", (0.95, 0.45, 0.1), roughness=0.25, emission_strength=0.0, subsurface=0.4, use_cpk=True)
    mol = c.fetch_molecule_dual_color(mn, c.UNIPROT_IDS["THE1"], "THE1", base_mat, kinase_mat, highlight_res_start=600)
    obj = mol.object
    obj.location = (0, 0, c.Z_PLASMA_MEMBRANE - 0.2)
    obj.rotation_euler = (math.radians(15), math.radians(5), math.radians(20))
    obj.scale = (2.3, 2.3, 2.3)

    c.add_brownian_jitter(obj, TOTAL_FRAMES, seed=1, amplitude_deg=4, cycles=3)

    for mat in (base_mat, kinase_mat):
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        emission_input = bsdf.inputs["Emission Strength"]
        emission_input.default_value = 0.0
        emission_input.keyframe_insert(data_path="default_value", frame=THE1_ACTIVATION_START)

    kinase_bsdf = next(n for n in kinase_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    kinase_bsdf.inputs["Emission Strength"].default_value = 0.12
    kinase_bsdf.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=THE1_ACTIVATION_END)

    return obj


def create_camera_and_lights():
    """Lente larga (teleobjetivo) + camara mas lejos: comprime la profundidad
    para que todo quede a una distancia focal parecida (sin fondo
    desenfocado en globos gigantes) -- un plano 'lleno' pero controlado,
    mas facil de iluminar de forma uniforme y mas barato de renderizar."""
    bpy.ops.object.camera_add(location=(1.2, -16, 3.0), rotation=(math.radians(85.5), 0, math.radians(4)))
    camera = bpy.context.active_object
    camera.name = "Camara"
    camera.data.lens = 65
    bpy.context.scene.camera = camera

    camera.data.dof.use_dof = True
    camera.data.dof.aperture_fstop = 5.6
    camera.data.dof.focus_distance = 16.0

    camera.location = (1.2, -16, 3.0)
    camera.keyframe_insert(data_path="location", frame=1)
    camera.location = (0.4, -13.5, 2.85)
    camera.keyframe_insert(data_path="location", frame=TOTAL_FRAMES)

    c.add_wehi_lighting(key_loc=(2.6, -10, 5.5), target=(0, 0, 2.8), key_energy=1400, key_size=7.5)

    return camera


def build_scene(engine="EEVEE"):
    c.clear_scene()
    c.setup_world_blue_glow()
    mn = c.enable_molecular_nodes()

    cutter = c.create_cell_wall_damage_cutter(WALL_DAMAGE_START, WALL_DAMAGE_END)
    c.create_cellulose_fibrils(
        center=(0, 0, c.Z_CELL_WALL), size=9, hole_exclude_radius=2.6,
        count_fibrils=16, seed=11,
    )
    c.create_wall_crosslinkers(center=(0, 0, c.Z_CELL_WALL), size=9, count=16, seed=17)
    wall = c.create_cell_wall(cutter)

    membrane = c.create_plasma_membrane(size=7, dome_radius=0, thickness=0.26)
    membrane.hide_render = True
    c.add_lipid_bilayer(
        membrane, count=3200, seed=21,
        head_color=(0.85, 0.55, 0.15), tail_color=(0.9, 0.65, 0.25),
    )

    create_the1(mn)
    create_damage_molecules()
    create_mca1_partner(mn)
    create_phospho_spark()

    create_camera_and_lights()
    c.setup_render_settings(TOTAL_FRAMES, "escena1_pared_celular", engine=engine)
    bpy.context.scene.frame_set(1)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    engine = "CYCLES" if "--engine-cycles" in args else "EEVEE"
    build_scene(engine=engine)
    if "--render-still" in args:
        frame_arg = int(c.FPS * 3.0)
        if len(args) > 1 and args[-1].isdigit():
            frame_arg = int(args[-1])
        if "--workbench" in args:
            bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        c.render_still(frame_arg, "escena1_preview.png")
    elif "--render" in args:
        c.render_animation("escena1_pared_celular.mp4")
    elif "--render-frames" in args:
        i = args.index("--render-frames")
        start, end = int(args[i + 1]), int(args[i + 2])
        c.render_frame_range(start, end, "escena1")
    elif "--encode" in args:
        c.encode_png_sequence("escena1", 1, TOTAL_FRAMES, c.FPS, "escena1_pared_celular.mp4")
