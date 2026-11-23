"""Apply placement, lighting and animation repairs to the existing Act One maps."""
from itertools import product
from math import isfinite
from random import Random

import unreal as ue

from ActOneScenes import attach
from ApartmentScene import make_material
from BrightonBarDressing import BOTTLES
from BrightonCitizens import MOTIONS
from BrightonStreetDetails import expression
from BrightonUpgrade import ACTORS, ASSETS, GROCERY, LIB, P, SOURCE, V, factory_asset, media, node, output, save
from FedorBuildingAndPursuit import ExistingScene, existing_mesh


TAG = ue.Name("ActOneSceneCorrection")
COLLISION_TAG = ue.Name("ActOneCollisionRepair")
ANIMATION = "/Game/Story/ActOne/Animation"
DATA = "/Game/Story/ActOne/DA_ActOne"
MOVABLE = ue.ComponentMobility.MOVABLE


def actor_list():
    return ACTORS.get_all_level_actors()


def named(actors, label):
    return next(actor for actor in actors if actor.get_actor_label() == label)


def mesh_component(actor):
    return actor.get_component_by_class(ue.StaticMeshComponent)


def remove(actors):
    if actors:
        assert ACTORS.destroy_actors(actors), actors


def move(actor, position):
    actor.set_actor_location(V(*position), False, True)


def center(actor, at, scale=1.0):
    original = actor.get_actor_bounds(False)[0]
    location = actor.get_actor_location()
    actor.set_actor_scale3d(actor.get_actor_scale3d() * scale)
    move(actor, (V(*at) + (location-original) * scale).to_tuple())


def support(actor, height):
    p, e = actor.get_actor_bounds(False)
    at = actor.get_actor_location()
    move(actor, (at.x, at.y, at.z + height - (p.z-e.z)))


class Repairs(ExistingScene):
    def __init__(self, location, tag=TAG):
        self.tag = tag
        remove([actor for actor in actor_list() if actor.actor_has_tag(tag)])
        super().__init__(location + "/Scene corrections")

    def spawn(self, *args, **kwargs):
        actor = super().spawn(*args, **kwargs)
        # This pass can be reapplied independently of the four-storey entrance.
        actor.tags = [self.tag] + [tag for tag in actor.tags if str(tag).startswith("ActCue:")]
        return actor


def cube(actor, at, size):
    actor.set_actor_scale3d(V(*(value/100 for value in size)))
    move(actor, at)


def horizontal(scene, name, xy, top, dimensions, material, collision=True):
    width, depth, thickness = dimensions
    return scene.box(name, (*xy, top-thickness/2), (width, depth, thickness), material,
                     collision=collision)


def plank_y(scene, name, y, x0, x1, z0, z1, material, depth=18, collision=True):
    return scene.box(name, ((x0+x1)/2, y, (z0+z1)/2), (x1-x0, depth, z1-z0),
                     material, collision=collision)


def transformed_box(mesh, transform):
    """Use source-space corner offsets to accommodate off-center OBJ pivots."""
    box = mesh.get_bounding_box()
    vectors = [ue.MathLibrary.transform_location(transform, V(*corner)) for corner in
               product(*zip(box.min.to_tuple(), box.max.to_tuple()))]
    axes = list(zip(*(v.to_tuple() for v in vectors)))
    return [(min(axis), max(axis)) for axis in axes]


