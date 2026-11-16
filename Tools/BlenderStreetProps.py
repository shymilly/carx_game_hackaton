"""Create editable street props, then export centimeter OBJ meshes for Unreal."""
from math import cos, pi, sin, tau
from pathlib import Path
from random import Random

import bpy
from mathutils import Vector


OUTPUT = Path(__file__).resolve().parents[1] / "SourceAssets" / "Street"
PALETTE = {
    "KioskPaint": (.090, .187, .175), "KioskDark": (.026, .040, .039), "Oxide": (.146, .078, .042),
    "Cream": (.71, .62, .43), "PrintPaper": (.73, .701, .60), "FadedRed": (.35, .069, .045),
    "PaperGreen": (.11, .23, .15), "PaperBlue": (.077, .16, .29), "Ochre": (.45, .31, .11),
    "Wood": (.178, .095, .049), "Glass": (.58, .72, .68), "ClockBlack": (.023, .021, .019),
    "ScreenFrame": (.082, .081, .072), "ClockFace": (.77, .737, .658), "Ink": (.029, .025, .020),
    "CarPaint": (.102, .235, .24), "CarGlass": (.050, .087, .12), "Rubber": (.022, .023, .024),
    "Steel": (.43, .45, .45), "Chrome": (.33, .36, .36), "Headlight": (.7, .63, .50),
    "TailLight": (.41, .032, .015), "Indicator": (.59, .24, .036), "Plate": (.67, .64, .49),
}


def prepare():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    for key, color in PALETTE.items():
        material = bpy.data.materials.new(key)
        material.diffuse_color = (*color, 1)
        material.use_nodes = True
        shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
        shader.inputs["Base Color"].default_value = (*color, 1)
        shader.inputs["Roughness"].default_value = .3 if key in ("CarPaint", "CarGlass", "Chrome") else .73
        shader.inputs["Metallic"].default_value = .72 if key in ("Chrome", "Steel") else 0
    OUTPUT.mkdir(parents=True, exist_ok=True)


def assign(obj, name, material):
    obj.name = name
    obj.data.materials.append(bpy.data.materials[material])
    return obj


def box(name, loc, dims, material, bevel=0, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = assign(bpy.context.object, name, material)
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = rotation
    if bevel:
        modifier = obj.modifiers.new("Rounded edges", "BEVEL")
        modifier.width, modifier.segments = bevel, 2
    return obj


def cylinder(name, loc, radius, length, material, vertices=40):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length,
                                       location=loc, rotation=(pi / 2, 0, 0))
    obj = assign(bpy.context.object, name, material)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def mesh(name, vertices, faces, material):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    return assign(obj, name, material)


def text(name, value, pos, size, material, width=None, bold=True):
    bpy.ops.object.text_add(location=pos, rotation=(pi / 2, 0, pi))
    obj = bpy.context.object
    obj.data.body, obj.data.size = value, size
    obj.data.align_x, obj.data.align_y = "CENTER", "CENTER"
    obj.data.extrude, obj.data.resolution_u = .0006, 4
    obj.data.font = bpy.data.fonts.load("C:/Windows/Fonts/" + ("arialbd.ttf" if bold else "arial.ttf"), check_existing=True)
    bpy.context.view_layer.update()
    if width and obj.dimensions.x > width:
        obj.scale *= width / obj.dimensions.x
    bpy.ops.object.convert(target="MESH")
    return assign(bpy.context.object, name, material)


