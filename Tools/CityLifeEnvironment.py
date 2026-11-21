"""Lay out the neighborhood dressing, distant blocks and elevated freight line."""
from random import Random

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, ASSETS, LIB, P, V, constant, media, output, save
from CityLifeCharacters import ROOT, SOURCE, apply_profile, mtl_colors, move_prop

TAG = ue.Name("CityLifeDressing")
FOLDER = "Brighton/City life"
RAIL_X, RAIL_HALF, RAIL_HEIGHT = -8145, 17160, 591.65
STREET_SHIFT = (0,-48,-640)


def material(name, tint, roughness=.77, emissive=0):
    result = make_material(ROOT,name,tint,roughness,emissive)
    LIB.set_material_usage(result,ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    save(result)
    return result


def save_instance_material_usage():
    materials = set()
    for actor in ACTORS.get_all_level_actors():
        for instances in actor.get_components_by_class(ue.InstancedStaticMeshComponent):
            for index in range(instances.get_num_materials()):
                surface = instances.get_material(index)
                while isinstance(surface, ue.MaterialInstance):
                    surface = surface.get_editor_property("parent")
                if isinstance(surface, ue.Material) and surface.get_path_name().startswith("/Game/"):
                    materials.add(surface)
    for surface in sorted(materials, key=lambda item: item.get_path_name()):
        if not surface.get_editor_property("used_with_instanced_static_meshes"):
            surface.set_editor_property("used_with_instanced_static_meshes", True)
            LIB.recompile_material(surface)
        # The editor can also enable the flag as soon as the map is loaded.
        assert ASSETS.save_loaded_asset(surface, True), surface
    return materials


def prop_meshes():
    result = {}
    for file in sorted((SOURCE/"Meshes").glob("SM_*.obj")):
        key = file.stem.removeprefix("SM_")
        mesh = media(file,ROOT+"/Meshes")
        palette = mtl_colors(file.with_suffix(".mtl"))
        for index,slot in enumerate(mesh.get_editor_property("static_materials")):
            name = str(slot.get_editor_property("material_slot_name"))
            tint = palette.get(name,(.32,.31,.29))
            rail = key=="RailStraight"
            train = key.startswith("Freight")
            if train and name in ("Main","DarkMain"):
                tint = (.21,.057,.040) if key=="FreightEngine" else (.18,.135,.082)
            if train and name in ("Glass","Windows"):
                tint = (.035,.048,.054)
            if key.startswith("Oak") and name in ("LightOrange","Orange"):
                tint = tuple(value*.83 for value in tint)
            surface = material(key+"_"+name,tint,.43 if train or rail else .77,4 if train and name=="Lights" else 0)
            if rail and name=="Steel" and not LIB.get_material_property_input_node(surface,P.MP_METALLIC):
                output(constant(surface,.78),surface,P.MP_METALLIC)
                LIB.recompile_material(surface)
                save(surface)
            mesh.set_material(index,surface)
        save(mesh)
        result[key] = mesh
    return result


class CityLayout:
    def __init__(self, models, offset=(0,0,0)):
        self.models=models
        self.offset=V(*offset)
        self.batches={}
        self.cube=ue.load_asset("/Engine/BasicShapes/Cube")
        self.cylinder=ue.load_asset("/Engine/BasicShapes/Cylinder")

    def actor(self, cls, label, position=(0,0,0), rotation=None):
        actor=ACTORS.spawn_actor_from_class(cls,V(*position)+self.offset,rotation or ue.Rotator())
        assert actor,label
        actor.set_actor_label(label)
        actor.set_folder_path(ue.Name(FOLDER+("/Third-floor view" if self.offset.z else "")))
        actor.tags=[*actor.tags,TAG]
        return actor

    def instance(self, label, model, position, scale=(1,1,1), yaw=0, surface=None, pitch=0, roll=0, cull=16000):
        mesh = self.models[model] if isinstance(model,str) else model
        # Split larger repeated groups by block to keep instance culling useful.
        tile = int(position[0]//4400),int(position[1]//4400)
        key = label,mesh.get_path_name(),surface.get_name() if surface else "",cull,tile
        component = self.batches.get(key)
        if component is None:
            placed=self.actor(ue.StreetMeshInstances,label,(tile[0]*4400,tile[1]*4400,0))
            component=placed.get_editor_property("instances")
            component.set_static_mesh(mesh)
            if surface:
                component.set_material(0,surface)
            else:
                for index,slot in enumerate(mesh.get_editor_property("static_materials")):
                    component.set_material(index,slot.get_editor_property("material_interface"))
            component.set_collision_profile_name(ue.Name("NoCollision"))
            component.set_cull_distances(int(cull*.84),cull)
            component.set_editor_property("affect_distance_field_lighting",False)
            self.batches[key]=component
        transform=ue.Transform(location=V(*position)+self.offset,rotation=ue.Rotator(pitch=pitch,yaw=yaw,roll=roll),
                                scale=V(*scale))
        component.add_instance(transform,True)

    def box(self, label, position, size, surface, yaw=0, pitch=0, cull=16000):
        self.instance(label,self.cube,position,tuple(v/100 for v in size),yaw,surface,pitch=pitch,cull=cull)

    def cylinder_part(self, label, position, size, surface, pitch=0, cull=12000):
        self.instance(label,self.cylinder,position,tuple(v/100 for v in size),surface=surface,pitch=pitch,cull=cull)

    def individual(self,label,model,position,yaw=0):
        actor=self.actor(ue.StaticMeshActor,label,position,ue.Rotator(yaw=yaw))
        mesh=actor.get_component_by_class(ue.StaticMeshComponent)
        mesh.set_static_mesh(model)
        mesh.set_collision_profile_name(ue.Name("NoCollision"))
        return actor


def extend_horizon(layout):
    asphalt=ue.load_asset("/Game/Prologue/Brighton/Materials/M_Wet_NeptuneAsphalt")
    curb=ue.load_asset("/Game/Prologue/Brighton/Materials/M_Wet_WeatheredConcrete")
    roadbed=material("DistantRoadBed",(.054,.051,.043))
    stripe=ue.load_asset("/Game/Prologue/Brighton/Materials/M_LanePaint")
    rng=Random(10494)
    layout.box("Outer ground below the skyline",(0,0,-118),(90000,74000,138),roadbed,cull=70000)
    for axis,side,near,mid in ((0,-1,18480,-1425),(1,-1,15380,2400),(1,1,16180,2400)):
        length=14200
        center=side*(near+length/2)
        road=(center,mid,-35) if axis==0 else (mid,center,-35)
        layout.box("Far city road",road,(length,1180,14) if axis==0 else (1500,length,14),asphalt,cull=55000)
        for kerb in (-1,1):
            p=(center,mid+kerb*760,-19) if axis==0 else (mid+kerb*915,center,-19)
            layout.box("Far city sidewalks",p,(length,340,28) if axis==0 else (330,length,28),curb,cull=55000)
        for index in range(9):
            run=side*(near+620+index*1510)
            for bank in (-1,1):
                width=mid+bank*rng.uniform(1530,1960)
                x,y=(run,width) if axis==0 else (width,run)
                height=rng.uniform(.77,1.11)
                model=("WalkupBrick","WalkupBay","MarketHouse","WalkupPale")[(index+(bank+1)//2+axis)%4]
                layout.instance("Beyond the next intersection",model,(x,y,-45),(.64,.96,height),
                    yaw=(0 if bank==1 else 180) if axis==0 else (90 if bank==1 else -90),cull=55000)
                if index%2==0:
                    layout.instance("Far roadside trees","OakAmber",(x+95,y+bank*275,-45),(.76,.76,.76),rng.randrange(360),cull=40000)
            p=(run,mid,-27.8) if axis==0 else (mid,run,-27.8)
            layout.box("Faded far lane marks",p,(187,9,1) if axis==0 else (9,187,1),stripe,cull=38500)

    # Stagger the silhouette in every direction, including behind the factory.
    for index in range(12):
        for x in (12200,18500,26600):
            y=-17900+index*3160+rng.uniform(-650,650)
            height=rng.uniform(.9,1.95)+(x-12200)/25000
            layout.instance("North skyline layers",("WalkupPale","WalkupBrick","WalkupBay")[index%3],
                (x+rng.uniform(-630,630),y,-44),(.93,1.11,height),yaw=rng.choice((0,90,180)),cull=59000)
    for bank in (-1,1):
        for index in range(12):
            x=-16300+index*2580
            y=bank*(12200+rng.uniform(-1500,2400))
            layout.instance("Side skyline layers",("WalkupBrick","WalkupPale","WalkupBay")[index%3],
                (x,y,-42),(.97,.92,rng.uniform(.8,1.52)),yaw=90*bank,cull=52500)

    for bank in (-1,1):
        for row,x in enumerate((-9480,-12250,-14740,-16870)):
            for col in range(5):
                y=-1425+bank*(2600+col*1490+rng.uniform(-270,270))
                variant=("WalkupPale","WalkupBay","WalkupBrick","MarketHouse")[(row+col)%4]
                layout.instance("South blocks behind the railway",variant,(x+rng.uniform(-220,220),y,-42),
                    (.61,.91,rng.uniform(.89,1.33)),yaw=90*bank,cull=51000)
    for index in range(11):
        y=-14650+index*2660
        if abs(y+1425)<1630:
            continue
        layout.instance("Last city blocks in the haze",("WalkupPale","WalkupBrick")[index%2],
            (-33800-rng.uniform(0,1300),y,-42),(1.06,1.22,rng.uniform(.9,1.43)),yaw=90,cull=58000)


def build_rail(layout):
    steel=material("BridgePaint",(.062,.079,.069),.63)
    aged=material("BridgeRust",(.15,.078,.045),.83)
    concrete=ue.load_asset("/Game/StreetRefinement/Materials/M_WeatheredConcrete")
    ballast=material("TrackBallast",(.122,.106,.088))
    length=2*RAIL_HALF
    layout.box("Elevated rail ballast",(RAIL_X,0,567),(395,length,36),ballast,cull=52000)
    for n in range(44):
        y=-RAIL_HALF+390+n*780
        # Stretch the track gauge to the spacing of the supplied wheelsets.
        layout.instance("Rail segments","RailStraight",(RAIL_X,y,RAIL_HEIGHT-6.2),(1,3.16,1),90,cull=48500)
    for side in (-1,1):
        x=RAIL_X+side*209
        layout.box("Steel girder of the freight bridge",(x,0,523),(41,length,65),steel,cull=53000)
        layout.box("Oxidized flange",(x,0,546),(58,length,13),aged,cull=51000)
        for y in range(-16180,16500,620):
            layout.box("Riveted girder stiffeners",(x,y,525),(56,27,68),steel,cull=29000)
    for y in (-15540,-13050,-10560,-7970,-5480,-3240,65,2520,4920,7420,9910,12450,14940):
        layout.box("Concrete trestle pier",(RAIL_X,y,207),(370,120,518),concrete,cull=48500)
        layout.box("Trestle pier seat",(RAIL_X,y,465),(500,156,26),steel,cull=48500)

    train=layout.actor(ue.CityRailTraffic,"Freight service every five minutes",(RAIL_X,0,RAIL_HEIGHT),ue.Rotator(yaw=90))
    vehicles=[]
    for key in ("FreightEngine","FreightBoxcar","FreightGondola","FreightBoxcar","FreightGondola","FreightBoxcar"):
        model=layout.models[key]
        bounds=model.get_bounding_box()
        wagon=ue.CityRailVehicle()
        wagon.set_editor_properties(dict(mesh=model,length=bounds.max.x-bounds.min.x,mesh_yaw=180 if key=="FreightEngine" else 0))
        vehicles.append(wagon)
    train.set_editor_properties(dict(consist=vehicles,half_route=RAIL_HALF,interval=300.,first_pass_delay=55.,speed=1510.))
    return train


def booth(layout,label,x,y,z,size,palette,window_side):
    width,depth,height=size
    paint,trim,glass=palette
    layout.box(label+" concrete plinth",(x,y,z+5),(width+16,depth+16,10),trim)
    roof=z+height
    layout.box(label+" roof",(x,y,roof),(width+16,depth+19,9),paint)
    layout.box(label+" lower walls",(x,y,z+42),(width,depth,72),paint)
    layout.box(label+" solid back",(x,y-window_side*(depth/2-5),z+height*.66),(width,10,height*.56),paint)
    for side in (-1,1):
        at=x+side*(width/2-4)
        layout.box(label+" metal corners",(at,y+window_side*(depth/2-4),z+height/2),(9,10,height),trim)
        layout.box(label+" side glazing",(at,y,z+height*.66),(5,depth-16,height*.54),glass)
    layout.box(label+" front glazing",(x,y+window_side*(depth/2-4),z+height*.66),(width-16,5,height*.54),glass)
    layout.box(label+" window sill",(x,y+window_side*(depth/2+1),z+height*.395),(width+4,13,7),trim)
    layout.box(label+" shelf inside",(x,y+window_side*22,z+113),(width-18,34,5),paint)


def dress_street(layout):
    rng=Random(1994)
    # Root all vegetation on the existing lawn or sidewalk, away from the door and travel markers.
    trees=(( -819,915,-7.9),( -261,1120,-7.9),(-904,2130,-7.9),(-136,1935,-7.9),
           (625,759,-7.9),(1131,1077,-7.9),(938,2380,-12),(-5480,-568,-12),
           (-3437,-1993,-12),(-5984,-602,-12),(3074,3040,-12),(3075,-3590,-12))
    soil=material("TreeBed",(.090,.066,.039))
    for index,(x,y,z) in enumerate(trees):
        scale=rng.uniform(.79,1.18)
        layout.cylinder_part("Unglazed street tree wells",(x,y,z+.7),(100,100,1.4),soil)
        layout.instance("Autumn trees",("OakAmber","BirchGold","OakGreen")[index%3],(x,y,z+.8),
            (scale,scale,scale),rng.randrange(360),cull=18200)
        for dx,dy in ((48,-30),(-27,41)):
            layout.instance("Low shrubs","Bush",(x+dx,y+dy,z),(.64,.64,.64),rng.randrange(360),cull=11500)

    faded_green=material("BoothOlive",(.079,.132,.092))
    enamel=material("BoothIvory",(.38,.34,.23))
    painted_blue=material("BoothBlue",(.074,.141,.183))
    trim=material("GalvanizedBoothTrim",(.21,.218,.215),.47)
    glass=material("BoothDarkGlass",(.077,.109,.123),.25)
    booth(layout,"Telephone booth",-5990,-1997,-12,(103,111,231),(painted_blue,trim,glass),1)
    booth(layout,"Park maintenance booth",1226,2373,-12,(161,132,227),(faded_green,enamel,glass),-1)
    booth(layout,"Parking attendant booth",1845,3670,-12,(128,123,226),(enamel,trim,glass),-1)

    paper=material("DirtyNewsprint",(.56,.51,.36))
    wrinkled=material("SoiledFlyer",(.45,.49,.44))
    old_ink=material("OldNewsprintInk",(.18,.17,.126))
    bottle=ue.load_asset("/Game/Prologue/Furniture/Grocery/soda_bottle_obj/SM_soda_bottle_obj")
    sites=((-3280,-1964,-12),(-5360,-1943,-12),(1454,-620,-12),(-1626,-503,-12),
           (1510,2260,-12),(1880,3810,-12),(3091,-3646,-12),(3210,1130,-12),(-1080,1160,-7.9))
    for index,(x,y,z) in enumerate(sites):
        layout.instance("Street bins","TrashCan" if index%3 else "Dumpster",(x,y,z),yaw=rng.randrange(360),cull=12500)
        for scrap in range(4):
            px=x+rng.uniform(-67,58)
            py=y+rng.uniform(-60,52)
            yaw=rng.randrange(360)
            layout.box("Scattered paper",(px,py,z+.44),(rng.uniform(10,23),rng.uniform(8,13),.65),
                       paper if scrap%2 else wrinkled,yaw,pitch=2,cull=7900)
            if scrap<2:
                layout.box("Faint print on litter",(px,py,z+.86),(7,3,.28),old_ink,yaw,cull=7900)
        layout.instance("Discarded pop bottle",bottle,(x+43,y-29,z+4.9),(.87,.87,.87),
                        yaw=rng.randrange(360),roll=90,cull=7600)


def add_pedestrians(layout, profiles):
    for label,profile,at,yaw,pose,phase in (
        ("Neighbor talking by the sidewalk","PedestrianMan",(698,-630,-12),10,ue.ActOnePose.CONVERSING,.27),
        ("Neighbor listening and replying","PedestrianWoman",(840,-605,-12),-170,ue.ActOnePose.CONVERSING,2.32),
        ("Smoker near the newsstand","Smoker",(-1203,-481,-12),-90,ue.ActOnePose.SMOKING,3.18),
    ):
        actor=layout.actor(ue.ActOneCast,label,at,ue.Rotator(yaw=yaw))
        actor.set_editor_properties(dict(default_pose=pose,animation_phase=phase))
        actor.set_actor_enable_collision(False)
        mesh=apply_profile(actor,profiles[profile])
        if profile=="Smoker":
            model=ue.load_asset("/Engine/BasicShapes/Cylinder")
            cigarette=layout.individual("Smoker's cigarette",model,at)
            cigarette.set_actor_scale3d(V(.010,.010,.078))
            cigarette.get_component_by_class(ue.StaticMeshComponent).set_material(0,
                material("CigarettePaper",(.64,.58,.44)))
            hand=next((key for key in ("MiddleHand_R","MiddleHand.R") if mesh.get_bone_index(ue.Name(key))>=0),"")
            assert hand
            move_prop(cigarette,actor,mesh,hand,(5,0,1))


def rebuild_city(models, profiles, interior=False):
    old=[a for a in ACTORS.get_all_level_actors() if a.actor_has_tag(TAG)]
    if old:
        assert ACTORS.destroy_actors(old)
    layout=CityLayout(models,STREET_SHIFT if interior else (0,0,0))
    extend_horizon(layout)
    build_rail(layout)
    dress_street(layout)
    if not interior:
        add_pedestrians(layout,profiles)
    ue.log("CITY_LIFE_LAYOUT "+("Third-floor windows" if interior else "Street")+" groups="+str(len(layout.batches)))
