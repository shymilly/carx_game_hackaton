"""Keep the industrial freight branch clear of the skyline and cover both approaches."""
from itertools import product

import unreal as ue

from BrightonUpgrade import ACTORS, V
from CityLifeEnvironment import RAIL_HALF, RAIL_X

START, END = -7470, 20610
CENTER = (START + END) / 2
Y = -7771.43
RAIL_Z = 539.
SETBACK = 280
PORTAL_WIDTH = 340
PORTAL_LENGTH = 2520
TRACK_SECTION = 780
TRACK_LABELS = ("Industrial line ", "Industrial viaduct ", "Industrial branch local service")


def label(actor):
    return actor.get_actor_label().removeprefix("Third-floor view ")


def planar_bounds(mesh, transform):
    box = mesh.get_bounding_box()
    corners = [ue.MathLibrary.transform_location(transform,V(x,y,z)) for x,y,z in
               product((box.min.x,box.max.x),(box.min.y,box.max.y),(box.min.z,box.max.z))]
    return min(p.x for p in corners),max(p.x for p in corners),min(p.y for p in corners),max(p.y for p in corners)


def clip_residential_blocks(placed, shift):
    corridor_y = Y+shift.y
    lower,upper = corridor_y-SETBACK,corridor_y+SETBACK
    retired_windows = []
    for house in placed:
        if label(house)!="Distant Brighton residential block": continue
        pos,half = house.get_actor_bounds(False)
        left,right = pos.y-half.y,pos.y+half.y
        if pos.x+half.x<START or pos.x-half.x>END or right<=lower+.05 or left>=upper-.05:
            continue
        # Move only the rear edge at the railway. The other wall, street and roof height stay aligned.
        new_left,new_right=(max(left,upper),right) if pos.y>corridor_y else (left,min(right,lower))
        assert new_right-new_left>440,house.get_actor_label()
        front = pos.x+half.x if pos.x<2400 else pos.x-half.x
        for column in range(-2,3):
            center=pos.y+column*172
            if center-65<new_left or center+65>new_right:
                retired_windows.append((front,center))
        scale = house.get_actor_scale3d()
        scale.y *= (new_right-new_left)/(2*half.y)
        house.set_actor_scale3d(scale)
        pos.y = (new_left+new_right)/2
        house.set_actor_location(pos,False,True)

    if not retired_windows: return

    def removed_window(point):
        return any(abs(point.x-x)<28 and abs(point.y-y)<70 for x,y in retired_windows)

    lights = []
    for actor in placed:
        if not label(actor).startswith("Distant regular windows "):continue
        instances=actor.get_component_by_class(ue.InstancedStaticMeshComponent)
        if instances:
            for index in reversed(range(instances.get_instance_count())):
                if removed_window(instances.get_instance_transform(index,True).translation):
                    assert instances.remove_instance(index)
        elif isinstance(actor,ue.SpotLight) and removed_window(actor.get_actor_location()):
            lights.append(actor)
    if lights: assert ACTORS.destroy_actors(lights)


def give_skyline_clearance(placed, shift):
    for actor in placed:
        name=label(actor)
        if name not in ("North skyline layers","Side skyline layers"):continue
        instances=actor.get_component_by_class(ue.InstancedStaticMeshComponent)
        for index in range(instances.get_instance_count()):
            transform=instances.get_instance_transform(index,True)
            x0,x1,y0,y1=planar_bounds(instances.static_mesh,transform)
            point=transform.translation
            if name=="North skyline layers" and x1>START and x0<END:
                lower,upper=Y+shift.y-PORTAL_WIDTH,Y+shift.y+PORTAL_WIDTH
                if y1<=lower or y0>=upper:continue
                point.y += lower-y1-20 if point.y<Y+shift.y else upper-y0+20
            elif name=="Side skyline layers" and y1>shift.y-RAIL_HALF and y0<shift.y+RAIL_HALF:
                lower,upper=RAIL_X-230,RAIL_X+230
                if x1<=lower or x0>=upper:continue
                point.x += lower-x1-20 if point.x<RAIL_X else upper-x0+20
            else:
                continue
            transform.translation=point
            instances.update_instance_transform(index,transform,True,True,True)