def kiosk():
    rng = Random(1994)
    box("Concrete pad", (0, 0, .045), (2.64, 1.78, .09), "ScreenFrame", .016)
    box("Rear timber wall", (0, -.81, 1.19), (2.52, .13, 2.23), "KioskPaint", .02)
    for side in (-1, 1):
        box("Side wall", (side * 1.23, 0, 1.19), (.12, 1.53, 2.23), "KioskPaint", .02)
        box("Front post", (side * 1.20, .79, 1.23), (.13, .12, 2.23), "KioskDark", .01)
        for row in range(13):
            box("Side siding seam", (side * 1.294, -.03, .16 + .16 * row), (.011, 1.49, .018), "KioskDark")
    box("Lower counter wall", (0, .81, .48), (2.29, .09, .78), "KioskPaint", .01)
    for index in range(11):
        box("Shutter seam", (-1.05 + .21 * index, .86, .48), (.014, .009, .75), "KioskDark")
    box("Counter ledge", (0, .82, .91), (2.45, .29, .09), "Wood", .018)
    for z in (1.00, 1.43, 1.86, 2.15):
        box("Bookcase shelf", (0, .59, z), (2.32, .30, .033), "Wood", .004)
        box("Horizontal sash", (0, .844, z + .014), (2.29, .05, .038), "KioskDark", .005)
    for index in range(7):
        box("Vertical glazing bars", (-1.12 + index * .373, .84, 1.575), (.028, .046, 1.14), "KioskDark", .004)
    box("Front display glass", (0, .817, 1.571), (2.25, .014, 1.134), "Glass")
    for row, z in enumerate((1.026, 1.456, 1.886)):
        x = -1.08
        while x < 1.04:
            width = min(rng.uniform(.046, .09), 1.11 - x)
            height = rng.uniform(.13, .265 if row == 2 else .33)
            color = rng.choice(("PrintPaper", "FadedRed", "PaperGreen", "PaperBlue", "Ochre", "Cream"))
            box("Book spine", (x + width / 2, .736, z + height / 2), (width, .079, height), color, .002)
            if rng.randrange(4) != 0:
                box("Spine title stripe", (x + width / 2, .778, z + height - .039),
                    (width * .65, .003, .012), "Cream" if color != "PrintPaper" else "Oxide")
            x += width + rng.uniform(.006, .022)
    box("Framed fascia", (0, .805, 2.305), (2.53, .19, .32), "KioskDark", .02)
    box("Fascia inset", (0, .907, 2.312), (2.36, .021, .244), "KioskPaint", .012)
    text("Kiosk fascia lettering", "КНИГИ  /  ПРЕССА", (0, .922, 2.32), .18, "Cream", 2.17)
    box("Roof edge", (0, 0, 2.526), (2.71, 1.88, .105), "KioskDark", .027)
    for index in range(20):
        x = -1.235 + index * .13
        box("Striped fixed canopy", (x, .92, 2.503), (.131, .69, .046),
            "KioskPaint" if index % 4 < 3 else "Cream", .004, (-.125, 0, 0))
    box("Canvas drop", (0, 1.273, 2.416), (2.63, .032, .093), "KioskPaint", .006)
    for x in (-1.18, 1.18):
        box("Awning bracket", (x, .96, 2.36), (.033, .31, .044), "Oxide", .004, (-.36, 0, 0))
    box("Bottom sign rail", (0, .867, .21), (2.28, .022, .058), "Oxide", .004)


def clock():
    cylinder("Quartz clock casing", (0, .021, 0), .211, .042, "ClockBlack", 64)
    cylinder("Inset cream dial", (0, .045, 0), .184, .008, "ClockFace", 64)
    cylinder("Centre metal cap", (0, .063, 0), .008, .009, "Steel", 18)
    for index in range(60):
        angle = index * tau / 60
        tick = (-sin(angle) * .173, .051, cos(angle) * .173)
        box("Dial tick", tick, (.0032 if index % 5 == 0 else .0014, .0007, .012 if index % 5 == 0 else .0055),
            "Ink", rotation=(0, -angle, 0))
    for number in range(1, 13):
        angle = number * tau / 12
        text("Dial numeral", str(number), (-sin(angle) * .140, .052, cos(angle) * .140), .045, "Ink")
    text("Quartz mark", "QUARTZ", (0, .052, -.073), .0155, "Ink", bold=False)


def hour_hand():
    box("Hour hand", (0, 0, .046), (.018, .0038, .112), "ClockBlack", .0016)


def minute_hand():
    box("Minute hand", (0, 0, .074), (.009, .0035, .165), "ClockBlack", .0013)


