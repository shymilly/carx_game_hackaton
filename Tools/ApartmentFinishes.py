"""Author seamless PBR maps at 256 texels per 160 cm and import them into Unreal."""
import math
from pathlib import Path
import random
import struct
import zlib

import unreal as ue

from ApartmentScene import make_material

SIZE = 256
TILE_CM = 160
ROOT = "/Game/Prologue/ModernFinishes"
CHANNELS = {
    "Albedo": (ue.MaterialProperty.MP_BASE_COLOR, "RGB", ue.MaterialSamplerType.SAMPLERTYPE_COLOR),
    "Normal": (ue.MaterialProperty.MP_NORMAL, "RGB", ue.MaterialSamplerType.SAMPLERTYPE_NORMAL),
    "Roughness": (ue.MaterialProperty.MP_ROUGHNESS, "R", ue.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR),
    "Metallic": (ue.MaterialProperty.MP_METALLIC, "R", ue.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR),
    "AO": (ue.MaterialProperty.MP_AMBIENT_OCCLUSION, "R", ue.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR),
}


def surface(kind, x, y, noise):
    u, v = x * math.tau / SIZE, y * math.tau / SIZE
    grain = noise * 2 + math.sin(4 * u + 2 * v) * 1.5
    if kind in ("wood", "oak"):
        board = y // 32 if kind == "wood" else 0
        stripe = math.sin(62 * v + 1.7 * math.sin(u) + .5 * math.cos(5 * u + 7 * v))
        joint = kind == "wood" and (y % 32 < 2 or (x + (y // 32) * 71) % SIZE < 2)
        shade = grain + stripe * 5 + (board * 9 % 19) - 7
        return ((163, 131, 100), shade - joint * 12, .58 + .035 * stripe, 0, .82 if joint else 1,
                stripe * .35 - joint * 1.15)
    if kind in ("tile", "ceramic"):
        joint = kind == "tile" and min(x % 64, y % 64) < 2
        return ((176, 181, 180) if joint else (207, 211, 209), grain, .82 if joint else .48,
                0, .79 if joint else 1, grain * .17 - joint * 1.6)
    if kind == "fabric":
        weave = math.cos(64 * u) * math.cos(64 * v)
        return (153, 156, 149), grain + 4 * weave, .88, 0, .98, weave * .7
    if kind == "dark_metal":
        brush = math.cos(64 * v + .3 * math.cos(u))
        return (103, 107, 110), grain + 3 * brush, .56 + .03 * brush, 1, 1, brush * .19
    palette = {"plaster": (222, 219, 210), "book_sage": (89, 111, 102), "book_rust": (141, 79, 60),
               "painted": (215, 216, 215)}
    return palette[kind], grain, .65 if kind == "painted" else .86, 0, 1, grain * .045


def write_png(path, pixels):
    def chunk(label, data):
        return struct.pack(">I", len(data)) + label + data + struct.pack(">I", zlib.crc32(label + data))

    rows = b"".join(b"\0" + pixels[i:i + 3 * SIZE] for i in range(0, len(pixels), 3 * SIZE))
    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
                     chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def write_maps(kind, files):
    rng = random.Random(1994)
    values = [[surface(kind, x, y, rng.uniform(-1, 1)) for x in range(SIZE)] for y in range(SIZE)]
    pixels = {name: bytearray() for name in CHANNELS}
    for y, row in enumerate(values):
        for x, (color, shade, roughness, metallic, ao, _) in enumerate(row):
            pixels["Albedo"].extend(max(0, min(255, round(c + shade))) for c in color)
            for name, value in (("Roughness", roughness), ("Metallic", metallic), ("AO", ao)):
                pixels[name].extend((round(255 * value),) * 3)
            dx = (row[(x - 1) % SIZE][5] - row[(x + 1) % SIZE][5]) * .24
            dy = (values[(y - 1) % SIZE][x][5] - values[(y + 1) % SIZE][x][5]) * .24
            length = math.sqrt(1 + dx * dx + dy * dy)
            pixels["Normal"].extend(round(127.5 * (1 + n / length)) for n in (dx, dy, 1))
    for channel, path in files.items():
        write_png(path, pixels[channel])


def import_textures(kind, assets):
    source = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())) / "SourceAssets" / "ModernFinishes"
    source.mkdir(parents=True, exist_ok=True)
    files = {channel: source / f"T_{kind}_{channel}.png" for channel in CHANNELS}
    missing = {channel: path for channel, path in files.items() if not assets.does_asset_exist(f"{ROOT}/{path.stem}")}
    if missing:
        write_maps(kind, missing)
        tasks = []
        for path in missing.values():
            task = ue.AssetImportTask()
            task.set_editor_properties({"filename": str(path), "destination_path": ROOT, "automated": True, "save": True})
            tasks.append(task)
        ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    textures = {}
    for channel, path in files.items():
        texture = ue.load_asset(f"{ROOT}/{path.stem}")
        if texture is None:
            raise RuntimeError(f"Missing PBR texture {path.name}")
        if channel in missing:
            if channel == "Normal":
                texture.set_editor_property("compression_settings", ue.TextureCompressionSettings.TC_NORMALMAP)
            texture.set_editor_property("srgb", channel == "Albedo")
            if not assets.save_loaded_asset(texture, False):
                raise RuntimeError(f"Could not save {path.name}")
        textures[channel] = texture
    return textures


def mapped_coordinates(material, lib, vertical):
    world = lib.create_material_expression(material, ue.MaterialExpressionWorldPosition, -900, 0)
    mask = lib.create_material_expression(material, ue.MaterialExpressionComponentMask, -670, -120)
    mask.set_editor_properties({"r": not vertical, "g": not vertical, "b": vertical, "a": False})
    lib.connect_material_expressions(world, "", mask, "Input")
    coordinates = mask
    if vertical:
        horizontal = lib.create_material_expression(material, ue.MaterialExpressionDotProduct, -660, 140)
        direction = lib.create_material_expression(material, ue.MaterialExpressionConstant3Vector, -900, 210)
        direction.set_editor_property("constant", ue.LinearColor(1, 1, 0, 1))
        lib.connect_material_expressions(world, "", horizontal, "A")
        lib.connect_material_expressions(direction, "", horizontal, "B")
        coordinates = lib.create_material_expression(material, ue.MaterialExpressionAppendVector, -445, 60)
        lib.connect_material_expressions(horizontal, "", coordinates, "A")
        lib.connect_material_expressions(mask, "", coordinates, "B")
    scaled = lib.create_material_expression(material, ue.MaterialExpressionMultiply, -250, 0)
    scaled.set_editor_property("const_b", 1 / TILE_CM)
    lib.connect_material_expressions(coordinates, "", scaled, "A")
    return scaled


def create_finishes():
    assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    lib = ue.MaterialEditingLibrary
    finishes = {}
    for kind in ("wood", "oak", "tile", "plaster", "fabric", "dark_metal", "book_sage", "book_rust", "ceramic", "painted"):
        textures = import_textures(kind, assets)
        for vertical in ((False, True) if kind in ("oak", "tile", "plaster") else (False,)):
            label = kind + ("_wall" if vertical else "")
            material = make_material(ROOT, label, (.5, .5, .5))
            if not isinstance(lib.get_material_property_input_node(material, ue.MaterialProperty.MP_BASE_COLOR),
                              ue.MaterialExpressionMultiply):
                if label not in ("wood", "tile", "tile_wall", "plaster", "plaster_wall", "oak_wall"):
                    # Object UVs move with the furniture and small props.
                    coordinates = None
                else:
                    coordinates = mapped_coordinates(material, lib, vertical)
                for i, (channel, (property_id, output, sampler)) in enumerate(CHANNELS.items()):
                    sample = lib.create_material_expression(material, ue.MaterialExpressionTextureSample, 0, 260 * i)
                    sample.set_editor_properties({"texture": textures[channel], "sampler_type": sampler})
                    if coordinates is not None:
                        lib.connect_material_expressions(coordinates, "", sample, "Coordinates")
                    source = sample
                    if channel == "Albedo":
                        tint = lib.create_material_expression(material, ue.MaterialExpressionVectorParameter, 0, -230)
                        tint.set_editor_properties({"parameter_name": ue.Name("Tint"),
                                                    "default_value": ue.LinearColor(1, 1, 1, 1)})
                        source = lib.create_material_expression(material, ue.MaterialExpressionMultiply, 280, 0)
                        lib.connect_material_expressions(sample, output, source, "A")
                        lib.connect_material_expressions(tint, "RGB", source, "B")
                        output = ""
                    if not lib.connect_material_property(source, output, property_id):
                        raise RuntimeError(f"Could not connect {channel} on {label}")
                lib.recompile_material(material)
                if not assets.save_loaded_asset(material, False):
                    raise RuntimeError(f"Could not save {label}")
            finishes[label] = material
    return finishes


def texture_asset(kind):
    """Keep the original OBJ importer compatible with the earlier apartment assets."""
    assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    old_path = f"/Game/Prologue/Finishes/T_{kind.title()}"
    if assets.does_asset_exist(old_path):
        return ue.load_asset(old_path)
    return import_textures(kind, assets)["Albedo"]
