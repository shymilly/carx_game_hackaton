"""Blockout geometry, materials, lighting and clue placement for L_Apartment."""
import math
import unreal as ue

V = ue.Vector
R = ue.Rotator
actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
mesh = ue.load_asset("/Engine/BasicShapes/Cube")
sphere = ue.load_asset("/Engine/BasicShapes/Sphere")
matlib = ue.MaterialEditingLibrary


def make_material(root, name, color, roughness=0.75, glow=0):
    path = f"{root}/Materials/M_{name}"
    material = ue.load_asset(path) if assets.does_asset_exist(path) else None
    if material:
        return material
    material = ue.AssetToolsHelpers.get_asset_tools().create_asset(
        f"M_{name}", f"{root}/Materials", ue.Material, ue.MaterialFactoryNew()
    )
    base = matlib.create_material_expression(material, ue.MaterialExpressionConstant3Vector, -450, -90)
    base.set_editor_property("constant", ue.LinearColor(*color, 1))
    matlib.connect_material_property(base, "", ue.MaterialProperty.MP_BASE_COLOR)
    value = matlib.create_material_expression(material, ue.MaterialExpressionConstant, -450, 80)
    value.set_editor_property("r", roughness)
    matlib.connect_material_property(value, "", ue.MaterialProperty.MP_ROUGHNESS)
    if glow:
        emission = matlib.create_material_expression(material, ue.MaterialExpressionConstant3Vector, -450, 250)
        emission.set_editor_property("constant", ue.LinearColor(*(c * glow for c in color), 1))
        matlib.connect_material_property(emission, "", ue.MaterialProperty.MP_EMISSIVE_COLOR)
    matlib.recompile_material(material)
    assets.save_loaded_asset(material)
    return material


