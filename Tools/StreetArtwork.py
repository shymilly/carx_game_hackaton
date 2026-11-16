"""Build layered asphalt, worn paint, and inexpensive industrial backdrop cards."""
from math import cos, sin, sqrt, tau
from pathlib import Path
from random import Random
from shutil import copyfile
import struct
import zlib

import unreal as ue

from ApartmentFinishes import mapped_coordinates
from ApartmentScene import make_material
from StreetMaterials import ASSETS, LIB, PROP, ROOT, custom_input, save, texture_file


def png(path, width, height, pixels, channels=3):
    def chunk(name, payload):
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload))

    stride = width * channels
    scanlines = b"".join(b"\0" + pixels[y:y + stride] for y in range(0, len(pixels), stride))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8,
                                                                    6 if channels == 4 else 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(scanlines, 6)) + chunk(b"IEND", b""))


def missing(name):
    return not ASSETS.does_asset_exist(f"{ROOT}/Textures/{name}")


def surface_textures(source):
    names = ("T_NeptuneAsphalt", "T_NeptuneAggregate", "T_NeptuneAggregate_N", "T_PressEnamel", "T_MarketWeave")
    base, aggregate, normal, enamel, weave = (source / (name + ".png") for name in names)
    if missing(names[0]):
        provided = Path.home() / "Desktop/assets/Downtown City MegaKit[Standard]/Textures/T_Concrete_Asphalt_BaseColor.png"
        if provided.is_file():
            copyfile(provided, base)
        else:
            image = bytearray()
            for y in range(512):
                for x in range(512):
                    u, v = x * tau / 512, y * tau / 512
                    shade = round(62 + 7 * sin(2*u + v) + 5 * cos(u - 4*v) + 4 * cos(11*u + 8*v))
                    image.extend((shade, shade, shade))
            png(base, 512, 512, image)
    if missing(names[1]) or missing(names[2]):
        rng = Random(1994)
        side = 512
        row_values = [[rng.random() for x in range(side)] for y in range(side)]
        rgb, vectors = bytearray(), bytearray()
        for y, row in enumerate(row_values):
            above, below = row_values[(y-1) % side], row_values[(y+1) % side]
            for x, value in enumerate(row):
                left, right = row[(x-1) % side], row[(x+1) % side]
                grain = value*.48 + (left + right + above[x] + below[x])*.13
                chip = 34 if value > .955 and grain > .6 else 0
                shade = min(255, round(163 + (grain-.5)*91 + chip))
                rgb.extend((shade, shade, shade))
                dx, dy = (left-right)*.42, (above[x]-below[x])*.42
                length = sqrt(1 + dx*dx + dy*dy)
                vectors.extend(round(127.5 * (1 + element / length)) for element in (dx, dy, 1))
        png(aggregate, side, side, rgb)
        png(normal, side, side, vectors)
    if missing(names[3]) or missing(names[4]):
        rng = Random(725)
        metal, cloth = bytearray(), bytearray()
        for y in range(256):
            for x in range(256):
                u, v = x * tau / 256, y * tau / 256
                grime = sin(4*u+v)*.6 + cos(9*u - 2*v)*.3 + sin(31*u + 5*v)*.17
                wear = .67 * grime + rng.random()
                if wear > 1.55:
                    color = (109, 84, 61)
                else:
                    color = tuple(round(value + 9*grime + rng.randrange(8)) for value in (51, 93, 85))
                metal.extend(color)
                strand = 166 + (14 if (x % 4 < 2) != (y % 4 < 2) else -6) + round(8*grime)
                cloth.extend((strand, strand, strand))
        png(enamel, 256, 256, metal)
        png(weave, 256, 256, cloth)
    textures = tuple(texture_file(path, name, index == 2)
                     for index, (path, name) in enumerate(zip((base, aggregate, normal, enamel, weave), names)))
    if textures[0].get_editor_property("max_texture_size") != 1024:
        textures[0].set_editor_property("max_texture_size", 1024)
        save(textures[0])
    return textures


