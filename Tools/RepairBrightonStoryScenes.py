"""Fit storefront hardware and refurnish the Fedor story levels in centimetres."""
import unreal as ue

from ActOneScenes import attach, rot
from BrightonUpgrade import ACTORS, LEVELS, V
from FedorBuildingAndPursuit import BRICK, CAST_IRON, ExistingScene, existing_mesh


TAG = ue.Name('BrightonStoryDetail')
FURNITURE = '/Game/Prologue/Furniture/Pack/'
OFFAIR = '/Game/Prologue/OffAir/Props/'


class Detail(ExistingScene):
    def spawn(self,*args,**kwargs):
        actor = super().spawn(*args,**kwargs)
        actor.tags = [tag for tag in actor.tags if str(tag)!='FedorBuildingAndPursuit']+[TAG]
        return actor


def require(path):
    asset = ue.load_asset(path)
    assert asset,path
    return asset


def tagged(actors,cue):
    return next(a for a in actors if a.actor_has_tag('ActCue:'+cue))


def named(actors,label):
    return next(a for a in actors if a.get_actor_label()==label)


def clear_details(actors):
    old = [a for a in actors if a.actor_has_tag(TAG)]
    if old:
        assert ACTORS.destroy_actors(old)
    return ACTORS.get_all_level_actors()


def storefront():
    actors = clear_details(ACTORS.get_all_level_actors())
    scene = Detail('Brighton store entrance hardware')
    leaf = named(actors,'Grocery entrance upper glass')
    handle = named(actors,'Grocery horizontal pull')
    center,extent = leaf.get_actor_bounds(False)
    outside = center.y+extent.y
    x = max(center.x-extent.x+11,min(center.x+extent.x-11,handle.get_actor_location().x))
    z = min(center.z+extent.z-12,max(center.z-extent.z+12,106))
    surface = handle.get_component_by_class(ue.StaticMeshComponent).get_material(0)
    handle.set_actor_location(V(x,outside+5.3,z),False,True)
    attach(handle,leaf)
    plate = scene.box('Grocery pull backing plate',(x,outside+.55,z),(20,2.3,6),surface,collision=False)
    attach(plate,leaf)
    for side in (-1,1):
        foot = scene.box('Grocery pull mounting foot',(x+side*4.7,outside+2.6,z),(3.2,5.8,4),surface,collision=False)
        attach(foot,leaf)
    assert handle.get_attach_parent_actor()==leaf
    ue.log('REPAIR_GROCERY_HANDLE_OK attached to glass door and supported by two mounting feet')


def courtyard_gate():
    actors = clear_details(ACTORS.get_all_level_actors())
    removed = [a for a in actors if a.actor_has_tag('ActCue:Patrol') or a.actor_has_tag('ActCue:PatrolOrigin')]
    if removed:
        assert ACTORS.destroy_actors(removed)
    scene = Detail('Courtyard gate')
    stone = require('/Game/StreetRefinement/Materials/M_WeatheredConcrete')
    steel = require(CAST_IRON)
    brick = require(BRICK)
    x = -803
    for y in (-116,116):
        scene.box('Brick gate pier',(x,y,96),(35,26,193),brick)
        scene.box('Gate pier cap',(x,y,196),(43,33,8),stone)
    for side in (-1,1):
        center = side*51
        scene.box('Solid kick panel on courtyard gate',(x,center,27),(5,99,48),steel,collision=False)
        for z in (49,181,190):
            scene.box('Courtyard gate crossbar',(x,center,z),(8,107,5),steel,collision=False)
        for i in range(9):
            y = center+(i-4)*11.8
            scene.box('Iron picket in closed gate',(x,y,116),(4.3,4.3,132),steel,collision=False)
        for z in (48,169):
            scene.mesh('Gate hinge barrel',(x+5,side*100,z),(8,8,18),steel,shape='Cylinder',collision=False)
    scene.box('Gate bolt and latch',(x+5,0,107),(9,22,7),steel,collision=False)
    collider = scene.box('Closed courtyard gate collision',(x,0,106),(12,211,212),steel)
    collider.set_actor_hidden_in_game(True)
    collider.get_component_by_class(ue.StaticMeshComponent).set_cast_shadow(False)
    ue.log(f'REPAIR_FEDOR_GATE_OK closed gate on grade; removed {len(removed)} patrol actors and markers')


