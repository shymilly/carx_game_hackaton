"""Import the supplied OBJ furniture and replace matching props in both apartment maps."""
from dataclasses import dataclass
import math
from pathlib import Path
import re
import sys

import unreal as ue

ROOT = "/Game/Prologue/Furniture"
SOURCE = Path.home() / "Desktop" / "assets" / "furniture"
PROJECT = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
IMPORT_SOURCE = PROJECT / "SourceAssets" / "Furniture"
SHELVED_FRIDGE = "Kitchen_FridgeCabinetShelved"
ASSETS = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
LEVELS = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
ACTORS = ue.get_editor_subsystem(ue.EditorActorSubsystem)


@dataclass(frozen=True)
class Placement:
    model: str
    label: str
    remove: str
    center: tuple
    dimensions: tuple
    yaw: float = 0
    tag: str = ""
    folder: str = ""


def apartment_furniture():
    yield Placement("Door_4", "Front door", r"Front door.*", (-320, -374, 109), (15, 110, 214), 90, "Exit", "02 Hall")
    yield Placement("Door_1", "Bedroom door", r"Bedroom door|Recessed .*door panel|Door knob", (-420, 145, 106),
                    (15, 105, 207), tag="BedroomDoor", folder="04 Bedroom")
    yield Placement("Door_2", "Bathroom door", r"Bathroom door", (-420, -205, 106), (15, 105, 207),
                    tag="BathDoor", folder="06 Bathroom")
    yield Placement("Carpet_2", "Entry mat", r"Entry mat", (-320, -310, 0.4), (104, 60, 1), folder="02 Hall")
    yield Placement("Table_RoundLarge", "Writing desk", r"Writing desk top|Desk drawer.*|Desk leg",
                    (263, 173, 44), (220, 105, 88), folder="03 Living room")
    yield Placement("Light_Desk", "Desk lamp", r"Desk lamp (base|stem|shade)", (346, 209, 118),
                    (25, 40, 60), 180, "DeskLamp", "03 Living room")
    yield Placement("Chair_1", "Desk chair", r"Desk chair .*|Chair leg", (247, 75, 49),
                    (49, 50, 98), 180, folder="03 Living room")
    yield Placement("Couch_Large1", "Sofa", r"Sofa .*|Throw pillow", (105, -330, 49), (228, 99, 98), 180, folder="03 Living room")
    yield Placement("Carpet_1", "Living room rug", r"Living room rug|Woven rug border",
                    (105, -182, 0.7), (265, 155, 1.5), folder="03 Living room")
    yield Placement("Table_RoundSmall", "Coffee table", r"Coffee table .*", (106, -163, 25),
                    (104, 78, 50), folder="03 Living room")
    yield Placement("Drawer_2", "Television cabinet", r"Television cabinet", (68, 317, 34),
                    (118, 57, 68), folder="03 Living room")
    yield Placement("Bed_King", "Bed", r"Bed foot|Bed frame|Headboard.*|Mattress|Quilt.*|Pillow",
                    (-593, 241, 55), (147, 212, 110), tag="Bed", folder="04 Bedroom")
    yield Placement("NightStand_1", "Nightstand", r"Nightstand", (-465, 326, 28.5), (52, 49, 57), folder="04 Bedroom")
    yield Placement("Shelf_Large", "Bedroom shelving", r"Wardrobe .*", (-642, 5, 98),
                    (98, 64, 196), 180, folder="04 Bedroom")
    for y, model in ((-205, "Kitchen_3Drawers"), (-135, "Kitchen_Oven"), (-65, "Kitchen_Cabinet1"),
                     (5, "Kitchen_Sink"), (75, "Kitchen_2Drawers"), (145, "Kitchen_Cabinet2")):
        height = 106 if model == "Kitchen_Sink" else 91
        yield Placement(model, model.removeprefix("Kitchen_"), r"Cabinet|Cabinet (raised panel|handle)|Laminate counter|Cooktop.*",
                        (701, y, height / 2), (68, 72, height), -90, folder="05 Kitchen")
    yield Placement("Kitchen_FridgeBody", "Fridge cabinet", r"Fridge (cabinet|dark seal|shelf.*|door|seam|handle)",
                    (658, 242, 92), (), folder="05 Kitchen")
    yield Placement("Kitchen_FridgeDoors", "Fridge doors", r"(?!)", (658, 242, 92), (), tag="FridgeDoor", folder="05 Kitchen")
    yield Placement("Table_RoundSmall2", "Kitchen table", r"Kitchen table.*", (534, 233, 38),
                    (100, 102, 76), folder="05 Kitchen")
    yield Placement("Bathroom_Bathtub", "Bathtub", r"Bathtub .*", (-657, -263, 32),
                    (179, 73, 64), 90, folder="06 Bathroom")
    yield Placement("Bathroom_Towel", "Bath towel", r"Bath towel", (-607, -320, 91),
                    (50, 7, 58), 90, folder="06 Bathroom")
    yield Placement("Bathroom_Toilet", "Toilet", r"Toilet .*", (-530, -333, 48),
                    (51, 78, 96), 180, folder="06 Bathroom")
    yield Placement("Bathroom_Sink", "Sink and tap", r"Sink (pedestal|basin|interior)|Tap (stem|spout|knob)",
                    (-562, -83, 61), (73, 49, 113), tag="Tap", folder="06 Bathroom")
    yield Placement("Bathroom_Mirror1", "Bathroom mirror", r"Mirror (frame|glass)", (-562, -61, 173),
                    (74, 7, 83), 180, folder="06 Bathroom")
    yield Placement("Bathroom_ToiletPaper", "Toilet paper holder", r"(?!)", (-507, -376, 105),
                    (28, 13, 16), 180, folder="06 Bathroom")
    for x, width in ((-555, 130), (14, 198), (565, 140)):
        yield Placement("Window_Large1", "Window frame", r"Window (mullion|crossbar)", (x, 390, 166),
                        (width, 13, 122), folder="01 Architecture/Windows")


