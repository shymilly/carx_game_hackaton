"""Make an editable fridge and export its fixed cabinet. Run with Blender -b -P."""
from pathlib import Path
import math

import bmesh
import bpy


PROJECT = Path(__file__).resolve().parents[1]
NORMALIZED = PROJECT / "SourceAssets" / "Furniture"
OUTPUT = PROJECT / "SourceAssets" / "Blender"
CABINET = "Kitchen_FridgeCabinetShelved"


def import_obj(stem):
    bpy.ops.wm.obj_import(filepath=str(NORMALIZED / f"{stem}.obj"), forward_axis="Y", up_axis="Z")
    return bpy.context.selected_objects[0]


def add_box(name, position, dimensions, material, pieces, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        edges = obj.modifiers.new("Rounded edges", "BEVEL")
        edges.width = bevel
        edges.segments = 1
        bpy.ops.object.modifier_apply(modifier=edges.name)
    pieces.append(obj)
    return obj


def wire(name, x, y, z, length, crosswise, material, pieces):
    rotation = (math.pi / 2, 0, 0) if crosswise else (0, math.pi / 2, 0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=.26, depth=length, location=(x, y, z), rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    pieces.append(obj)


def join_pieces(name, pieces):
    bpy.ops.object.select_all(action="DESELECT")
    for piece in pieces:
        piece.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = name
    return result


def make_wire_shelf(name, z, white, pieces):
    module = []
    for y in (-31.5, 31.5):
        add_box("Molded support rail", (33.4, y, z - .5), (52, 1.8, 1.5), white, module, .22)
    for x in (8.2, 58.6):
        add_box("Shelf edge rail", (x, 0, z), (1.6, 62.2, 1), white, module, .25)
    for i in range(-8, 9):
        wire("Coated wire", 33.4, i * 3.4, z, 50.4, False, white, module)
    wire("Wire stiffener", 33.4, 0, z - .35, 61.6, True, white, module)
    pieces.append(join_pieces(name, module))


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = .01
    cabinet = import_obj("Kitchen_FridgeBody")
    doors = import_obj("Kitchen_FridgeDoors")
    doors.name = "Original doors (rotation reference)"
    cabinet.name = "Fixed cabinet shell"
    assert not cabinet.modifiers
    # Resolve the existing centimeter-space OBJ transform before editing the shell.
    bpy.ops.object.select_all(action="DESELECT")
    cabinet.select_set(True)
    bpy.context.view_layer.objects.active = cabinet
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    mesh = cabinet.data
    low = min(vertex.co.x for vertex in mesh.vertices)
    high = max(vertex.co.x for vertex in mesh.vertices)
    assert -1.7 < low < -1.5 and 66.1 < high < 66.4, (low, high)
    center_sum = low + high

    # Bring the shell's openings to the side with the unchanged door assembly.
    # Pull the cavity back planes deeper so the liner holds full-depth shelves.
    topology = bmesh.new()
    topology.from_mesh(mesh)
    for vertex in topology.verts:
        x = vertex.co.x
        vertex.co.x = 61.5 if 63.30 < x < 63.45 else center_sum - x
    bmesh.ops.reverse_faces(topology, faces=list(topology.faces))
    topology.to_mesh(mesh)
    topology.free()
    mesh.update()
    white = next(material for material in cabinet.data.materials if material.name.startswith("White"))
    pieces = [cabinet]
    add_box("Insulated partition", (30.3, 0, 23.2), (62.65, 63.4, 2.6), white, pieces, .35)
    for name, z in (("Lower wire shelf", -31), ("Upper wire shelf", -2), ("Freezer wire shelf", 55)):
        make_wire_shelf(name, z, white, pieces)

    cover = []
    add_box("Crisper cover", (32, 0, -57.5), (53, 63.5, 1.3), white, cover, .3)
    add_box("Crisper cover front edge", (5.8, 0, -58.1), (2.5, 63.5, 2.4), white, cover, .3)
    pieces.append(join_pieces("Lower produce shelf", cover))

    # Keep the covers and shelves as distinct editable objects in the Blender source.
    # Material IDs in Blender are global, so all fixed parts share the shell's white slot.
    OUTPUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    cabinet.select_set(True)
    bpy.context.view_layer.objects.active = cabinet
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / f"{CABINET}.blend"))

    merged = join_pieces(CABINET, pieces)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    merged.data.calc_loop_triangles()
    bpy.ops.wm.obj_export(filepath=str(OUTPUT / f"{CABINET}.obj"), export_selected_objects=True,
                          export_materials=True, forward_axis="Y", up_axis="Z")
    print(f"FRIDGE_BLENDER_EXPORT_OK {len(merged.data.vertices)} vertices, {len(merged.data.loop_triangles)} tris")


if __name__ == "__main__":
    build()