def repair_stock(actors, counter):
    shelves = [actor.get_actor_bounds(False) for actor in actors
               if actor.get_actor_label().startswith("Scuffed empty shelf")]
    count = 0
    for actor in actors:
        label = actor.get_actor_label()
        if not label.startswith("Shelf stock ") and label != "Chocolate beside the till":
            continue
        component = actor.get_editor_property("instances")
        component.set_collision_profile_name("NoCollision")
        component.set_editor_properties(dict(cast_shadow=False, affect_distance_field_lighting=False))
        component.set_cull_distances(1500, 1900)
        for i in range(component.get_instance_count()):
            old = component.get_instance_transform(i, True)
            pos = old.translation
            if label == "Chocolate beside the till":
                base, half = counter.get_actor_bounds(False)
            else:
                base, half = min(shelves, key=lambda pair:
                                 abs(pos.z-(pair[0].z+pair[1].z))*4 +
                                 (pos-pair[0]).length())
            # The lane spacing of adjacent stock units is 24 cm.
            span = 8.6 if label == "Chocolate beside the till" else 22.5
            row_on_x = label == "Chocolate beside the till" or half.x >= half.y
            orientation = ue.Transform(location=V(), rotation=old.rotation.rotator(), scale=old.scale3d)
            offsets = transformed_box(component.static_mesh, orientation)
            along = offsets[0 if row_on_x else 1]
            scale = min(1.0, span/(along[1]-along[0]))
            position = []
            for origin, extent, anchor, (low, high) in zip(
                    base.to_tuple(), half.to_tuple(), pos.to_tuple(), offsets):
                position.append(max(origin-extent+.2-low*scale,
                                    min(origin+extent-.2-high*scale, anchor)))
            position[2] = base.z+half.z+.08-offsets[2][0]*scale
            transform = ue.Transform(location=V(*position), rotation=old.rotation.rotator(),
                                     scale=old.scale3d*scale)
            assert component.update_instance_transform(i, transform, True, True, True), (label, i)
            box = transformed_box(component.static_mesh, transform)
            assert abs(box[2][0]-(base.z+half.z)) < .12, label
            assert all(lo >= b-e-.05 and hi <= b+e+.05 for (lo, hi), b, e in
                       zip(box[:2], base.to_tuple(), half.to_tuple())), label
            count += 1
    ue.log(f"SCENE_CORRECTION_STOCK {count} grounded and contained products")


def grocery():
    scene = Repairs("Grocery")
    actors = actor_list()
    wall = next(a for a in actors if a.get_actor_label() == "Grocery side wall" and a.get_actor_location().y < 0)
    move(wall, (9, -339, 145))
    for actor in (a for a in actors if a.get_actor_label().startswith("Steel shelf frame")):
        pos, half = actor.get_actor_bounds(False)
        top = pos.z+half.z
        cube(actor, (pos.x, pos.y, top/2), (2*half.x, 2*half.y, top))
    for label, point in (("SM_posters_Plane_029",(236,348.6,171)),("SM_posters_Plane_015",(-76,348.6,165)),
                         ("SM_posters_Plane_018",(-347,348.6,182))):
        poster = named(actors, label)
        scale = 44/poster.get_actor_bounds(False)[1].z
        center(poster, point, scale)
        mesh_component(poster).set_collision_profile_name("NoCollision")
        mesh_component(poster).set_editor_properties(dict(cast_shadow=False, affect_distance_field_lighting=False))
    countertop = named(actors, "Faded plastic counter top")
    mesh_component(named(actors,"Grocery floor")).set_material(0,grocery_tile())
    ceiling = ue.load_asset("/Game/Prologue/ModernFinishes/Materials/M_painted")
    assert ceiling
    mesh_component(named(actors,"Grocery ceiling")).set_material(0,ceiling)
    top, extent = countertop.get_actor_bounds(False)
    level = top.z+extent.z
    cube(named(actors, "Grocery check-out counter"), (237,93,(top.z-extent.z)/2), (124,246,top.z-extent.z))
    support(named(actors, "Imported cash register"), level)
    support(named(actors, "Marlboro cigarette packet"), level)
    move(named(actors,"Red Marlboro packet shoulder"), (205,19,level+2.55))
    move(named(actors,"Marlboro"), (210,19,level+2.76))
    move(named(actors,"Marlboro on the counter"), (197,19,level+6))
    for a in actors:
        if a.get_actor_label().startswith("Fluorescent light"):
            point = a.get_component_by_class(ue.PointLightComponent)
            point.set_cast_shadows(a.get_actor_location().x > 0)
            point.set_intensity(15. if a.get_actor_location().x > 0 else 9.)
            point.set_editor_properties(dict(source_radius=26., volumetric_scattering_intensity=0.))
    for x, y, w, d in ((-350,-317,199,2),(-102,-317,199,2),(132,-317,199,2),
                       (529,-165,2,219),(529,98,2,219)):
        scene.box("Sheet steel shelf back", (x,y,122), (w,d,204), "steel", collision=False)
    repair_stock(actors, countertop)


