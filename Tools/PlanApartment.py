"""Build the apartment layout from the supplied plan. World units are centimeters."""
import math
import unreal as ue

from ApartmentScene import make_material
from ImportFurniture import Placement, place

MAP_NAME = "L_DimaApartmentRefined"
PREVIOUS_MAP = "L_DimaApartmentModern"
DESK_VIEW = (26, -24)
KITCHEN_WEST = -765
BATH_EAST = 800
DOORS = {
    "KitchenDoor": ((-390, 165, 106), (-397.5, 219, 106), 0, -90),
    "BathDoor": ((390, -296, 106), (397.5, -242, 106), 0, 90),
    "FridgeDoor": ((-689.76, 401, 91.5), (-689.76, 436.7, 91.5), 180, 90),
}
DOOR_FOOTPRINTS = {"KitchenDoor": (15, 105), "BathDoor": (15, 105), "FridgeDoor": (12, 72)}

WALL_FACES = {"west_kitchen": (0, KITCHEN_WEST + 7), "east_main": (0, 383), "north_main": (1, 443),
              "west_main": (0, -383), "east_bath": (0, BATH_EAST - 7), "south_bath": (1, -443),
              "north_bath": (1, 103), "north_kitchen": (1, 443)}

# Each entry names the supporting surface, side of the model and designed gap in cm.
WALL_FITS = {
    "Bed": ("north_main", 1, 0), "TV stand": ("west_main", -1, 0),
    "Wardrobe shelves": ("east_main", 1, 0),
    "Kitchen sink": ("west_kitchen", -1, 0), "Cooker": ("west_kitchen", -1, 0),
    "Kitchen drawers": ("west_kitchen", -1, 0), "Fridge cabinet": ("west_kitchen", -1, 2),
    "Bathtub": ("north_bath", 1, 0), "Bathroom sink and tap": ("east_bath", 1, 0),
    "Bathroom mirror": ("east_bath", 1, 0), "Towel radiator": ("east_bath", 1, 0),
    "Toilet": ("south_bath", -1, 0), "Washing machine": ("south_bath", -1, 2),
    "Toilet paper holder": ("east_bath", 1, 0),
}


