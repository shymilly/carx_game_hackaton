"""The four-floor walk-up, the apartment threshold and the enclosed chase route."""
from math import atan2, cos, degrees, hypot, sin
import re

import unreal as ue

from ActOneScenes import Scene, attach, named, rot
from BrightonUpgrade import ACTORS, LIB, V, save
from CityLifeCharacters import PEOPLE, apply_profile

TAG=ue.Name('FedorBuildingAndPursuit')
FLOOR=270
ENTRY_TOP=3*FLOOR
BRICK='/Game/StreetArtPass/Materials/M_Wall_AgedRedBrick'
CAST_IRON='/Game/Prologue/ModernFinishes/Materials/M_dark_metal'
FENCE='/Game/ImportedAssets/Industrial/ExteriorPack/Models/IndustrialHorror_PS_like/SM_IndustrialHorror_PS_like_Fence_long'
WET='/Game/Prologue/Brighton/Materials/M_Wet_'


class ExistingScene(Scene):
    def __init__(self,location):
        self.folder='Act One/'+location
        self.materials={}
        self.shapes={name:ue.load_asset('/Engine/BasicShapes/'+name) for name in ('Cube','Sphere','Cylinder','Plane')}
        self.director=next(a for a in ACTORS.get_all_level_actors() if isinstance(a,ue.ActOneDirector))

    def spawn(self,*args,**kwargs):
        actor=super().spawn(*args,**kwargs)
        actor.tags=list(actor.tags)+[TAG]
        return actor


def existing_mesh(scene,label,mesh,center,size,yaw=0,collision=False,material=None):
    bounds=mesh.get_bounding_box()
    length=bounds.max-bounds.min
    scale=V(*(requested/real for requested,real in zip(size,length.to_tuple())))
    local=ue.Transform(location=V(),rotation=rot(yaw),scale=scale)
    offset=ue.MathLibrary.transform_location(local,(bounds.min+bounds.max)*.5)
    a=scene.spawn(ue.StaticMeshActor,label,(V(*center)-offset).to_tuple(),yaw)
    c=a.get_component_by_class(ue.StaticMeshComponent)
    c.set_static_mesh(mesh)
    if material:
        for slot in range(c.get_num_materials()): c.set_material(slot,material)
    c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
    c.set_editor_properties(dict(cast_shadow=True,affect_distance_field_lighting=collision))
    if mesh.get_editor_property('nanite_settings').get_editor_property('enabled'):
        for surface in set(c.get_materials()):
            if isinstance(surface,ue.Material):
                LIB.set_material_usage(surface,ue.MaterialUsage.MATUSAGE_NANITE)
                save(surface)
    a.set_actor_scale3d(scale)
    return a


def floor_box(scene,name,x0,x1,y0,y1,top,thickness,material):
    return scene.box(name,((x0+x1)/2,(y0+y1)/2,top-thickness/2),(x1-x0,y1-y0,thickness),material)


def wall_x(scene,name,x,y0,y1,bottom,top,material):
    return scene.box(name,(x,(y0+y1)/2,(bottom+top)/2),(22,y1-y0,top-bottom),material)


def wall_y(scene,name,y,x0,x1,bottom,top,material):
    return scene.box(name,((x0+x1)/2,y,(bottom+top)/2),(x1-x0,23,top-bottom),material)


def paneled_leaf(scene,hinge,center,width,facade,finish):
    def place(name,lateral,height,depth,size,material,collision=False):
        x,y,z=center
        depth_size,width_size,height_size=size
        if facade:
            position=(x+depth,y+lateral,z+height)
            dimensions=(depth_size,width_size,height_size)
        else:
            position=(x+lateral,y+depth,z+height)
            dimensions=(width_size,depth_size,height_size)
        actor=scene.box(name,position,dimensions,material,collision=collision)
        attach(actor,hinge)
    place('Full-width timber door leaf',0,112,0,(9,width,223),finish,True)
    for side in (-1,1):
        place('Raised door edging',side*(width/2-7),112,-6,(3,6.5,213),'dark_wood')
        place('Raised upper door inset',side*(width/4-1),152,-5,(2,width/2-15,64),'dark_wood')
        place('Raised lower door inset',side*(width/4-1),58,-5,(2,width/2-15,53),'dark_wood')
    for height in (25,110,196):
        place('Horizontal timber rail',0,height,-5,(2,width-14,4),'dark_wood')
    place('Brass escutcheon',width/2-15,108,-8,(3,10,28),'brass')
    place('Dark metal pull handle',width/2-15,111,-12,(8,7,21),'charcoal')


