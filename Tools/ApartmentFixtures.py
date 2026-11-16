"""Model the period CRT, shower enclosure, and animated plumbing for Dima's apartment."""
from pathlib import Path
from math import cos, sin, tau, sqrt, atan2, degrees, hypot

import unreal as ue

from ApartmentScene import make_material


ROOT = "/Game/Prologue/ApartmentFixtures"
LIVING = "02 Main room/Television"
BATH = "04 Bathroom/Plumbing"
KITCHEN = "03 Kitchen/Plumbing"


def save_asset(asset):
    if not ue.get_editor_subsystem(ue.EditorAssetSubsystem).save_loaded_asset(asset, False):
        raise RuntimeError(f"Could not save {asset.get_path_name()}")


def dimensions_material(name, color, roughness, metallic=0):
    material = make_material(ROOT, name, color, roughness)
    library = ue.MaterialEditingLibrary
    channel = ue.MaterialProperty.MP_METALLIC
    if metallic and not library.get_material_property_input_node(material, channel):
        metal = library.create_material_expression(material, ue.MaterialExpressionConstant, -400, 250)
        metal.set_editor_property("r", metallic)
        library.connect_material_property(metal, "", channel)
        library.recompile_material(material)
        save_asset(material)
    return material


def transmissive_material(name, color, roughness, face_opacity, edge_opacity, flowing=False):
    material = make_material(ROOT, name, color, roughness)
    library = ue.MaterialEditingLibrary
    if library.get_material_property_input_node(material, ue.MaterialProperty.MP_OPACITY):
        return material
    lighting = ue.TranslucencyLightingMode
    material.set_editor_properties({"blend_mode": ue.BlendMode.BLEND_TRANSLUCENT,
                                    "translucency_lighting_mode": (lighting.TLM_SURFACE_PER_PIXEL_LIGHTING
                                                                  if flowing else lighting.TLM_SURFACE),
                                    "two_sided": not flowing})

    fresnel = library.create_material_expression(material, ue.MaterialExpressionFresnel, -550, -80)
    fresnel.set_editor_properties({"exponent": 3.0, "base_reflect_fraction": .02})
    opacity = library.create_material_expression(material, ue.MaterialExpressionLinearInterpolate, 280, 0)
    opacity.set_editor_properties({"const_a": face_opacity, "const_b": edge_opacity})
    library.connect_material_expressions(fresnel, "", opacity, "Alpha")
    if flowing:
        # Scroll narrow highlights down the jet. The two scales keep the pattern from reading as fixed stripes.
        uv = library.create_material_expression(material, ue.MaterialExpressionTextureCoordinate, -950, 240)
        travel = library.create_material_expression(material, ue.MaterialExpressionPanner, -760, 240)
        travel.set_editor_property("speed_y", .62)
        library.connect_material_expressions(uv, "", travel, "Coordinate")
        phase = library.create_material_expression(material, ue.MaterialExpressionDotProduct, -560, 240)
        frequency = library.create_material_expression(material, ue.MaterialExpressionConstant2Vector, -760, 400)
        frequency.set_editor_properties({"r": 3.0, "g": 8.0})
        library.connect_material_expressions(travel, "", phase, "A")
        library.connect_material_expressions(frequency, "", phase, "B")
        ripples = library.create_material_expression(material, ue.MaterialExpressionSine, -360, 240)
        library.connect_material_expressions(phase, "", ripples, "")
        gain = library.create_material_expression(material, ue.MaterialExpressionMultiply, -160, 200)
        gain.set_editor_property("const_b", .09)
        library.connect_material_expressions(ripples, "", gain, "A")
        shift = library.create_material_expression(material, ue.MaterialExpressionAdd, 65, 45)
        shift.set_editor_property("const_b", face_opacity)
        library.connect_material_expressions(gain, "", shift, "A")
        library.connect_material_expressions(shift, "", opacity, "A")

    library.connect_material_property(opacity, "", ue.MaterialProperty.MP_OPACITY)
    library.recompile_material(material)
    save_asset(material)
    return material