def grocery_tile():
    material = make_material(GROCERY,"Grocery_Tile",(.31,.36,.317),.66)
    if not isinstance(LIB.get_material_property_input_node(material,P.MP_BASE_COLOR),ue.MaterialExpressionCustom):
        position = node(material,ue.MaterialExpressionWorldPosition)
        surface = expression(material,{"Position":position},"""
            float2 p = Position.xy / 32;
            float2 cell = floor(p);
            float2 edge = min(frac(p), 1 - frac(p));
            float mortar = 1 - smoothstep(.008, .022 + min(.013, fwidth(p.x) + fwidth(p.y)), min(edge.x, edge.y));
            float tint = frac(sin(dot(cell, float2(93.7, 17.3))) * 18453.17);
            float grain = sin(Position.x * .46 + sin(Position.y * 1.28)) * .009;
            float3 tile = lerp(float3(.28, .319, .283),float3(.40, .418, .38),tint) + grain;
            return lerp(tile, float3(.12, .128, .113), mortar);
            """,ue.CustomMaterialOutputType.CMOT_FLOAT3)
        output(surface,material,P.MP_BASE_COLOR)
        LIB.recompile_material(material)
        save(material)
    return material


def grocery_models():
    folder = GROCERY + "/Created"
    for name in ("Milk","Cereal","Rice","Buckwheat","Flour","Bread","Eggs"):
        package = folder + "/SM_" + name
        mesh = ue.load_asset(package)
        before = mesh.get_bounding_box()
        materials = {str(slot.get_editor_property("imported_material_slot_name")):
                     slot.get_editor_property("material_interface") for slot in mesh.static_materials}
        mesh = media(SOURCE/"Groceries"/"Created"/("SM_"+name+".obj"),folder,replace_existing=True)
        for slot_index,slot in enumerate(mesh.static_materials):
            mesh.set_material(slot_index,materials[str(slot.get_editor_property("imported_material_slot_name"))])
        after = mesh.get_bounding_box()
        assert (after.min-before.min).length() < .2 and (after.max-before.max).length() < .2, name
        save(mesh)
    ue.log("SCENE_CORRECTION_PRODUCT_MESHES seven checked bounds, labels and source normals")


def fedor_window(scene, actors):
    wall = next((a for a in actors if a.get_actor_label()=="Fedor's flat side wall"
                 and a.get_actor_location().y < 0), None)
    if wall:
        remove([wall])
    for name, x0, x1, z0, z1 in (("West of the sash",-520,-180,0,285), ("East of the sash",-30,535,0,285),
                                 ("Window apron",-180,-30,0,126), ("Window lintel",-180,-30,237,285)):
        plank_y(scene, name, -395, x0, x1, z0, z1, "plaster")
    glass = make_material("/Game/Story/ActOne","FedorNightGlass",(.025,.048,.082),.36)
    plank_y(scene, "Sealed night window", -396, -180, -30, 126, 237, glass, depth=5)
    for x in (-178,-105,-32):
        scene.box("Dark sash upright",(x,-386,181.5),(4,10,111),"dark_wood",collision=False)
    for z in (127.5,177,235.5):
        scene.box("Dark sash rail",(-105,-386,z),(150,10,4),"dark_wood",collision=False)
    scene.box("Timber window sill",(-105,-381,123),(165,29,6),"wood",collision=False)
    scene.box("Curtain rod",(-105,-372,254),(172,3.4,3.4),"brass",collision=False)
    for side in (-1,1):
        for fold in range(5):
            scene.box("Fold of the old curtain",(-105+side*(66-fold*4),-369+fold%2*1.6,194),
                      (5.4,5.5,117),"cloth",collision=False)
    radiator = named(actors, "Old steam radiator in front of the window")
    cube(radiator, (-90,-376,37), (162,16,71))
    for x in (-156,-27):
        scene.box("Radiator wall bracket",(x,-380,43),(8,15,8),"steel",collision=False)
    scene.box("Radiator pipe into the skirting",(-166,-375,7),(3.4,5,15),"steel",collision=False)