def father_furniture():
    yield Placement("Door_4", "Apartment exit", r"Apartment exit|Exit handle", (-411, -148, 115),
                    (16, 116, 229), tag="Exit")
    yield Placement("Table_RoundLarge", "Writing desk", r"Desk top|Desk leg", (263, 173, 44), (220, 105, 88))
    yield Placement("Chair_1", "Desk chair", r"Chair (seat|back|leg)", (247, 75, 49), (49, 50, 98), 180)
    yield Placement("Light_Desk", "Desk lamp", r"Desk lamp (base|stem|shade)", (344, 204, 118), (25, 40, 60), 180)
    yield Placement("Couch_Large1", "Sofa", r"Sofa (base|back|arm)", (-56, -237, 51), (218, 103, 102), 180)
    yield Placement("Carpet_1", "Rug", r"Rug|Rug border", (28, -53, 0.7), (268, 169, 1.5))
    yield Placement("Window_Large1", "Window frame", r"Window (mullion|crossbar)", (-56, 310, 160), (200, 13, 128))


def model_source(name):
    return "Kitchen_Fridge" if name in ("Kitchen_FridgeBody", "Kitchen_FridgeDoors") else name


def write_obj(name):
    if name == SHELVED_FRIDGE:
        return write_blender_fridge()
    original = model_source(name)
    source = SOURCE / "OBJ" / (original + ".obj")
    lines = source.read_text(encoding="utf-8").splitlines()
    vertices = [tuple(map(float, line.split()[1:4])) for line in lines if line.startswith("v ")]
    if not vertices:
        raise ValueError(f"No vertices in {source}")

    fridge = original == "Kitchen_Fridge"
    body_vertices = set()
    if fridge:
        # The original OBJ has one object, but the cabinet and door shells are disconnected.
        faces = [[int(item.split("/")[0]) - 1 for item in line.split()[1:]]
                 for line in lines if line.startswith("f ")]
        body_vertices = {0}
        while True:
            connected = body_vertices.union(*(face for face in faces if body_vertices.intersection(face)))
            if connected == body_vertices:
                break
            body_vertices = connected

    door = original.startswith("Door_")
    has_uv = any(line.startswith("vt ") for line in lines)

    def transform(x, y, z):
        # Interchange reflects the OBJ Y axis. Put up on Z and front on -Y in Unreal.
        if fridge:
            return (-55 * (z - .62), 55 * x, 55 * (y - 1.67))
        if door:
            return (z * 100, -(x + .868) * 100, (y - 2.094) * 100)
        return (x * 100, z * 100, y * 100)

    # The window pack uses an opaque glass material. Use its frame and keep the skyline visible.
    material = ""
    output = []
    if not has_uv:
        # Some pack meshes have explicit normals and no UVs. Interchange expects UV indices.
        output.extend(f"vt {x:.8f} {z + y:.8f}" for x, y, z in vertices)
    for line in lines:
        key = line.split(maxsplit=1)[0] if line.strip() else ""
        if key == "mtllib":
            line = "mtllib " + name + ".mtl"
        elif key == "o":
            line = "o " + name
        elif key in ("v", "vn"):
            xyz = tuple(map(float, line.split()[1:4]))
            offset = transform(0, 0, 0) if key == "vn" else (0, 0, 0)
            value = tuple(a - b for a, b in zip(transform(*xyz), offset))
            if key == "vn":
                length = sum(axis ** 2 for axis in value) ** .5 or 1
                value = tuple(axis / length for axis in value)
            line = key + " " + " ".join(f"{axis:.8f}" for axis in value)
        elif key == "usemtl":
            material = line.split(maxsplit=1)[1]
        elif key == "f":
            if name.startswith("Window_") and material == "Glass":
                continue
            if fridge:
                indices = {int(item.split("/")[0]) - 1 for item in line.split()[1:]}
                if indices.issubset(body_vertices) != (name == "Kitchen_FridgeBody"):
                    continue
            corners = line.split()[1:]
            if not has_uv:
                corners = [corner.replace("//", f"/{corner.split('/')[0]}/") for corner in corners]
            line = "f " + " ".join(reversed(corners))
        elif key == "s":
            continue  # This UE OBJ translator reads explicit vertex normals.
        output.append(line)
    IMPORT_SOURCE.mkdir(parents=True, exist_ok=True)
    normalized = IMPORT_SOURCE / (name + ".obj")
    normalized.write_text("\n".join(output) + "\n", encoding="utf-8")
    normalized.with_suffix(".mtl").write_bytes(source.with_suffix(".mtl").read_bytes())
    return normalized


