"""Build full-size exterior door meshes with recessed joinery and separate finishes."""
from math import cos, sin, tau

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import LIB, P, PROJECT, constant, media, output, save


PACK = '/Game/StreetArtPass/Entrances'
HALF_WIDTH = 74.
HEIGHT = 240.
STEP_HEIGHT = 7.4
STEP_DEPTH = 39.


class DoorMesh:
    def __init__(self):
        self.faces = []

    def extrusion(self, back, shoulder, front, material):
        self.faces.append((material, back))
        self.faces.append((material, tuple(reversed(front))))
        for inner, outer in ((back, shoulder),(shoulder, front)):
            for i in range(len(inner)):
                j = (i+1) % len(inner)
                self.faces.append((material, (inner[i],outer[i],outer[j],inner[j])))

    def block(self, x0, x1, z0, z1, y0, y1, bevel, material):
        def ring(y, inset):
            return ((x0+inset,y,z0+inset),(x1-inset,y,z0+inset),
                    (x1-inset,y,z1-inset),(x0+inset,y,z1-inset))
        self.extrusion(ring(y0,0),ring(y1-bevel,0),ring(y1,bevel),material)

    def knob(self, x, z, y0, y1, radius, material):
        def ring(y, r):
            return tuple((x+r*cos(tau*i/12),y,z+r*sin(tau*i/12)) for i in range(12))
        self.extrusion(ring(y0,radius),ring(y1-.9,radius*1.10),ring(y1,radius*.81),material)

    def write(self, path):
        lines = ['o '+path.stem, 's off']
        index = 1
        previous = None
        for material, face in sorted(self.faces, key=lambda item: item[0]):
            if material != previous:
                lines.append('usemtl '+material)
                previous = material
            a, b, c, *_ = (ue.Vector(*point) for point in face)
            normal = ue.MathLibrary.cross_vector_vector(b-a,c-a).to_tuple()
            dominant = max(range(3), key=lambda axis: abs(normal[axis]))
            u, v = ((1,2),(0,2),(0,1))[dominant]
            # Outward is +Y here. Interchange reflects the file's Y onto the mesh's -Y frontage.
            lines.extend('v %.5f %.5f %.5f' % point for point in face)
            lines.extend('vt %.6f %.6f' % (point[u]/110,point[v]/110) for point in face)
            for corner in range(1,len(face)-1):
                lines.append('f ' + ' '.join(f'{i}/{i}' for i in (index,index+corner,index+corner+1)))
            index += len(face)
        path.write_text('\n'.join(lines)+'\n',encoding='ascii')


