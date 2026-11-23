"""Rebuild the five period traffic models and author separate rolling wheels."""
from collections import defaultdict
from math import sqrt
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project/'Tools'))
from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, LEVELS, factory_asset, media, save
from BrightonTrafficFleet import FOLDER, VARIANTS
from BrightonVehicleSurfaces import BODY_TOPS, CABINS, cabin_geometry, exterior_materials, face


DEST = FOLDER+'/Rolling'
WORK = project/'Saved/MovementReview/VehicleParts'
WORK.mkdir(parents=True, exist_ok=True)
ue.load_module('StaticMeshEditor')
WHEEL_NAMES = {'Tire','Wheel_hub','Wheel_center','Wheel_bolt','Hubcap','Center_cap','Hub_detail'}
WHEEL_RADIUS = dict(sedan=.318,coupe=.303,station_wagon=.322,pickup=.343,van=.334)


def split_source(file,model,radius):
    vertices = []
    objects = []
    for line in file.read_text(encoding='utf-8-sig').splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0]=='o':
            objects.append((parts[1], []))
        elif parts[0]=='v':
            vertices.append(tuple(map(float,parts[1:4])))
        elif parts[0]=='usemtl':
            material = parts[1].casefold()
        elif parts[0]=='f':
            polygon = [int(item.split('/')[0])-1 for item in parts[1:]]
            objects[-1][1].append((material,polygon))
    groups = defaultdict(list)
    body_faces = None
    wheel_source = {}
    for name,faces in objects:
        if name in ('Body','Main_body'):
            body_faces = faces
            continue
        lowered = name.lower()
        if lowered in ('cabin','window_pillar') or ('mirror' not in lowered and
                faces and all(material=='glass' for material,_ in faces)):
            continue
        if name not in WHEEL_NAMES:
            groups['Chassis'].extend(faces)
            continue
        coords = [vertices[index] for _,face in faces for index in face]
        axle = 'Front' if min(p[0] for p in coords)+max(p[0] for p in coords)>0 else 'Rear'
        side = 'Pos' if min(p[1] for p in coords)+max(p[1] for p in coords)>0 else 'Neg'
        groups[axle+side].extend(faces)
        if name=='Tire':
            wheel_source[axle+side] = bounds(coords)
    assert set(groups)=={'Chassis','FrontPos','FrontNeg','RearPos','RearNeg'}, file
    assert body_faces and len(wheel_source)==4,file
    for key,(lo,hi) in wheel_source.items():
        x,y,z = tuple((a+b)*.5 for a,b in zip(lo,hi))
        shrink = radius/((hi[2]-lo[2])*.5)
        for index in {index for _,face in groups[key] for index in face}:
            old_x,old_y,old_z = vertices[index]
            vertices[index] = (x+(old_x-x)*shrink,y+(old_y-y)*.89,radius+(old_z-z)*shrink)
    # The sides follow the real hubs. The old continuous side panel covered part of each tire.
    axle_x = [(wheel_source[key][0][0]+wheel_source[key][1][0])*.5 for key in ('FrontPos','RearPos')]
    body = [vertices[index] for _,face in body_faces for index in face]
    add_body_panels(vertices,groups['Chassis'],*bounds(body),axle_x,radius,model)
    cabin_geometry(vertices,groups['Chassis'],model)
    return vertices,groups


def bounds(positions):
    return tuple(map(min,zip(*positions))),tuple(map(max,zip(*positions)))