def remove_labels(actors,labels,prefixes=()):
    found = [a for a in actors if a.get_actor_label() in labels or a.get_actor_label().startswith(prefixes)]
    if found:
        assert ACTORS.destroy_actors(found)
    return ACTORS.get_all_level_actors()


def placed_model(scene,name,asset,center,size,yaw=0,blocking=True):
    actor = existing_mesh(scene,name,asset,center,size,yaw,blocking)
    mesh = actor.get_component_by_class(ue.StaticMeshComponent)
    p,e = actor.get_actor_bounds(False)
    if blocking:
        assert e.z>1 and p.z-e.z>=-.8,(name,p,e)
        if mesh.get_collision_profile_name()!=ue.Name('BlockAll'):
            mesh.set_collision_profile_name('BlockAll')
    return actor


def flat():
    actors = clear_details(ACTORS.get_all_level_actors())
    # A floorboard, drawer, papers and clues remain separate so they can change during play.
    actors = remove_labels(actors, {
        'Searched and half-stripped bed','Nightstand against the headboard','Small photo cabinet',
        'Armchair beside the common wall','Reading chair pulled out from the desk','Folded blanket on the armchair',
        'Bookcase upright','Bookcase back','Bookcase foot and lower shelf','Bookcase cap',
        'Shelf with gaps after the search','Closed cardboard document box','Document box lid',
        'Stacked engineering notebooks','Paper edges of engineering notebooks','Closed drawer face below the bedside lamp',
        'Dresser side panel','Dresser back','Dresser top','Dresser base','Empty drawer bottom',
        'Drawer front with worn edges','Drawer handle','Drawer side','Photograph easel foot',
        'Desk lamp weighted base','Desk lamp stem','Painted reading lamp shade','Desk support','Desk worktop',
        'Worn book','Fold of the old curtain','Curtain rod',
    })
    scene = Detail('Refurnished flat')
    models = {
        'bed':require(FURNITURE+'Bed_Single'),
        'night':require(FURNITURE+'NightStand_2'),
        'photo':require(FURNITURE+'Drawer_1'),
        'dresser':require(FURNITURE+'Drawer_4'),
        'chair':require(FURNITURE+'Chair_2'),
        'seat':require(FURNITURE+'Couch_Small1'),
        'shelf':require(FURNITURE+'Bookshelf'),
        'lamp':require(FURNITURE+'Light_Desk'),
        'curtain':require(FURNITURE+'Curtains_Single'),
    }
    for key,label,center,size,yaw in (
        ('bed','Refurnished narrow bed',(-25,315,38),(204,120,76),0),
        ('night','Walnut bedside table',(114,315,32),(43,46,64),90),
        ('photo','Cabinet supporting the photograph',(157,-302,38.5),(87,70,77),0),
        ('dresser','Dresser with evidence on its top',(-44,-319,42.25),(131,86,84.5),0),
        ('chair','Recovered wooden desk chair',(245,280,44.5),(52,50,89),-24),
        ('seat','Period armchair beside the hall wall',(-427,294,42),(86,84,84),-15),
        ('shelf','Engineering bookcase by the east wall',(489,-249,100.5),(171,48,201),90),
    ):
        placed_model(scene,label,models[key],center,size,yaw)
    placed_model(scene,'Imported reading lamp on the desk',models['lamp'],
                 (378,272,100),(28,26,38),-39,False)
    for side in (-1,1):
        placed_model(scene,'Curtain panel at the night window',models['curtain'],
                     (-105+side*65,-368,194),(41,10,123),0,False)
    desk = require('/Game/Prologue/OffAir/Desk/Meshes/OffAir_Desk')
    # The slot for the clue drawer is on the west-facing edge of the desk.
    placed_model(scene,'1990s writing desk',desk,(346,206,40.5),(209,92,81),90)
    placed_model(scene,'Bedside lamp with a fabric shade',require(OFFAIR+'TasselLamp/Meshes/SM_TasselLamp'),
                 (103,327,84),(18,18,40),-18,False)
    placed_model(scene,'Archive box on the floor by the desk',require(OFFAIR+'Boxes/Meshes/SM_Box_A'),
                 (456,347,14.5),(47,40,29),14)
    placed_model(scene,'Second archive box by the desk',require(OFFAIR+'Boxes/Meshes/SM_Box_B'),
                 (453,348,39),(35,32,20),-5,False)
    placed_model(scene,'Potted houseplant near the armchair',require(FURNITURE+'Houseplant_4'),
                 (-480,174,26),(29,33,52),0,False)
    board = require(OFFAIR+'Corkboard/Meshes/SM_Corkboard')
    extent = board.get_bounding_box()
    dim = extent.max-extent.min
    dimensions,yaw = ((5,118,73),180) if dim.x<dim.y else ((118,5,73),-90)
    placed_model(scene,'Fedor’s cork noticeboard',board,(531.9,208,159),dimensions,yaw,False)
    scene.box('Searching marks on the dresser case',(-49,-274,65),(113,3,19),'dark_wood',collision=False)
    scene.box('Tipped drawer below the dresser',(-53,-239,9),(63,43,16),'wood',collision=False,yaw=-15)
    scene.box('Open portfolio on the armchair',(-419,282,49),(27,22,3),'navy',collision=False,yaw=23)
    scene.box('Support beneath the badge photograph',(158,-327,77.8),(16,15,1.6),'dark_wood',collision=False)
    actors = ACTORS.get_all_level_actors()
    listener = tagged(actors,'FedorListener')
    listener.set_actor_location(V(-612,-126,0),False,True)
    listener.set_actor_rotation(rot(-93),False)
    listener.set_actor_hidden_in_game(True)
    listener.set_actor_enable_collision(False)
    # Both ends are inside the common hallway. The far corner hides the actor on exit.
    tagged(actors,'FedorListenerExit').set_actor_location(V(-630,-310,0),False,True)
    assert len([a for a in actors if isinstance(a,ue.ActOneInteraction)])>=8
    ue.log('REPAIR_FEDOR_FLAT_OK furniture library, positioned clues, clear hallway')