def stairs(scene,base,inner,iron):
    for direction,y,level in ((1,-91,base),(-1,64,base+135)):
        rail_y=y+direction*67
        rise=135
        angle=atan2(rise*direction,224)
        ramp_length=hypot(224,rise)
        # The slope is the walking surface. Individual riser meshes leave headroom under the next flight.
        scene.mesh('Sloping concrete stair slab',(772+sin(angle)*18,y,level+67.5-cos(angle)*18),
            (ramp_length+2,125,16),inner,pitch=degrees(angle))
        ramp=scene.mesh('Walkable stair slope',(772+sin(angle)*7,y,level+67.5-cos(angle)*7),
            (ramp_length+1.4,125,14),inner,collision=True,pitch=degrees(angle))
        ramp.set_actor_hidden_in_game(True)
        ramp.get_component_by_class(ue.StaticMeshComponent).set_editor_properties(dict(
            cast_shadow=False,affect_distance_field_lighting=False))
        for number in range(8):
            x=(660+(number+.5)*28) if direction==1 else (884-(number+.5)*28)
            top=level+(number+1)*16.875
            scene.box('Concrete stair tread and riser',(x,y,top-11),(28.16,126,22),inner,collision=False)
            scene.box('Worn anti-slip nosing',(x-direction*12.7,y,top-.7),(3.1,126,1.4),iron,collision=False)
            if number%2==0:
                scene.box('Iron baluster',(x,rail_y,top+42),(4.5,4.5,86),iron)
        bar=scene.mesh('Sloping iron handrail',(772,rail_y,level+157),(ramp_length+4,7,6),iron,
            collision=True,pitch=degrees(angle))
        bar.get_component_by_class(ue.StaticMeshComponent).set_editor_property('cast_shadow',False)


def clear_entrance(placed):
    old_labels=('Wet drive and public steps','Door surround','Sealed apartment entrance','Door inset',
        'Police seal attachment','Apartment entrance riser','Alert light on the landing','23','Sealed door to Fedor',
        'Sealed door hinge','Stoop riser')
    old=[a for a in placed if a.actor_has_tag(TAG) or a.get_actor_label() in old_labels or a.get_actor_label().startswith(
        ('Street retaining wall','Window_Large','Police tape','Black stripe on the police tape')) or
        re.fullmatch(r'SM_Cube(?:[0-9]+)?',a.get_actor_label())]
    if old: assert ACTORS.destroy_actors(old)