def add_body_panels(vertices,faces,lo,hi,axles,radius,model):
    x0,x1 = lo[0],hi[0]
    width = max(hi[1],-lo[1])
    rear,front,sill_width,sill_height = CABINS[model].belt
    profile = BODY_TOPS[model]
    stations = {x0+(x1-x0)*t/36 for t in range(37)}
    stations.update((rear,front))
    stations.update(x for x,_ in profile)
    arch = radius+.055
    for axle in axles:
        stations.update(axle+arch*t/8 for t in range(-8,9))
    rings = []
    positions = sorted({round(x,6) for x in stations})
    for x in positions:
        end_distance = min(x-x0,x1-x)
        half = width*(.88+.12*min(1,end_distance/.27))
        on_cab = rear<=x<=front
        if on_cab:
            half = max(half,sill_width+.012)
            top = sill_height-.003
        else:
            top = next((z0+(z1-z0)*(x-a)/(b-a) for (a,z0),(b,z1) in zip(profile,profile[1:]) if a<=x<=b),
                       profile[0][1] if x<profile[0][0] else profile[-1][1])
        lower = max(lo[2],*(radius+sqrt(max(0,arch**2-(x-axle)**2)) for axle in axles))
        lower = min(lower,top-.035)
        shoulder = max(lower+.012,top-.125)
        flat = max(half*.888,sill_width+.005) if on_cab else half*.888
        outline = ((-.82*half,lower+.016),(-.974*half,lower),(-half,shoulder),(-flat,top),
                   (flat,top),(half,shoulder),(.974*half,lower),(.82*half,lower+.016))
        ring = list(range(len(vertices),len(vertices)+len(outline)))
        vertices.extend((x,y,z) for y,z in outline)
        rings.append(ring)
    for xa,xb,left,right in zip(positions,positions[1:],rings,rings[1:]):
        in_cabin = rear<=xa and xb<=front
        for i in range(len(left)):
            j = (i+1)%len(left)
            if i==3 and in_cabin:
                for side,edge in ((-1,3),(1,4)):
                    a,b = vertices[left[edge]],vertices[right[edge]]
                    face(vertices,faces,'paint',(a,b,(xb,side*sill_width,b[2]),(xa,side*sill_width,a[2])),side>0)
            else:
                faces.append(('paint',[left[i],right[i],right[j],left[j]]))
    faces.append(('paint',rings[0]))
    faces.append(('paint',list(reversed(rings[-1]))))
    floor = max(lo[2]+.04,sill_height-.31)
    face(vertices,faces,'interior',((rear,-sill_width,floor),(front,-sill_width,floor),
                                    (front,sill_width,floor),(rear,sill_width,floor)))


def mesh_part(name,vertices,faces,turn,materials):
    indices = sorted({index for _,face in faces for index in face})
    remap = {raw:index for index,raw in enumerate(indices,1)}
    direction = -1 if turn else 1
    obj = ['o '+name]
    for index in indices:
        x,y,z = vertices[index]
        obj.append(f'v {100*x*direction:.5f} {100*y*direction:.5f} {100*z:.5f}')
        obj.append(f'vt {x/5.5+.5:.5f} {(y+.32*z)/3+.5:.5f}')
    current = None
    for material,face in faces:
        if material!=current:
            obj.append('usemtl '+material)
            current = material
        obj.append('f '+' '.join(f'{remap[item]}/{remap[item]}' for item in face))
    temp = WORK/(name+'.obj')
    temp.write_text('\n'.join(obj)+'\n',encoding='utf-8')
    mesh = media(temp,DEST+'/Meshes',replace_existing=True)
    for index,slot in enumerate(mesh.get_editor_property('static_materials')):
        imported = str(slot.get_editor_property('imported_material_slot_name')).casefold()
        material = next(materials[key] for key in sorted(materials,key=len,reverse=True) if imported.endswith(key))
        mesh.set_material(index,material)
    save(mesh)
    return mesh