def write_blender_fridge():
    # Blender exports this replacement directly in the normalized centimeter basis.
    source = PROJECT / "SourceAssets" / "Blender" / f"{SHELVED_FRIDGE}.obj"
    lines = source.read_text(encoding="utf-8").splitlines()
    uv_count = sum(line.startswith("vt ") for line in lines)
    vertices = [tuple(map(float, line.split()[1:4])) for line in lines if line.startswith("v ")]
    # The legacy cabinet shell has no UVs, while the new shelf modules have their own UVs.
    # Give only the original corners a fallback so Interchange always sees a valid index.
    output = []
    faces_started = False
    for line in lines:
        if line.startswith("s "):
            continue
        if line.startswith("f "):
            if not faces_started:
                output.extend(f"vt {x / 64:.7f} {(y + z) / 64:.7f}" for x, y, z in vertices)
                faces_started = True
            corners = []
            for vertex in line.split()[1:]:
                position, uv, normal = vertex.split("/")
                corners.append(f"{position}/{uv or uv_count + int(position)}/{normal}")
            line = "f " + " ".join(corners)
        output.append(line)
    IMPORT_SOURCE.mkdir(parents=True, exist_ok=True)
    destination = IMPORT_SOURCE / source.name
    destination.write_text("\n".join(output) + "\n", encoding="utf-8")
    destination.with_suffix(".mtl").write_bytes(source.with_suffix(".mtl").read_bytes())
    return destination


def apply_materials(name, model):
    from ApartmentScene import make_material
    from ApartmentFinishes import texture_asset

    colors = {}
    current = ""
    materials = IMPORT_SOURCE / f"{name}.mtl"
    for line in materials.read_text().splitlines():
        if line.startswith("newmtl "):
            current = line.split(maxsplit=1)[1]
        elif line.startswith("Kd "):
            colors[current] = tuple(map(float, line.split()[1:4]))
    for index, slot in enumerate(model.get_editor_property("static_materials")):
        key = str(slot.get_editor_property("imported_material_slot_name"))
        if key not in colors:
            key = str(slot.get_editor_property("material_slot_name"))
        if key not in colors:
            raise RuntimeError(f"Missing MTL diffuse color for {name} slot {key}: {list(colors)}")
        wood = "wood" in key.lower()
        textile = name.startswith(("Carpet_", "Couch_", "Bathroom_Towel")) or (
            name == "Bed_King" and key in ("Red", "DarkRed", "White", "Grey")
        ) or (name.startswith("Chair_") and "cush" in key.lower())
        tint = tuple(min(1.0, (channel * 2.1) + .018) for channel in colors[key]) if wood or textile else colors[key]
        material = make_material(f"{ROOT}/{name}", ("Textured_" if wood or textile else "Solid_") + key, tint, 0.74)
        if wood or textile:
            library = ue.MaterialEditingLibrary
            base = library.get_material_property_input_node(material, ue.MaterialProperty.MP_BASE_COLOR)
            if isinstance(base, ue.MaterialExpressionConstant3Vector):
                texture = texture_asset("wood" if wood else "fabric")
                uv = library.create_material_expression(material, ue.MaterialExpressionTextureCoordinate, -660, 80)
                uv.set_editor_properties({"u_tiling": 2.0, "v_tiling": 2.0})
                sample = library.create_material_expression(material, ue.MaterialExpressionTextureSample, -440, 110)
                sample.set_editor_property("texture", texture)
                library.connect_material_expressions(uv, "", sample, "Coordinates")
                shade = library.create_material_expression(material, ue.MaterialExpressionMultiply, -210, 30)
                library.connect_material_expressions(base, "", shade, "A")
                library.connect_material_expressions(sample, "RGB", shade, "B")
                library.connect_material_property(shade, "", ue.MaterialProperty.MP_BASE_COLOR)
                library.recompile_material(material)
                if not ASSETS.save_loaded_asset(material, False):
                    raise RuntimeError(f"Could not save textured material {key} for {name}")
        model.set_material(index, material)