def fedor_shelving(scene, actors):
    remove([a for a in actors if a.get_actor_label() in {"Former engineering bookshelf", "Dresser with tilted drawers",
                                                       "Drawer left open by the search"}])
    actors = actor_list()
    for y in (-338,-157):
        scene.box("Bookcase upright",(477,y,101),(87,6,202),"dark_wood")
    scene.box("Bookcase back", (519,-247,101), (5,183,202), "dark_wood")
    horizontal(scene,"Bookcase foot and lower shelf",(477,-247),14,(87,181,14),"wood")
    horizontal(scene,"Bookcase cap",(477,-247),202,(87,186,6),"dark_wood")
    for a in actors:
        name = a.get_actor_label()
        if name == "Shelf with gaps after the search":
            z = a.get_actor_location().z
            cube(a, (476,-247,z), (85,175,6))
            mesh_component(a).set_collision_profile_name("BlockAll")
        if name == "Worn book":
            z = a.get_actor_location().z
            shelf = min((62,114,169), key=lambda h: abs(z-h))
            move(a, (451,a.get_actor_location().y,z))
            support(a,shelf+3)
    for y in (-289,-210):
        scene.box("Stacked engineering notebooks",(454,y,120),(23,19,6),"navy",collision=False)
        scene.box("Paper edges of engineering notebooks",(442.8,y,120),(1.2,18,4.5),"paper",collision=False)
    scene.box("Closed cardboard document box",(484,-236,26),(45,54,24),"cloth",collision=False)
    scene.box("Document box lid",(484,-236,39),(47,56,3),"ivory",collision=False)
    for x in (-109,21):
        scene.box("Dresser side panel",(x,-319,40),(7,86,80),"dark_wood")
    scene.box("Dresser back",(-44,-359,40),(124,6,80),"wood")
    horizontal(scene,"Dresser top",(-44,-319),84.5,(137,86,5),"wood")
    horizontal(scene,"Dresser base",(-44,-319),8,(126,82,8),"dark_wood")
    for z, y in ((24,-276),(52,-261),(72,-275)):
        horizontal(scene,"Empty drawer bottom",(-44,y-16),z-7,(120,36,4),"wood")
        scene.box("Drawer front with worn edges",(-44,y+3,z),(123,4,20),"wood")
        scene.box("Drawer handle",(-44,y+7,z+1),(23,4.1,3.4),"brass",collision=False)
        for x in (-102,14):
            scene.box("Drawer side", (x,y-16,z-1), (4,34,12), "dark_wood",collision=False)
    support(named(actors,"Found audio cassette"),84.5)
    move(named(actors,"Tape label"),(-16,-305,86.23))
    move(named(actors,"Fedor's audio cassette"),(-16,-306,93.5))
    for label,z in (("Old photograph of Fedor frame",95.5),("Old photograph of Fedor",95.5),("Photo evidence",94.5)):
        a = named(actors,label)
        p = a.get_actor_location()
        move(a,(p.x,p.y,z))
    scene.mesh("Photograph easel foot",(157,-329,79),(12,18,5),"dark_wood",pitch=-18)


def fedor_floor(scene, actors):
    whole_floor = named(actors, "Fedor's flat floor")
    # Keep its simple collision across the small opening. Only the visible surface is cut.
    whole_floor.set_actor_hidden_in_game(True)
    source = mesh_component(whole_floor)
    source.set_editor_properties(dict(cast_shadow=False, affect_distance_field_lighting=False))
    for name,x0,x1,y0,y1 in (("North boards",-520,535,124,399), ("South boards",-520,535,-386,78),
                             ("West boards",-520,-234.5,78,124),("East boards",-173.5,535,78,124)):
        board = horizontal(scene,name,((x0+x1)/2,(y0+y1)/2),0,(x1-x0,y1-y0,4),"wood",False)
        mesh_component(board).set_editor_property("affect_distance_field_lighting",True)
    cube(named(actors, "Floorboard recess"),(-204,101,-4.3),(61,46,1.2))
    move(named(actors, "Loose floorboard"),(-204,101,-1.5))
    folder = named(actors, "Top secret folder under the boards")
    if abs(folder.get_actor_location().z - 1.52) < 1:
        folder.add_actor_world_offset(V(0,0,-3.02), False, True)
    stamp = named(actors,"Red stamp on the file")
    move(stamp,(-216,98,-.60))
    if not stamp.get_attach_parent_actor():
        attach(stamp,folder)
    rug = named(actors, "Search-stained woven rug")
    support(rug,.05)
    rng = Random(251)
    for a in (x for x in actors if x.get_actor_label().startswith("Scattered typed sheet")):
        x,y,z = a.get_actor_location().to_tuple()
        if 285<x and 88<y<323:
            x -= 110
        if -134<x<91 and 236<y:
            y -= 112
        if 395<x and y<-152:
            x -= 85
        move(a,(x,y,z))
        p,e=rug.get_actor_bounds(False)
        support(a,p.z+e.z+.03+rng.uniform(0,.09) if abs(x-p.x)<e.x and abs(y-p.y)<e.y else .04)