def imported_mesh(name, vertices, faces, smooth=False):
    path = f"{ROOT}/Meshes/{name}"
    model = ue.load_asset(path) if ue.EditorAssetLibrary.does_asset_exist(path) else None
    if model:
        return model
    source = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())) / "SourceAssets" / "Fixtures"
    source.mkdir(parents=True, exist_ok=True)
    obj = source / f"{name}.obj"
    lines = [f"o {name}"]
    # The OBJ translator reflects Y. Reverse winding to preserve outward facing surfaces.
    lines.extend(f"v {x:.6f} {-y:.6f} {z:.6f}" for x, y, z in vertices)
    uvs = [(y * .01, z * .01) for _, y, z in vertices]
    lines.extend(f"vt {u:.6f} {1 - v:.6f}" for u, v in uvs)
    normals = []
    average = [[0.0, 0.0, 0.0] for _ in vertices]
    for face in faces:
        a, b, c = [vertices[i] for i in face[:3]]
        ux, uy, uz = (end - start for start, end in zip(a, b))
        vx, vy, vz = (end - start for start, end in zip(a, c))
        normal = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        normals.append(normal)
        if smooth:
            for i in face:
                for axis, value in enumerate(normal):
                    average[i][axis] += value
    for nx, ny, nz in average if smooth else normals:
        length = sqrt(nx * nx + ny * ny + nz * nz)
        if length < 1e-6:
            raise RuntimeError(f"Degenerate normal in {name}")
        lines.append(f"vn {nx / length:.6f} {-ny / length:.6f} {nz / length:.6f}")
    for index, face in enumerate(faces, 1):
        lines.append("f " + " ".join(f"{i + 1}/{i + 1}/{i + 1 if smooth else index}" for i in reversed(face)))
    obj.write_text("\n".join(lines) + "\n", encoding="utf-8")

    task = ue.AssetImportTask()
    task.set_editor_properties({"filename": str(obj), "destination_path": f"{ROOT}/Meshes",
                                "automated": True, "save": True})
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    model = ue.load_asset(path)
    if not isinstance(model, ue.StaticMesh):
        raise RuntimeError(f"Could not import {name}")
    ue.log(f"FIXTURE_MESH {name} vertices={len(vertices)} faces={len(faces)}")
    return model


def rounded_profile(x, width, height, corner):
    vertices = []
    for quadrant in range(4):
        angle = (quadrant + .5) * tau / 4
        y = (width / 2 - corner) * (1 if cos(angle) > 0 else -1)
        z = (height / 2 - corner) * (1 if sin(angle) > 0 else -1)
        for step in range(5):
            angle = (quadrant + step / 4) * tau / 4
            vertices.append((x, y + corner * cos(angle), z + corner * sin(angle)))
    return vertices


def join_profiles(n, profiles):
    return [tuple(ring * n + j for ring, j in ((i, j), (i, (j + 1) % n),
                                               (i + 1, (j + 1) % n), (i + 1, j)))
            for i in range(profiles - 1) for j in range(n)]


def crt_meshes():
    shell_profiles = [(-43, 52, 32, 4), (-39, 64, 38, 5), (-10, 77, 52, 6),
                      (0, 79, 54, 6), (4, 75, 50, 5)]
    bezel_profiles = [(3, 75, 49, 5), (5, 73, 47, 5)]
    case_parts = []
    for name, profiles in (("SM_CRTCabinet", shell_profiles), ("SM_CRTBezel", bezel_profiles)):
        verts = [p for profile in profiles for p in rounded_profile(*profile)]
        face_count = len(verts) // len(profiles)
        faces = join_profiles(face_count, len(profiles))
        faces += [tuple(range(face_count - 1, -1, -1)), tuple(range(len(verts) - face_count, len(verts)))]
        case_parts.append(imported_mesh(name, verts, faces))

    rings = [(6.2, 52, 39, 5), (7.7, 46, 34.5, 4.5), (8.8, 29, 22, 3), (9.3, 13, 10, 1.5)]
    verts = [p for profile in rings for p in rounded_profile(*profile)]
    ring_size = len(verts) // len(rings)
    faces = join_profiles(ring_size, len(rings))
    # Profiles advance toward the viewer and inward, giving the screen a modest CRT bulge.
    faces += [tuple(range(len(verts) - ring_size, len(verts)))]
    case_parts.append(imported_mesh("SM_CRTGlass", verts, faces, smooth=True))
    return case_parts