def portal(layout, end, direction, steel, brick, dark):
    center = end + direction * PORTAL_LENGTH / 2
    mouth = end + direction * PORTAL_LENGTH
    roof = RAIL_Z + 455
    layout.box("Industrial line tunnel abutment",(center,Y,237),(PORTAL_LENGTH,656,520),brick,cull=49000)
    for side in (-1,1):
        wall_y=Y+side*279
        layout.box("Industrial line tunnel wall",(center,wall_y,747),(PORTAL_LENGTH,104,510),brick,cull=49000)
        layout.box("Industrial line portal jamb",(mouth,wall_y,749),(94,120,510),brick,cull=49000)
        layout.box("Industrial line tunnel cap",(center,wall_y,roof+48),(PORTAL_LENGTH,116,24),steel,cull=49000)
    layout.box("Industrial line tunnel roof",(center,Y,roof),(PORTAL_LENGTH,660,48),brick,cull=49000)
    layout.box("Industrial line portal lintel",(mouth,Y,roof),(96,681,66),brick,cull=49000)
    layout.box("Industrial line tunnel interior",(end-direction*9,Y,752),(14,458,510),dark,cull=49000)


def industrial_branch(layout):
    placed=ACTORS.get_all_level_actors()
    clip_residential_blocks(placed,layout.offset)
    give_skyline_clearance(ACTORS.get_all_level_actors(),layout.offset)

    steel=ue.load_asset("/Game/Prologue/CityLife/Materials/M_BridgePaint")
    ballast=ue.load_asset("/Game/Prologue/CityLife/Materials/M_TrackBallast")
    factory="/Game/Prologue/Street/RefinedFactory/Materials/M_Factory_"
    brick,dark=(ue.load_asset(factory+key) for key in ("brick","black"))
    length=END-START
    layout.box("Industrial line track bed",(CENTER,Y,RAIL_Z-30),(length,386,37),ballast,cull=49000)
    for x in range(START+TRACK_SECTION//2,END,TRACK_SECTION):
        layout.instance("Industrial line rails","RailStraight",(x,Y,RAIL_Z-6.2),(1,3.16,1),cull=49000)
    for side in (-1,1):
        beam_y=Y+side*194
        layout.box("Industrial line girder",(CENTER,beam_y,RAIL_Z-62),(length,32,88),steel,cull=49000)
        for x in range(START+TRACK_SECTION//2,END,TRACK_SECTION):
            layout.box("Industrial line ribs",(x,beam_y,RAIL_Z-62),(24,48,86),steel,cull=28000)
    for x in (-4750,-2310,-105,1410,3460,5700,7940,10180,12420,14620,16820):
        layout.box("Industrial viaduct masonry piers",(x,Y,206),(143,370,491),brick,cull=45000)
    portal(layout,START,1,steel,brick,dark)
    portal(layout,END,-1,steel,brick,dark)

    service=layout.actor(ue.CityRailTraffic,"Industrial branch local service",(CENTER,Y,RAIL_Z))
    consist=[]
    for key in ("FreightEngine","FreightGondola","FreightBoxcar","FreightGondola"):
        mesh=layout.models[key]
        box=mesh.get_bounding_box()
        assert box.max.z < 425 and max(abs(box.min.y),abs(box.max.y)) < 220,key
        assert box.max.x-box.min.x < PORTAL_LENGTH,key
        vehicle=ue.CityRailVehicle()
        vehicle.set_editor_properties(dict(mesh=mesh,length=box.max.x-box.min.x,
            mesh_yaw=180 if key=="FreightEngine" else 0))
        consist.append(vehicle)
    service.set_editor_properties(dict(consist=consist,half_route=length/2,covered_ends=True,
        interval=300.,first_pass_delay=95.,speed=980.))


def replace_industrial_branch(layout):
    previous=[actor for actor in ACTORS.get_all_level_actors() if label(actor).startswith(TRACK_LABELS)]
    if previous: assert ACTORS.destroy_actors(previous)
    industrial_branch(layout)