def entrance():
    placed=ACTORS.get_all_level_actors()
    clear_entrance(placed)
    scene=ExistingScene('Fedor building • four floors')
    brick,iron=ue.load_asset(BRICK),ue.load_asset(CAST_IRON)
    concrete=ue.load_asset('/Game/StreetRefinement/Materials/M_WeatheredConcrete')
    pavement=ue.load_asset(WET+'WeatheredConcrete')
    asphalt=ue.load_asset(WET+'NeptuneAsphalt')
    plaster=ue.load_asset('/Game/StreetRefinement/Materials/M_GreyPaintedPlaster')
    stair_mat=ue.load_asset('/Game/Prologue/Finishes/Materials/M_tile')
    window=ue.load_asset('/Game/Prologue/Furniture/Window_Large1/Window_Large1')
    entry=ue.load_asset('/Game/Prologue/Furniture/Door_4/Door_4')
    fence=ue.load_asset(FENCE)
    stone_step=ue.load_asset('/Game/ImportedAssets/Industrial/ExteriorV2/Industrial_exterior_v2/Industrial_exterior_v2/StaticMeshes/Concrete_stairs')
    assert all((brick,iron,concrete,pavement,asphalt,plaster,stair_mat,window,entry,fence,stone_step))
    floor_box(scene,'Rain-darkened public pavement',-822,483,-562,570,0,28,pavement)
    floor_box(scene,'Wet road outside the courtyard',-1660,-822,-1210,1085,-8,42,asphalt)
    floor_box(scene,'Land beyond the external wall',-810,1180,570,1100,-4,26,pavement)
    floor_box(scene,'Ground beneath the southern wall',-810,1180,-1050,-562,-4,26,pavement)
    for side in (-1,1):
        y=side*557
        wall_y(scene,'Brick retaining boundary',y,-822,1035,-16,119,brick)
        scene.box('Stone coping on the rain-dark wall',(106,y,122),(1860,31,11),concrete)
        for x in (-640,-282,78,438,798):
            existing_mesh(scene,'Original iron fence module',fence,(x,y,182),(358,11,115))
        wall_y(scene,'Continuous collision behind the iron fence',y,-822,1035,117,232,iron).set_actor_hidden_in_game(True)
    for a,b in ((-557,-118),(118,557)):
        wall_x(scene,'Low wall at the sidewalk entrance',-803,a,b,-14,125,brick)
        existing_mesh(scene,'Entrance end of the iron fence',fence,(-803,(a+b)/2,181),(b-a,11,115),90,True)
    wall_x(scene,'Rain-dark frontage across the road',-1519,-1050,1085,-25,830,brick)
    for y in (-905,-682,-459,-235,-12,214,439,667,900):
        for z in (164,430,698):
            existing_mesh(scene,'Lit building across the road',window,(-1505,y,z),(109,10,136),90,material=iron)
            scene.box('Recessed glass across the road',(-1508,y,z),(4,96,125),'glass',collision=False)
    for y in (-830,823):
        scene.box('Neighboring rear building',(310,y,384),(1497,488,776),brick)
    scene.lamp('Warm light falling on courtyard paving',(-449,299,304),17,687,(1,.73,.46))
    scene.lamp('Diffuse overcast sky in the courtyard',(-205,25,505),12.5,1190,(.65,.77,1))
    scene.lamp('Streetlight reflected on the south wall',(-361,-325,352),8.2,715,(.76,.79,.91))
    scene.lamp('Brick wall light catching the rain',(257,189,486),10.9,1000,(.89,.82,.70))

    floor_box(scene,'Lobby ground floor',483,1080,-205,195,0,26,stair_mat)
    # The first floor has a real doorway, with upper masonry supported on a lintel.
    wall_x(scene,'Street facade left of building door',494,-555,-75,-15,239,brick)
    wall_x(scene,'Street facade right of building door',494,75,567,-15,239,brick)
    wall_x(scene,'Upper four-floor frontage',494,-555,567,228,1108,brick)
    scene.box('Roof cornice over the four storeys',(496,5,1108),(77,1130,26),concrete)
    for z in (130,400,670,940):
        for y in (-427,-237,0,236,433):
            if not y and z==130: continue
            scene.box('Recessed dark sash glass',(479,y,z),(7,112,127),'glass',collision=False)
            existing_mesh(scene,'Reused window sash',window,(474,y,z),(124,14,136),-90,material=iron)
            scene.box('Limestone sash sill',(468,y,z-72),(34,143,8),concrete,collision=False)
    for side in (-1,1):
        scene.box('Stone architrave at front door',(481,side*77,114),(29,10,228),concrete)
    scene.box('Front door lintel',(481,0,228),(34,164,13),concrete)
    existing_mesh(scene,'Imported concrete stoop',stone_step,(460,0,6),(244,65,12),90,False,pavement)
    scene.box('Stoop threshold collision',(479,0,5),(57,144,10),pavement,collision=True)
    hinge=scene.target('Ground-floor entrance hinge',(494,-72,0),cue='FedorBuildingLeaf')
    paneled_leaf(scene,hinge,(494,0,0),143,True,'green')
    scene.use('Open the unsealed door from the courtyard','BUILDING_ENTRY','Открыть дверь подъезда',(475,0,114),(15,75,106))

    wall_x(scene,'Lobby rear plaster wall',1060,-207,200,0,1100,plaster)
    wall_y(scene,'Stairwell outer plaster wall',-202,503,1070,0,1100,plaster)
    wall_y(scene,'Landings beside the apartments',190,506,1070,0,ENTRY_TOP,plaster)
    wall_y(scene,'Fourth floor wall on the left of the apartment',190,506,540,ENTRY_TOP,1098,plaster)
    wall_y(scene,'Fourth floor wall on the right of the apartment',190,664,1070,ENTRY_TOP,1098,plaster)
    wall_y(scene,'Fourth floor apartment door lintel',190,537,669,ENTRY_TOP+222,1098,plaster)
    wall_y(scene,'Masonry behind the fourth-floor apartment',299,510,693,ENTRY_TOP,1100,plaster)
    wall_x(scene,'Short return inside the apartment',692,190,299,ENTRY_TOP,1100,plaster)
    floor_box(scene,'Floor inside the fourth-floor vestibule',502,694,185,301,ENTRY_TOP,18,stair_mat)
    floor_box(scene,'Top of the stairwell',494,1080,-216,312,1117,19,concrete)
    for floor in range(4):
        h=FLOOR*floor
        if floor:
            floor_box(scene,'Full-width main landing',502,660,-193,190,h,18,stair_mat)
        if floor<3:
            floor_box(scene,'Intermediate landing between flights',884,1051,-193,185,h+135,20,concrete)
            stairs(scene,h,concrete,iron)
        if floor==3:
            scene.box('Retaining rail at the landing',(658,-125,h+46),(7,117,92),iron,collision=True)
        scene.lamp('Tungsten landing lamp',(552,-24,h+207),36,353,(1,.78,.56))
        scene.box('Ribbed glass landing fixture',(518,-24,h+205),(9,31,27),'light',collision=False)
        scene.label(str(floor+1),(519,112,h+160),0,25)
        if floor<3:
            scene.lamp('Stair turn fill',(1014,-31,h+294),26,311,(.77,.84,1))
            scene.box('Painted apartment entrance mount',(598,179,h+113),(118,10,224),'dark_wood',collision=False)
            door=existing_mesh(scene,'Original inner apartment door',entry,(598,173,h+111),(110,9,217),material=None)
            door.get_component_by_class(ue.StaticMeshComponent).set_cull_distance(2500)

    seal=scene.target('Fourth-floor apartment hinge',(541,190,ENTRY_TOP),cue='SealedLeaf')
    paneled_leaf(scene,seal,(602,190,ENTRY_TOP),120,False,'dark_wood')
    tape=scene.target('Police tape at apartment 23 only',(604,178,ENTRY_TOP+124),cue='PoliceTape')
    attach(tape,seal)
    for index,z in enumerate((ENTRY_TOP+88,ENTRY_TOP+128)):
        attach(scene.mesh('Police tape only on apartment 23',(604,178,z),(127,2.8,8),'tape',
                          pitch=9 if index else -9),tape)
        for stripe in range(-49,50,16):
            attach(scene.mesh('Black marks on apartment 23 seal',(604+stripe,176,z+stripe*(.158 if index else -.158)),
                              (6,2,7),'seam',pitch=9 if index else -9),tape)
    scene.label('23',(603,177,ENTRY_TOP+189),-90,15)
    scene.use('Inspect apartment 23 on the fourth floor','SEAL','Осмотреть опечатанную дверь',(603,165,ENTRY_TOP+109),(62,17,98))
    lamp=scene.mesh('Police scanner alarm on fourth floor',(534,170,ENTRY_TOP+203),(11,8,11),'alarmed',shape='Sphere',cue='AlarmLamp')
    lamp.set_actor_hidden_in_game(True)
    for actor in ACTORS.get_all_level_actors():
        if actor.actor_has_tag('ActCue:Patrol') or actor.actor_has_tag('ActCue:PatrolOrigin'):
            actor.set_actor_location(V(591,-53,ENTRY_TOP),False,True)
            actor.set_actor_rotation(rot(76),False)
    ue.log('FEDOR_BUILDING_READY four floors, exterior entry without a seal, sealed apartment at z=810')


