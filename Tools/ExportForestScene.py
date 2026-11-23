"""Export the supplied Forest Scene meshes and foliage textures in Unreal's centimeter scale.

Run with Blender in background mode. The Unity project and its scripts are never opened.
"""
from math import cos, sin, tau
from pathlib import Path
import re
from struct import pack, unpack_from
import zlib

import bpy
from mathutils import Vector


FOREST = Path.home() / 'Desktop/assets/Forest Scene/Forest Scene/Assets'
CONIFERS = FOREST / 'Assets/Conifers [BOTD]/Sources'
BUSHES = FOREST / 'Astra113 Assets/YughuesFreeBushes2018'
OUT = Path(__file__).resolve().parents[1] / 'Saved/BrightonDetail/ForestAssets'
OUT.mkdir(parents=True, exist_ok=True)


def write_obj(name, vertices, normals, uvs, sections):
    with (OUT / f'{name}.obj').open('w', encoding='ascii', newline='\n') as output:
        output.write(f'mtllib {name}.mtl\no {name}\n')
        for position, normal, uv in zip(vertices, normals, uvs):
            output.write('v %.6f %.6f %.6f\n' % tuple(position))
            output.write('vn %.6f %.6f %.6f\n' % tuple(normal))
            output.write('vt %.6f %.6f\n' % tuple(uv))
        for material, indices in sections:
            output.write(f'usemtl {material}\ns 1\n')
            for a, b, c in zip(*[iter(indices)] * 3):
                face_normal = (vertices[b] - vertices[a]).cross(vertices[c] - vertices[a])
                if face_normal.dot(normals[a] + normals[b] + normals[c]) < 0:
                    b, c = c, b
                output.write('f ' + ' '.join(f'{i+1}/{i+1}/{i+1}' for i in (a,b,c)) + '\n')
    (OUT / f'{name}.mtl').write_text(''.join(f'newmtl {material}\nKd 1.0 1.0 1.0\n\n'
                                           for material, _ in sections), encoding='ascii')


def export_conifer(variant):
    source = CONIFERS / 'Meshes' / f'Conifer {variant} LOD0.asset'
    text = source.read_text(encoding='utf-8-sig')
    vertices = int(re.search(r'm_VertexCount: (\d+)', text)[1])
    data = bytes.fromhex(re.search(r'_typelessdata: ([0-9a-f]+)', text)[1])
    stride, remainder = divmod(len(data), vertices)
    assert stride == 80 and remainder == 0, (source, stride, remainder)
    pos, normals, uv = [], [], []
    for offset in range(0, len(data), stride):
        x,y,z,nx,ny,nz = unpack_from('<6f',data,offset)
        pos.append(Vector((x*100,-z*100,y*100)))
        normals.append(Vector((nx,-nz,ny)))
        uv.append(unpack_from('<2f',data,offset+56))
    ground = min(p.z for p in pos)
    for vertex in pos:
        vertex.z -= ground
    indices = bytes.fromhex(re.search(r'm_IndexBuffer: ([0-9a-f]+)', text)[1])
    sections = []
    for material, (first, count) in zip(('Bark','Needles'), re.findall(r'firstByte: (\d+)\s+indexCount: (\d+)', text), strict=True):
        sections.append((material, unpack_from(f'<{count}H', indices, int(first))))
    write_obj('SM_ForestConifer' + variant, pos, normals, uv, sections)


def export_shrub(variant):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.obj_import(filepath=str(BUSHES / 'Meshes/OLD' / f'bush_{variant}.obj'), forward_axis='NEGATIVE_Z', up_axis='Y')
    shrub, = bpy.context.selected_objects
    shrub.data.materials.clear()
    shrub.data.materials.append(bpy.data.materials.get('Leaves') or bpy.data.materials.new('Leaves'))
    shrub.location.z -= min((shrub.matrix_world @ v.co).z for v in shrub.data.vertices)
    bpy.ops.wm.obj_export(filepath=str(OUT / f'SM_ForestShrub{variant}.obj'), export_selected_objects=True,
                          export_materials=True, export_normals=True, export_uv=True, forward_axis='Y', up_axis='Z')
    bpy.data.objects.remove(shrub, do_unlink=True)


