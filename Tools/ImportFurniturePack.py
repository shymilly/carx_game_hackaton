"""Import the complete Quaternius pack without changing the apartment's furniture."""
import hashlib
from pathlib import Path
import re
import sys

import unreal as ue

sys.path.insert(0, str(Path(__file__).parent))
from ApartmentFinishes import texture_asset
from ApartmentScene import make_material
from ImportFurniture import ASSETS, PROJECT, ROOT, SOURCE


PACK = ROOT + "/Pack"
STAGING = PROJECT / "Saved" / "FurniturePackImport"
LIB = ue.MaterialEditingLibrary
PROPERTIES = ue.MaterialProperty


def prepare_obj(source):
    """Put the Y-up source on Z, leave the floor at zero and supply missing UVs."""
    lines = source.read_text(encoding="utf-8").splitlines()
    vertices = [tuple(map(float, line.split()[1:4])) for line in lines if line.startswith("v ")]
    normals = [tuple(map(float, line.split()[1:4])) for line in lines if line.startswith("vn ")]
    uv_count = sum(line.startswith("vt ") for line in lines)
    bottom = min(y for _, y, _ in vertices)
    scale = 50
    output = [f"mtllib {source.stem}.mtl", f"o {source.stem}"]
    output.extend(f"v {x * scale:.7f} {z * scale:.7f} {(y - bottom) * scale:.7f}" for x, y, z in vertices)
    output.extend(f"vn {x:.7f} {z:.7f} {y:.7f}" for x, y, z in normals)
    output.extend(line for line in lines if line.startswith("vt "))
    faces = []
    projections = {}
    for line in lines:
        if line.startswith("usemtl "):
            faces.append(line)
        elif line.startswith("f "):
            corners = [corner.split("/") for corner in line.split()[1:]]
            normal = normals[int(corners[0][2]) - 1]
            omitted = max(range(3), key=lambda axis: abs(normal[axis]))
            for corner in corners:
                vertex, uv, _ = corner
                if uv:
                    continue
                key = (int(vertex) - 1, omitted)
                if key not in projections:
                    u, v = (value for axis, value in enumerate(vertices[key[0]]) if axis != omitted)
                    output.append(f"vt {u * .5:.7f} {v * .5:.7f}")
                    projections[key] = uv_count + len(projections) + 1
                corner[1] = str(projections[key])
            # The OBJ translator reflects Y. Reverse the corners to preserve outward faces.
            faces.append("f " + " ".join("/".join(corner) for corner in reversed(corners)))
    STAGING.mkdir(parents=True, exist_ok=True)
    destination = STAGING / source.name
    destination.write_text("\n".join(output + faces) + "\n", encoding="utf-8")
    destination.with_suffix(".mtl").write_bytes(source.with_suffix(".mtl").read_bytes())
    return destination


def material_definitions(file):
    materials = {}
    for line in file.read_text(encoding="utf-8").splitlines():
        if line.startswith("newmtl "):
            name = line.split(maxsplit=1)[1]
        elif line.startswith("Kd "):
            materials[name] = tuple(map(float, line.split()[1:4]))
    return materials