def import_meshes(names, refresh=False):
    tasks = []
    imported_names = set()
    for name in sorted(names):
        folder = f"{ROOT}/{name}"
        if not refresh and ASSETS.does_asset_exist(f"{folder}/{name}"):
            continue
        task = ue.AssetImportTask()
        task.set_editor_properties({
            "filename": str(write_obj(name)), "destination_path": folder,
            "automated": True, "save": True, "replace_existing": refresh,
            "replace_existing_settings": refresh,
        })
        tasks.append(task)
        imported_names.add(name)
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    meshes = {name: ue.load_asset(f"{ROOT}/{name}/{name}") for name in sorted(names)}
    missing = [name for name, model in meshes.items() if not isinstance(model, ue.StaticMesh)]
    if missing:
        raise RuntimeError(f"Missing imported Static Meshes: {missing}")
    for name, model in meshes.items():
        if name not in imported_names:
            continue
        apply_materials(name, model)
        body = model.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag", ue.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        if not ASSETS.save_loaded_asset(model, False):
            raise RuntimeError(f"Could not save collision for {name}")
    return meshes


def place(item, model):
    bounds = model.get_bounding_box()
    middle = (bounds.min + bounds.max) * 0.5
    extent = bounds.max - bounds.min
    rotation = ue.Rotator(0, 0, item.yaw)
    scale = ue.Vector(1, 1, 1)
    if item.dimensions:
        x, y, z = item.dimensions
        if abs(item.yaw) == 90:
            x, y = y, x
        scale = ue.Vector(x / extent.x, y / extent.y, z / extent.z)
    actor = ACTORS.spawn_actor_from_class(ue.StaticMeshActor, ue.Vector(*item.center), rotation)
    actor.set_actor_label(item.label)
    actor.set_folder_path(ue.Name(item.folder or "Furniture"))
    comp = actor.get_component_by_class(ue.StaticMeshComponent)
    comp.set_static_mesh(model)
    comp.set_collision_profile_name(ue.Name("BlockAll"))
    if item.model.startswith("Carpet_"):
        comp.set_collision_enabled(ue.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(scale)
    if item.tag:
        actor.set_editor_property("tags", [ue.Name(item.tag)])
    if item.tag in ("BedroomDoor", "KitchenDoor", "BathDoor", "FridgeDoor"):
        comp.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
    elif item.dimensions:
        local_center = ue.Vector(middle.x * scale.x, middle.y * scale.y, middle.z * scale.z)
        yaw = math.radians(item.yaw)
        c, s = math.cos(yaw), math.sin(yaw)
        rotated = ue.Vector(c * local_center.x - s * local_center.y,
                            s * local_center.x + c * local_center.y, local_center.z)
        comp.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
        actor.set_actor_location(ue.Vector(*item.center) - rotated, False, True)
        comp.set_editor_property("mobility", ue.ComponentMobility.STATIC)
    return actor


def replace_level(path, placements, meshes):
    if not LEVELS.load_level(path):
        raise RuntimeError(f"Could not load {path}")
    old = ACTORS.get_all_level_actors()
    if any("FurnitureImported" in map(str, actor.get_editor_property("tags")) for actor in old):
        ue.log(f"FURNITURE_ALREADY_PLACED {path}")
        return
    for item in placements:
        actor = place(item, meshes[item.model])
        tags = actor.get_editor_property("tags")
        tags.append(ue.Name("FurnitureImported"))
        actor.set_editor_property("tags", tags)
    for actor in old:
        if any(re.fullmatch(item.remove, actor.get_actor_label()) for item in placements):
            if not ACTORS.destroy_actor(actor):
                raise RuntimeError(f"Could not replace {actor.get_actor_label()}")
    if not LEVELS.save_current_level():
        raise RuntimeError(f"Could not save {path}")
    ue.log(f"FURNITURE_PLACED {len(placements)} props in {path}")


def main():
    sys.path.insert(0, str(Path(__file__).parent))
    from PlanApartment import furniture

    previous, father = tuple(apartment_furniture()), tuple(father_furniture())
    meshes = import_meshes({item.model for item in previous + father + tuple(furniture())}, refresh="--refresh" in sys.argv)
    (IMPORT_SOURCE / "License.txt").write_bytes((SOURCE / "License.txt").read_bytes())
    replace_level("/Game/Prologue/L_Apartment", father, meshes)
    ue.log(f"FURNITURE_IMPORT_OK {len(meshes)} Static Meshes")


if __name__ == "__main__":
    main()
