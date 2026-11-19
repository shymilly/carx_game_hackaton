"""Generate the street's bilingual enamel lettering with Blender in background mode."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sign:
    russian: str
    english: str
    family: str
    font: str
    width: float
    height: float
    yaw: float

    @property
    def text(self):
        return f"{self.russian} / {self.english}" if self.russian else self.english


# Width and height are the usable area of the fascia, in centimeters.
SIGNS = {
    "SM_NeighborhoodGrocery": Sign("ПРОДУКТЫ", "GROCERY", "Russo One", "russoone/RussoOne-Regular.ttf", 700, 49, 0),
    "SM_NeighborhoodPharmacy": Sign("АПТЕКА", "PHARMACY", "PT Serif", "ptserif/PT_Serif-Web-Bold.ttf", 680, 49, 0),
    "SM_NeighborhoodBar": Sign("Бар «Маяк»", "Lighthouse Bar", "Lobster", "lobster/Lobster-Regular.ttf", 443, 72, 90),
    "SM_NeighborhoodFlea": Sign("БАРАХОЛКА", "FLEA MARKET", "Rubik Mono One", "rubikmonoone/RubikMonoOne-Regular.ttf", 435, 47, 90),
    "SM_NeighborhoodPrecinct": Sign("", "POLICE · 60TH PRECINCT", "PT Sans Narrow",
                                   "ptsansnarrow/PT_Sans-Narrow-Web-Bold.ttf", 575, 47, -90),
    "SM_NeighborhoodPark": Sign("БРАЙТОНСКИЙ ДВОР", "BRIGHTON PLAYGROUND", "Marmelad",
                               "marmelad/Marmelad-Regular.ttf", 246, 43, 180),
    "SM_SignStreet": Sign("4-я БРАЙТОН-БИЧ", "4th Brighton beach", "IBM Plex Mono", "ibmplexmono/IBMPlexMono-SemiBold.ttf", 101, 24, 180),
    "Press": Sign("КНИГИ И ПРЕССА", "BOOKS & NEWSPAPERS", "IBM Plex Serif", "ibmplexserif/IBMPlexSerif-Bold.ttf", 222, 29, 180),
}


def append_row(bpy, text, font, width, height, center, vertices, faces):
    curve = bpy.data.curves.new(text, "FONT")
    curve.body = text
    curve.font = font
    curve.fill_mode = "BOTH"
    curve.resolution_u = 3 if height >= 23 else 2
    curve.extrude = .02
    obj = bpy.data.objects.new(text, curve)
    bpy.context.scene.collection.objects.link(obj)
    graph = bpy.context.evaluated_depsgraph_get()
    outline = bpy.data.meshes.new_from_object(obj.evaluated_get(graph))
    outline.calc_loop_triangles()
    points = [tuple(vertex.co) for vertex in outline.vertices]
    x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
    y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
    z0, z1 = min(p[2] for p in points), max(p[2] for p in points)
    scale = min(width / (x1 - x0), height / (y1 - y0))
    depth = .64 / (z1 - z0)
    start = len(vertices) + 1
    # Sign coordinates are X right, Z up and Y through the face. This is a proper rotation.
    vertices.extend(((x - (x0+x1)/2)*scale, -(z - (z0+z1)/2)*depth, center + (y - (y0+y1)/2)*scale)
                    for x, y, z in points)
    faces.extend(tuple(start + i for i in triangle.vertices) for triangle in outline.loop_triangles)
    bpy.data.meshes.remove(outline)
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.curves.remove(curve)


def build():
    import bpy

    source = Path(__file__).resolve().parents[1] / "Resources/StreetRefinement"
    for key, sign in SIGNS.items():
        font = bpy.data.fonts.load(str(source / "SignFonts" / sign.font), check_existing=True)
        vertices, faces = [], []
        if sign.russian:
            append_row(bpy, sign.russian, font, sign.width, .51*sign.height, .24*sign.height, vertices, faces)
            append_row(bpy, sign.english, font, sign.width, .40*sign.height, -.25*sign.height, vertices, faces)
        else:
            append_row(bpy, sign.english, font, sign.width, .82*sign.height, 0, vertices, faces)
        assert faces, key
        name = "SM_N94_" + key
        lines = [f"# {sign.family} | {sign.text}", "o " + name, "usemtl EnamelLetters", "s off"]
        lines.extend("v %.5f %.5f %.5f" % point for point in vertices)
        lines.extend("vt %.5f %.5f" % (.5+(x+y*.07)/sign.width, .5+(z+y*.13)/sign.height) for x,y,z in vertices)
        lines.extend("f " + " ".join(f"{index}/{index}" for index in face) for face in faces)
        (source / (name + ".obj")).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"BILINGUAL_SIGN {key} | {sign.family} | {len(faces)} triangles")


if __name__ == "__main__":
    build()