def add_crt(prop, materials):
    materials.update({
        "crt_shell": dimensions_material("CRT_MoldedABS", (.036, .037, .04), .47),
        "crt_bezel": dimensions_material("CRT_TexturedBezel", (.014, .016, .018), .59),
        "crt_glass": dimensions_material("CRT_PhosphorGlass", (.014, .027, .024), .11),
        "crt_hardware": dimensions_material("CRT_Hardware", (.21, .22, .21), .56, .34),
        "crt_led": make_material(ROOT, "CRT_Standby", (.31, .027, .01), .45, 1.45),
    })
    case, bezel, screen = crt_meshes()
    for label, pos, surface, shape in (
        ("Molded CRT case", (-328, -67, 85), "crt_shell", case),
        ("CRT control bezel", (-328, -67, 85), "crt_bezel", bezel),
        ("Curved CRT screen", (-328, -74, 87), "crt_glass", screen),
    ):
        prop(label, pos, (100, 100, 100), surface, LIVING, shape=shape, collision=False)

    # One simple body for physics and player collision. Decorative controls are query-free.
    body = prop("CRT collision", (-349.5, -67, 85), (46.5, 78, 54), "crt_shell", LIVING)
    component = body.get_component_by_class(ue.StaticMeshComponent)
    component.set_editor_properties({"hidden_in_game": True, "cast_shadow": False})
    component.set_mass_override_in_kg(ue.Name("None"), 22.0, True)
    for y, z, size, label in ((-38, 77, 5.2, "Power button"), (-38, 87, 4, "Channel selector"),
                              (-38, 95, 4, "Volume knob")):
        knob = prop(label, (-321.9, y, z), (size, size, 1.8), "crt_hardware", LIVING,
                    shape=ue.load_asset("/Engine/BasicShapes/Cylinder"), collision=False)
        knob.set_actor_rotation(ue.Rotator(0, -90, 0), False)
    prop("CRT standby lamp", (-322.2, -38, 72), (.8, 1.1, 1.1), "crt_led", LIVING, collision=False)
    prop("CRT maker badge", (-322.5, -74, 64), (.4, 9, 1.5), "crt_hardware", LIVING, collision=False)
    for index in range(5):
        prop("CRT speaker grille", (-322.9, -46.3, 98 - index * 2), (1, 2.4, .6), "ink", LIVING, collision=False)


def world_point(actor, xyz):
    return ue.MathLibrary.transform_location(actor.get_actor_transform(), ue.Vector(*xyz))


def add_water(prop, label, tag, folder, x, y, z_top, z_bottom, width, spread=(0, 0)):
    drop = z_top - z_bottom
    if drop <= 0:
        raise RuntimeError(f"Invalid water jet length for {label}")
    dx, dy = spread
    horizontal = hypot(dx, dy)
    center = (x + dx / 2, y + dy / 2, (z_top + z_bottom) / 2)
    cylinder = ue.load_asset("/Engine/BasicShapes/Cylinder")
    actor = prop(label, center, (width, width, hypot(drop, horizontal)), "flowing_water", folder, tag,
                 cylinder, False)
    if horizontal:
        actor.set_actor_rotation(ue.Rotator(0, degrees(atan2(horizontal, drop)), degrees(atan2(dy, dx))), False)
    actor.set_actor_hidden_in_game(True)
    component = actor.get_component_by_class(ue.StaticMeshComponent)
    component.set_editor_property("cast_shadow", False)
    return actor


def add_plumbing(prop, materials, furniture, bath_east=800):
    materials["flowing_water"] = transmissive_material("TapWater", (.77, .88, .9), .09, .22, .66, flowing=True)
    materials["shower_glass"] = transmissive_material("ShowerSafetyGlass", (.63, .79, .80), .10, .065, .28)
    materials["plumbing_steel"] = dimensions_material("BrushedPlumbingSteel", (.36, .38, .40), .29, 1.0)
    for label, placement, spout, base, tag, folder, width in (
        ("Kitchen faucet", "Kitchen sink", (.0001, 21.06995, 176.5592), (.0001, 21.06995, 123.4317),
         "KitchenTapWater", KITCHEN, 1.55),
        ("Basin faucet", "Bathroom sink and tap", (0, -16.2615, 142.179), (0, -16.2615, 109.2623),
         "TapWater", BATH, 1.55),
    ):
        sink = furniture[placement]
        # These points come from the corresponding spout-lip rings in the imported OBJ mesh.
        tip = world_point(sink, spout)
        bowl = world_point(sink, base)
        if abs(tip.x - bowl.x) > .1 or abs(tip.y - bowl.y) > .1:
            raise RuntimeError(f"Water jet must be vertical under {label}")
        add_water(prop, label + " stream", tag, folder, tip.x, tip.y, tip.z + .15, bowl.z + .1, width)
        splash = prop(label + " splash", (bowl.x, bowl.y, bowl.z + .27), (5.2, 5.2, .4),
                      "flowing_water", folder, tag, ue.load_asset("/Engine/BasicShapes/Cylinder"), False)
        splash.set_actor_hidden_in_game(True)
        splash.get_component_by_class(ue.StaticMeshComponent).set_editor_property("cast_shadow", False)
        ue.log(f"PLUMBING_ALIGNMENT {tag} spout=({tip.x:.2f},{tip.y:.2f},{tip.z:.2f}) basin={bowl.z:.2f}")

    prop("Basin wall mount", (bath_east - 9.5, -111, 82), (5, 37, 12), "plumbing_steel", BATH)
    add_shower(prop, bath_east - 7)


