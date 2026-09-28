"""Utilidades compartidas por las 3 escenas de autofagia no canonica (VQC).
Ver tonoplast_scene.py (version anterior, plano general) para el modelo biologico completo.
"""

import os
import math
import random
import bpy
from mathutils import Vector, Quaternion

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")

MN_ASSETS_PATH = os.path.join(
    PROJECT_DIR, "reference-repos", "MolecularNodes", "molecularnodes", "assets", "node_data_file.blend"
)

FPS = 24

Z_CELL_WALL = 4.3
Z_PLASMA_MEMBRANE = 3.0
Z_TONOPLAST = 0.0
Z_VACUOLE_CENTER = -7.0

NUCLEUS_LOCATION = (4.3, -3.2, 1.4)
NUCLEUS_RADIUS = 1.1

UNIPROT_IDS = {
    "THE1": "Q9LK35",
    "ZAC": "Q9FVJ3",
    "ATG16": "Q6NNP0",
    "ATG8A": "Q8LEM4",
    "TCH3": "P25071",
    "MCA1": "Q8L7E9",
    "VHA_H": "Q9LX65",
}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_collection in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.worlds):
        for block in list(block_collection):
            if block.users == 0:
                block_collection.remove(block)


def enable_molecular_nodes():
    bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.molecularnodes")
    import bl_ext.blender_org.molecularnodes as mn
    return mn