def node(material, kind, x, y, **properties):
    expression = LIB.create_material_expression(material, kind, x, y)
    if properties:
        expression.set_editor_properties(properties)
    return expression


def sample(material, texture, coordinates=None, normal=False, row=0):
    sampler = ue.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else ue.MaterialSamplerType.SAMPLERTYPE_COLOR
    read = node(material, ue.MaterialExpressionTextureSample, -140, row, texture=texture, sampler_type=sampler)
    if coordinates:
        LIB.connect_material_expressions(coordinates, "", read, "Coordinates")
    return read


def world_uv(material, centimeters, vertical=False):
    location = mapped_coordinates(material, LIB, vertical)
    location.set_editor_property("const_b", 1 / centimeters)
    return location


def asphalt(name, textures, coarse_span, fine_span, tint):
    material = make_material(ROOT, name, (.12, .12, .12), .92)
    if LIB.get_material_property_input_node(material, PROP.MP_NORMAL):
        return material
    base, aggregate, normal = textures[:3]
    patch = sample(material, base, world_uv(material, coarse_span), row=0)
    fine_uv = world_uv(material, fine_span)
    grain = sample(material, aggregate, fine_uv, row=140)
    relief = sample(material, normal, fine_uv, normal=True, row=420)
    grain_range = node(material, ue.MaterialExpressionLinearInterpolate, 50, 140, const_a=.68, const_b=1.56)
    LIB.connect_material_expressions(grain, "R", grain_range, "Alpha")
    mix = node(material, ue.MaterialExpressionMultiply, 240, 0)
    LIB.connect_material_expressions(patch, "RGB", mix, "A")
    LIB.connect_material_expressions(grain_range, "", mix, "B")
    color = node(material, ue.MaterialExpressionMultiply, 430, 0)
    pigment = node(material, ue.MaterialExpressionConstant3Vector, 245, 160, constant=ue.LinearColor(*tint, 1))
    LIB.connect_material_expressions(mix, "", color, "A")
    LIB.connect_material_expressions(pigment, "", color, "B")
    LIB.connect_material_property(color, "", PROP.MP_BASE_COLOR)
    LIB.connect_material_property(relief, "RGB", PROP.MP_NORMAL)
    LIB.recompile_material(material)
    save(material)
    return material


def painted_surface(name, texture, tint, roughness, scale, vertical=False):
    material = make_material(ROOT, name, tint, roughness)
    color = LIB.get_material_property_input_node(material, PROP.MP_BASE_COLOR)
    if not isinstance(color, ue.MaterialExpressionConstant3Vector):
        return material
    pattern = sample(material, texture, world_uv(material, scale, vertical))
    mix = node(material, ue.MaterialExpressionMultiply, 230, 0)
    LIB.connect_material_expressions(pattern, "RGB", mix, "A")
    LIB.connect_material_expressions(color, "RGB", mix, "B")
    LIB.connect_material_property(mix, "", PROP.MP_BASE_COLOR)
    LIB.recompile_material(material)
    save(material)
    return material


class FactoryImage:
    width = 1024
    height = 512

    def __init__(self):
        self.pixels = bytearray(self.width * self.height * 4)

    def rect(self, x0, y0, x1, y1, color):
        left, right = max(x0, 0), min(x1, self.width)
        row = bytes((*color, 255)) * max(0, right - left)
        for y in range(max(y0, 0), min(y1, self.height)):
            index = (y * self.width + left) * 4
            self.pixels[index:index+len(row)] = row

    def poly(self, points, color):
        edges = list(zip(points, points[1:] + points[:1]))
        for y in range(max(0, min(p[1] for p in points)), min(self.height, max(p[1] for p in points))):
            row = y + .5
            crossings = sorted(a+(c-a)*(row-b)/(d-b) for (a,b), (c,d) in edges if min(b,d) <= row < max(b,d))
            for x0, x1 in zip(crossings[::2], crossings[1::2]):
                self.rect(round(x0), y, round(x1), y+1, color)

    def weather(self, seed):
        rng = Random(seed)
        for y in range(self.height):
            for x in range(self.width):
                index = (y*self.width+x)*4
                if not self.pixels[index+3]:
                    continue
                value = round(rng.uniform(-7, 7) + 4 * sin(x*.061) * cos(y*.043))
                for channel in range(index, index+3):
                    self.pixels[channel] = max(0, min(255, self.pixels[channel]+value))