def furniture():
    living, kitchen, bath = "02 Main room", "03 Kitchen", "04 Bathroom"

    def item(name, label, xyz, size, yaw=0, tag="", folder=living):
        return Placement(name, label, "", xyz, size, yaw, tag, folder)

    yield item("Door_1", "Kitchen door", DOORS["KitchenDoor"][0], (15, 105, 207), tag="KitchenDoor", folder=kitchen)
    yield item("Door_2", "Bathroom door", DOORS["BathDoor"][0], (15, 105, 207), tag="BathDoor", folder=bath)
    yield item("Table_RoundLarge", "Writing desk", (-20, 342, 43), (213, 112, 86))
    yield item("Light_Desk", "Desk lamp", (-90, 365, 113), (25, 40, 54), 180, "DeskLamp")
    yield item("Bed_King", "Bed", (273, 337, 53), (148, 212, 106), tag="Bed")
    yield item("Couch_Large1", "Sofa facing TV", (46, -75, 48), (96, 220, 96), -90, "SofaSeat")
    yield item("Carpet_1", "Living room rug", (-46, -68, .8), (260, 275, 1.4))
    yield item("Table_RoundSmall", "Coffee table", (-115, -68, 23), (68, 95, 46))
    yield item("Drawer_2", "TV stand", (-356, -67, 29), (54, 135, 58), 90)
    yield item("Shelf_Large", "Wardrobe shelves", (354.5, -31, 98), (57, 141, 196), -90)
    yield item("Carpet_2", "Entry mat", (-194, -382, .6), (112, 57, 1))
    yield item("Light_Floor2", "Floor lamp", (140, -182, 79), (35, 35, 158), tag="FloorLamp")
    yield item("Houseplant_2", "Potted plant", (323, 95, 48), (42, 42, 96))
    yield item("Kitchen_FridgeCabinetShelved", "Fridge cabinet", DOORS["FridgeDoor"][0], (), DOORS["FridgeDoor"][2], folder=kitchen)
    yield item("Kitchen_FridgeDoors", "Fridge doors", DOORS["FridgeDoor"][0], (), DOORS["FridgeDoor"][2], "FridgeDoor", kitchen)
    for name, label, y, height in (("Kitchen_Sink", "Kitchen sink", 276, 109),
                                    ("Kitchen_Oven", "Cooker", 204, 89),
                                    ("Kitchen_3Drawers", "Kitchen drawers", 133, 89)):
        yield item(name, label, (KITCHEN_WEST + 45, y, height / 2), (76, 69, height), 90,
                   "KitchenTap" if name == "Kitchen_Sink" else "", kitchen)
    yield item("Table_RoundSmall2", "Kitchen table", (-554, 104, 37), (94, 86, 74), folder=kitchen)
    yield item("Chair_2", "Kitchen chair", (-546, 173, 46), (47, 47, 92), 180, "KitchenSeat", kitchen)
    yield item("Bathroom_Bathtub", "Bathtub", (532, 59.5, 32), (222, 87, 64), folder=bath)
    yield item("Bathroom_Sink", "Bathroom sink and tap", (BATH_EAST - 33.5, -111, 54), (53, 77, 108), -90, "Tap", bath)
    yield item("Bathroom_Mirror1", "Bathroom mirror", (BATH_EAST - 10.5, -111, 164), (7, 75, 82), -90, folder=bath)
    yield item("Bathroom_Towel", "Towel radiator", (BATH_EAST - 12, -248, 116), (10, 47, 65), -90, folder=bath)
    yield item("Bathroom_Toilet", "Toilet", (666, -402, 44), (58, 82, 88), 180, folder=bath)
    yield item("Bathroom_WashingMachine", "Washing machine", (448, -402, 47), (78, 78, 94), 180, folder=bath)
    yield item("Bathroom_ToiletPaper", "Toilet paper holder", (BATH_EAST - 13.5, -343, 99), (13, 26, 17), -90, folder=bath)
    yield item("Window_Large1", "Desk window", (-20, 450, 172), (220, 15, 125), folder="01 Architecture")
    yield item("Window_Large1", "Kitchen window", (-558, 40, 170), (152, 15, 120), 180, folder="01 Architecture")
    yield item("Window_Large1", "Side window", (-390, -286, 169), (15, 154, 124), -90, folder="01 Architecture")