def joinery(style):
    mesh = DoorMesh()
    box = mesh.block
    box(-72.8,72.8,0,STEP_HEIGHT,-3.5,STEP_DEPTH,1.5,'Stone')
    for side in (-1,1):
        a,b = sorted((side*58.,side*70.6))
        box(a,b,STEP_HEIGHT-.6,234.,-3.2,14.2,.85,'Stone')
        a,b = sorted((side*51.6,side*59.))
        box(a,b,STEP_HEIGHT,229.,-2.9,11.2,.55,'Finish')
    box(-HALF_WIDTH,HALF_WIDTH,230.6,HEIGHT,-3.5,17.2,.75,'Stone')
    box(-58.2,58.2,225.,231.0,-2.8,10.8,.48,'Finish')
    box(-53.,53.,7.1,227.,-2.9,1.2,.30,'Recess')
    box(-53.,53.,196.3,202.5,.7,10.7,.52,'Finish')
    box(-51.7,51.7,201.9,225.3,.7,4.9,.15,'Glass')
    for x in (-17.2,17.2):
        box(x-1.0,x+1.0,202,225.3,3.4,7.3,.22,'Finish')

    # Continuous leaf rails shield the panel edges, so the recesses read at oblique angles.
    for x0,x1 in ((-52.5,-42.2),(42.2,52.5)):
        box(x0,x1,8.1,197.15,1.,8.7,.42,'Finish')
    box(-42.4,42.4,8.1,21.0,1.,8.1,.55,'Finish')
    box(-42.4,42.4,182.9,197.15,1.,8.1,.55,'Finish')
    box(-42.4,42.4,82.6,94.5,1.,8.3,.48,'Finish')
    glass_panel = style == 'Steel'
    box(-2.8,2.8,20.7,182.95,1.2,8.1,.32,'Finish')
    for x0,x1 in ((-42.6,-2.4),(2.4,42.6)):
        for z0,z1 in ((20.5,83.2),(94.1,183.4)):
            glazed = glass_panel and z0>90
            panel = 'Glass' if glazed else 'Finish'
            if glazed:
                for edge in (x0,x1-2.5):
                    box(edge,edge+2.5,z0,z1,1,6.25,.47,'Finish')
                for edge in (z0,z1-3.2):
                    box(x0+2.4,x1-2.4,edge,edge+3.2,1,6.25,.47,'Finish')
            else:
                box(x0,x1,z0,z1,1,6.25,.90,'Finish')
            box(x0+2.5,x1-2.5,z0+3.2,z1-3.2,4.2,5.1 if glazed else 7.65,.54,panel)
            if glazed:
                box(x0+.4,x1-.4,138.4,141.4,4.6,7.4,.35,'Finish')

    if glass_panel:
        box(-49,49,11.8,20.2,7.75,8.7,.22,'Hardware')
        box(43.7,50.2,90.3,119.8,8.2,9.4,.32,'Hardware')
        for z in (96.6,115.2):
            mesh.knob(47,z,9.2,14.3,1.32,'Hardware')
        box(45.65,48.35,96.2,115.6,13.1,15.35,.45,'Hardware')
    else:
        box(43.2,50.8,91.5,110.5,8.42,9.85,.52,'Hardware')
        mesh.knob(47,103.7,9.2,13.6,2.15,'Hardware')
        mesh.knob(47,103.7,12.3,15.75,2.75,'Hardware')
        box(46.38,47.62,95.3,97.8,9.6,10.0,.12,'Recess')
        box(-14.6,14.6,87.4,91.4,8.1,8.8,.30,'Hardware')
        box(-11.1,11.1,88.3,90.3,8.55,9.03,.15,'Recess')
    return mesh


def make_entry_meshes():
    base = PROJECT / 'Saved/BrightonEntranceFix/Meshes'
    base.mkdir(parents=True,exist_ok=True)
    materials = {
        'Stone': ue.load_asset('/Game/StreetArtPass/Materials/M_Wall_WeatheredConcrete'),
        'Glass': ue.load_asset('/Game/Prologue/Street/Materials/M_dark_glass'),
        'Recess': ue.load_asset('/Game/Prologue/ModernFinishes/Materials/M_dark_metal'),
        'Hardware': make_material(PACK,'EntranceWeatheredBronze',(.23,.147,.069),.43),
    }
    brass = materials['Hardware']
    if not LIB.get_material_property_input_node(brass,P.MP_METALLIC):
        output(constant(brass,.71),brass,P.MP_METALLIC)
        LIB.recompile_material(brass)
        save(brass)
    finishes = {
        'Oak': ue.load_asset('/Game/Prologue/ModernFinishes/Materials/M_oak'),
        'Painted': make_material(PACK,'EntrancePaintedTimber',(.069,.111,.085),.53),
        'Steel': make_material(PACK,'EntranceBlueEnamel',(.081,.102,.131),.42),
    }
    meshes = {}
    for style,finish in finishes.items():
        materials['Finish'] = finish
        name = f'SM_BrightonEntry_{style}'
        path = base / (name + '.obj')
        joinery(style).write(path)
        result = media(path,PACK+'/Meshes')
        slots = set()
        for index,slot in enumerate(result.static_materials):
            original = str(slot.get_editor_property('imported_material_slot_name'))
            key = next(key for key in materials if original.endswith(key))
            result.set_material(index,materials[key])
            slots.add(key)
        assert slots == set(materials), (style, slots)
        box = result.get_bounding_box()
        assert abs(box.max.z-HEIGHT)<.1 and abs(box.min.y+STEP_DEPTH)<.1, (style,box)
        save(result)
        meshes[style] = result
    return meshes
