"""World-mapped exterior finishes and the shared time-of-day sky material."""
from math import cos, sin, sqrt, tau
from pathlib import Path
from random import Random

import unreal as ue

from ApartmentFinishes import SIZE, mapped_coordinates, write_png
from ApartmentScene import make_material


ROOT = "/Game/Prologue/Street"
ASSETS = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
TOOLS = ue.AssetToolsHelpers.get_asset_tools()
LIB = ue.MaterialEditingLibrary
PROP = ue.MaterialProperty


def save(asset):
    if not ASSETS.save_loaded_asset(asset, False):
        raise RuntimeError(f"Could not save {asset.get_path_name()}")


def load_or_create(folder, name, asset_class, factory):
    path = f"{folder}/{name}"
    return (ue.load_asset(path) if ASSETS.does_asset_exist(path) else
            TOOLS.create_asset(name, folder, asset_class, factory()))


def texture_file(path, name, normal=False):
    folder = ROOT + "/Textures"
    destination = f"{folder}/{name}"
    if ASSETS.does_asset_exist(destination):
        return ue.load_asset(destination)
    task = ue.AssetImportTask()
    task.set_editor_properties({"filename": str(path), "destination_path": folder,
                                "automated": True, "save": False})
    TOOLS.import_asset_tasks([task])
    texture = ue.load_asset(destination)
    if not isinstance(texture, ue.Texture2D):
        raise RuntimeError(f"Could not import {name}")
    if normal:
        texture.set_editor_property("compression_settings", ue.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("srgb", False)
    save(texture)
    return texture


def noise_surface(kind, x, y, noise):
    u, v = x * tau / SIZE, y * tau / SIZE
    stain = .65 * sin(3 * u + v) + .22 * cos(4 * v - 2 * u) + .24 * sin(7 * u - 7 * v)
    if kind in ("brick", "ochre_brick"):
        course = y // 16
        brick_x = (x + (course % 2) * 32) % 64
        mortar = min(y % 16, brick_x, 63 - brick_x) < 2
        unit = ((x + (course % 2) * 32) // 64) % 4
        shade = ((unit * 13 + course * 19) % 31 - 15) + 7 * stain
        colors = {"brick": (124, 75, 58), "ochre_brick": (157, 118, 87)}
        return ((118, 106, 92), noise * 3, -.95 + noise * .1) if mortar else (
            colors[kind], shade + noise * 8, .09 * shade + noise * .22)
    if kind == "asphalt":
        fleck = max(0, noise - .78) * 63
        return (58, 59, 60), stain * 4 + noise * 8 + fleck, stain * .16 + noise * .46
    if kind == "concrete":
        joint = x % 128 < 2 or y % 128 < 2
        return (142, 137, 123), 10 * stain + noise * 8 - 24 * joint, .1 * stain + .24 * noise - .9 * joint
    return (105, 103, 85), 8 * stain + noise * 9, noise * .16


def ground_textures(kind, source):
    names = (f"T_{kind}_Color", f"T_{kind}_Normal")
    files = [source / (name + ".png") for name in names]
    if any(not ASSETS.does_asset_exist(f"{ROOT}/Textures/{name}") for name in names):
        rng = Random(1994)
        values = [[noise_surface(kind, x, y, rng.uniform(-1, 1)) for x in range(SIZE)] for y in range(SIZE)]
        albedo, normal = bytearray(), bytearray()
        for y, row in enumerate(values):
            for x, (color, delta, _) in enumerate(row):
                albedo.extend(max(0, min(255, round(c + delta))) for c in color)
                dx = (row[(x - 1) % SIZE][2] - row[(x + 1) % SIZE][2]) * .235
                dy = (values[(y - 1) % SIZE][x][2] - values[(y + 1) % SIZE][x][2]) * .235
                length = sqrt(1 + dx * dx + dy * dy)
                normal.extend(round(127.5 * (1 + value / length)) for value in (dx, dy, 1))
        write_png(files[0], albedo)
        write_png(files[1], normal)
    return tuple(texture_file(path, name, index == 1) for index, (path, name) in enumerate(zip(files, names)))


def mapped_surface(kind, source, vertical, span, roughness):
    material = make_material(ROOT, kind, (.3, .3, .3), roughness)
    if isinstance(LIB.get_material_property_input_node(material, PROP.MP_NORMAL), ue.MaterialExpressionTextureSample):
        return material
    coordinates = mapped_coordinates(material, LIB, vertical)
    coordinates.set_editor_property("const_b", 1 / span)
    color, normal = ground_textures(kind, source)
    for index, (channel, texture, sampler) in enumerate((
        (PROP.MP_BASE_COLOR, color, ue.MaterialSamplerType.SAMPLERTYPE_COLOR),
        (PROP.MP_NORMAL, normal, ue.MaterialSamplerType.SAMPLERTYPE_NORMAL),
    )):
        node = LIB.create_material_expression(material, ue.MaterialExpressionTextureSample, -30, 150 * index)
        node.set_editor_properties({"texture": texture, "sampler_type": sampler})
        LIB.connect_material_expressions(coordinates, "", node, "Coordinates")
        LIB.connect_material_property(node, "RGB", channel)
    LIB.recompile_material(material)
    save(material)
    return material


def custom_input(name):
    value = ue.CustomInput()
    value.set_editor_property("input_name", ue.Name(name))
    return value


def create_sky_material():
    material = make_material(ROOT, "Sky", (.05, .09, .15), .85)
    if LIB.get_material_property_input_node(material, PROP.MP_EMISSIVE_COLOR):
        return material
    material.set_editor_properties({"shading_model": ue.MaterialShadingModel.MSM_UNLIT,
                                    "two_sided": True, "is_sky": True})
    position = LIB.create_material_expression(material, ue.MaterialExpressionWorldPosition, -750, -100)
    names = ("Position", "HorizonTint", "ZenithTint", "SolarTint", "SunDirection", "SunGlow")
    custom = LIB.create_material_expression(material, ue.MaterialExpressionCustom, 0, 0)
    custom.set_editor_properties({"inputs": [custom_input(name) for name in names],
                                  "output_type": ue.CustomMaterialOutputType.CMOT_FLOAT3,
                                  "description": "Horizon gradient and clouds",
                                  "code": """
float3 Dir = normalize(Position);
float h = saturate(Dir.z);
float3 color = lerp(HorizonTint, ZenithTint, pow(h, 0.46));
float2 p = Dir.xy * (3.2 / (max(0.0, Dir.z) + 0.54));
float n = sin(10.9*p.x+4.0*p.y+1.5*sin(6.6*p.y))
    + 0.63*sin(18.7*p.y-12.1*p.x+cos(p.x*11.0))
    + 0.39*sin(39.0*p.y+29.0*p.x) + 0.27*cos(76.0*p.y-53.0*p.x);
float cloud = smoothstep(0.63, 1.76, n) * smoothstep(0.04, 0.21, h) * (1.0 - 0.6*h);
color += lerp(0.010, 0.17, saturate(SunGlow + ZenithTint.g * .8)) * cloud;
float sun = saturate(dot(Dir, normalize(SunDirection)));
color += (1.85 * pow(sun, 1700.0) + .17 * pow(sun, 11.0)) * SolarTint * SunGlow;
return color;
"""})
    LIB.connect_material_expressions(position, "", custom, "Position")
    for row, (name, default) in enumerate((
        ("HorizonTint", (.58, .24, .115)), ("ZenithTint", (.059, .15, .369)),
        ("SolarTint", (1., .54, .27)), ("SunDirection", (-.86, .42, .22)),
    )):
        parameter = LIB.create_material_expression(material, ue.MaterialExpressionVectorParameter, -450, row * 145)
        parameter.set_editor_properties({"parameter_name": ue.Name(name), "default_value": ue.LinearColor(*default, 1)})
        LIB.connect_material_expressions(parameter, "RGB", custom, name)
    glow = LIB.create_material_expression(material, ue.MaterialExpressionScalarParameter, -450, 585)
    glow.set_editor_properties({"parameter_name": ue.Name("SunGlow"), "default_value": .65})
    LIB.connect_material_expressions(glow, "", custom, "SunGlow")
    LIB.connect_material_property(custom, "", PROP.MP_EMISSIVE_COLOR)
    LIB.recompile_material(material)
    save(material)
    return material


def glow_collection():
    path = ROOT + "/Materials"
    collection = load_or_create(path, "MPC_StreetLighting", ue.MaterialParameterCollection,
                                ue.MaterialParameterCollectionFactoryNew)
    if not collection.get_editor_property("scalar_parameters"):
        parameter = ue.CollectionScalarParameter()
        parameter.set_editor_properties({"parameter_name": ue.Name("StreetGlow"), "default_value": .47})
        collection.set_editor_property("scalar_parameters", [parameter])
        save(collection)
    return collection


def shift_emissive(material, collection, color):
    if LIB.get_material_property_input_node(material, PROP.MP_EMISSIVE_COLOR):
        return
    intensity = LIB.create_material_expression(material, ue.MaterialExpressionCollectionParameter, -575, 300)
    intensity.set_editor_properties({"collection": collection, "parameter_name": ue.Name("StreetGlow")})
    tint = LIB.create_material_expression(material, ue.MaterialExpressionConstant3Vector, -575, 390)
    tint.set_editor_property("constant", ue.LinearColor(*color, 1))
    shade = LIB.create_material_expression(material, ue.MaterialExpressionMultiply, -310, 300)
    LIB.connect_material_expressions(intensity, "", shade, "A")
    LIB.connect_material_expressions(tint, "", shade, "B")
    LIB.connect_material_property(shade, "", PROP.MP_EMISSIVE_COLOR)
    LIB.recompile_material(material)
    save(material)


def create_street_materials(source):
    source.mkdir(parents=True, exist_ok=True)
    materials = {}
    for label, wall, span, roughness in (("brick", True, 108, .86), ("ochre_brick", True, 108, .83),
                                        ("asphalt", False, 220, .95), ("concrete", False, 230, .87),
                                        ("soil", False, 240, .93)):
        materials[label] = mapped_surface(label, source, wall, span, roughness)
    for label, color, roughness in (
        ("stone", (.37, .34, .278), .78), ("dark_stone", (.166, .155, .142), .82),
        ("roof", (.042, .044, .041), .9), ("white_line", (.59, .57, .48), .89),
        ("yellow_line", (.79, .52, .065), .91), ("frame", (.041, .052, .05), .48),
        ("dark_glass", (.054, .087, .102), .28), ("store_glass", (.079, .085, .086), .34),
        ("lit_window", (.112, .078, .043), .43), ("curtain", (.41, .34, .245), .91),
        ("red", (.29, .051, .04), .66), ("awning", (.207, .045, .039), .84),
        ("teal", (.06, .17, .141), .8), ("steel", (.18, .19, .18), .55),
        ("galvanized", (.26, .28, .27), .6), ("faded_white", (.52, .48, .38), .68),
        ("wood", (.185, .093, .04), .83), ("paper", (.56, .55, .47), .92),
        ("lamp_glass", (.66, .50, .31), .35), ("leaf_a", (.079, .137, .050), .95),
        ("leaf_b", (.12, .19, .067), .94), ("sedan_burgundy", (.32, .059, .061), .29),
        ("sedan_cream", (.45, .39, .25), .33),
    ):
        materials[label] = make_material(ROOT, label, color, roughness)
    collection = glow_collection()
    for label, color in (("lit_window", (.68, .36, .14)), ("lamp_glass", (1.65, 1.02, .43)),
                         ("store_glass", (.38, .23, .105))):
        shift_emissive(materials[label], collection, color)
    materials["sky"] = create_sky_material()
    return materials, collection