def apartment():
    placed=ACTORS.get_all_level_actors()
    scene=ExistingScene('Fedor apartment • eavesdropper')
    old=[a for a in placed if a.actor_has_tag(TAG) or a.actor_has_tag('ActCue:IvanFedorExit')]
    if old: assert ACTORS.destroy_actors(old)
    placed=ACTORS.get_all_level_actors()
    wall=next((a for a in placed if a.get_actor_label()=="Fedor's flat end wall" and a.get_actor_location().x<-520),None)
    if wall:
        assert ACTORS.destroy_actor(wall)
    panel=ue.load_asset('/Game/Story/ActOne/Materials/M_plaster')
    levels={'Fedor lamp key':28,'Search aftermath tungsten':46,'Window reflecting blue night':20,
            'Light reflected from the hallway':10,'Low bounce on the bed':11}
    for actor in placed:
        level=levels.get(actor.get_actor_label())
        if level is not None:
            actor.get_component_by_class(ue.PointLightComponent).set_intensity(level)
    floor_box(scene,'Floor of the fourth-floor common hall',-779,-499,-283,-61,0,24,'wood')
    wall_x(scene,'Apartment wall to the left of the door',-529,-404,-209,0,285,panel)
    wall_x(scene,'Apartment wall to the right of the door',-529,-91,417,0,285,panel)
    wall_x(scene,'Apartment door lintel in the wall',-529,-211,-89,214,285,panel)
    wall_x(scene,'Common hall rear wall',-767,-395,-59,0,285,panel)
    wall_y(scene,'Common hall end by the staircase',-353,-777,-529,0,285,panel)
    wall_y(scene,'Common hall opposite dado',-65,-777,-529,0,285,panel)
    floor_box(scene,'Common hall ceiling',-780,-512,-362,-57,305,20,panel)
    floor_box(scene,'Stair corner hall paving',-778,-512,-356,-282,0,24,'wood')
    scene.box('Dado along the common hall',(-755,-207,50),(5,279,92),'dark_wood',collision=False)
    scene.lamp('Sodium glow in the hallway',(-686,-125,228),13,272,(.88,.77,.61))
    barrier=scene.box('Collision at the apartment loading threshold',(-551,-150,117),(8,108,238),'plaster')
    barrier.set_actor_hidden_in_game(True)
    barrier.get_component_by_class(ue.StaticMeshComponent).set_editor_property('cast_shadow',False)

    hinge=scene.target('Common hallway door hinge',(-510,-207,0),cue='FedorFlatLeaf')
    leaf=next(a for a in placed if a.get_actor_label()=="Fedor's main door")
    knob=next(a for a in placed if a.get_actor_label()=='Door knob')
    leaf.set_actor_location(V(-510,-150,105),False,True)
    leaf.set_actor_rotation(rot(),False)
    knob.set_actor_location(V(-497,-112,108),False,True)
    knob.set_actor_rotation(rot(),False)
    attach(leaf,hinge)
    attach(knob,hinge)
    hinge.set_actor_rotation(rot(13),False)
    brother=next(a for a in placed if a.actor_has_tag('ActCue:IvanFedor'))
    brother.set_editor_property('character_profile',ue.load_asset(PEOPLE+'/Profiles/DA_Ivan'))
    brother.set_editor_property('default_pose',ue.ActOnePose.IDLE)
    brother.set_actor_location(V(-658,-155,0),False,True)
    brother.set_actor_rotation(rot(0),False)
    brother.set_actor_label('Ivan enters and waits inside the apartment')
    scene.target('Ivan steps inside',(-425,-155,0),cue='IvanFedorArrival')
    scene.target('Ivan waits beside the door',(-396,-243,0),cue='IvanFedorWait')
    watcher=scene.spawn(ue.ActOneCast,'Aegis listener outside the apartment',(-588,-104,0),-83,cue='FedorListener')
    apply_profile(watcher,ue.load_asset(PEOPLE+'/Profiles/DA_Agent'))
    watcher.set_editor_property('default_pose',ue.ActOnePose.IDLE)
    watcher.set_actor_hidden_in_game(True)
    watcher.set_actor_enable_collision(False)
    scene.target('Listener runs toward the stairwell',(-601,-321,0),cue='FedorListenerExit')
    ue.log('FEDOR_LISTENER_READY separate Ivan and eavesdropping Aegis actor')