def export_grass():
    pos, normals, uv, indices = [], [], [], []
    for index in range(3):
        angle = index * tau / 3
        right = Vector((cos(angle), sin(angle), 0))
        outward = Vector((-sin(angle), cos(angle), 0))
        up = Vector((0,0,1))
        pos.extend((-right*18, right*18, right*17+up*28+outward*6, -right*17+up*28+outward*6))
        normals.extend([outward] * 4)
        uv.extend(((0,0),(1,0),(1,1),(0,1)))
        indices.extend(index*4+i for i in (0,1,2,0,2,3))
    write_obj('SM_ForestGrass',pos,normals,uv,[('Grass',indices)])


def texture(source, name, maximum):
    image = bpy.data.images.load(str(source))
    width, height = image.size
    if max(width,height) > maximum:
        image.scale(round(width*maximum/max(width,height)),round(height*maximum/max(width,height)))
    image.file_format = 'PNG'
    image.filepath_raw = str(OUT / (name+'.png'))
    image.save()
    bpy.data.images.remove(image)


def photo_alpha(source, name):
    # The grass PSD uses a separate alpha channel that Blender's RGB import leaves out.
    data = source.read_bytes()
    signature,version,channels,height,width,depth,mode = unpack_from('>4sH6xHIIHH',data)
    assert (signature,version,channels,depth,mode) == (b'8BPS',1,4,8,3),source
    offset = 26
    for _ in range(3):
        offset += 4+unpack_from('>I',data,offset)[0]
    compression, = unpack_from('>H',data,offset)
    offset += 2
    if compression == 0:
        pixels = data[offset:offset+width*height*channels]
    else:
        assert compression == 1,source
        stride = height*channels
        lengths = unpack_from(f'>{stride}H',data,offset)
        offset += stride*2
        pixels = bytearray()
        for length in lengths:
            end = offset+length
            row = bytearray()
            while offset < end:
                run = data[offset]
                offset += 1
                if run < 128:
                    row.extend(data[offset:offset+run+1])
                    offset += run+1
                elif run > 128:
                    row.extend(bytes([data[offset]])*(257-run))
                    offset += 1
            assert len(row) == width
            pixels.extend(row)
    plane = width*height
    rgba = bytearray(plane*4)
    for index in range(4):
        rgba[index::4] = pixels[index*plane:(index+1)*plane]
    assert max(rgba[3::4]) > 200 and min(rgba[3::4]) < 10

    def chunk(kind, payload):
        return pack('>I',len(payload))+kind+payload+pack('>I',zlib.crc32(kind+payload))

    rows = b''.join(b'\0'+rgba[start:start+width*4] for start in range(0,len(rgba),width*4))
    (OUT/(name+'.png')).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',pack('>IIBBBBB',width,height,8,6,0,0,0))
        +chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))


for variant in ('Small','Medium','Tall'):
    export_conifer(variant)
for variant in ('02','05'):
    export_shrub(variant)
export_grass()

shared = CONIFERS / 'Shared Textures'
texture(shared/'BODT Conifer Trunk [Albedo] [Smoothness].tif','T_ForestBark',1024)
texture(shared/'BODT Conifer  Branches [Albedo] [Smoothness].tif','T_ForestNeedles',1024)
texture(shared/'BODT Conifer Branches_Normal combined.tif','T_ForestNeedles_N',1024)
for variant in ('02','05'):
    texture(BUSHES/'Textures'/f'T_Bush{variant}_d.tga',f'T_ForestShrub{variant}',1024)
grass = FOREST / 'Assets/Standard Assets/Environment/TerrainAssets/BillboardTextures/GrassFrond01AlbedoAlpha.psd'
photo_alpha(grass,'T_ForestGrass')
print('FOREST_EXPORT_OK')