def fedor():
    scene = Repairs("Fedor Apartment")
    actors = actor_list()
    fedor_window(scene, actors)
    actors = actor_list()
    fedor_shelving(scene, actors)
    actors = actor_list()
    fedor_floor(scene, actors)
    for label in ("Small photo cabinet","Nightstand against the headboard","Searched and half-stripped bed"):
        support(named(actors,label),0.)
    chair = scene.furniture("Chair_2","Reading chair pulled out from the desk",(245,264,45),(48,49,90),-25)
    chair.tags = [TAG]
    support(chair,0.)
    existing_mesh(scene,"Armchair beside the common wall",ue.load_asset(
        "/Game/ImportedAssets/Office/couches/armchair_pattern/SM_armchair_pattern"),
        (-438,287,43),(84,83,86),-22,collision=True)
    scene.box("Folded blanket on the armchair",(-442,288,47),(38,29,4),"cloth",collision=False,yaw=-22)
    scene.mesh("Porcelain ceiling rose",(296,147,280),(49,49,10),"ivory",shape="Cylinder")
    scene.mesh("Frosted ceiling diffuser",(296,147,272),(45,45,8),"light",shape="Cylinder")
    for index in range(3):
        sheet = scene.box("Folded notes on the desk",(354+index*1.1,137,81.24+index*.38),
                          (26,19,.43),"paper",collision=False,yaw=index*4-7)
        mesh_component(sheet).set_cast_shadow(False)
    scene.mesh("Desk lamp weighted base",(376,270,83),(23,23,4),"brass",shape="Cylinder")
    scene.mesh("Desk lamp stem",(376,270,95),(3.4,3.4,21),"brass",shape="Cylinder")
    scene.mesh("Painted reading lamp shade",(374,270,112),(24,25,15),"green",shape="Cylinder",pitch=-16)
    scene.box("Closed drawer face below the bedside lamp",(114,287.4,45),(40,2.3,15),"wood",collision=False)
    scene.mesh("Enameled mug by Fedor's bed",(120,315,68),(9,9,8),"ivory",shape="Cylinder")
    scene.box("Old cardboard map portfolio",(472,356,3),(63,31,6),"navy",collision=False,yaw=7)
    frame = ue.load_asset("/Game/Story/ActOne/Materials/M_M_FedorPhotograph")
    scene.box("Framed engineers' group photo",(178,397,165),(43,4,33),"dark_wood",collision=False)
    scene.mesh("Old group photograph",(178,394.85,165),(38,27,1),frame,shape="Plane",pitch=0,roll=-90)
    for label,intensity,radius,color,shadows in (
            ("Fedor lamp key",11,525,(1,.87,.72),False),
            ("Search aftermath tungsten",22,573,(1,.81,.63),True),
            ("Window reflecting blue night",8,348,(.57,.70,1),False),
            ("Light reflected from the hallway",7.7,340,(.79,.83,1),False),
            ("Low bounce on the bed",8.6,385,(.79,.71,.63),False),
            ("Sodium glow in the hallway",13,272,(.91,.78,.64),False)):
        a = named(actors,label)
        if label == "Window reflecting blue night":
            move(a,(-105,-352,190))
        elif label == "Search aftermath tungsten":
            move(a,(296,147,253))
        point = a.get_component_by_class(ue.PointLightComponent)
        local_light(point,intensity,radius,color,shadows,.27)
        if label == "Window reflecting blue night":
            point.set_editor_property("specular_scale",.08)
    scene.lamp("Pool of light from the reading lamp",(370,269,97),4.8,154,(1,.81,.57))


def finale():
    scene = Repairs("Dima Apartment")
    actors = actor_list()
    target = named(actors, "Tape playback button")
    pos = target.get_actor_location()
    key = min((a for a in actors if a.get_actor_label() == "Tape deck key"),
              key=lambda a: (a.get_actor_location()-pos).length())
    key.tags = list(dict.fromkeys(list(key.tags) + [ue.Name("ActCue:FinalePlaybackKey")]))
    key_mesh = mesh_component(key)
    key_mesh.set_mobility(MOVABLE)
    key_mesh.set_material(0,scene.mat("steel"))
    key_mesh.set_cast_shadow(False)
    camera = named(actors,"Finale at the desk")
    camera_location = pos + V(-33,-89,55)
    move(camera,camera_location.to_tuple())
    camera.set_actor_rotation(ue.MathLibrary.find_look_at_rotation(camera_location,pos+V(6,6,2)),False)
    camera.get_component_by_class(ue.CameraComponent).set_field_of_view(55.)
    x,y,z = named(actors,"Cassette recorder case").get_actor_location().to_tuple()
    for dy in (-9,9):
        scene.mesh("Cassette reel spindle",(x,y+dy,z+4.73),(3.5,3.5,.35),"charcoal",shape="Cylinder")
    for dy in range(-12,13,4):
        scene.box("Recorder speaker grille",(x+7,y+dy,z+4.88),(9,.7,.25),"steel",collision=False)
    scene.box("Cassette tape window front edge",(x-4.7,y,z+4.18),(1.2,28,.4),"steel",collision=False)


