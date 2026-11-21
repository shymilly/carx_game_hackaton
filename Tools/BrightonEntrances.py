"""Replace street entrance assemblies and clear the architectural bay and sidewalk in front."""
from math import atan2, degrees

import unreal as ue

from BrightonEntranceMeshes import HALF_WIDTH, HEIGHT, STEP_DEPTH, STEP_HEIGHT, make_entry_meshes
from BrightonUpgrade import ACTORS, V


CURB = -11.95
TAG = ue.Name('BrightonResidentialEntry')
FACADES = {
    'South block brownstones': (0,1), 'South block walk-up': (0,1), 'Corner row house': (0,1),
    'Corner apartments beside Dima': (0,-1), 'South extension brick walk-up': (0,-1),
    'South extension brownstone': (0,-1), 'Fork perspective townhouses': (0,-1),
    'Weathered tenement west': (-1,0), 'Weathered tenement east': (-1,0),
    'Tall apartment opposite Neptune': (-1,0), 'Cross-street apartments': (-1,0),
    'Far east cross-street block': (-1,0), 'Eastbound perspective row': (-1,0),
}
WINDOW_PARTS = {'stone reveal', 'glazing', 'side jamb', 'horizontal jamb', 'center mullion',
                'transom', 'projecting sill', 'drawn curtain', 'projected window light'}
LEGACY_PARTS = {'Entry stone backplate','Closed decorative entry leaf','Dark transom glass','Entry jamb pilaster',
    'Lower door inset','Upper door inset','Door handle','Letter slot','Masonry entry crown','Deep canvas entrance awning',
    'Awning valance','Awning brace','Facade lamp cast mounting','Facade lamp ribbed glass','Facade iron canopy',
    'Facade lintel drip edge','Ground-floor cast iron meter panel','Stone base planter','Low plant outside residence'}


def label(actor):
    return actor.get_actor_label().removeprefix('Third-floor view ')


def saved_anchors(placed, shift):
    result = {}
    for actor in placed:
        name = label(actor).removesuffix(' stone threshold')
        if name not in FACADES or not (actor.actor_has_tag(TAG) or actor.actor_has_tag('BrightonBlockDressing')):
            continue
        if not label(actor).endswith(' stone threshold'):
            continue
        position = actor.get_actor_location()-shift
        nx, _ = FACADES[name]
        result[name] = position.y if nx else position.x
    return result


def clear_old_entries(placed):
    old = [a for a in placed if a.actor_has_tag(TAG) or (a.actor_has_tag('BrightonBlockDressing') and (
        label(a) in LEGACY_PARTS or label(a).removesuffix(' stone threshold') in FACADES
        and label(a).endswith(' stone threshold')))]
    if old:
        assert ACTORS.destroy_actors(old)


def clear_window_bay(placed, house, center, along, tangent, normal, across, face, shift):
    """Remove complete affected openings, including higher rows whose sills reach the lintel."""
    group = [(label(a)[len(house)+1:],a) for a in placed if label(a).startswith(house+' ')
             and label(a)[len(house)+1:] in WINDOW_PARTS]
    bays = []
    for suffix,actor in group:
        if suffix != 'stone reveal':
            continue
        component = actor.get_component_by_class(ue.InstancedStaticMeshComponent)
        for index in range(component.get_instance_count()):
            transform = component.get_instance_transform(index,True)
            point = transform.translation-shift
            if abs((getattr(point,normal)-face)*across)>34:
                continue
            half_width = abs(getattr(transform.scale3d,tangent))*50
            half_height = abs(transform.scale3d.z)*50
            if point.z-half_height-8 < CURB+HEIGHT+1:
                bays.append((getattr(point,tangent),point.z,half_width,half_height))
    if along is None:
        along = min(bays,key=lambda bay: abs(bay[0]-center))[0] if bays else center
    overlaps = [bay for bay in bays if abs(bay[0]-along)<HALF_WIDTH+bay[2]+10]
    if overlaps:
        along = min(overlaps,key=lambda bay: abs(bay[0]-along))[0]
        overlaps = [bay for bay in bays if abs(bay[0]-along)<HALF_WIDTH+bay[2]+10]
    for suffix,actor in group:
        def belongs(position):
            p = position-shift
            return abs(getattr(p,normal)-face)<55 and any(
                abs(getattr(p,tangent)-x)<w+12 and abs(p.z-z)<h+24 for x,z,w,h in overlaps)

        component = actor.get_component_by_class(ue.InstancedStaticMeshComponent)
        if component:
            for index in reversed(range(component.get_instance_count())):
                if belongs(component.get_instance_transform(index,True).translation):
                    assert component.remove_instance(index)
        elif suffix == 'projected window light' and belongs(actor.get_actor_location()):
            assert ACTORS.destroy_actor(actor)
    if overlaps:
        ue.log(f'ENTRANCE_WINDOW_CLEAR {house}: {len(overlaps)} replaced below the lintel')
    return along