def build_scene(root, dima=False):
    palette = {
        "plaster": ((0.29, 0.24, 0.18),),
        "olive": ((0.09, 0.14, 0.10),),
        "walnut": ((0.12, 0.055, 0.023),),
        "floor": ((0.16, 0.078, 0.037),),
        "metal": ((0.042, 0.046, 0.048), 0.42),
        "brass": ((0.42, 0.23, 0.07), 0.38),
        "paper": ((0.83, 0.68, 0.43),),
        "red": ((0.28, 0.035, 0.025),),
        "cloth": ((0.11, 0.15, 0.13),),
        "skin": ((0.43, 0.24, 0.16),),
        "sky": ((0.023, 0.09, 0.16), 1, 1.9),
        "lamp": ((0.86, 0.44, 0.14), 0.7, 3),
    }
    materials = {name: make_material(root, name, *properties) for name, properties in palette.items()}

    def prop(name, xyz, size, material, tag=None, yaw=0, shape=mesh):
        actor = actors.spawn_actor_from_class(ue.StaticMeshActor, V(*xyz), R(0, 0, yaw))
        actor.set_actor_label(name)
        actor.set_actor_scale3d(V(*(d / 100 for d in size)))
        comp = actor.get_component_by_class(ue.StaticMeshComponent)
        comp.set_static_mesh(shape)
        comp.set_material(0, materials[material])
        if tag:
            actor.set_editor_property("tags", [ue.Name(tag)])
        return actor

    def lamp(name, xyz, color, intensity, radius):
        actor = actors.spawn_actor_from_class(ue.PointLight, V(*xyz))
        actor.set_actor_label(name)
        comp = actor.get_component_by_class(ue.PointLightComponent)
        comp.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
        comp.set_editor_property("use_inverse_squared_falloff", False)
        comp.set_intensity(intensity)
        comp.set_attenuation_radius(radius)
        comp.set_light_color(ue.LinearColor(*color, 1))
        comp.set_editor_property("source_radius", 12)

    prop("Ceiling", (0, 0, 295), (840, 620, 18), "plaster")
    prop("West wall", (-420, 0, 150), (16, 620, 300), "plaster")
    prop("South wall", (0, -310, 150), (840, 16, 300), "plaster")
    prop("East wall", (420, 0, 150), (16, 620, 300), "olive")
    for y in range(-300, 301, 20):
        prop(f"Floor board {y}", (0, y, -6), (840, 19.7, 12), "floor")
    prop("Window wall left", (-288, 310, 150), (264, 16, 300), "plaster")
    prop("Window wall right", (232, 310, 150), (376, 16, 300), "plaster")
    prop("Window wall below", (-56, 310, 48), (200, 16, 96), "olive")
    prop("Window wall above", (-56, 310, 262), (200, 16, 76), "plaster")
    prop("Window sill", (-56, 305, 98), (210, 32, 8), "walnut")
    prop("Window mullion", (-56, 310, 162), (7, 10, 130), "walnut")
    prop("Window crossbar", (-56, 310, 169), (202, 10, 6), "walnut")
    prop("Twilight", (-70, 665, 188), (1000, 10, 490), "sky")
    prop("Factory", (-40, 595, 65), (300, 100, 130), "metal")
    for x in (-132, -48, 46):
        prop("Factory chimney", (x, 580, 140), (22, 28, 130 + x * 0.25), "metal")
        prop("Factory window", (x, 543, 106), (32, 5, 12), "lamp")

    prop("Hall partition", (-243, -121, 150), (18, 372, 300), "olive")
    prop("Hall doorway header", (-243, 126, 253), (18, 120, 96), "walnut")
    prop("Hall partition north", (-243, 245, 150), (18, 120, 300), "olive")
    prop("Apartment exit", (-420, -148, 115), (20, 117, 230), "walnut", "Exit")
    prop("Exit handle", (-405, -181, 102), (7, 24, 5), "brass", "Exit")
    for xyz, size in (((0, -300, 12), (825, 6, 18)), ((410, 0, 12), (6, 596, 18)),
                      ((0, 300, 12), (825, 6, 18))):
        prop("Baseboard", xyz, size, "walnut")

    prop("Desk top", (263, 173, 84), (220, 90, 10), "walnut")
    for x in (165, 361):
        for y in (137, 209):
            prop("Desk leg", (x, y, 41), (9, 9, 83), "walnut")
    document = "Report" if dima else "Note"
    second_document = "Newspaper" if dima else "Folder"
    prop(document, (225, 144, 90), (32, 24, 1.4), "paper", document, -10)
    for i, width in enumerate((18, 20, 13)):
        prop("Ink on document", (225, 139 + i * 4, 91), (width, 1.2, 0.3), "metal", document, -10)
    prop(second_document, (330, 149, 91), (43, 33, 5), "paper" if dima else "red", second_document, 8)
    prop("Document label", (330, 149, 94), (24, 13, 1), "metal" if dima else "paper", second_document, 8)
    prop("Radio case", (239, 198, 107), (70, 26, 34), "metal", "Radio")
    prop("Radio dial", (244, 184, 112), (49, 2, 8), "lamp", "Radio")
    prop("Antenna", (263, 203, 139), (2.8, 2.8, 49), "brass", "Radio")
    prop("Desk lamp base", (344, 206, 94), (31, 24, 11), "metal")
    prop("Desk lamp stem", (344, 209, 121), (5, 5, 46), "metal")
    prop("Desk lamp shade", (344, 196, 145), (43, 38, 13), "lamp")
    prop("Chair seat", (247, 75, 44), (58, 52, 8), "walnut")
    prop("Chair back", (247, 53, 74), (58, 7, 60), "walnut")
    for x in (224, 270):
        for y in (55, 94):
            prop("Chair leg", (x, y, 20), (6, 6, 41), "walnut")

    if not dima:
        prop("Map frame", (408, -98, 190), (8, 208, 115), "walnut", "Map")
        prop("Map of the USSR", (403, -98, 190), (3, 192, 101), "paper", "Map")
        for i in range(8):
            y = -164 + i * 17
            z = 177 + round(math.sin(i) * 18)
            prop("Map contour", (401, y, z), (0.7, 22, 38 - abs(i - 4) * 4), "olive", "Map")
    prop("Photo frame", (122, -300, 165), (55, 9, 44), "walnut", "Photo")
    prop("Photograph", (122, -294, 165), (46, 3, 35), "paper", "Photo")
    for i in range(4):
        prop("Figure in photo", (105 + i * 11, -292, 161), (7, 1, 21), "metal", "Photo")
    prop("Sofa base", (-56, -231, 30), (218, 95, 60), "cloth")
    prop("Sofa back", (-56, -273, 60), (218, 23, 119), "cloth")
    for x in (-154, 44):
        prop("Sofa arm", (x, -226, 58), (23, 89, 63), "cloth")
    prop("Rug", (28, -53, 0.6), (268, 169, 1.1), "red")
    for x in (-96, 151):
        prop("Rug border", (x, -53, 1.3), (3, 157, 0.6), "brass")

    if dima:
        start = actors.spawn_actor_from_class(ue.PlayerStart, V(165, 65, 98), R(0, 0, 55))
        start.set_actor_label("Dima stands beside the desk")
        camera = actors.spawn_actor_from_class(ue.CameraActor, V(244, 89, 130), R(0, -35, 108))
        camera.set_actor_label("Seated report camera")
        camera.get_component_by_class(ue.CameraComponent).set_field_of_view(64)
    else:
        # Ivan is a lit silhouette in the vestibule.
        prop("Ivan coat", (-353, 243, 116), (60, 29, 82), "metal", "Ivan", shape=sphere)
        prop("Ivan head", (-353, 241, 172), (24, 23, 30), "skin", "Ivan", shape=sphere)
        for x in (-367, -339):
            prop("Ivan leg", (x, 246, 39), (19, 21, 78), "metal", "Ivan")
            prop("Ivan shoulder", (x, 240, 143), (30, 29, 31), "metal", "Ivan", shape=sphere)
        start = actors.spawn_actor_from_class(ue.PlayerStart, V(-332, -170, 98), R(0, 0, 90))
        start.set_actor_label("Dima starts in the vestibule")
        camera = actors.spawn_actor_from_class(ue.CameraActor, V(-325, 57, 154), R(0, -1, 98.5))
        camera.set_actor_label("Ivan briefing camera")
        camera.get_component_by_class(ue.CameraComponent).set_field_of_view(55)

    lamp("Hall tungsten", (-342, 19, 234), (1, 0.61, 0.34), 4.0, 390)
    lamp("Desk tungsten", (331, 193, 135), (1, 0.65, 0.32), 4.4, 280)
    lamp("Window fill", (-60, 267, 192), (0.26, 0.52, 1), 4.6, 465)
    lamp("Living room bounce", (104, -116, 218), (0.73, 0.53, 0.39), 2.2, 500)
    if not dima:
        lamp("Ivan rim", (-335, 272, 215), (0.35, 0.55, 1), 2.5, 235)