def recorder_animation():
    data = ue.load_asset(DATA)
    model = data.get_editor_property("smoking_arms")
    skeleton = model.get_editor_property("skeleton")
    smoke = ue.load_asset("/Game/Story/ActOne/Smoking/A_DimaSmoke_FirstPerson")
    assert ue.CityCharacterAuthoring.author_first_person_smoke(model,skeleton,smoke)
    save(smoke)
    factory = ue.AnimSequenceFactory()
    factory.set_editor_properties(dict(target_skeleton=skeleton,preview_skeletal_mesh=model))
    clip = factory_asset(ANIMATION,"A_DimaPressRecorder",ue.CityGestureSequence,factory)
    contact = ue.CityCharacterAuthoring.author_first_person_recorder(model,clip)
    assert contact is not None and all(isfinite(axis) for axis in contact.to_tuple()), contact
    for channel in ("bone","curve"):
        settings = ue.load_asset("/ACLPlugin/ACLAnim" + channel.title() + "CompressionSettings")
        assert settings
        clip.set_editor_property(channel+"_compression_settings",settings)
    montage_factory = ue.AnimMontageFactory()
    montage_factory.set_editor_properties(dict(target_skeleton=skeleton,source_animation=clip))
    montage = factory_asset(ANIMATION,"AM_DimaPressRecorder",ue.AnimMontage,montage_factory)
    assert 1.5 < montage.get_play_length() < 1.7, montage.get_play_length()
    data.set_editor_properties(dict(recorder_montage=montage,recorder_contact_point=contact,
                                     recorder_press_time=26/30))
    recording = data.get_editor_property("documents")[ue.Name("FedorRecording")]
    recording.set_editor_property("open_sound",None)
    for asset in (model,clip,montage,data,recording):
        save(asset)
    ue.log(f"SCENE_CORRECTION_RECORDER {montage.get_play_length():.3f}s contact={contact}")


def bar():
    actors = actor_list()
    for name,kind in (("Bartender with broken nose","whisky"),("Older immigrant holding a bottle","wine")):
        character = named(actors,name)
        profile = character.get_editor_property("character_profile")
        model = profile.get_editor_property("mesh")
        motions = profile.get_editor_property("motions")
        for motion,source,gesture in (("Idle","Idle_Loop","HoldBottle"),("Talk","Idle_Talking_Loop","TalkWithBottle")):
            clip = motions[ue.Name(motion)]
            assert ue.CityCharacterAuthoring.author_gesture(model,ue.load_asset(MOTIONS+"/A_Citizen_"+source),clip,gesture)
            save(clip)
        save(model)
        mesh = character.get_editor_property("character_mesh")
        prop = named(character.get_attached_actors(True,True),"Green glass bottle")
        component = mesh_component(prop)
        assert mesh.does_socket_exist("BottleGrip") and component.static_mesh
        component.set_absolute(False,False,True)
        prop.set_actor_scale3d(V(1,1,1))
        assert prop.attach_to_component(mesh,"BottleGrip",ue.AttachmentRule.SNAP_TO_TARGET,
            ue.AttachmentRule.SNAP_TO_TARGET,ue.AttachmentRule.KEEP_WORLD,False)
        component.set_relative_rotation(ue.Rotator(),False,True)
        scale = mesh.get_socket_transform("BottleGrip").scale3d
        component.set_relative_location(V(1.1/scale.x,.6/scale.y,-.49*BOTTLES[kind]/scale.z),False,True)
    ue.log("SCENE_CORRECTION_BOTTLES animated grip on both bar characters")


def local_light(light, intensity, radius, color, shadows, scattering=0.):
    light.set_intensity(intensity)
    light.set_attenuation_radius(radius)
    light.set_light_color(ue.LinearColor(*color,1))
    light.set_editor_properties(dict(cast_shadows=shadows, contact_shadow_length=0.,
        shadow_bias=.4, shadow_slope_bias=.46, source_radius=17., volumetric_scattering_intensity=scattering))