def make_material(name, base_color, roughness=0.4, transmission=0.0, emission_strength=0.0, subsurface=0.0, use_cpk=False):
    """use_cpk=True lee el atributo 'Color' que genera el esquema de color
    'common' (CPK por elemento: rojo=O, azul=N...) de Molecular Nodes y lo
    mezcla (multiply) con base_color -- asi la proteina mantiene su tinte
    identificativo (THE1 naranja, MCA1 teal...) pero con toda la variacion
    de detalle real del CPK, en vez de un tono plano sin textura."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = roughness

    if use_cpk:
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        attr = nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Color"
        attr.attribute_type = "GEOMETRY"
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        mix_a = next(s for s in mix.inputs if s.name == "A" and s.type == "RGBA")
        mix_b = next(s for s in mix.inputs if s.name == "B" and s.type == "RGBA")
        mix_result = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
        mix_b.default_value = (*base_color, 1.0)
        links.new(attr.outputs["Color"], mix_a)
        links.new(mix_result, bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    if subsurface > 0:
        if "Subsurface Weight" in bsdf.inputs:
            bsdf.inputs["Subsurface Weight"].default_value = subsurface
            bsdf.inputs["Subsurface Radius"].default_value = (0.5, 0.25, 0.15)
        elif "Subsurface" in bsdf.inputs:
            bsdf.inputs["Subsurface"].default_value = subsurface
    if emission_strength > 0:
        bsdf.inputs["Emission Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


_mn_official_materials = {}


def get_mn_material(mat_name="MN Ambient Occlusion"):
    """Carga (una sola vez por sesion) los materiales oficiales que trae
    Molecular Nodes en su archivo de assets -- disenados por el propio
    creador del addon para este uso exacto, con mucho mejor acabado que
    un Principled BSDF hecho a mano. Repo: BradyAJohnston/MolecularNodes."""
    if mat_name in _mn_official_materials:
        return _mn_official_materials[mat_name]
    if mat_name not in bpy.data.materials:
        with bpy.data.libraries.load(MN_ASSETS_PATH, link=False) as (data_from, data_to):
            if mat_name in data_from.materials:
                data_to.materials = [mat_name]
    mat = bpy.data.materials.get(mat_name)
    _mn_official_materials[mat_name] = mat
    return mat


def fetch_molecule(mn, code, name, material=None, tint=None):
    """Estilo 'spheres' (esferas atomicas tipo van der Waals/CPK). Usa
    color='common' (coloreado CPK por elemento: rojo=O, azul=N, etc.) sobre
    el material oficial 'MN Ambient Occlusion' -- eso da toda la variacion
    visual/textura que un material de un solo tono plano no puede dar. Si
    se pasa 'tint', se aplica como una luz de acento de ese color cerca de
    la molecula en vez de recolorearla entera (para no tapar el CPK)."""
    mol = mn.Molecule.fetch(code, format="cif", database="alphafold", centre="centroid")
    mol.object.name = name
    mn_material = material if material is not None else get_mn_material()
    mol.add_style("spheres", material=mn_material, color="common")
    return mol


def fetch_molecule_dual_color(mn, code, name, base_material, highlight_material, highlight_res_start):
    """Trae una estructura real y la colorea en dos tonos: el dominio desde
    'highlight_res_start' hasta el final (p.ej. el dominio quinasa citoplasmatico
    de THE1) resaltado, el resto con el material base. Los limites de dominio
    son una aproximacion (THE1 es un RLK tipo I: ectodominio N-terminal,
    quinasa C-terminal), suficiente para comunicar la idea sin resolucion atomica."""
    mol = mn.Molecule.fetch(code, format="cif", database="alphafold", centre="centroid")
    mol.object.name = name
    max_res = int(mol.array.res_id.max())

    mol.add_style("spheres", material=base_material, color="common")
    highlight_ids = list(range(highlight_res_start, max_res + 1))
    mol.select.reset()
    mol.add_style(
        "spheres",
        material=highlight_material,
        color="common",
        selection=mol.select.res_id(highlight_ids),
        name="dominio_resaltado",
    )
    return mol


def duplicate_object(source_obj, new_name):
    bpy.ops.object.select_all(action="DESELECT")
    source_obj.select_set(True)
    bpy.context.view_layer.objects.active = source_obj
    bpy.ops.object.duplicate(linked=True)
    dup = bpy.context.active_object
    dup.name = new_name
    return dup


def add_brownian_jitter(obj, total_frames, seed, amplitude_deg=12, cycles=2):
    """Rotacion continua sutil tipo 'movimiento browniano' para que las
    moleculas no se vean congeladas cuando no se estan desplazando."""
    rnd = random.Random(seed)
    axis_order = rnd.choice(["XYZ", "XZY", "YXZ", "ZXY"])
    obj.rotation_mode = axis_order
    base = obj.rotation_euler.copy()
    steps = max(cycles * 4, 4)
    for step in range(steps + 1):
        frame = int(1 + (total_frames - 1) * step / steps)
        wob = math.radians(amplitude_deg) * math.sin(step * math.pi / 2 + seed)
        obj.rotation_euler = (
            base[0] + wob * rnd.uniform(0.5, 1.0),
            base[1] + wob * rnd.uniform(0.5, 1.0),
            base[2] + wob * rnd.uniform(0.5, 1.0),
        )
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def create_crowding_proteins(bounds, count, seed, total_frames, base_color=(0.32, 0.36, 0.46), name_prefix="Fondo"):
    """Relleno de 'molecular crowding': decenas de blobs organicos genericos
    en movimiento browniano constante, para que el citosol se vea denso y
    vivo en vez de vacio con 2-3 moleculas aisladas flotando. Son formas
    procedurales simples (no estructuras reales) por coste de computo, con
    color apagado para no competir visualmente con las proteinas protagonistas."""
    rnd = random.Random(seed)
    blobs = []
    for i in range(count):
        pos = (
            rnd.uniform(*bounds[0]),
            rnd.uniform(*bounds[1]),
            rnd.uniform(*bounds[2]),
        )
        radius = rnd.uniform(0.1, 0.3)
        bpy.ops.mesh.primitive_ico_sphere_add(radius=radius, location=pos, subdivisions=2)
        blob = bpy.context.active_object
        blob.name = f"{name_prefix}_{i+1}"
        blob.scale = (rnd.uniform(0.7, 1.4), rnd.uniform(0.7, 1.4), rnd.uniform(0.7, 1.4))

        displace = blob.modifiers.new("Bulto", "DISPLACE")
        tex = bpy.data.textures.new(f"{name_prefix}Noise{i}", type="CLOUDS")
        tex.noise_scale = rnd.uniform(0.4, 0.8)
        displace.texture = tex
        displace.strength = 0.14

        color = tuple(max(0.05, min(0.95, ch + rnd.uniform(-0.05, 0.05))) for ch in base_color)
        mat = make_material(f"Mat_{name_prefix}_{i+1}", color, roughness=0.55, subsurface=0.2)
        blob.data.materials.append(mat)
        bpy.ops.object.shade_smooth()

        add_brownian_jitter(blob, total_frames, seed=seed * 137 + i, amplitude_deg=18, cycles=rnd.randint(1, 3))

        drift = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(-0.25, 0.25))
        blob.keyframe_insert(data_path="location", frame=1)
        blob.location = (pos[0] + drift[0], pos[1] + drift[1], pos[2] + drift[2])
        blob.keyframe_insert(data_path="location", frame=total_frames)

        blobs.append(blob)
    return blobs


def create_background_dust(center, radius, count=250, seed=99, color=(0.5, 0.7, 1.0)):
    """Polvo/bokeh atmosferico: puntitos brillantes dispersos en un volumen
    detras del sujeto principal, para dar sensacion de profundidad y
    atmosfera en vez de un fondo vacio -- como en las referencias con
    fondo azul lleno de particulas desenfocadas."""
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.02, subdivisions=2)
    dot = bpy.context.active_object
    dot.data.materials.append(
        make_material("Mat_Polvo", color, roughness=0.3, emission_strength=5.0)
    )
    bpy.ops.object.shade_smooth()
    dot.hide_render = True
    dot.hide_viewport = True

    coll = bpy.data.collections.new("PolvoAtmosferico")
    bpy.context.scene.collection.children.link(coll)

    rnd = random.Random(seed)
    dust = []
    for i in range(count):
        theta = rnd.uniform(0, math.tau)
        phi = rnd.uniform(0, math.pi)
        r = radius * rnd.uniform(0.3, 1.0)
        pos = (
            center[0] + r * math.sin(phi) * math.cos(theta),
            center[1] + r * math.sin(phi) * math.sin(theta),
            center[2] + r * math.cos(phi),
        )
        dup = bpy.data.objects.new(f"Polvo_{i}", dot.data)
        coll.objects.link(dup)
        dup.location = pos
        s = rnd.uniform(0.5, 2.2)
        dup.scale = (s, s, s)
        dust.append(dup)
    return dust


def create_vacuole():
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=6, location=(0, 0, Z_VACUOLE_CENTER), segments=48, ring_count=24
    )
    vacuole = bpy.context.active_object
    vacuole.name = "Vacuola"
    vacuole.data.materials.append(
        make_material("Mat_Vacuola", (0.5, 0.3, 0.85), roughness=0.1, transmission=0.65, subsurface=0.3)
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
    tex.noise_scale = 0.09
    displace_mod.texture = tex
    displace_mod.strength = 0.16
    displace_mod.mid_level = 0.5

    solidify_mod = membrane.modifiers.new("Grosor", "SOLIDIFY")
    solidify_mod.thickness = 0.25

    membrane.data.materials.append(
        make_material("Mat_Tonoplasto", (0.32, 0.13, 0.58), roughness=0.22, transmission=0.25, subsurface=0.3)
    )
    bpy.ops.object.shade_smooth()
    return membrane


def create_cell_wall_damage_cutter(start_frame, end_frame):
    """Cilindro (corte recto, de lado a lado de la pared) con ruido radial
    para que el borde del agujero sea organico/irregular en vez de un
    circulo perfecto de sacabocados."""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=1.0, depth=3.0, location=(0, 0, Z_CELL_WALL), vertices=64
    )
    cutter = bpy.context.active_object
    cutter.name = "CorteDanoParedCelular"
    cutter.hide_render = True
    cutter.hide_viewport = True

    displace_mod = cutter.modifiers.new("Irregularidad", "DISPLACE")
    tex = bpy.data.textures.new("DanoNoise", type="CLOUDS")
    tex.noise_scale = 0.3
    displace_mod.texture = tex
    displace_mod.strength = 0.25
    displace_mod.direction = "RGB_TO_XYZ"

    cutter.scale = (0.001, 0.001, 1.0)
    cutter.keyframe_insert(data_path="scale", frame=start_frame)

    cutter.scale = (2.3, 2.3, 1.0)
    cutter.keyframe_insert(data_path="scale", frame=end_frame)

    return cutter


def create_cellulose_fibrils(center, size, hole_exclude_radius, count_fibrils=22, seed=11):
    """Microfibrillas de celulosa: varillas cilindricas largas y gruesas
    (tostado/beige, como en los diagramas de anatomia de pared celular),
    entrecruzadas en 2 capas perpendiculares -- no anillos de glucosa
    sueltos, que se veian como una masa de ruido verde."""
    mat = make_material("Mat_Celulosa", (0.82, 0.68, 0.4), roughness=0.5, subsurface=0.1)

    rnd = random.Random(seed)
    fibrils = []
    half = size / 2

    for f in range(count_fibrils):
        axis = "X" if f % 2 == 0 else "Y"
        cross = rnd.uniform(-half * 0.9, half * 0.9)
        z_base = center[2] + (0.16 if f % 2 == 0 else -0.16) + rnd.uniform(-0.02, 0.02)
        length = size * rnd.uniform(0.88, 0.98)

        bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=length, vertices=10)
        rod = bpy.context.active_object
        rod.name = f"Celulosa_{f}"
        rod.data.materials.append(mat)

        bend = rod.modifiers.new("Ondulacion", "SIMPLE_DEFORM")
        bend.deform_method = "BEND"
        bend.angle = math.radians(rnd.uniform(-6, 6))

        rod.rotation_euler = (0, math.radians(90), 0)
        if axis == "X":
            rod.location = (center[0], center[1] + cross, z_base)
        else:
            rod.rotation_euler = (0, math.radians(90), math.radians(90))
            rod.location = (center[0] + cross, center[1], z_base)

        bpy.ops.object.shade_smooth()
        fibrils.append(rod)

    return fibrils


def create_wall_crosslinkers(center, size, count=14, seed=17, color=(0.35, 0.55, 0.7)):
    """Hemicelulosa/pectina: hebras finas y onduladas que cruzan por encima
    de las microfibrillas de celulosa, uniendolas -- el 'tejido' visible en
    los diagramas de pared celular, en vez de dejar las varillas sueltas."""
    curve_data = bpy.data.curves.new("Hebra", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = 0.012
    curve_data.bevel_resolution = 2

    mat = make_material("Mat_Hemicelulosa", color, roughness=0.4, subsurface=0.15)

    rnd = random.Random(seed)
    half = size / 2
    strands = []
    for i in range(count):
        spline = curve_data.splines.new("NURBS")
        angle = rnd.uniform(0, math.pi)
        offset = rnd.uniform(-half * 0.8, half * 0.8)
        n_pts = 8
        spline.points.add(n_pts - 1)
        for p in range(n_pts):
            t = p / (n_pts - 1)
            along = (t - 0.5) * size * 0.95
            wobble = math.sin(t * math.pi * rnd.uniform(2, 4) + i) * rnd.uniform(0.15, 0.3)
            x = math.cos(angle) * along - math.sin(angle) * offset + wobble * math.sin(angle)
            y = math.sin(angle) * along + math.cos(angle) * offset + wobble * math.cos(angle)
            z = center[2] + rnd.uniform(-0.22, 0.22)
            spline.points[p].co = (center[0] + x, center[1] + y, z, 1)

    obj = bpy.data.objects.new("Hemicelulosa", curve_data)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    strands.append(obj)
    return strands


def create_cell_wall(cutter):
    """Lamina media: capa fina y translucida (tipo vidrio esmerilado) que se
    apoya SOBRE las microfibrillas de celulosa (create_cellulose_fibrils),
    no un bloque opaco verde que sustituye a toda la pared."""
    bpy.ops.mesh.primitive_grid_add(
        size=14, x_subdivisions=48, y_subdivisions=48, location=(0, 0, Z_CELL_WALL + 0.32)
    )
    wall = bpy.context.active_object
    wall.name = "LaminaMedia"

    displace_mod = wall.modifiers.new("Fibras", "DISPLACE")
    tex = bpy.data.textures.new("ParedCelularNoise", type="CLOUDS")
    tex.noise_scale = 0.1
    displace_mod.texture = tex
    displace_mod.strength = 0.06

    boolean_mod = wall.modifiers.new("Dano", "BOOLEAN")
    boolean_mod.operation = "DIFFERENCE"
    boolean_mod.object = cutter

    solidify_mod = wall.modifiers.new("Grosor", "SOLIDIFY")
    solidify_mod.thickness = 0.05

    wall.data.materials.append(
        make_material("Mat_ParedCelular", (0.5, 0.75, 0.55), roughness=0.25, transmission=0.65, subsurface=0.1)
    )
    bpy.ops.object.shade_smooth()
    return wall


def add_lipid_bilayer(membrane_obj, count=900, seed=7, head_color=(0.35, 0.55, 0.85), tail_color=(0.3, 0.45, 0.8)):
    """Puebla ambas caras de una membrana solidificada con fosfolipidos
    individuales, orientados exactamente a la normal de cada cara. Colas
    MUY finas y densas (aspecto 'flequillo'/pelo, no palitos gruesos) y
    color casi monocromatico cabeza/cola para que lea como una capa
    continua de fibras, no bolitas con palillos sueltos."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, location=(0, 0, 0.02), segments=7, ring_count=5)
    head = bpy.context.active_object
    head.data.materials.append(make_material("Mat_LipidoCabeza", head_color, roughness=0.25, subsurface=0.35))

    tails = []
    for dx in (-0.012, 0.012):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=0.13, location=(dx, 0, -0.045), vertices=5)
        tail = bpy.context.active_object
        tail.data.materials.append(make_material("Mat_LipidoCola", tail_color, roughness=0.4))
        tails.append(tail)

    bpy.ops.object.select_all(action="DESELECT")
    head.select_set(True)
    for t in tails:
        t.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.join()
    lipid = bpy.context.active_object
    lipid.name = f"{membrane_obj.name}_Fosfolipido"
    lipid.hide_render = True
    lipid.hide_viewport = True

    depsgraph = bpy.context.evaluated_depsgraph_get()
    membrane_eval = membrane_obj.evaluated_get(depsgraph)
    mesh_eval = membrane_eval.to_mesh()
    mesh_eval.calc_loop_triangles()

    flat_faces = [p for p in mesh_eval.polygons if abs(p.normal.z) > 0.5]
    rnd = random.Random(seed)
    rnd.shuffle(flat_faces)
    n = min(count, len(flat_faces))

    coll = bpy.data.collections.new(f"{membrane_obj.name}_Bicapa")
    bpy.context.scene.collection.children.link(coll)

    lipids = []
    for i, poly in enumerate(flat_faces[:n]):
        center = membrane_obj.matrix_world @ poly.center
        normal = (membrane_obj.matrix_world.to_3x3() @ poly.normal).normalized()

        dup = bpy.data.objects.new(f"{membrane_obj.name}_Lipido_{i}", lipid.data)
        coll.objects.link(dup)
        jitter = Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), rnd.uniform(-0.015, 0.015)))
        dup.location = center + jitter

        up = Vector((0, 0, 1))
        quat = up.rotation_difference(normal)
        spin = Quaternion(normal, rnd.uniform(0, 2 * math.pi))
        tilt_axis = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized()
        tilt = Quaternion(tilt_axis, math.radians(rnd.uniform(0, 22)))
        quat = tilt @ quat
        dup.rotation_mode = "QUATERNION"
        dup.rotation_quaternion = spin @ quat

        s = rnd.uniform(0.65, 1.35)
        dup.scale = (s, s, s)
        lipids.append(dup)

    membrane_eval.to_mesh_clear()
    return lipids