def make_factory_images(source):
    back, front = FactoryImage(), FactoryImage()
    for x, top, width in ((85, 295, 178), (234, 217, 270), (474, 239, 225), (663, 178, 137), (780, 224, 178)):
        back.rect(x, top, x+width, 512, (91, 108, 123))
        back.rect(x-5, top, x+width+5, top+10, (116, 126, 132))
        for i in range(x+17, x+width-12, 26):
            back.rect(i, top+27, i+11, top+71, (81, 99, 116))
    for x, y, w in ((155, 194, 19), (528, 152, 28), (890, 168, 18)):
        back.poly([(x-w,y), (x+w,y), (x+w+9,383), (x-w-10,383)], (95, 109, 121))
        back.rect(x-w-4, y, x+w+4, y+8, (78, 97, 109))
    back.weather(38)

    for x, top, width in ((300, 69, 32), (458, 112, 24), (717, 93, 28)):
        front.poly([(x-width,top), (x+width,top), (x+width+15,430), (x-width-15,430)], (102, 81, 79))
        front.poly([(x-width,top+4), (x-3,top+4), (x-2,430), (x-width-15,430)], (125, 100, 90))
        for offset in (0, 17, 79):
            pad = width + (6 if offset == 0 else 0)
            front.rect(x-pad, top+offset, x+pad+2, top+offset+8, (87, 76, 73))
        for i in range(top+34, 338, 13):
            front.rect(x-width, i, x+width+1, i+2, (114, 96, 87))
    front.poly([(23,359),(130,359),(130,320),(269,320),(310,284),(348,316),(409,316),(448,276),
                (510,314),(564,314),(598,267),(656,311),(739,311),(766,318),(766,339),(977,339),
                (977,512),(23,512)], (114, 106, 104))
    for left, right, height in ((27,271,367), (274,738,330), (759,980,353)):
        front.rect(left, height, right, 512, (123, 106, 99))
        front.rect(left, height, right, height+9, (152, 135, 121))
        for x in range(left+14, right-18, 38):
            front.rect(x, height+27, x+24, height+70, (68, 81, 87))
            front.rect(x+3, height+30, x+21, height+54, (147, 159, 154))
            front.rect(x+11, height+28, x+13, height+61, (82, 96, 102))
            front.rect(x, height+70, x+25, height+73, (147, 128, 113))
        for y in range(height+84, 510, 11):
            front.rect(left+4, y, right-4, y+1, (102, 92, 88))
    front.weather(73)
    for name, image in (("T_AegisDistant", back), ("T_AegisWorks", front)):
        if missing(name):
            png(source / (name + ".png"), image.width, image.height, image.pixels, 4)


def exposure(material, collection):
    return node(material, ue.MaterialExpressionCollectionParameter, -190, 210,
                collection=collection, parameter_name=ue.Name("FactoryExposure"))


def factory_card(name, texture, collection):
    material = make_material(ROOT, name, (.285, .26, .24), .9)
    if LIB.get_material_property_input_node(material, PROP.MP_OPACITY_MASK):
        return material
    material.set_editor_properties({"shading_model": ue.MaterialShadingModel.MSM_UNLIT,
                                    "blend_mode": ue.BlendMode.BLEND_MASKED, "two_sided": True})
    raster = sample(material, texture)
    lit = node(material, ue.MaterialExpressionMultiply, 115, 0)
    LIB.connect_material_expressions(raster, "RGB", lit, "A")
    LIB.connect_material_expressions(exposure(material, collection), "", lit, "B")
    LIB.connect_material_property(lit, "", PROP.MP_EMISSIVE_COLOR)
    LIB.connect_material_property(raster, "A", PROP.MP_OPACITY_MASK)
    LIB.recompile_material(material)
    save(material)
    return material