def collision_editor():
    ue.load_module("StaticMeshEditor")
    return ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)


def simple_hull(editor, mesh, shape):
    if editor.get_simple_collision_count(mesh) + editor.get_convex_collision_count(mesh) == 0:
        assert editor.add_simple_collisions(mesh,shape) >= 0, mesh
        save(mesh)


def blocking_cylinder(editor):
    path = "/Game/Story/ActOne/Geometry/SM_BlockingCylinder"
    result = ue.load_asset(path) if ASSETS.does_asset_exist(path) else ASSETS.duplicate_asset(
        "/Engine/BasicShapes/Cylinder",path)
    assert result
    simple_hull(editor,result,ue.ScriptCollisionShapeType.NDOP10_Z)
    return result


def fence_body(scene, actor, component):
    p, h = actor.get_actor_bounds(False)
    body = scene.box("Simple collision behind " + actor.get_actor_label(),p.to_tuple(),
                     (max(8,2*h.x),max(8,2*h.y),2*h.z),"charcoal")
    body.set_actor_hidden_in_game(True)
    mesh_component(body).set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False))
    component.set_collision_profile_name("NoCollision")


def repair_precinct(actors):
    for label in ("Precinct floor","Office floor"):
        floor = named(actors,label)
        p,h = floor.get_actor_bounds(False)
        move(floor,(p.x,p.y,-10.1-h.z))
    for label in ("SM_couch_red","SM_coffee_machine","SM_water_cooler_bottle"):
        support(named(actors,label),-10)
    desk = named(actors,"SM_desk2")
    p,h = desk.get_actor_bounds(False)
    for label in ("SM_computer_monitor","SM_computer_keyboard","SM_computer_mouse",
                  "SM_square_desklamp","SM_mug_alt3","SM_desk_phone"):
        support(named(actors,label),p.z+h.z+.05)


def collision_repairs(level):
    scene = Repairs(level,tag=COLLISION_TAG) if level in ("L_NeptuneStreet","L_FedorEntry") else None
    actors = actor_list()
    if level == "L_PolicePrecinct":
        repair_precinct(actors)
    duplicate = next((a for a in actors if level=="L_NeptuneStreet" and a.get_actor_label()=="Fence5"),None)
    if duplicate:
        original = named(actors,"Fence3")
        if (duplicate.get_actor_location()-original.get_actor_location()).length()<.01:
            remove([duplicate])
            actors = actor_list()
    editor = collision_editor()
    shape = ue.ScriptCollisionShapeType
    cylinder = blocking_cylinder(editor) if level in ("L_NeptuneStreet","L_LighthouseBar","L_BrightonAlley") else None
    touched = 0
    furniture = {"SM_desk2","SM_armchair_red","SM_couch_red","SM_couch_large_red","SM_office_chair_fancy",
                 "SM_water_cooler_bottle_attached","SM_book_case","SM_book_case_small","SM_book_case_with_back",
                 "SM_file_cabinet_larger","SM_file_cabinet_largest","SM_coffee_machine"}
    for actor in actors:
        label = actor.get_actor_label()
        for component in actor.get_components_by_class(ue.StaticMeshComponent):
            mesh = component.static_mesh
            if not mesh:
                continue
            name = mesh.get_name()
            replace_cylinder = name=="Cylinder" and component.get_collision_enabled()!=ue.CollisionEnabled.NO_COLLISION
            is_fence = (level=="L_NeptuneStreet" and name=="Fence") or (
                level=="L_FedorEntry" and label=="Entrance end of the iron fence")
            if is_fence:
                fence_body(scene,actor,component)
            elif replace_cylinder:
                component.set_static_mesh(cylinder)
            elif level == "L_NeptuneStreet" and actor.actor_has_tag("Brighton1994ParkedCar"):
                simple_hull(editor,mesh,shape.NDOP18)
            elif (level=="L_FedorApartment" and label=="Armchair beside the common wall") or (
                    level=="L_PolicePrecinct" and name in furniture):
                simple_hull(editor,mesh,shape.BOX)
            elif (level=="L_PolicePrecinct" and mesh.get_path_name().startswith("/Game/ImportedAssets/Office/")
                  and component.get_collision_enabled()!=ue.CollisionEnabled.NO_COLLISION) or (
                    level=="L_FedorEntry" and label=="SM_CourtyardShrub") or (
                    level=="L_NeptuneStreet" and name in {"Building_1","Building_2","Building_8",
                                                          "SM_IndustrialHorror_PS_like_Building_4"}):
                component.set_collision_profile_name("NoCollision")
            else:
                continue
            touched += 1
    ue.log(f"SCENE_COLLISION_REPAIRS {level} components={touched}")


