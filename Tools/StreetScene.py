"""Build the 1994 street around the apartment without loading a second world."""
from math import atan2, degrees, hypot
from pathlib import Path
from random import Random

import unreal as ue

from ApartmentFixtures import transmissive_material
from ApartmentScene import make_material
from ImportFurniturePack import material_definitions
from StreetMaterials import ASSETS, ROOT, TOOLS, create_street_materials, save


PROJECT = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
STREET_ART = PROJECT / "SourceAssets" / "Street"
STAGE = PROJECT / "Saved" / "Street" / "Import"
V, R = ue.Vector, ue.Rotator
SIDEWALK_Z = -12
ROAD_Z = -28
MAIN_ROAD_NORTH = -756
MAIN_ROAD_SOUTH = -1544
BLENDER_MESHES = ("SM_BookKiosk", "SM_WallClock", "SM_ClockHour", "SM_ClockMinute", "SM_Sedan94",
                  "SM_SignDeli", "SM_SignPharmacy", "SM_SignAegis", "SM_SignStreet")


def normalized_obj(name):
    path = STREET_ART / (name + ".obj")
    if not path.exists():
        raise RuntimeError("Export the street props with Tools/BlenderStreetProps.py before importing.")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    positions = [line for line in lines if line.startswith("v ")]
    uvs = [line for line in lines if line.startswith("vt ")]
    normals = [line for line in lines if line.startswith("vn ")]
    faces = [line for line in lines if line.startswith(("usemtl ", "f "))]
    fallback = len(uvs) + 1
    # Font outlines and other solid-color pieces may have no UVs in the Blender file.
    uvs.append("vt 0.0 0.0")
    for index, line in enumerate(faces):
        if not line.startswith("f "):
            continue
        corners = [corner.split("/") for corner in line.split()[1:]]
        if any(len(corner) != 3 or not corner[2] for corner in corners):
            raise RuntimeError(f"The Blender export for {name} is missing a normal.")
        faces[index] = "f " + " ".join(f"{v}/{uv or fallback}/{normal}" for v, uv, normal in corners)
    STAGE.mkdir(parents=True, exist_ok=True)
    destination = STAGE / path.name
    # One Static Mesh with all material groups. Blender exports in centimeters and Z up.
    destination.write_text("\n".join([f"mtllib {name}.mtl", f"o {name}"] + positions + uvs + normals + faces) + "\n",
                           encoding="utf-8")
    destination.with_suffix(".mtl").write_bytes(path.with_suffix(".mtl").read_bytes())
    return destination