def create_plasma_membrane(size=14, dome_radius=0, thickness=0.15):
    """dome_radius > 0 curva la membrana como un trozo de superficie celular
    real (domo), envolviendola sobre una esfera grande invisible con
    Shrinkwrap -- Simple Deform Bend NO sirve aqui: solo curva dentro del
    propio plano XY de una malla plana, nunca la abomba en Z."""
    bpy.ops.mesh.primitive_grid_add(
        size=size, x_subdivisions=48, y_subdivisions=48, location=(0, 0, Z_PLASMA_MEMBRANE)
    )
    membrane = bpy.context.active_object
    membrane.name = "MembranaPlasmatica"

    if dome_radius > 0:
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=dome_radius, location=(0, 0, Z_PLASMA_MEMBRANE - dome_radius), segments=64, ring_count=32
        )
        sphere = bpy.context.active_object
        sphere.name = "MembranaEsferaGuia"
        sphere.hide_render = True
        sphere.hide_viewport = True
        bpy.context.view_layer.objects.active = membrane
        wrap_mod = membrane.modifiers.new("Domo", "SHRINKWRAP")
        wrap_mod.wrap_method = "NEAREST_SURFACEPOINT"
        wrap_mod.target = sphere

    displace_mod = membrane.modifiers.new("Ondulacion", "DISPLACE")
    tex = bpy.data.textures.new("MembranaPMNoise", type="CLOUDS")
    tex.noise_scale = 0.15
    displace_mod.texture = tex
    displace_mod.strength = 0.08

    solidify_mod = membrane.modifiers.new("Grosor", "SOLIDIFY")
    solidify_mod.thickness = thickness

    membrane.data.materials.append(
        make_material("Mat_MembranaPM", (0.85, 0.55, 0.5), roughness=0.35, transmission=0.2, subsurface=0.25)
    )
    bpy.ops.object.shade_smooth()
    return membrane


