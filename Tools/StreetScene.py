"""Build the 1994 street around the apartment without loading a second world."""
from contextlib import contextmanager
from pathlib import Path
import re

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
BLENDER_MESHES = ("SM_BookKiosk", "SM_WallClock", "SM_ClockHour", "SM_ClockMinute", "SM_Sedan94",
                  "SM_SignStreet", "SM_NeighborhoodGrocery", "SM_NeighborhoodPharmacy", "SM_NeighborhoodPrecinct",
                  "SM_NeighborhoodFlea", "SM_NeighborhoodBar", "SM_NeighborhoodPark", "SM_PressBundles",
                  "SM_FactoryCard", "SM_CourtyardBirch", "SM_CourtyardShrub")


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
                    material_name = re.sub(r"[^a-zA-Z0-9_]", "_", key)
                    material = make_material(ROOT, "Prop_" + material_name, palette[key], roughness)
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
        self.folder = "Street/01 Pavement"
        self.turn = 0

    @contextmanager
    def rotated(self, yaw):
        previous, self.turn = self.turn, yaw
        try:
            yield
        finally:
            self.turn = previous

    def world_pose(self, pos, rotation):
        if self.turn == 90:
            x, y, z = pos
            return (-y, x, z), (rotation[0], rotation[1], rotation[2] + 90)
        return pos, rotation

    def spawn(self, actor_class, label, pos=(0, 0, 0), rotation=(0, 0, 0), tag=None):
        position, angles = self.world_pose(pos, rotation)
        actor = self.actors.spawn_actor_from_class(actor_class, V(*position), R(*angles))
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

    def detail(self, pos, dimensions, material, rotation=(0, 0, 0), shape="Cube", *, facade=False):
        position, angles = self.world_pose(pos, rotation)
        cell = (int(position[0]//2400), int(position[1]//2400))
        if facade:
            cull_distances = (14800, 18600)
        elif max(dimensions) <= 170 and self.folder != "Street/07 Interior additions":
            cull_distances = (5700, 7600)
        else:
            cull_distances = (0, 0)
        key = (self.folder, material, shape, cell, cull_distances)
        if key not in self.batches:
            actor = self.spawn(ue.StreetMeshInstances, f"Detail instances · {material} · {shape} · {cell}")
            actor.set_actor_location(V(cell[0] * 2400, cell[1] * 2400, 0), False, False)
            actor.set_actor_rotation(R(), False)
            component = actor.get_editor_property("instances")
            component.set_static_mesh(self.shapes[shape])
            component.set_material(0, self.materials[material])
            if cull_distances[1]:
                component.set_cull_distances(*cull_distances)
            self.batches[key] = component
        transform = ue.Transform(location=V(*position), rotation=R(*angles),
                                 scale=V(*(entry / 100 for entry in dimensions)))
        self.batches[key].add_instance(transform, True)

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
        self.detail((x, y + face * 8, z), (width, 3.3, height), "lit_window" if lit else "dark_glass", facade=True)
        for dx in (-width/2, 0, width/2):
            self.detail((x + dx, y + face * 11, z), (4.7, 5, height), "frame", facade=True)
        for dz in (-height/2, -14, height/2):
            self.detail((x, y + face * 11, z + dz), (width + 5, 5, 4.8), "frame", facade=True)
        self.detail((x, y + face * 13, z - height/2 - 7), (width + 25, 21, 11), "stone", facade=True)
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
        board = {"SM_NeighborhoodGrocery": "warning_paint", "SM_NeighborhoodPharmacy": "precinct_green",
                 "SM_NeighborhoodBar": "frame"}[sign]
        self.detail((x, y + face * 25, 242), (width - 34, 35, 54), board)
        lettering = self.model("Fascia lettering", self.meshes[sign], (x, y + face * 45, 243),
                               180 if face > 0 else 0, False)
        lettering.set_actor_scale3d(V(2.25, 1, 1.55))
        if sign == "SM_NeighborhoodPharmacy":
            for offset in (-.38, .38):
                for length, height in ((34, 10), (10, 34)):
                    self.detail((x + width*offset, y + face*44, 243), (length, 3, height), "faded_white")
        for index in range(15):
            stripe_width = (width - 47) / 15
            self.detail((x + stripe_width * (index-7), y + face * 69, 200),
                        (stripe_width + .1, 107, 5.2), shade if index % 4 < 3 else "faded_white", (22*face,0,0))
        self.detail((x, y + face * 120, 179), (width - 47, 7, 21), shade)
        for dx in (-.26, .25):
            self.detail((x + width*dx, y + face*29, 113), (88, 2.1, 49), "paper")
            for dz in (-16, 0, 16):
                self.detail((x + width*dx, y + face*31, 113+dz), (71, 1, 2.1), shade)

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

def build_street(bed, reimport=(), time=None):
    from StreetArtwork import add_street_art
    from StreetNeighborhood import assemble_neighborhood

    materials, collection = create_street_materials(STAGE)
    add_street_art(materials, collection, STAGE)
    builder = StreetBuilder(materials, street_models(reimport))
    assemble_neighborhood(builder)
    if time:
        time.modify()
        time.set_editor_properties({"street_lights": builder.lights, "street_light_parameters": collection})
    else:
        hour, minute, pillow = builder.interior(bed)
        time = builder.atmosphere(collection, hour, minute, pillow)
    ambient = time.get_editor_property("ambient_sky").get_component_by_class(ue.SkyLightComponent)
    ambient.set_editor_property("cubemap_resolution", 64)
    ue.log(f"STREET_GEOMETRY_OK {len(builder.batches)} detail batches, {len(builder.lights)} street light actors")
    return time