def alley():
    placed=ACTORS.get_all_level_actors()
    old=[a for a in placed if a.actor_has_tag(TAG)]
    if old: assert ACTORS.destroy_actors(old)
    scene=ExistingScene('Alley • closed building seams')
    brick=ue.load_asset(BRICK)
    floor_box(scene,'Pavement beneath the closed alley yards',-805,5370,-790,3250,-15,40,
              ue.load_asset(WET+'WeatheredConcrete'))
    for name,pos,size in (
        ('Brick return at the alley entrance A',(-529,-218,253),(45,22,520)),
        ('Brick return at the alley entrance B',(-529,219,277),(44,22,568)),
        ('Wall sealing the back of the first bend',(802,913,316),(23,306,645)),
        ('Masonry below the inner corner',(2203,604,263),(462,20,539)),
        ('Solid rear wall joining the last corner',(1973,1689,287),(25,376,588)),
        ('Back building joining the gate lane',(2204,1837,296),(481,25,607)),
        ('Retaining wall beyond the end of the courtyard',(4844,514,305),(833,28,621)),
        ('Yard wall behind the old gate',(4844,2594,305),(845,28,621)),
    ):
        a=scene.box(name,pos,size,brick)
        scene.box(name+' stone coping',(pos[0],pos[1],pos[2]+size[2]/2+2.5),
                  (size[0]+4,size[1]+5,6),'pavement',collision=False)
    fence=ue.load_asset(FENCE)
    for x,y in ((130,2520),(544,2520),(2314,2520),(2730,2520)):
        existing_mesh(scene,'Iron closure between the rear buildings',fence,(x,y,89),(420,15,190))
    scene.lamp('Reflected lamplight before the last bend',(2184,1372,271),10,580,(.67,.79,1))
    scene.lamp('Warm yard light beyond the turn',(2541,1695,305),10.8,670,(1,.76,.56))
    scene.lamp('Night fill through the last alley mouth',(2195,1105,387),5.8,680,(.66,.78,1))
    ue.log('PURSUIT_BUILDINGS_READY eight closed gaps and continuous paving')