def add_shower(prop, east):
    west, south, north = east - 143, 0, 103
    x, y = (east + west) / 2, (north + south) / 2
    width, depth = east - west, north - south
    folder = "04 Bathroom/Shower"
    cylinder = ue.load_asset("/Engine/BasicShapes/Cylinder")
    prop("Low-profile shower tray", (x, y, 1.75), (width, depth, 3.5), "ceramic", folder)
    prop("Shower tray back lip", (x, north - 1, 4.5), (width, 2, 2), "ceramic", folder, collision=False)
    prop("Shower tray west lip", (west + 1, y, 4.5), (2, depth, 2), "ceramic", folder, collision=False)
    prop("Shower tray east lip", (east - 1, y, 4.5), (2, depth, 2), "ceramic", folder, collision=False)

    # The fixed return panel leaves a walk-in opening of 81 cm along the south side.
    return_width, glass_height = 59, 195
    return_left = east - return_width
    for label, pos, size in (
        ("Fixed west shower screen", (west + 1, y, 5 + glass_height / 2), (1.2, depth - 2, glass_height)),
        ("Fixed shower return panel", (east - return_width / 2, south + 1, 5 + glass_height / 2),
         (return_width, 1.2, glass_height)),
    ):
        glass = prop(label, pos, size, "shower_glass", folder)
        glass.get_component_by_class(ue.StaticMeshComponent).set_editor_property("cast_shadow", False)
    for label, pos, size in (
        ("West glass wall channel", (west + 1, north - 1, 102.5), (2.5, 3, 195)),
        ("West glass edge profile", (west + 1, south + 1, 102.5), (2.5, 3, 195)),
        ("Return glass wall channel", (east - 1, south + 1, 102.5), (2.5, 3, 195)),
        ("Return glass edge profile", (return_left, south + 1, 102.5), (2.5, 3, 195)),
        ("West glass floor channel", (west + 1, y, 5), (3.5, depth, 2.5)),
        ("Return glass floor channel", (east - return_width / 2, south + 1, 5), (return_width + 2, 3.5, 2.5)),
    ):
        prop(label, pos, size, "plumbing_steel", folder, collision=False)

    head_x, head_y = east - 28, 47
    prop("Drain strainer", (head_x, head_y, 3.65), (11, 11, .3), "plumbing_steel", folder,
         shape=cylinder, collision=False)
    prop("Shower riser", (east - 4, head_y, 172), (2.8, 2.8, 103), "plumbing_steel", folder,
         shape=cylinder, collision=False)
    for z in (130, 205):
        prop("Shower riser wall bracket", (east - 2, head_y, z), (4, 5, 3), "plumbing_steel", folder,
             collision=False)
    arm = prop("Shower overhead arm", (east - 16, head_y, 223.5), (2.8, 2.8, 24), "plumbing_steel",
               folder, shape=cylinder, collision=False)
    arm.set_actor_rotation(ue.Rotator(0, -90, 0), False)
    prop("Shower head", (head_x, head_y, 221.1), (17, 17, 2.4), "plumbing_steel", folder,
         shape=cylinder, collision=False)
    control = prop("Shower mixer", (east - 4.5, 20, 121), (9, 9, 8), "plumbing_steel", folder,
                   "ShowerTap", cylinder)
    control.set_actor_rotation(ue.Rotator(0, -90, 0), False)
    prop("Shower mixer backplate", (east - .65, 20, 121), (1.3, 11, 11), "plumbing_steel", folder,
         collision=False)
    for dx, dy in ((0, 0), (4.6, 0), (-4.6, 0), (0, 4.6), (0, -4.6)):
        prop("Shower nozzle", (head_x + dx, head_y + dy, 219.8), (1, 1, .6), "ink", folder,
             shape=cylinder, collision=False)
        add_water(prop, "Shower spray", "ShowerWater", folder, head_x + dx, head_y + dy, 219.65,
                  4.5 + (abs(dx) + abs(dy)) * .26, .48, (2.2 * dx, 2.2 * dy))
    ue.log(f"SHOWER_FIT tray {width:.0f}x{depth:.0f} cm, clear entry {return_left - west - 3:.0f} cm")