def build_plan(meshes, materials):
    from ApartmentFixtures import add_crt, add_plumbing
    from ApartmentPhysics import configure_prop, configure_furniture, create_physical_materials
    from ApartmentLighting import build_lighting

    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    cube = ue.load_asset("/Engine/BasicShapes/Cube")
    cylinder = ue.load_asset("/Engine/BasicShapes/Cylinder")
    sphere = ue.load_asset("/Engine/BasicShapes/Sphere")
    v, r = ue.Vector, ue.Rotator
    root = "/Game/Prologue"
    physical_materials = create_physical_materials(root)
    for name, color, emission in (
        ("ink", (.031, .025, .019), 0), ("metal", (.11, .11, .09), 0),
        ("paper", (.72, .58, .36), 0),
        ("night", (.032, .063, .13), 1.35), ("lit", (.68, .35, .13), 2.2),
    ):
        materials[name] = make_material(root, "Plan_" + name, color, .67, emission)

    def prop(label, pos, size, material, folder="01 Architecture", tag="", shape=cube, collision=True):
        actor = actors.spawn_actor_from_class(ue.StaticMeshActor, v(*pos))
        actor.set_actor_label(label)
        actor.set_folder_path(ue.Name(folder))
        actor.set_actor_scale3d(v(*(n / 100 for n in size)))
        comp = actor.get_component_by_class(ue.StaticMeshComponent)
        comp.set_static_mesh(shape)
        comp.set_material(0, materials[material])
        if tag:
            actor.set_editor_property("tags", [ue.Name(tag)])
        configure_prop(actor, comp, physical_materials, material, collision, tag)
        return actor

    def wall(label, a, b, fixed, axis="x", bottom=0, top=280, material="plaster"):
        mid, z, length = (a + b) / 2, (bottom + top) / 2, b - a
        pos = (mid, fixed, z) if axis == "x" else (fixed, mid, z)
        size = (length, 14, top - bottom) if axis == "x" else (14, length, top - bottom)
        prop(label, pos, size, material + "_wall")
        if bottom == 0:
            trim_size = (length, 18, 10) if axis == "x" else (18, length, 10)
            prop("Baseboard", (*pos[:2], 5), trim_size, "wood")

    def opening(label, a, b, fixed, gap, axis="x", sill=0, lintel=213, material="plaster"):
        wall(label, a, gap[0], fixed, axis, material=material)
        wall(label, gap[1], b, fixed, axis, material=material)
        wall(label + " lintel", *gap, fixed, axis, lintel, 280, material)
        if sill:
            wall(label + " sill", *gap, fixed, axis, 0, sill, material)
            return

        def frame(part, along, across, z, width, depth, height, finish="oak"):
            pos = (along, fixed + across, z) if axis == "x" else (fixed + across, along, z)
            size = (width, depth, height) if axis == "x" else (depth, width, height)
            prop(label + " " + part, pos, size, finish, "01 Architecture/Door frames")

        start, end = gap
        mid = (start + end) / 2
        for edge, sign in ((start, 1), (end, -1)):
            # The jamb overlaps the wall. The casing covers the seam on both faces.
            frame("jamb", edge + sign * .8, 0, 106.5, 4.8, 15, 213)
            for face in (-8.3, 8.3):
                frame("casing", edge - sign * 1.2, face, 107.5, 5.8, 2.8, 215)
        frame("head", mid, 0, 212.2, 112, 15, 4.4)
        for face in (-8.3, 8.3):
            frame("head casing", mid, face, 214, 117, 2.8, 6)
        frame("threshold", mid, 0, .7, 112, 17, 1.4, "dark_metal")

    opening("Main north wall", -390, 390, 450, (-130, 90), sill=109, lintel=235)
    opening("Main west wall", -450, 40, -390, (-363, -209), "y", 106, 232)
    opening("Kitchen partition", 40, 450, -390, (109, 221), "y")
    opening("Main east wall", -450, 450, 390, (-352, -240), "y")
    wall("Kitchen north wall", KITCHEN_WEST, -390, 450)
    wall("Kitchen west wall", 40, 450, KITCHEN_WEST, "y", material="tile")
    opening("Kitchen south wall", KITCHEN_WEST, -390, 40, (-634, -482), sill=110, lintel=230)
    wall("Bath north wall", 390, BATH_EAST, 110, material="tile")
    wall("Bath east wall", -450, 110, BATH_EAST, "y", material="tile")
    wall("Bath south wall", 390, BATH_EAST, -450, material="tile")

    for label, x1, x2, y1, y2, finish in (
        ("Main room", -390, 390, -450, 450, "wood"),
        ("Kitchen", KITCHEN_WEST, -390, 40, 450, "tile"),
        ("Bathroom", 390, BATH_EAST, -450, 110, "tile"),
    ):
        columns, rows = math.ceil((x2 - x1) / 300), math.ceil((y2 - y1) / 300)
        width, depth = (x2 - x1) / columns, (y2 - y1) / rows
        for i in range(columns):
            for j in range(rows):
                x, y = x1 + (i + .5) * width, y1 + (j + .5) * depth
                for part, z, surface in (("floor", -7, finish), ("ceiling", 287, "plaster")):
                    prop(f"{label} {part} {i + 1}-{j + 1}", (x, y, z), (width, depth, 14), surface)

    instances = {}
    assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    lib = ue.MaterialEditingLibrary
    placed_furniture = {}
    for item in furniture():
        actor = place(item, meshes[item.model])
        placed_furniture[item.label] = actor
        component = actor.get_component_by_class(ue.StaticMeshComponent)
        if item.tag in DOORS:
            component.set_collision_profile_name(ue.Name("BlockAllDynamic"))
            component.set_editor_properties({"cast_shadow": True, "cast_dynamic_shadow": True})
        for index, slot in enumerate(meshes[item.model].get_editor_property("static_materials")):
            key = str(slot.get_editor_property("imported_material_slot_name"))
            original = slot.get_editor_property("material_interface")
            if not isinstance(original, ue.Material):
                continue
            finish, tint = furniture_finish(item.model, key, original, lib)
            if tint is None:
                component.set_material(index, materials[finish])
                continue
            label = f"MI_{item.model}_{index}_{finish}"
            if label not in instances:
                folder = f"{root}/ModernFinishes/Furniture"
                asset_path = f"{folder}/{label}"
                instance = ue.load_asset(asset_path) if assets.does_asset_exist(asset_path) else None
                if instance is None:
                    instance = ue.AssetToolsHelpers.get_asset_tools().create_asset(
                        label, folder, ue.MaterialInstanceConstant, ue.MaterialInstanceConstantFactoryNew())
                    lib.set_material_instance_parent(instance, materials[finish])
                    lib.set_material_instance_vector_parameter_value(instance, "Tint", tint)
                    lib.update_material_instance(instance)
                    if not assets.save_loaded_asset(instance, False):
                        raise RuntimeError(f"Could not save {label}")
                instances[label] = instance
            component.set_material(index, instances[label])
        configure_furniture(actor, component, item, mesh=meshes[item.model],
                            props=prop, physical_materials=physical_materials)

    living = "02 Main room"
    add_living_details(prop, living, cylinder, sphere)
    for tag, label, x, y, w, h in (
        ("Report", "Patrol report", -43, 312, 21.6, 28),
        ("Newspaper", "Industrial Herald", 35, 325, 42, 34),
    ):
        prop(label, (x, y, 86.26), (w, h, .5), "paper", living, tag)
        for n in range(6):
            prop(label + " print", (x, y - 8 + n * 3.2, 86.52), (w * .73, .23, .02), "ink", living, tag)
    add_crt(prop, materials)
    add_plumbing(prop, materials, placed_furniture, bath_east=BATH_EAST)

    prop("Northern sky", (0, 865, 200), (1600, 10, 640), "night", "05 Exterior")
    prop("Western sky", (-1020, -185, 190), (10, 1400, 620), "night", "05 Exterior")
    prop("Kitchen courtyard backdrop", (-565, -149, 180), (290, 10, 475), "night", "05 Exterior")
    for x in (-400, -20, 350):
        prop("Factory silhouette", (x, 720, 107), (236, 60, 214), "ink", "05 Exterior")
        for dx in (-70, -26, 20, 66):
            prop("Factory window", (x + dx, 686, 150), (24, 5, 15), "lit", "05 Exterior")

    build_lighting(actors, prop, materials, placed_furniture["Floor lamp"])
    start = actors.spawn_actor_from_class(ue.PlayerStart, v(-132, 245, 98), r(0, 0, DESK_VIEW[0]))
    start.set_actor_label("Dima stands beside the desk")
    camera = actors.spawn_actor_from_class(ue.CameraActor, v(-43, 250, 135), r(0, -38, 90))
    camera.set_actor_label("Seated report camera")
    camera.set_editor_property("tags", [ue.Name("ReportView")])
    camera.get_component_by_class(ue.CameraComponent).set_field_of_view(65)
    for label, pos, pitch, yaw in (("SofaSeat", (35, -75, 119), -6, 180),
                                   ("DeskSeat", (-20, 239, 124), -11, 90),
                                   ("KitchenSeat", (-546, 174, 121), -9, -90)):
        seat = actors.spawn_actor_from_class(ue.CameraActor, v(*pos), r(0, pitch, yaw))
        seat.set_actor_label(label + " camera")
        seat.set_folder_path(ue.Name("07 Seating viewpoints"))
        seat.set_editor_property("tags", [ue.Name(label + "View")])
        seat.get_component_by_class(ue.CameraComponent).set_field_of_view(78)