def pursuit():
    actors = clear_details(ACTORS.get_all_level_actors())
    actors = remove_labels(actors,{'Rear exit gate','Gate bars','Gate horizontal bracing'})
    scene = Detail('Pursuit path')
    # The service gate opens onto the gap between the two rear buildings.
    steel = require(CAST_IRON)
    for start,end in ((1410,1569),(1671,1834)):
        for y in (start,end):
            scene.box('Rear gate post',(3501,y,126),(14,11,252),steel)
        for z in (15,107,242):
            scene.box('Rear gate rail',(3501,(start+end)*.5,z),(7,end-start,6),steel,collision=False)
        for y in range(start+13,end-5,14):
            scene.box('Rear gate iron picket',(3501,y,128),(3.2,3.2,221),steel,collision=False)
    boundary = scene.box('Boundary beyond the service gate',(3547,1620,111),(10,435,222),steel)
    component = boundary.get_component_by_class(ue.StaticMeshComponent)
    component.set_collision_profile_name('StreetPawnBoundary')
    component.set_cast_shadow(False)
    boundary.set_actor_hidden_in_game(True)
    scene.box('Brick return beside the escape passage',(4575,925,289),(26,690,582),require(BRICK))
    route = [V(-326,0,0),V(1020,0,0),V(1020,822,0),V(2190,822,0),V(2190,1620,0),
             V(4650,1620,0),V(4650,874,0)]
    rounded = [route[0]]
    radius = 130
    for previous,corner,following in zip(route,route[1:],route[2:]):
        incoming = corner-previous
        outgoing = following-corner
        enter = corner-incoming*(radius/incoming.length())
        leave = corner+outgoing*(radius/outgoing.length())
        for i in range(13):
            t = i/12
            rounded.append(enter*(1-t)**2+corner*(2*t*(1-t))+leave*t**2)
    rounded.append(route[-1])
    spline = scene.director.get_editor_property('pursuit_route')
    spline.clear_spline_points(False)
    for index,point in enumerate(rounded):
        spline.add_spline_point(point,ue.SplineCoordinateSpace.WORLD,False)
        spline.set_spline_point_type(index,ue.SplinePointType.LINEAR,False)
    spline.update_spline()
    scene.target('First step of Dima’s stumble',(2190,1434,0),cue='PursuitTripStart')
    runner = tagged(actors,'Agent')
    runner.set_actor_location(spline.get_location_at_distance_along_spline(530,ue.SplineCoordinateSpace.WORLD),False,True)
    runner.set_actor_rotation(rot(0),False)
    ue.log(f'REPAIR_PURSUIT_PATH_OK {len(rounded)} points, exit behind a masonry corner')


def apply_scene(level,edit):
    assert ue.EditorLoadingAndSavingUtils.load_map('/Game/Locations/'+level),level
    edit()
    assert LEVELS.save_current_level(),level