def sedan():
    # Boxy early-1990s American sedan with steel wheels and separate trim slots.
    rows = ((-2.44,.825,.43,.79), (-2.29,.91,.30,.86), (-1.70,.94,.29,.89),
            (1.74,.93,.29,.88), (2.24,.905,.31,.82), (2.43,.79,.43,.73))
    vertices = [(x, side * width, z) for x, width, bottom, top in rows
                for side, z in ((-1, bottom), (1, bottom), (1, top), (-1, top))]
    faces = [(3, 2, 1, 0), (20, 21, 22, 23)]
    for row in range(len(rows) - 1):
        for side in range(4):
            a, b = 4 * row + side, 4 * row + (side + 1) % 4
            faces.append((a, b, b + 4, a + 4))
    mesh("Pressed sedan shell", vertices, faces, "CarPaint")
    window = [(-1.42,-.82,.89), (-1.42,.82,.89), (1.37,.82,.89), (1.37,-.82,.89),
              (-.86,-.72,1.42), (-.86,.72,1.42), (.65,.71,1.42), (.65,-.71,1.42)]
    mesh("Green-tinted windscreen and side glass", window, [(4,5,1,0),(5,6,2,1),(6,7,3,2),(7,4,0,3)], "CarGlass")
    box("Sedan roof", (-.101, 0, 1.442), (1.58, 1.484, .099), "CarPaint", .044)
    for side in (-1, 1):
        for x in (-1.52, 1.48):
            cylinder("Tire", (x, side * .85, .361), .363, .24, "Rubber", 32)
            cylinder("Steel wheel trim", (x, side * .979, .361), .217, .027, "Steel", 24)
            cylinder("Centre hub cap", (x, side * .998, .361), .092, .024, "Chrome", 18)
        for x in (-.88, .12, .70):
            lean = .36 if x > .6 else -.26 if x < -.5 else 0
            box("Door pillar", (x, side * .76, 1.15), (.079, .103, .56), "CarPaint", .008, (0, lean, 0))
        for x in (-.56, .42):
            box("Chrome door handle", (x, side * .936, .782), (.166, .027, .04), "Chrome", .008)
            box("Door seam", (x + .19, side * .936, .54), (.01, .008, .54), "Rubber")
        box("Side rub strip", (0, side * .934, .547), (4.51, .037, .055), "Rubber", .011)
        box("Sideview mirror", (.78, side * .956, 1.01), (.221, .179, .10), "CarPaint", .027)
        box("Front headlight", (2.407, side * .566, .682), (.07, .43, .128), "Headlight", .017)
        box("Turn indicator", (2.403, side * .801, .669), (.065, .13, .092), "Indicator", .01)
        box("Tail cluster", (-2.429, side * .561, .681), (.08, .46, .115), "TailLight", .012)
    for x in (-2.427, 2.427):
        box("Rubber bumper", (x, 0, .419), (.20, 1.74, .188), "Rubber", .041)
        box("Bright trim", (x * 1.038, 0, .482), (.029, 1.70, .021), "Chrome", .008)
    box("Rectangular radiator grille", (2.44, 0, .672), (.037, .614, .145), "Rubber", .009)
    for row in range(4):
        box("Grille bright bar", (2.462, 0, .617 + .034 * row), (.015, .59, .013), "Chrome", .004)
    box("Rear number plate", (-2.481, 0, .60), (.023, .31, .153), "Plate", .009)


def sign(label, message, width):
    text(label, message, (0, 0, 0), .28, "Cream", width)


def press_bundles():
    rng = Random(491)
    for column, center in enumerate((-.47, -.17, .15, .46)):
        height = .035 + column % 3 * .016
        angle = rng.uniform(-.06, .06)
        box("Folded newspaper stack", (center, 0, height / 2), (.27, .33, height), "PrintPaper", .001,
            (0, 0, angle))
        for j in range(3):
            box("Uneven folded edges", (center, -.164, .009 + j * .008), (.266, .003, .0018), "Oxide")
        box("Newspaper masthead block", (center, .098, height + .0008), (.218, .045, .002), "FadedRed")
        box("Halftone photo", (center + .052, -.01, height + .0008), (.092, .091, .002), "PaperBlue")
        for row in range(8):
            box("Printed columns", (center - .067, .047 - row * .02, height + .0008), (.07, .004, .002), "Ink")
        tab = box("Folded cardboard price ticket", (center, -.13, height + .014), (.099, .07, .004), "Cream")
        tab.rotation_euler.x = .34