def move_tree_group(placed, shift):
    old = V(-5168,-568,-12)
    move = V(-312,0,0)
    offsets = {'Autumn trees': [(0,0)], 'Unglazed street tree wells': [(0,0)], 'Low shrubs': [(48,-30),(-27,41)]}
    moved = 0
    for actor in placed:
        name = label(actor)
        if name in offsets:
            component = actor.get_component_by_class(ue.InstancedStaticMeshComponent)
            for index in range(component.get_instance_count()):
                transform = component.get_instance_transform(index,True)
                point = transform.translation-shift-old
                if any(abs(point.x-x)<.3 and abs(point.y-y)<.3 for x,y in offsets[name]):
                    transform.translation += move
                    assert component.update_instance_transform(index,transform,True,True,True)
                    moved += 1
        elif name == 'Tree trunk collision':
            point = actor.get_actor_location()-shift-old
            if abs(point.x)<.3 and abs(point.y)<.3:
                actor.set_actor_location(actor.get_actor_location()+move,False,True)
    if moved:
        assert moved==4, moved
        ue.log('ENTRANCE_TREE_CLEAR birch, tree well and both shrubs relocated together')


def clear_old_boards(placed, shift):
    for actor in placed:
        if not label(actor).startswith('Detail instances'):
            continue
        component = actor.get_component_by_class(ue.InstancedStaticMeshComponent)
        if not component or not component.get_material(0):
            continue
        material = component.get_material(0).get_name()
        if material not in ('M_ply','M_dark_stone'):
            continue
        for index in reversed(range(component.get_instance_count())):
            p = component.get_instance_transform(index,True).translation-shift
            if 3358 < p.x < 3370 and abs(p.y+4424)<2 and 90<p.z<174:
                assert component.remove_instance(index)
                ue.log(f'ENTRANCE_BOARD_CLEAR {material} at {p}')


def build_entries(city, placed, anchors, meshes=None):
    meshes = meshes or make_entry_meshes()
    move_tree_group(placed,city.offset)
    clear_old_boards(placed,city.offset)
    by_label = {label(a):a for a in placed}
    for index, (name,(nx,ny)) in enumerate(FACADES.items()):
        house = by_label[name]
        center, extent = house.get_actor_bounds(False)
        center -= city.offset
        tangent,normal = ('y','x') if nx else ('x','y')
        across = nx or ny
        face = getattr(center,normal)+across*getattr(extent,normal)
        along = clear_window_bay(placed,name,getattr(center,tangent),anchors.get(name),tangent,normal,across,face,city.offset)
        x,y = (face,along) if nx else (along,face)
        yaw = degrees(atan2(nx,-ny))
        style = ('Oak','Painted','Steel')[index%3]
        mesh = city.individual(name+' entrance',meshes[style],(x,y,CURB),yaw)
        mesh.tags = [*mesh.tags,TAG]
        mesh.get_component_by_class(ue.StaticMeshComponent).set_cull_distance(9500)

        step_center = (STEP_DEPTH-3.5)*.5
        step = city.solid(name+' stone threshold',(x+nx*step_center,y+ny*step_center,CURB+STEP_HEIGHT/2),
                          (144,STEP_DEPTH+3.4,STEP_HEIGHT),'stone',yaw)
        step.tags = [*step.tags,TAG]
        step.set_actor_hidden_in_game(True)
        step.get_component_by_class(ue.StaticMeshComponent).set_editor_properties(dict(
            cast_shadow=False,affect_distance_field_lighting=False))
        keep = ue.AttachmentRule.KEEP_WORLD
        assert step.attach_to_actor(mesh,ue.Name(),keep,keep,keep,False)

        edge = 3250 if nx else (-2080 if ny>0 else -451)
        gap = (edge-face)*across
        if gap>1 and name+' paved setback' not in by_label:
            surface = (face+edge)*.5
            p = (surface,center.y,-24.4) if nx else (center.x,surface,-24.4)
            city.solid(name+' paved setback',p,(2*getattr(extent,tangent),gap+2,25),'pavement',yaw)
        if name=='Corner row house' and 'Vintage wall advert 02' in by_label:
            advert = by_label['Vintage wall advert 02']
            point = advert.get_actor_location()-city.offset
            if abs(point.x-along)<HALF_WIDTH+22 and abs(point.y-face)<5:
                point.x = along+110
                advert.set_actor_location(point+city.offset,False,True)
        ue.log(f'ENTRANCE_PLACED {name} {style} at {(x,y,CURB)}')