def street_models(reimport=()):
    result = {}
    finishes = {}
    options = ue.FbxImportUI()
    options.set_editor_properties({"import_materials": False, "import_textures": False, "import_as_skeletal": False})
    folder = ROOT + "/Meshes"
    for name in BLENDER_MESHES:
        target = f"{folder}/{name}"
        if name not in reimport and ASSETS.does_asset_exist(target):
            result[name] = ue.load_asset(target)
            continue
        source = normalized_obj(name)
        task = ue.AssetImportTask()
        task.set_editor_properties({"filename": str(source), "destination_path": folder,
                                    "automated": True, "save": False, "options": options,
                                    "replace_existing": name in reimport})
        TOOLS.import_asset_tasks([task])
        model = ue.load_asset(target)
        if not isinstance(model, ue.StaticMesh) or model.get_num_triangles(0) < 1:
            raise RuntimeError(f"Could not import {name} from Blender.")
        palette = material_definitions(source.with_suffix(".mtl"))
        for index, slot in enumerate(model.get_editor_property("static_materials")):
            key = str(slot.get_editor_property("imported_material_slot_name"))
            if key not in finishes:
                if key == "Glass":
                    finishes[key] = transmissive_material("BookKioskGlass", (.56, .70, .67), .2, .14, .24)
                else:
                    library = ue.MaterialEditingLibrary
                    roughness = {"CarPaint": .32, "CarGlass": .24, "Chrome": .27, "Steel": .48}.get(key, .76)
                    material = make_material(ROOT, "Prop_" + key, palette[key], roughness)
                    base = library.get_material_property_input_node(material, ue.MaterialProperty.MP_BASE_COLOR)
                    base.set_editor_property("constant", ue.LinearColor(*palette[key], 1))
                    if key in ("Chrome", "Steel") and not library.get_material_property_input_node(
                        material, ue.MaterialProperty.MP_METALLIC
                    ):
                        metal = library.create_material_expression(material, ue.MaterialExpressionConstant, -450, 260)
                        metal.set_editor_property("r", .72)
                        library.connect_material_property(metal, "", ue.MaterialProperty.MP_METALLIC)
                    library.recompile_material(material)
                    save(material)
                    finishes[key] = material
            model.set_material(index, finishes[key])
        model.get_editor_property("body_setup").set_editor_property("collision_trace_flag",
                                                                     ue.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        save(model)
        result[name] = model
        ue.log(f"STREET_MESH_OK {name} triangles={model.get_num_triangles(0)}")
    return result


class StreetBuilder:
    def __init__(self, materials, meshes):
        self.actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        self.materials = materials
        self.meshes = meshes
        self.shapes = {shape: ue.load_asset(f"/Engine/BasicShapes/{shape}") for shape in ("Cube", "Sphere", "Cylinder")}
        self.batches = {}
        self.lights = []
        self.rng = Random(1994)
        self.folder = "Street/01 Pavement"

    def spawn(self, actor_class, label, pos=(0, 0, 0), rotation=(0, 0, 0), tag=None):
        actor = self.actors.spawn_actor_from_class(actor_class, V(*pos), R(*rotation))
        if not actor:
            raise RuntimeError(f"Could not place {label}")
        actor.set_actor_label(label)
        actor.set_folder_path(ue.Name(self.folder))
        if tag:
            actor.set_editor_property("tags", [ue.Name(tag)])
        return actor

    def model(self, label, mesh, pos, yaw=0, collision=True, rotation=None, material=None):
        actor = self.spawn(ue.StaticMeshActor, label, pos, rotation or (0, 0, yaw))
        component = actor.get_component_by_class(ue.StaticMeshComponent)
        component.set_static_mesh(mesh)
        component.set_collision_profile_name(ue.Name("BlockAll" if collision else "NoCollision"))
        if not collision:
            actor.set_actor_enable_collision(False)
        if material:
            component.set_material(0, self.materials[material])
        return actor

    def block(self, label, pos, dimensions, material, *, collision=True, rotation=(0, 0, 0), shape="Cube"):
        actor = self.model(label, self.shapes[shape], pos, collision=collision, rotation=rotation, material=material)
        actor.set_actor_scale3d(V(*(entry / 100 for entry in dimensions)))
        return actor

    def detail(self, pos, dimensions, material, rotation=(0, 0, 0), shape="Cube"):
        key = (self.folder, material, shape)
        if key not in self.batches:
            actor = self.spawn(ue.StreetMeshInstances, f"Detail instances · {material} · {shape}")
            component = actor.get_editor_property("instances")
            component.set_static_mesh(self.shapes[shape])
            component.set_material(0, self.materials[material])
            self.batches[key] = component
        transform = ue.Transform(location=V(*pos), rotation=R(*rotation),
                                 scale=V(*(entry / 100 for entry in dimensions)))
        self.batches[key].add_instance(transform)

    def between(self, first, second, thickness, material):
        start, end = V(*first), V(*second)
        difference = end - start
        direction = ue.MathLibrary.find_look_at_rotation(start, end)
        middle = (start + end) * .5
        self.detail((middle.x, middle.y, middle.z), (difference.length(), thickness, thickness), material,
                    (direction.roll, direction.pitch, direction.yaw))

    def slab(self, label, x_min, x_max, y_min, y_max, top, depth, material, collision=True):
        return self.block(label, ((x_min + x_max) / 2, (y_min + y_max) / 2, top - depth / 2),
                          (x_max - x_min, y_max - y_min, depth), material, collision=collision)

    def camera(self, label, tag, pos, target, fov):
        rot = ue.MathLibrary.find_look_at_rotation(V(*pos), V(*target))
        actor = self.spawn(ue.CameraActor, label, pos, (rot.roll, rot.pitch, rot.yaw), tag)
        actor.get_component_by_class(ue.CameraComponent).set_field_of_view(fov)
        return actor

    def pavement(self):
        self.folder = "Street/01 Pavement"
        self.slab("World foundation", -3930, 4050, -3520, 2940, -31, 120, "asphalt")
        self.slab("Neptune Avenue roadway", -3490, 3690, MAIN_ROAD_SOUTH, MAIN_ROAD_NORTH, ROAD_Z, 9, "asphalt")
        self.slab("Alley from side street", -2360, -1530, -2900, 1990, ROAD_Z, 9, "asphalt")
        self.slab("Near sidewalk", -1550, 3490, MAIN_ROAD_NORTH, -452, SIDEWALK_Z, 24, "concrete")
        self.slab("Far sidewalk", -1550, 3490, -1830, MAIN_ROAD_SOUTH, SIDEWALK_Z, 24, "concrete")
        self.slab("Kitchen courtyard", -1490, -392, -451, 39, SIDEWALK_Z, 26, "concrete")
        self.slab("Side passage paving", -1490, -769, 39, 1074, SIDEWALK_Z, 24, "concrete")
        self.slab("Rear service lane paving", -770, 2860, 451, 1250, SIDEWALK_Z, 24, "concrete")
        self.slab("Eastern sidewalk", 804, 2880, -451, 451, SIDEWALK_Z, 24, "concrete")
        self.slab("Door landing", -270, -117, -512, -440, -.4, 16, "stone")
        self.slab("West sidewalk north of junction", -3400, -2360, -750, 1720, SIDEWALK_Z, 23, "concrete")
        self.slab("West sidewalk south of junction", -3400, -2360, -2970, -1550, SIDEWALK_Z, 23, "concrete")
        # Road paint sits well below the curb and does not participate in collision.
        for y in (-1159, -1144):
            for left, right in ((-1395, 3350), (-3390, -2465)):
                self.detail(((left + right) / 2, y, ROAD_Z + .17), (right - left, 8, .25), "yellow_line")
        for index in range(12):
            self.detail((-1440, -1506 + index * 64, ROAD_Z + .25), (206, 31, .3), "white_line")
        for x in range(-1315, 3280, 385):
            for y in (-843, -1453):
                self.detail((x, y, ROAD_Z + .17), (127, 4.1, .27), "white_line")
        for x in range(-1440, 3430, 90):
            for y in (MAIN_ROAD_NORTH + 1, MAIN_ROAD_SOUTH - 1):
                if x < -1310:
                    continue
                self.detail((x, y, SIDEWALK_Z - 6), (86.6, 14, 13), "stone")
        for x, y in ((-344, -905), (1087, -1220), (-1321, -1466), (2262, -790)):
            self.detail((x, y, ROAD_Z + .22), (54, 54, .55), "steel", shape="Cylinder")
            for j in (-12, 0, 12):
                self.detail((x, y + j, ROAD_Z + .5), (23, 3, .2), "frame")
        for start, end in (((-1530,-1544),(-2400,-1500)), ((-3500,-1530),(-3500,-785)), ((3450,-1550),(3450,-755)),
                           ((-2290,1580),(-1490,1580))):
            # Loading docks and retaining walls close the playable ends of the block.
            dx, dy = end[0]-start[0], end[1]-start[1]
            self.block("Masonry end of block", ((start[0]+end[0])/2, (start[1]+end[1])/2, 86),
                       (hypot(dx, dy), 32, 228), "brick", rotation=(0, 0, degrees(atan2(dy, dx))))
        for pos, size in (((-3650, -375, 250), (25, 4350, 550)), ((3580, -375, 250), (25, 4350, 550)),
                          ((-35, -2550, 250), (7260, 25, 550)), ((-35, 1800, 250), (7260, 25, 550))):
            boundary = self.block("Playable block boundary", pos, size, "frame")
            boundary.set_actor_hidden_in_game(True)
            boundary.get_component_by_class(ue.StaticMeshComponent).set_editor_property("cast_shadow", False)

    def facade_strip(self, label, axis, fixed, first, last, bottom, top, material="brick"):
        mid, z = (first + last) / 2, (bottom + top) / 2
        if axis == "x":
            self.block(label, (mid, fixed, z), (last-first, 9, top-bottom), material)
        else:
            self.block(label, (fixed, mid, z), (9, last-first, top-bottom), material)

    def facade_opening(self, axis, fixed, first, last, opening, bottom, top):
        lo, hi = opening
        self.facade_strip("Brick beside opening", axis, fixed, first, lo, SIDEWALK_Z, 295)
        self.facade_strip("Brick beside opening", axis, fixed, hi, last, SIDEWALK_Z, 295)
        if bottom > SIDEWALK_Z:
            self.facade_strip("Brick under window", axis, fixed, lo, hi, SIDEWALK_Z, bottom)
        self.facade_strip("Brick lintel", axis, fixed, lo, hi, top, 295)

    def window(self, x, y, z, face, width=108, height=136, lit=False):
        self.detail((x, y, z), (width + 18, 15, height + 17), "stone")
        self.detail((x, y + face * 8, z), (width, 3.3, height), "lit_window" if lit else "dark_glass")
        for dx in (-width/2, 0, width/2):
            self.detail((x + dx, y + face * 11, z), (4.7, 5, height), "frame")
        for dz in (-height/2, -14, height/2):
            self.detail((x, y + face * 11, z + dz), (width + 5, 5, 4.8), "frame")
        self.detail((x, y + face * 13, z - height/2 - 7), (width + 25, 21, 11), "stone")
        if lit:
            self.detail((x - width * .31, y + face * 10, z + 9), (width * .21, 2, height * .82), "curtain")

    def apartment_facade(self):
        self.folder = "Street/02 Apartment facade"
        self.facade_opening("x", -462, -393, 806, (-253, -135), SIDEWALK_Z, 213)
        self.facade_opening("x", 462, -771, 396, (-133, 93), 108, 236)
        self.facade_opening("x", 28, -770, -393, (-637, -479), 109, 231)
        self.facade_opening("y", -402, -453, 39, (-366, -206), 106, 233)
        for axis, fixed, first, last in (("y", -777, 33, 467), ("y", 812, -453, 118),
                                         ("x", 122, 394, 803), ("y", 402, 115, 467)):
            self.facade_strip("Return wall brick", axis, fixed, first, last, SIDEWALK_Z, 295)
        for a, b, c, d in ((-390, 390, -452, 455), (390, 808, -452, 115), (-777, -390, 32, 455)):
            self.slab("Upper walk-up dwelling", a, b, c, d, 824, 530, "brick")
            self.slab("Flat roof and parapet", a - 9, b + 9, c - 9, d + 9, 862, 40, "roof")
        for y, direction, xs in ((-462,-1,(-296,-97,103,298,493,690)), (460,1,(-653,-445,-246,-47,161,350))):
            for z in (432, 698):
                for index, x in enumerate(xs):
                    self.window(x, y, z, direction, 98, 125, (index + int(z)) % 5 == 2)
            self.detail(((xs[-1] + xs[0]) / 2, y, 293), (xs[-1] - xs[0] + 170, 22, 13), "stone")
        # Shallow door hood ends above the frame, leaving the leaf sweep clear.
        self.block("Building entrance hood", (-194, -501, 230), (156, 88, 11), "dark_stone", collision=False)
        self.detail((-194, -493, 220), (24, 21, 10), "lamp_glass")
        for x in (-267, -119):
            self.detail((x, -470, 118), (10, 20, 214), "stone")
        for x in (74, 315, 595):
            self.detail((x, -467, 101), (45, 13, 39), "frame")
            for z in (88, 97, 106, 115):
                self.detail((x, -476, z), (42, 3, 2.7), "galvanized")

    def building(self, label, center_x, front, face, width, depth, height, wall, storefront=None):
        y = front - face * depth / 2
        self.block(label, (center_x, y, SIDEWALK_Z + height / 2), (width, depth, height), wall)
        self.detail((center_x, front, height + SIDEWALK_Z - 8), (width + 38, 60, 30), "stone")
        self.detail((center_x, y, height + SIDEWALK_Z), (width + 13, depth + 18, 12), "roof")
        pitch = 157
        count = max(2, int((width - 50) // pitch))
        xs = [center_x + (index-(count-1)/2)*pitch for index in range(count)]
        for z in range(410, height - 44, 243):
            for idx, x in enumerate(xs):
                self.window(x, front + face * 3, z, face, lit=(idx + int(z) + int(center_x)) % 4 == 0)
        self.detail((center_x, front + face * 6, 266), (width + 5, 20, 16), "dark_stone")
        if storefront:
            sign, shade = storefront
            self.storefront(center_x, front, face, width, sign, shade)
        else:
            for index, x in enumerate(xs):
                self.window(x, front + face * 3, 145, face, 94, 128, lit=index == 1)
        if height >= 740:
            self.detail((center_x + width * .18, y + 25, height + 69), (111, 103, 161), "brick")
            self.detail((center_x + width * .18, y + 25, height + 153), (140, 130, 13), "stone")
        if width >= 620 and height >= 700:
            self.detail((center_x - width*.17, y - 60, height + 87), (139, 139, 143), "wood", shape="Cylinder")
            self.detail((center_x - width*.17, y - 60, height + 160), (153, 153, 15), "roof", shape="Cylinder")
            for angle in (0, 90):
                self.detail((center_x - width*.17, y - 60, height + 26), (159, 13, 50), "frame", (0, 0, angle))

    def storefront(self, x, y, face, width, sign, shade):
        self.detail((x, y + face * 9, 111), (width - 55, 19, 220), "frame")
        self.detail((x, y + face * 21, 106), (width - 89, 7, 169), "store_glass")
        self.detail((x, y + face * 23, 29), (width - 89, 9, 42), shade)
        for dx in (-.33, -.17, 0, .17, .33):
            self.detail((x + width * dx, y + face * 26, 123), (5, 11, 175), "frame")
        self.detail((x, y + face * 29, 106), (width - 85, 9, 6), "frame")
        self.detail((x, y + face * 25, 242), (width - 34, 35, 54), shade)
        self.model("Fascia lettering", self.meshes[sign], (x, y + face * 44, 243),
                   180 if face > 0 else 0, False)
        for index in range(15):
            stripe_width = (width - 47) / 15
            self.detail((x + stripe_width * (index-7), y + face * 69, 200),
                        (stripe_width + .1, 107, 5.2), shade if index % 4 < 3 else "faded_white", (22*face,0,0))
        self.detail((x, y + face * 120, 179), (width - 47, 7, 21), shade)
        for dx in (-.26, .25):
            self.detail((x + width*dx, y + face*29, 113), (88, 2.1, 49), "paper")
            for dz in (-16, 0, 16):
                self.detail((x + width*dx, y + face*31, 113+dz), (71, 1, 2.1), shade)

    def blockfronts(self):
        self.folder = "Street/03 Retail and walk-ups"
        self.building("Baltic Deli walk-up", -367, -1811, 1, 677, 491, 791, "ochre_brick", ("SM_SignDeli", "awning"))
        self.building("Apothecary walk-up", 346, -1811, 1, 673, 495, 880, "brick", ("SM_SignPharmacy", "teal"))
        self.building("West tenement", -1092, -1822, 1, 734, 534, 777, "brick")
        self.building("Brownstone terrace", 1099, -1822, 1, 810, 549, 1040, "ochre_brick")
        self.building("East corner warehouses", 1998, -1829, 1, 972, 775, 710, "brick")
        self.building("Elevated rear buildings", 3030, -1825, 1, 1040, 660, 1280, "ochre_brick")
        self.building("North corner tenement", 1245, -461, -1, 668, 529, 937, "ochre_brick")
        self.building("Laundry tenement", 2051, -462, -1, 910, 706, 1097, "brick")
        self.building("North block terminal", 2940, -462, -1, 858, 608, 722, "brick")
        self.building("West corner rowhome", -2850, -757, -1, 865, 742, 945, "ochre_brick")
        self.building("West corner shops", -2911, -1546, 1, 1080, 525, 773, "brick")
        for x, z, w, d in ((-1180, 997, 820, 850), (2780, 1210, 1146, 800), (1650, 1475, 676, 535)):
            self.block("Distant upper block", (x, -2650, z/2 + SIDEWALK_Z), (w, d, z), "brick")

    def industrial_yard(self):
        self.folder = "Street/04 Aegis freight yard"
        self.building("Aegis freight building", 283, 1330, -1, 1640, 793, 568, "brick")
        self.building("Boiler house", -1025, 1486, -1, 810, 693, 721, "ochre_brick")
        self.building("Loading warehouse", 1542, 1380, -1, 932, 658, 501, "ochre_brick")
        self.detail((245, 1309, 293), (626, 26, 58), "frame")
        self.model("Freight sign", self.meshes["SM_SignAegis"], (245, 1294, 290), collision=False)
        for x in (-265, 770):
            self.detail((x, 1318, 118), (247, 23, 249), "frame")
            self.detail((x, 1304, 104), (219, 9, 212), "dark_stone")
            for z in range(16, 206, 13):
                self.detail((x, 1299, z), (211, 3, 3.3), "steel")
        for x, y, h, diameter in ((-1160, 1490, 1490, 122), (-926, 1596, 1215, 95), (889, 1773, 1050, 78)):
            self.block("Factory smokestack", (x, y, h/2+SIDEWALK_Z), (diameter, diameter, h), "brick", shape="Cylinder")
            for offset, width in ((-15, 1.23), (-86, 1.07), (215-h, 1.1)):
                self.detail((x, y, h + offset), (diameter*width, diameter*width, 19), "dark_stone", shape="Cylinder")
        self.fence(-1310, 1995, 1132)
        for x in (1150, 1266, 1382):
            self.block("Freight pallet crate", (x, 1019, 37), (108, 94, 99), "wood")
            for z in (7, 66):
                self.detail((x, 970, z), (111, 5, 13), "dark_stone")

    def fence(self, lo, hi, y):
        for x in range(lo, hi + 1, 215):
            self.detail((x, y, 92), (9, 9, 208), "galvanized", shape="Cylinder")
        for z in (28, 106, 184):
            self.detail(((lo+hi)/2, y, z), (hi-lo, 4, 4), "galvanized")
        # Repeat diamond-shaped runs in a plane. A thin rail defines the yard's physical boundary.
        for x in range(lo + 35, hi - 34, 26):
            for shift in (-19, 19):
                self.between((x, y, 22), (x + shift, y, 183), 1.5, "steel")
        guard = self.block("Freight fence collision", ((lo+hi)/2, y, 85), (hi-lo, 7, 197), "frame")
        guard.set_actor_hidden_in_game(True)

    def lamp(self, x, y, facing):
        self.detail((x, y, 19), (31, 31, 61), "dark_stone", shape="Cylinder")
        self.block("Galvanized street lamp post", (x, y, 249), (15, 15, 522), "steel", shape="Cylinder")
        self.between((x, y, 486), (x, y+facing*37, 549), 12, "steel")
        self.between((x, y+facing*37, 549), (x, y+facing*105, 560), 10, "steel")
        self.detail((x, y+facing*119, 554), (29, 45, 14), "frame")
        self.detail((x, y+facing*119, 545), (23, 39, 7), "lamp_glass")
        self.spot("Sodium street lamp", (x, y+facing*118, 532), (0, -90, 0), 4.0, 950, (1, .60, .25))

    def spot(self, label, pos, rotation, intensity, radius, color, shadow=False):
        lamp = self.spawn(ue.SpotLight, label, pos, rotation)
        light = lamp.get_component_by_class(ue.SpotLightComponent)
        light.set_editor_properties({"mobility": ue.ComponentMobility.MOVABLE, "use_inverse_squared_falloff": False,
                                     "light_falloff_exponent": 3.0, "cast_shadows": shadow, "source_radius": 12.0})
        light.set_intensity(intensity)
        light.set_light_color(ue.LinearColor(*color, 1))
        light.set_attenuation_radius(radius)
        light.set_outer_cone_angle(58)
        self.lights.append(lamp)

    def details(self):
        self.folder = "Street/05 Fixtures and vehicles"
        self.model("Киоск КНИГИ / ПРЕССА", self.meshes["SM_BookKiosk"], (-700, -426, SIDEWALK_Z))
        for x, y, yaw, paint in ((-115, -901, 0, "sedan_burgundy"), (1039, -1416, 180, "sedan_cream"),
                                  (2104,-892,0,None), (-1302,-1388,180,"sedan_cream")):
            actor = self.model("Parked early-1990s sedan", self.meshes["SM_Sedan94"], (x, y, ROAD_Z), yaw)
            if paint:
                component = actor.get_component_by_class(ue.StaticMeshComponent)
                for index, slot in enumerate(self.meshes["SM_Sedan94"].get_editor_property("static_materials")):
                    if str(slot.get_editor_property("imported_material_slot_name")) == "CarPaint":
                        component.set_material(index, self.materials[paint])
        for x, y, facing in ((-1045,-721,-1), (535,-719,-1), (1815,-724,-1), (-775,-1581,1), (1142,-1581,1),
                             (-1290,874,1)):
            self.lamp(x, y, facing)
        self.spot("Entrance hood light", (-194, -493, 217), (0, -76, 0), 2.3, 330, (1, .72, .42), True)
        self.detail((-700, -541, 230), (88, 5, 5), "lamp_glass")
        self.spot("Book display light", (-700, -542, 228), (0, -49, 90), 1.0, 274, (1, .81, .57))
        for x, y in ((-394,-719), (398,-721), (923,-1578), (-888,-1585)):
            self.detail((x, y, 48), (6.3, 6.3, 119), "steel", shape="Cylinder")
            self.detail((x, y, 111), (18, 12, 25), "steel")
            self.detail((x, y+6.3, 116), (11, 1.5, 13), "dark_glass")
            self.detail((x, y+6.8, 108), (4, 1.5, 2.3), "frame")
        for x, y in ((-1005,-497), (545,-1699), (-1292,872), (1190,-576)):
            self.block("Corrugated metal trash can", (x, y, 28), (42, 42, 79), "steel", shape="Cylinder")
            self.detail((x, y, 69), (47, 47, 8), "galvanized", shape="Cylinder")
            self.detail((x, y, 75), (13, 4, 4), "steel")
        self.detail((-1325,-698,137), (8,8,294), "galvanized", shape="Cylinder")
        self.detail((-1325,-698,264), (110,5,28), "teal")
        self.model("Neptune Avenue letters", self.meshes["SM_SignStreet"], (-1325,-701,266), collision=False)
        for x, y in ((-1290,-576), (109,-1692), (1602,-618), (2705,-1697), (-1105,590)):
            self.slab("Street tree pit", x-59, x+59, y-47, y+47, SIDEWALK_Z + .6, 2, "soil", False)
            self.block("Street tree trunk", (x,y,141), (28,29,304), "wood", shape="Cylinder")
            for dx, dy, z, size in ((0,1,325,222), (57,27,279,163), (-51,-25,284,172), (18,-22,382,146)):
                self.detail((x+dx,y+dy,z), (size, size*.88,size*1.26), "leaf_a" if dx > 0 else "leaf_b",
                            shape="Sphere")
        for x in (-1435, -430, 560, 1940):
            for y in (-541, -1775):
                length = self.rng.uniform(14, 29)
                self.detail((x+self.rng.uniform(-40,40), y, SIDEWALK_Z+.3), (length, length*.7, .28), "paper",
                            (0,0,self.rng.uniform(-165,165)))
        for side in (-1, 1):
            self.between((-1335,-533,464+side*15), (-386, -536, 424+side*15), 2.05, "frame")
            self.between((-386,-536,424+side*15), (675,-538,468+side*15), 2.05, "frame")

    def atmosphere(self, collection, hour, minute, pillow):
        self.folder = "Street/06 Sky and time"
        sky = self.block("Shared sky dome", (0, 0, 0), (157000, 157000, 157000), "sky", collision=False, shape="Sphere")
        mesh = sky.get_component_by_class(ue.StaticMeshComponent)
        mesh.set_editor_properties({"cast_shadow": False, "affect_distance_field_lighting": False})
        sun = self.spawn(ue.DirectionalLight, "Sun and moon key light", (0,0,1300), (0,-13,334))
        component = sun.get_component_by_class(ue.DirectionalLightComponent)
        component.set_editor_properties({"mobility": ue.ComponentMobility.MOVABLE, "light_source_angle": 2.0,
                                         "dynamic_shadow_distance_movable_light": 8400.0,
                                         "dynamic_shadow_cascades": 3, "shadow_bias": .36})
        component.set_intensity(1.95)
        component.set_light_color(ue.LinearColor(1, .54, .27, 1))
        ambient = self.spawn(ue.SkyLight, "Street ambient skylight", (-1140, -973, 310))
        light = ambient.get_component_by_class(ue.SkyLightComponent)
        light.set_editor_properties({"mobility": ue.ComponentMobility.MOVABLE, "real_time_capture": True,
                                     "sky_distance_threshold": 18000.0, "cubemap_resolution": 128,
                                     "lower_hemisphere_is_black": True})
        light.set_intensity(.69)
        fog = self.spawn(ue.ExponentialHeightFog, "Industrial distance haze", (0, 0, -260))
        component = fog.get_component_by_class(ue.ExponentialHeightFogComponent)
        component.set_editor_properties({"fog_density": .012, "fog_height_falloff": .28, "start_distance": 810.0})
        component.set_fog_inscattering_color(ue.LinearColor(.155,.136,.116,1))
        manager = self.spawn(ue.PrologueTimeOfDay, "Shared clock and daylight")
        manager.set_editor_properties({"sun": sun, "ambient_sky": ambient, "sky_dome": sky, "street_lights": self.lights,
                                      "hour_hand": hour, "minute_hand": minute, "pillow_view": pillow,
                                      "street_light_parameters": collection, "opening_hour": 18.0, "clock_rate": 8.0})
        return manager

    def interior(self, bed):
        self.folder = "Street/07 Interior additions"
        clock_x, clock_y, clock_z = 127, 442.5, 200
        self.model("Wall-mounted quartz clock", self.meshes["SM_WallClock"], (clock_x, clock_y, clock_z), collision=False)
        hands = []
        for name, offset in (("SM_ClockHour", 5.8), ("SM_ClockMinute", 6.3)):
            hand = self.model(name, self.meshes[name], (clock_x, clock_y-offset, clock_z), collision=False)
            hand.get_component_by_class(ue.StaticMeshComponent).set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
            hands.append(hand)
        center, extent = bed.get_actor_bounds(False)
        pillow = self.spawn(ue.CameraActor, "First-person pillow pose", (center.x, center.y + extent.y*.65, 111),
                            (73, 44, -91), "SleepPillow")
        pillow.get_component_by_class(ue.CameraComponent).set_field_of_view(75)
        self.open_curtains()
        return *hands, pillow

    def open_curtains(self):
        mesh = ue.load_asset("/Game/Prologue/Furniture/Pack/Curtains_Double")
        if not mesh:
            return
        for pos, sideways, width in (((-20, 424, 30), False, 220), ((-361, -286, 30), True, 154)):
            x, y, z = pos
            for side in (-1, 1):
                off = side * (width / 2 - 11)
                panel = self.model("Open curtain panel", mesh, (x if sideways else x+off, y+off if sideways else y, z),
                                   yaw=90 if sideways else 0, collision=False)
                panel.set_actor_scale3d(V(.19, 1, 1))
            half = width / 2 + 8
            if sideways:
                self.between((x, y-half, 245), (x, y+half, 245), 2.4, "steel")
            else:
                self.between((x-half, y, 245), (x+half, y, 245), 2.4, "steel")

    def review_views(self):
        self.folder = "Street/08 Review cameras"
        self.camera("Street overview", "StreetReview", (-756,-1388,170), (-178,-438,248), 89)
        self.camera("View through desk window", "WindowReview", (-48,228,156), (8,454,170), 73)
        self.camera("Book kiosk detail", "KioskReview", (-803,-850,149), (-701,-508,128), 64)


def build_street(bed, reimport=()):
    materials, collection = create_street_materials(STAGE)
    builder = StreetBuilder(materials, street_models(reimport))
    builder.pavement()
    builder.apartment_facade()
    builder.blockfronts()
    builder.industrial_yard()
    builder.details()
    hour, minute, pillow = builder.interior(bed)
    time = builder.atmosphere(collection, hour, minute, pillow)
    builder.review_views()
    ue.log(f"STREET_GEOMETRY_OK {len(builder.batches)} detail batches, {len(builder.lights)} street light actors")
    return time