def pack_material(key, color, model_name, cache):
    lower = key.lower()
    if lower in ("glass", "mirror"):
        finish = lower
    elif "metal" in lower:
        finish = "metal"
    elif "wood" in lower:
        finish = "wood"
    elif model_name.startswith(("Carpet_", "Couch_", "Curtains_")) or any(word in lower for word in ("cush", "fabric")):
        finish = "fabric"
    else:
        finish = "solid"
    record = (key, color, finish)
    if record in cache:
        return cache[record]
    suffix = hashlib.sha1(repr(record).encode()).hexdigest()[:7]
    name = re.sub(r"[^a-zA-Z0-9_]", "_", key) + "_" + suffix
    path = f"{PACK}/Materials/M_{name}"
    if ASSETS.does_asset_exist(path):
        cache[record] = ue.load_asset(path)
        return cache[record]
    roughness = {"wood": .63, "fabric": .88, "glass": .14, "mirror": .16, "metal": .42, "solid": .72}[finish]
    material = make_material(PACK, name, color, roughness)
    if finish in ("wood", "fabric") and isinstance(
        LIB.get_material_property_input_node(material, PROPERTIES.MP_BASE_COLOR), ue.MaterialExpressionConstant3Vector
    ):
        tint = LIB.get_material_property_input_node(material, PROPERTIES.MP_BASE_COLOR)
        tint.set_editor_property("constant", ue.LinearColor(*(min(1, 2.1 * c + .018) for c in color), 1))
        sample = LIB.create_material_expression(material, ue.MaterialExpressionTextureSample, -450, -280)
        sample.set_editor_property("texture", texture_asset(finish))
        mix = LIB.create_material_expression(material, ue.MaterialExpressionMultiply, -180, -120)
        LIB.connect_material_expressions(tint, "RGB", mix, "A")
        LIB.connect_material_expressions(sample, "RGB", mix, "B")
        LIB.connect_material_property(mix, "", PROPERTIES.MP_BASE_COLOR)
    elif finish == "glass":
        material.set_editor_properties({"blend_mode": ue.BlendMode.BLEND_TRANSLUCENT, "two_sided": True,
                                        "translucency_lighting_mode": ue.TranslucencyLightingMode.TLM_SURFACE})
        opacity = LIB.create_material_expression(material, ue.MaterialExpressionConstant, -420, 220)
        opacity.set_editor_property("r", .23)
        LIB.connect_material_property(opacity, "", PROPERTIES.MP_OPACITY)
    elif finish in ("metal", "mirror"):
        metallic = LIB.create_material_expression(material, ue.MaterialExpressionConstant, -420, 220)
        metallic.set_editor_property("r", .8 if finish == "mirror" else .65)
        LIB.connect_material_property(metallic, "", PROPERTIES.MP_METALLIC)
    LIB.recompile_material(material)
    if not ASSETS.save_loaded_asset(material, False):
        raise RuntimeError(f"Could not save material {name}")
    cache[record] = material
    return material


def main():
    names = {value for value in sys.argv[1:] if not value.startswith("-")}
    sources = [source for source in sorted((SOURCE / "OBJ").glob("*.obj")) if not names or source.stem in names]
    if not sources or (names and {source.stem for source in sources} != names):
        raise RuntimeError(f"Could not locate the requested furniture sources in {SOURCE / 'OBJ'}")
    options = ue.FbxImportUI()
    options.set_editor_properties({"import_materials": False, "import_textures": False, "import_as_skeletal": False})
    tools = ue.AssetToolsHelpers.get_asset_tools()
    cache = {}
    for source in sources:
        name = source.stem
        path = f"{PACK}/{name}"
        if not ASSETS.does_asset_exist(path):
            task = ue.AssetImportTask()
            task.set_editor_properties({"filename": str(prepare_obj(source)), "options": options,
                                        "destination_path": PACK, "automated": True, "save": False})
            tools.import_asset_tasks([task])
        model = ue.load_asset(path)
        if not isinstance(model, ue.StaticMesh) or model.get_num_lods() < 1 or model.get_num_triangles(0) < 1:
            raise RuntimeError(f"No usable Static Mesh was imported for {name}")
        definitions = material_definitions(source.with_suffix(".mtl"))
        slots = model.get_editor_property("static_materials")
        if not slots:
            raise RuntimeError(f"{name} has no material slots")
        for index, slot in enumerate(slots):
            key = str(slot.get_editor_property("imported_material_slot_name"))
            if key not in definitions:
                raise RuntimeError(f"Unknown material {key} on {name}: {tuple(definitions)}")
            model.set_material(index, pack_material(key, definitions[key], name, cache))
        body = model.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag", ue.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        if not ASSETS.save_loaded_asset(model, False):
            raise RuntimeError(f"Could not save {name}")
        bounds = model.get_bounding_box()
        if abs(bounds.min.z) > .2 or bounds.max.z <= .001:
            raise RuntimeError(f"Unexpected floor or orientation for {name}: {bounds}")
        ue.log(f"FURNITURE_PACK_MESH_OK {name} slots={len(slots)} triangles={model.get_num_triangles(0)} "
               f"height_cm={bounds.max.z:.2f}")
    ue.log(f"FURNITURE_PACK_IMPORT_OK meshes={len(sources)} materials={len(cache)}")


if __name__ == "__main__":
    main()