def smoke_card(collection):
    material = make_material(ROOT, "AegisSmoke", (.2, .21, .22), .9)
    if LIB.get_material_property_input_node(material, PROP.MP_OPACITY):
        return material
    material.set_editor_properties({"shading_model": ue.MaterialShadingModel.MSM_UNLIT,
                                    "blend_mode": ue.BlendMode.BLEND_TRANSLUCENT, "two_sided": True})
    uv = node(material, ue.MaterialExpressionTextureCoordinate, -350, -180)
    seconds = node(material, ue.MaterialExpressionTime, -350, 0)
    band = node(material, ue.MaterialExpressionCustom, 80, -100, inputs=[custom_input("UV"), custom_input("Seconds")],
                output_type=ue.CustomMaterialOutputType.CMOT_FLOAT1, description="Expanding, wind-driven stack smoke", code="""
float h = saturate(1 - UV.y);
float center = .30 + .38*h + .095*h*sin(h*9.7 - Seconds*.43);
float dist = (UV.x - center) / (.07 + h*.31);
float n = sin(19*UV.x + 24*h - Seconds*.95)*sin(13*h - Seconds*.61) + .43*sin(h*51 + UV.x*23 - Seconds*1.35);
return saturate(1 - dist*dist + n*.24) * smoothstep(0, .09, h) * (1 - h) * .48;
""")
    LIB.connect_material_expressions(uv, "", band, "UV")
    LIB.connect_material_expressions(seconds, "", band, "Seconds")
    LIB.connect_material_property(band, "", PROP.MP_OPACITY)
    tint = node(material, ue.MaterialExpressionConstant3Vector, -220, 330, constant=ue.LinearColor(.43,.41,.40,1))
    light = node(material, ue.MaterialExpressionMultiply, 110, 305)
    LIB.connect_material_expressions(tint, "RGB", light, "A")
    LIB.connect_material_expressions(exposure(material, collection), "", light, "B")
    LIB.connect_material_property(light, "", PROP.MP_EMISSIVE_COLOR)
    LIB.recompile_material(material)
    save(material)
    return material


def add_street_art(materials, collection, source):
    textures = surface_textures(source)
    materials["asphalt"] = asphalt("NeptuneAsphalt", textures, 1010, 188, (1.11, 1.075, 1.045))
    materials["asphalt_repair"] = asphalt("RepairedAsphalt", textures, 780, 172, (.77, .79, .81))
    materials["press_enamel"] = painted_surface("PressEnamel", textures[3], (.87, .99, .94), .79, 134, True)
    for name, tint in (("burgundy_canvas", (.50, .135, .095)), ("green_canvas", (.16, .39, .27)),
                       ("tan_canvas", (.70, .53, .31)), ("blue_canvas", (.18, .34, .48))):
        materials[name] = painted_surface(name, textures[4], tint, .97, 83)
    for name, tint, roughness in (
        ("precinct_green", (.092,.22,.18), .52), ("patina", (.19,.25,.23), .78), ("lino", (.23,.26,.23), .57),
        ("plaster_lobby", (.56,.51,.37), .93), ("grass", (.105,.155,.067), .98), ("court", (.108,.115,.103), .95),
        ("ply", (.31,.21,.11), .89), ("warning_paint", (.20,.055,.034), .8), ("marker_blue", (.12,.28,.48), .76),
    ):
        materials[name] = make_material(ROOT, name, tint, roughness)

    entries = list(collection.get_editor_property("scalar_parameters"))
    if not any(str(entry.get_editor_property("parameter_name")) == "FactoryExposure" for entry in entries):
        light = ue.CollectionScalarParameter()
        light.set_editor_properties({"parameter_name": ue.Name("FactoryExposure"), "default_value": .56})
        collection.set_editor_property("scalar_parameters", entries + [light])
        save(collection)
    if any(missing(name) for name in ("T_AegisDistant", "T_AegisWorks")):
        make_factory_images(source)
    for name, texture in (("factory_distant", "T_AegisDistant"), ("factory_works", "T_AegisWorks")):
        materials[name] = factory_card(name, texture_file(source / (texture + ".png"), texture), collection)
    materials["factory_smoke"] = smoke_card(collection)