def furniture_finish(model, slot, original, lib):
    key = slot.lower()
    if model.startswith("Carpet_"):
        return "fabric", None
    if model == "Table_RoundLarge" or "wood" in key or (model.startswith("Door_") and "metal" not in key):
        return "oak", None
    if "metal" in key or "chrome" in key:
        return "dark_metal", None
    base = lib.get_material_property_input_node(original, ue.MaterialProperty.MP_BASE_COLOR)
    color = base.get_editor_property("constant") if isinstance(base, ue.MaterialExpressionConstant3Vector) else None
    if color is not None:
        color = ue.LinearColor(*(min(1.0, max(.16, c ** .55 * 1.42)) for c in (color.r, color.g, color.b)), 1)
    if model.startswith(("Couch_", "Bed_", "Bathroom_Towel")):
        return "fabric", color
    if model.startswith(("Bathroom_", "Kitchen_Sink")):
        return "ceramic", color
    return "painted", color


def add_living_details(prop, folder, cylinder, sphere):
    def detail(label, pos, size, finish, shape=None, yaw=0, pitch=0):
        options = {"shape": shape} if shape else {}
        actor = prop(label, pos, size, finish, folder, collision=False, **options)
        if yaw or pitch:
            actor.set_actor_rotation(ue.Rotator(0, pitch, yaw), False)
        return actor

    # Chair faces the desk (+Y). The wheel bottoms lie at the finished floor height.
    x, y = -20, 235
    prop("Task chair seat", (x, y, 47), (52, 48, 11), "fabric", folder, "DeskSeat", sphere)
    prop("Task chair backrest", (x, y - 22, 76), (49, 10, 53), "fabric", folder, "DeskSeat", sphere)
    detail("Task chair lumbar support", (x, y - 24, 52), (11, 8, 24), "dark_metal")
    detail("Task chair gas lift", (x, y, 26), (9, 9, 34), "dark_metal", cylinder)
    for side in (-1, 1):
        detail("Task chair arm support", (x + side * 23, y, 55), (4, 5, 15), "dark_metal")
        detail("Task chair arm pad", (x + side * 24, y, 64), (8, 27, 4), "fabric")
    for angle in range(0, 360, 72):
        dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        detail("Task chair spoke", (x + 13 * dx, y + 13 * dy, 8), (27, 5, 4), "dark_metal", yaw=angle)
        detail("Task chair caster", (x + 26 * dx, y + 26 * dy, 5), (10, 7, 10), "dark_metal", sphere)

    # Bookcase backs onto the north wall, leaving the window and desk clear.
    x, y = -251, 425
    for side in (-1, 1):
        prop("Bookcase side", (x + side * 50, y, 98), (3, 36, 196), "oak_wall", folder)
    prop("Bookcase back", (x, 442, 98), (97, 2, 196), "oak_wall", folder)
    for level, z in enumerate((5, 43, 81, 119, 157, 195)):
        prop("Bookcase shelf", (x, y, z), (97, 36, 2), "oak", folder)
        if level == 5:
            break
        cursor = x - 44 + level * 2
        for i in range(11 - level % 3):
            width = 3 + (level * 5 + i * 3) % 5
            height = 17 + (level * 7 + i * 5) % 13
            finish = ("book_sage", "book_rust", "paper", "ink", "fabric")[(i + level) % 5]
            detail("Book spine", (cursor + width / 2, y - 4, z + 1 + height / 2),
                   (width, 22, height), finish)
            cursor += width + 1.5

    detail("Pencil", (-9, 355, 86.55), (15, .85, .9), "oak", yaw=-18)
    detail("Memo sheet", (54, 364, 86.14), (17, 22, .22), "paper", yaw=11)
    detail("Coffee table coaster", (-118, -78, 46.35), (11, 11, .65), "oak", cylinder)
    detail("Coffee mug", (-118, -78, 51.2), (8, 8, 9), "tile", cylinder)
    detail("Lamp plug", (-99, 365, 86.8), (4, 2, 1.4), "dark_metal")
    for start, end in zip(points := ((-99, 365, 86.45), (-107, 375, 86.45), (-100, 383, 86.45),
                                    (-85, 389, 86.45), (-68, 396, 86.45), (-68, 397, 4),
                                    (-68, 403, .5), (-68, 442, .5)), points[1:]):
        a, b = ue.Vector(*start), ue.Vector(*end)
        delta = b - a
        midpoint = a + delta * .5
        horizontal = math.hypot(delta.x, delta.y)
        detail("Desk lamp cable", (midpoint.x, midpoint.y, midpoint.z), (.7, .7, delta.length() + .5),
               "dark_metal", cylinder, math.degrees(math.atan2(delta.y, delta.x)),
               math.degrees(math.atan2(delta.z, horizontal)) - 90)