def grade(actor, exposure):
    settings = actor.get_editor_property("settings")
    settings.set_editor_properties(dict(override_auto_exposure_bias=True,auto_exposure_bias=exposure,
        override_local_exposure_shadow_contrast_scale=True,local_exposure_shadow_contrast_scale=.83,
        override_local_exposure_highlight_contrast_scale=True,local_exposure_highlight_contrast_scale=.92))
    actor.set_editor_property("settings", settings)


def exterior(level):
    actors = actor_list()
    street = level == "L_NeptuneStreet"
    alley = level == "L_BrightonAlley"
    fill = {"Playground courtyard end fill":(3.15,700,(.74,.84,1)),
            "Press kiosk reflected canopy light":(1.55,340,(1,.87,.74)),
            "Diffuse overcast sky in the courtyard":(8.4,1050,(.71,.81,1)),
            "Reflected blue night light":(2.1,720,(.63,.76,1)),
            "Sky bounce on the first corner":(5.7,930,(.70,.79,1)),
            "Sky bounce over the rear passage":(4.6,1150,(.68,.78,1)),
            "Night fill through the last alley mouth":(5.9,594,(.69,.80,1))}
    projections = casters = 0
    for a in actors:
        label = a.get_actor_label()
        if isinstance(a,ue.DirectionalLight):
            light = a.get_component_by_class(ue.DirectionalLightComponent)
            light.set_editor_properties(dict(shadow_bias=.37,shadow_slope_bias=.49,contact_shadow_length=0.,
                light_source_angle=1.8 if street else 4.5,volumetric_scattering_intensity=.33 if street else 0.))
            casters += int(light.get_editor_property("cast_shadows"))
        elif isinstance(a,ue.SkyLight):
            light = a.get_component_by_class(ue.SkyLightComponent)
            light.set_editor_property("lower_hemisphere_color",ue.LinearColor(.063,.077,.10,1))
            if not street:
                light.set_intensity(.69)
        elif isinstance(a,ue.ExponentialHeightFog):
            fog = a.get_component_by_class(ue.ExponentialHeightFogComponent)
            fog.set_editor_properties(dict(fog_density=.012 if street else .018, fog_height_falloff=.18,
                fog_max_opacity=.35 if street else .32, enable_volumetric_fog=street,
                volumetric_fog_distance=4100., start_distance=760. if street else 480.))
        elif isinstance(a,ue.PostProcessVolume):
            grade(a,.22 if not street else .10)
        elif isinstance(a,ue.Light):
            light = a.get_component_by_class(ue.LightComponent)
            if label == "Sky bounce on the first corner":
                move(a,(803,74,407))
            p = a.get_actor_location()
            shadows = light.get_editor_property("cast_shadows")
            scattering = 0.
            if a.actor_has_tag("WindowProjection"):
                projections += 1
                shadows = ((-2130<p.x<-1940 and -470<p.y<-250)
                           or (abs(p.x+1350)<1. and 900<p.y<1550))
                light.set_editor_properties(dict(indirect_lighting_intensity=.20 if shadows else 0.))
            elif street:
                scattering = .28 if label.startswith("Sodium street lamp") else .09
            elif alley and label == "Cool rain light":
                shadows = p.x < 400 or p.x > 2700
            if label in fill:
                intensity,radius,tint = fill[label]
                local_light(light,intensity,radius,tint,shadows,scattering)
            else:
                light.set_editor_properties(dict(cast_shadows=shadows,shadow_bias=.39,
                    shadow_slope_bias=.46,contact_shadow_length=0.,volumetric_scattering_intensity=scattering))
                if isinstance(light,ue.LocalLightComponent) and not a.actor_has_tag("WindowProjection"):
                    light.set_editor_property("source_radius",16. if shadows else 21.)
            casters += int(shadows)
    for a in actors:
        for kind in (ue.BillboardComponent,ue.MaterialBillboardComponent,ue.ArrowComponent):
            for component in a.get_components_by_class(kind):
                component.set_hidden_in_game(True,False)
    ue.log(f"SCENE_CORRECTION_LIGHTS {level} shadow_casters={casters} window_projections={projections}")
