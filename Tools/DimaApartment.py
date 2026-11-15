"""Geometry and fixture placement for Dima's two-room apartment (centimeters)."""
import unreal as ue

from ApartmentScene import V, R, actors, make_material, mesh, sphere

MAP_NAME = "L_DimaApartmentExpanded"
STANDING = (165, 65, 98)
# Center of each slab in its closed and open positions. Detail meshes follow the slab.
DOORS = {
    "BedroomDoor": ((-420, 145, 106), (-473, 92, 106), 90),
    "BathDoor": ((-420, -205, 106), (-473, -258, 106), 90),
    "FridgeDoor": ((658, 242, 92), (626, 210, 92), 90),
}


def build_apartment(root):
    palette = {
        "wall": (0.50, 0.42, 0.30), "trim": (0.33, 0.25, 0.16),
        "wood": (0.24, 0.107, 0.044), "wood_light": (0.34, 0.167, 0.069),
        "wood_dark": (0.10, 0.046, 0.023), "linen": (0.63, 0.61, 0.51),
        "moss": (0.14, 0.24, 0.17), "rust": (0.34, 0.084, 0.049),
        "paper": (0.82, 0.74, 0.55), "ink": (0.045, 0.035, 0.025),
        "tile": (0.30, 0.44, 0.43), "grout": (0.16, 0.20, 0.19),
        "porcelain": (0.72, 0.76, 0.73), "chrome": (0.39, 0.43, 0.46),
        "brass": (0.49, 0.28, 0.09), "water": (0.14, 0.45, 0.63),
        "night": (0.035, 0.105, 0.20), "shade": (0.72, 0.41, 0.15),
    }
    materials = {
        name: make_material(root, "Home_" + name, color, 0.21 if name in ("chrome", "porcelain", "water") else 0.72,
                            {"night": 1.4, "shade": 2.2, "water": 0.55}.get(name, 0))
        for name, color in palette.items()
    }
    cylinder = ue.load_asset("/Engine/BasicShapes/Cylinder")
    cone = ue.load_asset("/Engine/BasicShapes/Cone")

    def prop(folder, label, xyz, size, material, tag=None, shape=mesh, yaw=0, parent=None, movable=False):
        actor = actors.spawn_actor_from_class(ue.StaticMeshActor, V(*xyz), R(0, 0, yaw))
        actor.set_actor_label(label)
        actor.set_folder_path(ue.Name(folder))
        actor.set_actor_scale3d(V(*(n / 100 for n in size)))
        comp = actor.get_component_by_class(ue.StaticMeshComponent)
        comp.set_static_mesh(shape)
        comp.set_material(0, materials[material])
        if parent or movable:
            comp.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
        if parent:
            rule = ue.AttachmentRule.KEEP_WORLD
            actor.attach_to_actor(parent, ue.Name(), rule, rule, rule, False)
        if tag:
            actor.set_editor_property("tags", [ue.Name(tag)])
        return actor

    def light(folder, label, xyz, rgb, intensity, radius, tag=None):
        actor = actors.spawn_actor_from_class(ue.PointLight, V(*xyz))
        actor.set_actor_label(label)
        actor.set_folder_path(ue.Name(folder))
        comp = actor.get_component_by_class(ue.PointLightComponent)
        comp.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
        comp.set_editor_property("use_inverse_squared_falloff", False)
        comp.set_intensity(intensity)
        comp.set_attenuation_radius(radius)
        comp.set_light_color(ue.LinearColor(*rgb, 1))
        comp.set_editor_property("source_radius", 17)
        if tag:
            actor.set_editor_property("tags", [ue.Name(tag)])
        return actor

    def wall(label, a, b, fixed, axis="x", low=0, high=280, finish="wall"):
        length, mid, z = b - a, (a + b) / 2, (low + high) / 2
        pos = (mid, fixed, z) if axis == "x" else (fixed, mid, z)
        size = (length, 14, high - low) if axis == "x" else (14, length, high - low)
        prop("01 Architecture/Walls", label, pos, size, finish)
        if low == 0:
            base_size = (length, 18, 12) if axis == "x" else (18, length, 12)
            prop("01 Architecture/Trim", label + " baseboard", (*pos[:2], 6), base_size, "trim")

    def partition(label, low, high, x, gap):
        wall(label + " south", low, gap[0], x, "y")
        wall(label + " north", gap[1], high, x, "y")
        wall(label + " header", *gap, x, "y", low=212)
        for y in (gap[0] + 2, gap[1] - 2):
            prop("01 Architecture/Trim", label + " jamb", (x, y, 105), (22, 5, 210), "trim")

    wall("West exterior", -390, 390, -700, "y")
    wall("East exterior", -390, 390, 740, "y")
    wall("South exterior", -700, 740, -390)
    windows = [(-620, -490), (-85, 113), (495, 635)]
    edge = -700
    for first, last in windows:
        wall("North exterior", edge, first, 390)
        wall("Window lower wall", first, last, 390, high=105)
        wall("Window upper wall", first, last, 390, low=227)
        prop("01 Architecture/Windows", "Painted sill", ((first + last) / 2, 381, 105), (last - first + 14, 34, 8), "linen")
        prop("01 Architecture/Windows", "Window mullion", ((first + last) / 2, 390, 165), (7, 12, 122), "linen")
        prop("01 Architecture/Windows", "Window crossbar", ((first + last) / 2, 390, 176), (last - first, 12, 6), "linen")
        edge = last
    wall("North exterior", edge, 740, 390)
    partition("Bedroom wall", -50, 390, -420, (87, 203))
    partition("Bathroom wall", -390, -50, -420, (-263, -147))
    partition("Living room wall", -390, 390, -210, (-115, 30))
    partition("Kitchen wall", -390, 390, 420, (-180, -40))
    wall("Bedroom and bathroom divider", -700, -420, -50)
    prop("01 Architecture", "Ceiling", (20, 0, 287), (1460, 800, 14), "linen")
    prop("01 Architecture", "Floor slab", (20, 0, -10), (1460, 800, 18), "grout")

    for room, left, right, bottom, top in (
        ("Living", -210, 420, -390, 390), ("Hall", -420, -210, -390, 390),
        ("Bedroom", -700, -420, -50, 390),
    ):
        for y in range(bottom, top, 20):
            shade = "wood_light" if (y // 20) % 5 in (1, 3) else "wood"
            prop("01 Architecture/Floors", room + " floorboard", ((left + right) / 2, y + 10, -1),
                 (right - left, 19.7, 2), shade)
    for left, right, bottom, top in ((-700, -420, -390, -50), (420, 740, -390, 390)):
        for x in range(left, right, 40):
            for y in range(bottom, top, 40):
                length = min(40, top - y)
                tone = "tile" if (x // 40 + y // 40) % 2 else "porcelain"
                prop("01 Architecture/Floors", "Vinyl tile", (x + 20, y + length / 2, -1), (39, length - 1, 2), tone)

    hall = "02 Hall"
    prop(hall, "Front door", (-320, -382, 109), (111, 14, 218), "wood_dark", "Exit")
    prop(hall, "Front door handle", (-277, -372, 102), (17, 9, 8), "brass", "Exit")
    prop(hall, "Entry mat", (-320, -310, 1), (104, 60, 2), "rust")
    prop(hall, "Coat rack rail", (-407, -53, 169), (8, 94, 16), "wood")
    for y in (-86, -55, -25):
        prop(hall, "Brass coat peg", (-398, y, 170), (20, 7, 8), "brass", shape=sphere)
    prop(hall, "Hanging coat", (-394, -56, 115), (19, 42, 96), "moss", shape=sphere)
    light(hall, "Entry light", (-320, -245, 254), (1, .77, .54), 5.1, 400)
    light(hall, "Hall light", (-320, 128, 253), (1, .82, .65), 3.9, 365)

    for tag, label, folder in (("BedroomDoor", "Bedroom door", "04 Bedroom"), ("BathDoor", "Bathroom door", "06 Bathroom")):
        closed, _, _ = DOORS[tag]
        x, y, z = closed
        slab = prop(folder, label, closed, (5, 106, 207), "wood", tag, movable=True)
        for px in (x - 3, x + 3):
            prop(folder, "Recessed upper door panel", (px, y, 144), (2, 77, 90), "wood_light", tag, parent=slab)
            prop(folder, "Recessed lower door panel", (px, y, 57), (2, 77, 56), "wood_light", tag, parent=slab)
            prop(folder, "Door knob", (px + (-5 if px < x else 5), y + 42, 105),
                 (9, 9, 9), "brass", tag, sphere, parent=slab)

    living = "03 Living room"
    prop(living, "Writing desk top", (263, 173, 84), (220, 90, 8), "wood")
    prop(living, "Desk drawer", (340, 165, 58), (54, 77, 43), "wood_dark")
    prop(living, "Desk drawer pull", (340, 124, 62), (25, 5, 4), "brass")
    for y in (135, 208):
        prop(living, "Desk leg", (159, y, 41), (8, 8, 83), "wood_dark")
    for tag, name, x, y, width, depth in (
        ("Report", "Report", 225, 144, 31, 24), ("Newspaper", "Newspaper", 330, 149, 43, 35),
    ):
        prop(living, name + " paper", (x, y, 89), (width, depth, 2), "paper", tag)
        for n in range(6):
            line = width * (.71 if n < 5 else .48)
            prop(living, name + " printed line", (x, y - 8 + n * 3, 90.1), (line, 0.65, .4), "ink", tag)
        if tag == "Newspaper":
            prop(living, "Newspaper masthead", (x, y + 12, 90.2), (35, 2.6, .6), "ink", tag)
            prop(living, "Newspaper photo", (x + 13, y - 8, 90.4), (9, 11, 1), "trim", tag)
    prop(living, "Desk lamp base", (346, 209, 92), (30, 27, 7), "brass", "DeskLamp", cylinder)
    prop(living, "Desk lamp stem", (346, 209, 120), (5, 5, 54), "brass", "DeskLamp", cylinder)
    prop(living, "Desk lamp shade", (346, 209, 149), (42, 42, 31), "shade", "DeskLamp", cone)
    light(living, "Switchable desk lamp", (337, 200, 130), (1, .68, .39), 5.8, 305, "DeskLampLight")
    prop(living, "Desk chair seat", (247, 77, 45), (49, 42, 10), "moss", shape=sphere)
    prop(living, "Desk chair back", (247, 56, 71), (48, 10, 56), "wood_dark")
    for x in (227, 267):
        for y in (60, 93):
            prop(living, "Chair leg", (x, y, 22), (5, 5, 44), "wood_dark", shape=cylinder)

    prop(living, "Sofa frame", (105, -333, 22), (227, 84, 44), "wood_dark")
    prop(living, "Sofa upholstered back", (105, -365, 56), (228, 32, 99), "moss")
    for x in (32, 105, 178):
        prop(living, "Sofa seat cushion", (x, -329, 48), (69, 74, 25), "moss", shape=sphere)
        prop(living, "Sofa back cushion", (x, -350, 78), (67, 29, 53), "moss", shape=sphere)
    for x in (-5, 215):
        prop(living, "Sofa arm", (x, -331, 55), (22, 89, 59), "moss", shape=sphere)
    prop(living, "Throw pillow", (178, -330, 72), (40, 22, 36), "rust", shape=sphere, yaw=17)
    prop(living, "Living room rug", (105, -182, 0.9), (265, 155, 2), "rust")
    for x in (-23, 233):
        prop(living, "Woven rug border", (x, -182, 2), (4, 149, 1), "linen")
    prop(living, "Coffee table top", (106, -163, 49), (118, 63, 7), "wood_dark")
    for x in (58, 153):
        for y in (-183, -142):
            prop(living, "Coffee table leg", (x, y, 24), (5, 5, 48), "wood_dark", shape=cylinder)
    prop(living, "Television cabinet", (68, 317, 35), (118, 57, 68), "wood_dark")
    prop(living, "CRT television body", (68, 319, 96), (87, 64, 59), "ink")
    prop(living, "Curved CRT glass", (58, 284, 97), (58, 10, 42), "tile", shape=sphere)
    for z in (85, 102):
        prop(living, "TV dial", (102, 286, z), (12, 8, 12), "chrome", shape=sphere)
    light(living, "Living room ambient", (72, -88, 250), (1, .83, .64), 5.4, 510)
    light(living, "Living room window light", (15, 358, 215), (.40, .62, 1), 5.4, 450)

    bedroom = "04 Bedroom"
    for x in (-655, -531):
        for y in (141, 330):
            prop(bedroom, "Bed foot", (x, y, 17), (10, 10, 34), "wood_dark", "Bed", cylinder)
    prop(bedroom, "Bed frame", (-593, 241, 31), (147, 212, 26), "wood_dark", "Bed")
    prop(bedroom, "Headboard", (-593, 347, 68), (150, 10, 103), "wood", "Bed")
    for x in range(-652, -533, 17):
        prop(bedroom, "Headboard slat", (x, 340, 82), (9, 5, 62), "wood_light", "Bed")
    prop(bedroom, "Mattress", (-593, 240, 48), (143, 204, 24), "linen", "Bed")
    prop(bedroom, "Quilt", (-593, 213, 62), (147, 148, 9), "moss", "Bed")
    for y in range(155, 282, 15):
        prop(bedroom, "Quilt stitched seam", (-593, y, 66.6), (139, .8, .55), "tile", "Bed")
    for x in (-626, -561):
        prop(bedroom, "Pillow", (x, 312, 64), (55, 37, 16), "linen", "Bed", sphere)
    prop(bedroom, "Nightstand", (-465, 326, 29), (52, 49, 57), "wood")
    prop(bedroom, "Alarm clock body", (-466, 325, 66), (26, 16, 15), "ink")
    prop(bedroom, "Alarm clock display", (-466, 316, 67), (17, 3, 7), "rust")
    prop(bedroom, "Wardrobe body", (-642, 5, 104), (98, 74, 208), "wood_dark")
    for x in (-666, -618):
        prop(bedroom, "Wardrobe panel", (x, 43, 105), (45, 6, 193), "wood")
        prop(bedroom, "Wardrobe handle", (x, 48, 108), (4, 7, 23), "brass")
    light(bedroom, "Bedroom ceiling light", (-552, 144, 256), (1, .80, .61), 4.8, 400)
    light(bedroom, "Bedroom window light", (-555, 360, 216), (.43, .65, 1), 3.3, 320)

    kitchen = "05 Kitchen"
    for y in (-205, -135, -65, 5, 75, 145):
        prop(kitchen, "Cabinet", (703, y, 43), (66, 68, 86), "moss")
        prop(kitchen, "Cabinet raised panel", (668, y, 42), (6, 57, 67), "tile")
        prop(kitchen, "Cabinet handle", (662, y, 65), (7, 18, 4), "brass")
    prop(kitchen, "Laminate counter", (699, -32, 88), (78, 422, 8), "linen")
    prop(kitchen, "Cooktop", (695, -137, 95), (65, 65, 6), "ink")
    for x in (680, 709):
        for y in (-152, -122):
            prop(kitchen, "Cooktop ring", (x, y, 99), (21, 21, 4), "chrome", shape=cylinder)
            prop(kitchen, "Cooktop center", (x, y, 102), (16, 16, 3), "ink", shape=cylinder)
    prop(kitchen, "Fridge cabinet", (698, 242, 93), (67, 64, 182), "porcelain")
    prop(kitchen, "Fridge dark seal", (663, 242, 92), (4, 63, 176), "ink")
    prop(kitchen, "Fridge shelf opening", (660.6, 242, 92), (1, 54, 163), "tile")
    for z in (51, 95, 137):
        prop(kitchen, "Fridge shelf edge", (657, 242, z), (7, 55, 2), "linen")
    fridge = prop(kitchen, "Fridge door", DOORS["FridgeDoor"][0], (7, 64, 175), "porcelain", "FridgeDoor", movable=True)
    prop(kitchen, "Fridge seam", (653, 242, 126), (3, 63, 2), "ink", "FridgeDoor", parent=fridge)
    prop(kitchen, "Fridge handle", (650, 262, 106), (8, 7, 41), "chrome", "FridgeDoor", parent=fridge)
    prop(kitchen, "Kitchen table", (534, 233, 76), (100, 102, 8), "wood")
    for x in (494, 572):
        for y in (195, 273):
            prop(kitchen, "Kitchen table leg", (x, y, 38), (6, 6, 76), "wood_dark")
    light(kitchen, "Kitchen ceiling light", (575, 15, 249), (1, .86, .65), 6.0, 460)

    bath = "06 Bathroom"
    prop(bath, "Bathtub apron", (-657, -263, 27), (73, 179, 54), "porcelain")
    prop(bath, "Bathtub interior", (-657, -263, 55), (55, 155, 5), "tile")
    for x in (-688, -626):
        prop(bath, "Bathtub long rim", (x, -263, 61), (12, 179, 8), "porcelain")
    for y in (-348, -177):
        prop(bath, "Bathtub end rim", (-657, y, 61), (67, 9, 8), "porcelain")
    prop(bath, "Bath towel", (-611, -320, 91), (6, 50, 58), "linen")
    prop(bath, "Toilet tank", (-530, -363, 70), (52, 29, 53), "porcelain")
    prop(bath, "Toilet bowl", (-530, -328, 35), (49, 67, 48), "porcelain", shape=sphere)
    prop(bath, "Toilet seat", (-530, -318, 58), (48, 51, 8), "linen", shape=sphere)
    prop(bath, "Sink pedestal", (-562, -79, 37), (33, 27, 75), "porcelain", shape=cylinder)
    prop(bath, "Sink basin", (-562, -83, 81), (73, 54, 24), "porcelain", "Tap", sphere)
    prop(bath, "Sink interior", (-562, -91, 93), (48, 32, 3), "tile", "Tap", sphere)
    prop(bath, "Tap stem", (-562, -64, 105), (7, 7, 26), "chrome", "Tap", cylinder)
    prop(bath, "Tap spout", (-562, -73, 117), (7, 22, 7), "chrome", "Tap")
    for x in (-581, -543):
        prop(bath, "Tap knob", (x, -68, 98), (12, 12, 12), "chrome", "Tap", sphere)
    flow = prop(bath, "Tap water stream", (-562, -82, 104), (3, 3, 22), "water", "TapWater", cylinder, movable=True)
    flow.set_actor_hidden_in_game(True)
    flow.set_actor_enable_collision(False)
    prop(bath, "Mirror frame", (-562, -58, 173), (74, 6, 83), "trim")
    prop(bath, "Mirror glass", (-562, -62, 173), (67, 3, 76), "chrome")
    light(bath, "Bathroom ceiling light", (-554, -220, 254), (.76, .87, 1), 5.3, 410)

    prop("07 Exterior", "Night backdrop", (20, 800, 200), (1800, 12, 650), "night")
    for x, width in ((-540, 260), (-30, 390), (480, 260)):
        prop("07 Exterior", "Industrial skyline", (x, 658, 115), (width, 80, 230), "ink")
        prop("07 Exterior", "Chimney", (x + 40, 655, 262), (25, 25, 160), "ink", shape=cylinder)
        for offset in (-70, -20, 30, 80):
            prop("07 Exterior", "Lit factory window", (x + offset, 615, 145), (26, 5, 13), "shade")

    start = actors.spawn_actor_from_class(ue.PlayerStart, V(*STANDING), R(0, 0, 27))
    start.set_actor_label("Dima stands beside the desk")
    camera = actors.spawn_actor_from_class(ue.CameraActor, V(244, 89, 130), R(0, -35, 108))
    camera.set_actor_label("Seated report camera")
    camera.get_component_by_class(ue.CameraComponent).set_field_of_view(64)