def check_furniture_fit(actors):
    def bounds(actor):
        origin, extent = actor.get_actor_bounds(False)
        return origin - extent, origin + extent

    for label, (surface, sign, wanted_gap) in WALL_FITS.items():
        axis, face = WALL_FACES[surface]
        edge = bounds(actors[label])[sign > 0]
        distance = sign * (face - (edge.x, edge.y)[axis])
        if abs(distance - wanted_gap) > 2:
            raise RuntimeError(f"{label}: expected {wanted_gap} cm from {surface}, got {distance:.2f}")
        ue.log(f"FURNITURE_FIT {label}: {distance:.2f} cm from {surface}")

    wall_mounted = {"Bathroom mirror", "Towel radiator", "Toilet paper holder"}
    openings = {"Front door", "Kitchen door", "Bathroom door", "Fridge doors",
                "Desk window", "Kitchen window", "Side window"}
    for label, actor in actors.items():
        if label in wall_mounted | openings | {"Desk lamp"}:
            continue
        low, _ = bounds(actor)
        if abs(low.z) > 1.5:
            raise RuntimeError(f"{label}: base is {low.z:.2f} cm from the floor")
    _, desk_top = bounds(actors["Writing desk"])
    lamp_base, _ = bounds(actors["Desk lamp"])
    if abs(lamp_base.z - desk_top.z) > 1:
        raise RuntimeError("Desk lamp must rest on the writing desk.")

    # With the doors open, each room must retain a straight path for the player capsule.
    for tag, (closed, hinge, _, swing) in DOORS.items():
        thickness, width = DOOR_FOOTPRINTS[tag]
        sine = math.sin(math.radians(swing))
        opened = (hinge[0] - sine * (closed[1] - hinge[1]), hinge[1] + sine * (closed[0] - hinge[0]))
        if tag == "FridgeDoor":
            north = WALL_FACES["north_kitchen"][1]
            if opened[1] + thickness / 2 > north or opened[0] - width / 2 < WALL_FACES["west_kitchen"][1]:
                raise RuntimeError("Open fridge doors intersect the kitchen walls.")
            _, high = bounds(actors["Fridge cabinet"])
            if not 5 <= north - high.y <= 12:
                raise RuntimeError("Fridge side clearance at the corner is out of range.")
            continue
        if abs(opened[1] - closed[1]) - thickness / 2 < 38:
            raise RuntimeError(f"{tag}: open position blocks the center of the doorway.")
    ue.log(f"FURNITURE_FIT_OK {len(actors)} furniture actors")