def create_nucleus():
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=NUCLEUS_RADIUS, location=NUCLEUS_LOCATION, segments=32, ring_count=16
    )
    nucleus = bpy.context.active_object
    nucleus.name = "Nucleo"
    nucleus.data.materials.append(
        make_material("Mat_Nucleo", (0.45, 0.4, 0.75), roughness=0.15, transmission=0.45)
    )
    bpy.ops.object.shade_smooth()
    return nucleus


def setup_world_dark():
    """Fondo oscuro tipo estudio (en vez de gris plano) para que las
    moleculas iluminadas resalten, al estilo WEHI/HHMI."""
    world = bpy.data.worlds.new("Mundo")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    bg = nodes["Background"]

    gradient = nodes.new("ShaderNodeTexGradient")
    gradient.gradient_type = "SPHERICAL"
    color_ramp = nodes.new("ShaderNodeValToRGB")
    color_ramp.color_ramp.elements[0].color = (0.004, 0.006, 0.014, 1.0)
    color_ramp.color_ramp.elements[1].color = (0.03, 0.035, 0.055, 1.0)

    coord = nodes.new("ShaderNodeTexCoord")
    links.new(coord.outputs["Generated"], gradient.inputs["Vector"])
    links.new(gradient.outputs["Color"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    return world


def setup_world_blue_glow():
    """Fondo azul atmosferico con resplandor radial (en vez de negro plano)
    -- el aire se ve 'lleno' de luz azulada, como en las referencias con
    fondo de nebulosa/profundidad, no vacio."""
    world = bpy.data.worlds.new("MundoAzul")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    bg = nodes["Background"]

    gradient = nodes.new("ShaderNodeTexGradient")
    gradient.gradient_type = "SPHERICAL"
    color_ramp = nodes.new("ShaderNodeValToRGB")
    color_ramp.color_ramp.elements[0].color = (0.015, 0.035, 0.11, 1.0)
    color_ramp.color_ramp.elements[1].color = (0.002, 0.004, 0.016, 1.0)

    coord = nodes.new("ShaderNodeTexCoord")
    links.new(coord.outputs["Generated"], gradient.inputs["Vector"])
    links.new(gradient.outputs["Color"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    return world


def setup_render_settings(total_frames, filename_prefix, engine="EEVEE", cycles_samples=128):
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = FPS
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100

    if engine == "CYCLES":
        scene.render.engine = "CYCLES"
        scene.cycles.samples = cycles_samples
        scene.cycles.use_denoising = True
        scene.cycles.device = "CPU"
    else:
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.use_raytracing = True
        scene.eevee.taa_render_samples = 96
        scene.eevee.use_shadows = True

    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.4

    scene.render.filepath = os.path.join(OUTPUT_DIR, filename_prefix + "_")
    scene.render.image_settings.file_format = "PNG"

    setup_compositor()


def setup_compositor():
    """Posproduccion (glow/bloom + gradacion de color) directamente en el
    compositor nativo de Blender -- el paso que separa un render en bruto
    de algo con acabado de divulgacion cientifica profesional."""
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.compositing_node_group
    if tree is None:
        tree = bpy.data.node_groups.new("Compositing Nodetree", "CompositorNodeTree")
        scene.compositing_node_group = tree
    tree.nodes.clear()

    render_layers = tree.nodes.new("CompositorNodeRLayers")

    glare = tree.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Fog Glow"
    glare.inputs["Quality"].default_value = "Medium"
    glare.inputs["Threshold"].default_value = 0.75
    glare.inputs["Size"].default_value = 7
    glare.inputs["Strength"].default_value = 0.6

    color_balance = tree.nodes.new("CompositorNodeColorBalance")
    color_balance.inputs["Type"].default_value = "Lift/Gamma/Gain"
    # inputs con nombre repetido (VALUE + RGBA): el RGBA es el segundo de cada par
    color_balance.inputs[4].default_value = (0.99, 0.99, 1.01, 1.0)  # Lift RGBA
    color_balance.inputs[6].default_value = (1.02, 1.0, 1.0, 1.0)    # Gamma RGBA
    color_balance.inputs[8].default_value = (1.05, 1.03, 1.0, 1.0)   # Gain RGBA

    contrast = tree.nodes.new("CompositorNodeBrightContrast")
    contrast.inputs["Brightness"].default_value = 2
    contrast.inputs["Contrast"].default_value = 14

    vignette_ramp = tree.nodes.new("CompositorNodeEllipseMask")
    vignette_ramp.inputs["Position"].default_value = (0.5, 0.5)
    vignette_ramp.inputs["Size"].default_value = (1.15, 1.15)
    vignette_blur = tree.nodes.new("CompositorNodeBlur")
    vignette_blur.inputs["Size"].default_value = (200, 200)
    vignette_mix = tree.nodes.new("ShaderNodeMix")
    vignette_mix.data_type = "RGBA"
    vignette_mix.blend_type = "MULTIPLY"
    vignette_mix.inputs[0].default_value = 0.35  # Factor (VALUE)
    mix_a = next(s for s in vignette_mix.inputs if s.name == "A" and s.type == "RGBA")
    mix_b = next(s for s in vignette_mix.inputs if s.name == "B" and s.type == "RGBA")
    mix_result = next(o for o in vignette_mix.outputs if o.name == "Result" and o.type == "RGBA")

    if not any(i.name == "Image" and i.in_out == "OUTPUT" for i in tree.interface.items_tree):
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    composite = tree.nodes.new("NodeGroupOutput")

    links = tree.links
    links.new(render_layers.outputs["Image"], glare.inputs["Image"])
    links.new(glare.outputs["Image"], color_balance.inputs["Image"])
    links.new(color_balance.outputs["Image"], contrast.inputs["Image"])
    links.new(vignette_ramp.outputs["Mask"], vignette_blur.inputs["Image"])
    links.new(contrast.outputs["Image"], mix_a)
    links.new(vignette_blur.outputs["Image"], mix_b)
    links.new(mix_result, composite.inputs["Image"])


def render_still(frame, filename):
    scene = bpy.context.scene
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(OUTPUT_DIR, filename)
    bpy.ops.render.render(write_still=True)


def render_frame_range(start, end, prefix):
    """Renderiza un rango de frames a PNG numerados (no video), para poder
    trocear un render largo en llamadas que quepan en una sola invocacion
    de Blender. Se juntan en video al final con encode_png_sequence()."""
    scene = bpy.context.scene
    scene.frame_start = start
    scene.frame_end = end
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(OUTPUT_DIR, f"{prefix}_frame_")
    bpy.ops.render.render(animation=True)


def encode_png_sequence(prefix, frame_start, frame_end, fps, output_filename):
    """Junta una secuencia de PNG ya renderizados en un mp4, usando el editor
    de secuencias de video de Blender (solo codifica, no vuelve a renderizar
    la escena 3D, asi que es rapido)."""
    scene = bpy.data.scenes.new("EncodeScene")
    bpy.context.window.scene = scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = fps

    scene.sequence_editor_create()
    seq = scene.sequence_editor
    first_frame_path = os.path.join(OUTPUT_DIR, f"{prefix}_frame_{frame_start:04d}.png")
    strip = seq.strips.new_image(
        name="frames", filepath=first_frame_path, channel=1, frame_start=frame_start
    )
    for f in range(frame_start + 1, frame_end + 1):
        strip.elements.append(f"{prefix}_frame_{f:04d}.png")

    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.filepath = os.path.join(OUTPUT_DIR, output_filename)
    bpy.ops.render.render(animation=True, scene=scene.name)


def render_animation(filename):
    scene = bpy.context.scene
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.filepath = os.path.join(OUTPUT_DIR, filename)
    bpy.ops.render.render(animation=True)


def add_wehi_lighting(key_loc, target, key_energy=400, key_size=2.5):
    """Iluminacion tipo WEHI/Drew Berry: UNA luz principal fuerte y calida que
    define volumen claro (highlight marcado + sombra oscura por esfera),
    relleno minimo (8% de la principal, no un segundo flood que lo empape
    todo) y un contorno frio sutil para separar del fondo negro. La relacion
    de intensidades importa mas que los valores absolutos."""
    key_dir = Vector(target) - Vector(key_loc)

    bpy.ops.object.light_add(type="AREA", location=key_loc)
    key = bpy.context.active_object
    key.name = "LuzPrincipal"
    key.data.energy = key_energy
    key.data.size = key_size
    key.data.color = (1.0, 0.93, 0.8)
    key.rotation_euler = key_dir.to_track_quat("-Z", "Y").to_euler()

    fill_loc = (-key_loc[0] * 0.5, key_loc[1] * 0.3, key_loc[2] * 0.15)
    bpy.ops.object.light_add(type="AREA", location=fill_loc)
    fill = bpy.context.active_object
    fill.name = "LuzRelleno"
    fill.data.energy = key_energy * 0.08
    fill.data.size = key_size * 2
    fill.data.color = (0.55, 0.68, 1.0)
    fill.rotation_euler = (Vector(target) - Vector(fill_loc)).to_track_quat("-Z", "Y").to_euler()

    rim_loc = (target[0] * 0.3, target[1] - (key_loc[1] - target[1]), target[2] + 2.5)
    bpy.ops.object.light_add(type="AREA", location=rim_loc)
    rim = bpy.context.active_object
    rim.name = "LuzContorno"
    rim.data.energy = key_energy * 0.18
    rim.data.size = key_size
    rim.data.color = (0.6, 0.8, 1.0)
    rim.rotation_euler = (Vector(target) - Vector(rim_loc)).to_track_quat("-Z", "Y").to_euler()

    return key, fill, rim