def backdrop_card():
    panel = mesh("Single two-triangle billboard", [(0, .5, -.5), (0, -.5, -.5), (0, -.5, .5), (0, .5, .5)],
                 [(0, 1, 2, 3)], "ScreenFrame")
    uvs = panel.data.uv_layers.new(name="Card")
    for corner, coordinate in zip(uvs.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        corner.uv = coordinate


def nature(model, base):
    source = Path.home() / "Desktop" / "assets" / "nature" / "OBJ" / (model + ".obj")
    if not source.is_file():
        base()
        return
    bpy.ops.wm.obj_import(filepath=str(source), forward_axis="NEGATIVE_Z", up_axis="Y")
    subjects = tuple(bpy.context.selected_objects)
    vertices = [obj.matrix_world @ Vector(corner) for obj in subjects for corner in obj.bound_box]
    bottom, top = min(v.z for v in vertices), max(v.z for v in vertices)
    height = 1 / max(.01, top - bottom)
    for obj in subjects:
        obj.location *= height
        obj.location.z -= bottom * height
        obj.scale *= height


def simple_tree():
    box("Trunk", (0, 0, .32), (.065, .065, .64), "Wood")
    for x, y, z, size in ((0, 0, .74, .36), (.10, 0, .70, .24), (-.09, .04, .83, .24)):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=size / 2, location=(x,y,z))
        assign(bpy.context.object, "Leaf crown", "PaperGreen")


def export(name, create):
    previous = set(bpy.data.objects)
    create()
    generated = [obj for obj in bpy.data.objects if obj not in previous]
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in generated:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
        obj.select_set(True)
    bpy.ops.wm.obj_export(filepath=str(OUTPUT / (name + ".obj")), export_selected_objects=True,
                          export_normals=True, export_uv=True, export_materials=True, export_triangulated_mesh=False,
                          global_scale=100, forward_axis="Y", up_axis="Z")
    return collection


prepare()
features = (("SM_BookKiosk", kiosk, (0, 0, 0)), ("SM_WallClock", clock, (-3.8, 0, 1.1)),
            ("SM_ClockHour", hour_hand, (-3.8, .058, 1.1)), ("SM_ClockMinute", minute_hand, (-3.8, .063, 1.1)),
            ("SM_Sedan94", sedan, (5, -.04, 0)),
            ("SM_SignDeli", lambda: sign("Deli", "BALTIC DELI  /  ПРОДУКТЫ", 4.6), (-.8, 4, 1)),
            ("SM_SignPharmacy", lambda: sign("Pharmacy", "PHARMACY   /   АПТЕКА", 4.6), (4.7, 4, 1)),
            ("SM_SignAegis", lambda: sign("Factory", "AEGIS  •  SHIPPING", 5.8), (0, 4, 2)),
            ("SM_SignStreet", lambda: sign("Street", "NEPTUNE AV", .95), (0, 4, .5)),
            ("SM_NeighborhoodGrocery", lambda: sign("Grocery", "ПРОДУКТЫ", 4.8), (-6, 4, 1)),
            ("SM_NeighborhoodPharmacy", lambda: sign("Pharmacy", "АПТЕКА", 4), (-1, 4, 1)),
            ("SM_NeighborhoodPrecinct", lambda: sign("Precinct", "POLICE   •   60 PRECINCT", 6), (5, 4, 1)),
            ("SM_NeighborhoodFlea", lambda: sign("Market", "БАРАХОЛКА", 3.8), (-5, 6, 1)),
            ("SM_NeighborhoodBar", lambda: sign("Bar", "БАР   МАЯК", 4.2), (1, 6, 1)),
            ("SM_NeighborhoodPark", lambda: sign("Park", "NEPTUNE PLAYGROUND", 2.7), (5, 6, 1)),
            ("SM_PressBundles", press_bundles, (0, 0, 1.03)),
            ("SM_FactoryCard", backdrop_card, (0, 8, 1)),
            ("SM_CourtyardBirch", lambda: nature("BirchTree_2", simple_tree), (3, 8, 0)),
            ("SM_CourtyardShrub", lambda: nature("Bush_2", simple_tree), (5, 8, 0)))
for name, create, display in features:
    for obj in export(name, create).objects:
        obj.location += Vector(display)
bpy.ops.object.select_all(action="DESELECT")
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.shading.color_type = "MATERIAL"
        area.spaces.active.region_3d.view_location = Vector((0, 0, 1.15))
        area.spaces.active.region_3d.view_distance = 7.5
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "StreetProps1994.blend"))