def author(model):
    name = 'SM_'+model.title().replace('_','')+'94'
    original = ue.load_asset(FOLDER+'/Meshes/'+name)
    root = project/'Resources/Brighton/Vehicles'/model
    source = root/'car.obj'
    if model=='sedan':
        sedan_dir = project/'Resources/Brighton/Vehicles/DetailedSedan'
        sedan_dir.mkdir(exist_ok=True)
        for file in ('car.obj','car.mtl'):
            stored = sedan_dir/file
            if not stored.is_file():
                copy2(Path.home()/'Desktop/assets/american_90s_car_obj'/file,stored)
        source = sedan_dir/'car.obj'
    vertices,groups = split_source(source,model,WHEEL_RADIUS[model])
    # Infer the importer orientation from the existing asset and its original source.
    origin_verts = [float(line.split()[1])*100 for line in (root/'car.obj').read_text(encoding='utf-8-sig').splitlines()
                    if line.startswith('v ')]
    low,high = min(origin_verts),max(origin_verts)
    box = original.get_bounding_box()
    direct = abs(box.min.x-low)+abs(box.max.x-high)
    rotated = abs(box.min.x+high)+abs(box.max.x+low)
    assert min(direct,rotated)<1, (model,low,high,box)
    turn = rotated<direct
    palette = {line[7:].strip().casefold() for line in (root/'car.mtl').read_text(encoding='utf-8').splitlines()
               if line.startswith('newmtl ')}
    materials = {}
    for slot in original.get_editor_property('static_materials'):
        label = str(slot.get_editor_property('imported_material_slot_name')).casefold()
        key = next(key for key in palette if label.endswith(key))
        materials[key] = slot.get_editor_property('material_interface')
    for old,new in (('black','trim'),('tire','rubber'),('headlight','lamp'),('taillight','red')):
        materials[old] = materials[new]
    materials.update(exterior_materials(DEST+'/Materials',model,VARIANTS[model]))
    materials['black'] = materials['trim']
    used = {key for part in groups.values() for key,_ in part}
    imported_colors = {}
    for line in source.with_suffix('.mtl').read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if fields and fields[0]=='newmtl':
            name_key = fields[1].casefold()
        elif fields and fields[0]=='Kd':
            imported_colors[name_key] = tuple(map(float,fields[1:4]))
    for key in used-materials.keys():
        materials[key] = make_material(DEST+'/Materials','Vehicle_'+key,imported_colors[key],.44)
    pieces = {role:mesh_part(name+'_'+role,vertices,faces,turn,materials) for role,faces in groups.items()}
    chassis = pieces.pop('Chassis')
    assert materials['glass'] in [slot.material_interface for slot in chassis.get_editor_property('static_materials')]
    wheels = list(pieces.values())
    for mesh in wheels:
        bounds = mesh.get_bounds()
        assert abs(bounds.box_extent.z-100*WHEEL_RADIUS[model])<.5 and abs(bounds.origin.z-bounds.box_extent.z)<.4,mesh
        assert abs(bounds.origin.x)>110 and abs(bounds.origin.y)>65, mesh
    assert len({(w.get_bounds().origin.x>0,w.get_bounds().origin.y>0) for w in wheels})==4
    appearance = ue.StreetTrafficModel()
    appearance.set_editor_properties(dict(chassis=chassis,wheels=wheels))
    parked = mesh_part(name+'_Parked',vertices,[face for part in groups.values() for face in part],turn,materials)
    editor = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    editor.remove_collisions(parked)
    assert editor.add_simple_collisions(parked,ue.ScriptCollisionShapeType.NDOP18)>=0
    save(parked)
    ue.log(f'CAR_KIT_MODEL {model} wheel radii {[round(w.get_bounds().box_extent.z,1) for w in wheels]} flip={turn}')
    return original,appearance,parked


factory = ue.DataAssetFactory()
factory.set_editor_property('data_asset_class',ue.StreetTrafficFleetAppearance)
fleet = factory_asset(DEST,'DA_RollingFleet',ue.StreetTrafficFleetAppearance,factory)
models = [author(model) for model in VARIANTS]
fleet.set_editor_property('models',{model:appearance for model,appearance,_ in models})
save(fleet)
assert ue.EditorLoadingAndSavingUtils.load_map('/Game/Locations/L_NeptuneStreet')
actors = ACTORS.get_all_level_actors()
flow, = [actor for actor in actors if isinstance(actor,ue.StreetTrafficFlow)]
assert set(flow.get_editor_property('fleet_meshes'))==set(fleet.get_editor_property('models').keys())
flow.set_editor_property('fleet_appearance',fleet)
parked_models = {model.get_name():parked for model,_,parked in models}
for actor in actors:
    if actor.actor_has_tag('Brighton1994ParkedCar'):
        body = actor.get_component_by_class(ue.StaticMeshComponent)
        name = body.static_mesh.get_name().removesuffix('_Parked')
        body.set_static_mesh(parked_models[name])
        body.set_editor_property('override_materials',[])
assert LEVELS.save_current_level()
ue.log('CAR_KIT_READY five rebuilt rolling chassis, tires and matching parked variants')
