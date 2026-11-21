"""Import the supplied period cars and route them through the two right-hand approaches."""
from math import cos, pi, sin
from pathlib import Path
from shutil import copy2

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, LIB, P, PROJECT, V, constant, media, output, save

FOLDER = '/Game/Prologue/Brighton/Traffic'
VARIANTS = {
    'sedan': (.105, .205, .277),
    'coupe': (.337, .070, .075),
    'station_wagon': (.385, .358, .235),
    'pickup': (.083, .225, .203),
    'van': (.346, .358, .397),
}
PARKED = ue.Name('Brighton1994ParkedCar')


def load_fleet():
    source = PROJECT/'Resources/Brighton/Vehicles'
    desktop = Path.home()/'Desktop/assets/five_cars'
    staging = PROJECT/'Saved/BrightonActRepair/Vehicles'
    staging.mkdir(parents=True, exist_ok=True)
    materials, cars = {}, {}
    meshes = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    for model, paint in VARIANTS.items():
        directory = source/model
        if not directory.exists():
            directory.mkdir(parents=True)
        for name in ('car.obj', 'car.mtl'):
            if not (directory/name).is_file():
                copy2(desktop/model/name, directory/name)
        model_name = 'SM_' + model.title().replace('_', '') + '94'
        path = staging/(model_name+'.obj')
        rows = ['o '+model_name]
        for row in (directory/'car.obj').read_text(encoding='utf-8-sig').splitlines():
            if row.startswith('v '):
                x,y,z = (float(value) for value in row.split()[1:4])
                rows.append(f'v {x*100:.5f} {y*100:.5f} {z*100:.5f}')
                rows.append(f'vt {x/5.5+.5:.5f} {(y+.32*z)/3+.5:.5f}')
                continue
            if row.startswith(('o ', 'mtllib ', 's ')):
                continue
            if row.startswith('f '):
                row = 'f ' + ' '.join(f'{v}/{v}' for v in row.split()[1:])
            rows.append(row)
        path.write_text('\n'.join(rows)+'\n', encoding='utf-8')
        mesh = media(path,FOLDER+'/Meshes',replace_existing=True)
        box = mesh.get_bounding_box()
        assert 450 < box.max.x-box.min.x < 520 and 205 <= box.max.y-box.min.y < 224
        assert abs(box.min.z)<.2 and 130 < box.max.z < 195, (model,box)
        slots = mesh.get_editor_property('static_materials')
        colors = {}
        for row in (directory/'car.mtl').read_text(encoding='utf-8-sig').splitlines():
            fields = row.split()
            if row.startswith('newmtl '):
                active = fields[1]
            elif row.startswith('Kd '):
                colors[active] = tuple(map(float,fields[1:4]))
        seen = set()
        for index, slot in enumerate(slots):
            imported = str(slot.get_editor_property('imported_material_slot_name')).lower()
            name = next(key for key in colors if imported.endswith(key.lower()))
            seen.add(name)
            key = model.title().replace('_','')+'_Paint' if name=='Paint' else name
            if key not in materials:
                roughness = {'Paint':.31,'Glass':.24,'Rubber':.85,'Chrome':.24,'Metal':.41}.get(name,.49)
                tint = paint if name=='Paint' else colors[name]
                material = make_material(FOLDER,key,tint,roughness)
                metal = {'Paint':.37,'Chrome':.70,'Metal':.59}.get(name,0)
                if metal and not LIB.get_material_property_input_node(material,P.MP_METALLIC):
                    output(constant(material,metal),material,P.MP_METALLIC)
                LIB.recompile_material(material)
                save(material)
                materials[key] = material
            mesh.set_material(index,materials[key])
        assert seen == set(colors), (model,seen)
        if meshes:
            meshes.remove_collisions(mesh)
            assert meshes.add_simple_collisions(mesh,ue.ScriptCollisionShapeType.BOX)>=0
        save(mesh)
        cars[model]=mesh
        ue.log(f'BRIGHTON_CAR_IMPORTED {model}: {box.max.x-box.min.x:.1f}×{box.max.y-box.min.y:.1f}×{box.max.z:.1f} cm')
    return cars


def right_hand_traffic(cars):
    flow, = [actor for actor in ACTORS.get_all_level_actors() if isinstance(actor,ue.StreetTrafficFlow)]
    # Along +X the right lane is +Y, and along +Y the right lane is -X.
    east = [(-8640,-1075)]+[(1715+535*sin(pi*i/40),-540-535*cos(pi*i/40)) for i in range(21)]+[(2250,6450)]
    west = [(2250,-6460)]+[(1730+520*cos(pi*i/40),-1965+520*sin(pi*i/40)) for i in range(21)]+[(-8640,-1445)]
    north = [(2250,-6460),(2250,6450)]
    south = [(2600,6450),(2600,-6460)]
    for field, points in zip(('eastbound','westbound','northbound','southbound'),(east,west,north,south)):
        lane = flow.get_editor_property(field)
        lane.clear_spline_points(False)
        for index, (x,y) in enumerate(points):
            lane.add_spline_point(V(x,y,-28),ue.SplineCoordinateSpace.WORLD,False)
            lane.set_spline_point_type(index,ue.SplinePointType.LINEAR,False)
        lane.update_spline()
    flow.set_editor_properties(dict(car_mesh=cars['sedan'],fleet_meshes=list(cars.values()),paint_slot=-1,paints=[]))


def replace_parked_cars(cars):
    for actor in ACTORS.get_all_level_actors():
        mesh = actor.get_component_by_class(ue.StaticMeshComponent)
        if not mesh or not mesh.static_mesh or not (mesh.static_mesh.get_name()=='SM_Sedan94'
                or actor.actor_has_tag(PARKED)):
            continue
        location = actor.get_actor_location()
        kind = ('pickup' if location.x<-3500 else 'station_wagon') if location.x<0 else (
            'sedan' if location.y<-2800 else 'coupe')
        mesh.set_static_mesh(cars[kind])
        mesh.set_editor_property('override_materials',[])
        if not actor.actor_has_tag(PARKED):
            actor.tags = list(actor.tags)+[PARKED]
