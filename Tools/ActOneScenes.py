"""Authored environments and interaction placement for the five parts of Act One."""
from math import cos, radians, sin
from random import Random

import unreal as ue

from ApartmentScene import make_material
from ImportFurniture import Placement, place as place_furniture


V = ue.Vector
ROOT = "/Game/Story/ActOne"
TAG = ue.Name("ActOneGenerated")
COLLISION = ue.Name("BlockAll")
NO_COLLISION = ue.Name("NoCollision")
ACTORS = ue.get_editor_subsystem(ue.EditorActorSubsystem)
LIB = ue.MaterialEditingLibrary
PALETTE = {
    "ivory": (.65,.57,.40), "green": (.10,.18,.116), "steel": (.28,.32,.34),
    "plaster": (.42,.36,.28), "charcoal": (.048,.053,.057), "glass": (.09,.18,.16),
    "dark_wood": (.16,.088,.038), "rust": (.24,.078,.041), "tobacco": (.51,.053,.034),
    "cloth": (.30,.21,.13), "olive": (.181,.198,.103), "navy": (.069,.12,.19),
    "flesh": (.44,.245,.139), "ochre": (.47,.30,.13), "grey": (.29,.27,.24),
    "asphalt": (.051,.055,.065), "rain": (.39,.55,.73), "silver": (.52,.58,.62),
    "brass": (.47,.29,.095), "tape": (.84,.65,.045), "seam": (.046,.031,.018),
    "patrol": (.072,.09,.14), "shirt": (.31,.38,.43), "head_black": (.048,.031,.022),
    "alarmed": (.51,.065,.027), "paper": (.63,.56,.45), "light": (.94,.75,.41),
}
EXISTING = {
    "wood": "/Game/Prologue/Finishes/Materials/M_wood",
    "tile": "/Game/Prologue/Finishes/Materials/M_tile",
    "brick": "/Game/StreetRefinement/Materials/M_AgedRedBrick",
    "soot_brick": "/Game/StreetRefinement/Materials/M_SootBrownBrick",
    "grey_plaster": "/Game/StreetRefinement/Materials/M_GreyPaintedPlaster",
    "pavement": "/Game/StreetRefinement/Materials/M_WeatheredConcrete",
}


def rot(yaw=0, pitch=0, roll=0):
    return ue.Rotator(yaw=yaw, pitch=pitch, roll=roll)


def xyz(vector):
    return vector.x,vector.y,vector.z


def named(actor, cue):
    actor.tags = list(actor.tags) + [ue.Name("ActCue:" + cue)]
    return actor


def attach(actor, parent, component=None):
    target = component or parent.get_component_by_class(ue.SceneComponent)
    actor.get_component_by_class(ue.SceneComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    keep = ue.AttachmentRule.KEEP_WORLD
    actor.attach_to_component(target, ue.Name(), keep, keep, keep, False)


class Scene:
    def __init__(self, data, location):
        self.folder = "Act One/" + location
        self.materials = {}
        self.shapes = {name: ue.load_asset("/Engine/BasicShapes/" + name) for name in ("Cube","Sphere","Cylinder","Plane")}
        self.director = self.spawn(ue.ActOneDirector,"Act One director",(0,0,0))
        self.director.set_editor_properties({"data":data,"location":getattr(ue.ActOneLocation,location.upper())})

    def spawn(self, cls, label, xyz, yaw=0, pitch=0, roll=0, cue=None):
        a = ACTORS.spawn_actor_from_class(cls,V(*xyz),rot(yaw,pitch,roll))
        assert a, label
        a.set_actor_label(label)
        a.set_folder_path(ue.Name(self.folder))
        a.tags = list(a.tags) + [TAG]
        return named(a,cue) if cue else a

    def mat(self, key):
        if key in self.materials:
            return self.materials[key]
        if key in EXISTING:
            asset = ue.load_asset(EXISTING[key])
            assert asset, key
        else:
            asset = make_material(ROOT,key,PALETTE[key],.48 if key in ("glass","brass","silver") else .82,
                                  .28 if key in ("alarmed","light","rain") else 0)
            if key == "rain":
                asset.set_editor_properties({"blend_mode":ue.BlendMode.BLEND_TRANSLUCENT,
                                             "shading_model":ue.MaterialShadingModel.MSM_UNLIT})
                if not LIB.get_material_property_input_node(asset,ue.MaterialProperty.MP_OPACITY):
                    node = LIB.create_material_expression(asset,ue.MaterialExpressionConstant,0,220)
                    node.set_editor_property("r",.34)
                    LIB.connect_material_property(node,"",ue.MaterialProperty.MP_OPACITY)
                    LIB.recompile_material(asset)
                    ue.EditorAssetLibrary.save_loaded_asset(asset)
        self.materials[key] = asset
        return asset

    def mesh(self, name, pos, size, mat, collision=False, yaw=0, shape="Cube", pitch=0, roll=0, cue=None):
        a = self.spawn(ue.StaticMeshActor,name,pos,yaw,pitch,roll,cue)
        c = a.get_component_by_class(ue.StaticMeshComponent)
        c.set_static_mesh(self.shapes[shape])
        c.set_material(0,self.mat(mat) if isinstance(mat,str) else mat)
        c.set_collision_profile_name(COLLISION if collision else NO_COLLISION)
        c.set_editor_properties({"cast_shadow":collision or max(size)>60,
                                 "affect_distance_field_lighting":collision})
        a.set_actor_scale3d(V(*(n/100 for n in size)))
        return a

    def box(self, name, xyz, dimensions, key, cue=None, collision=True, yaw=0):
        return self.mesh(name,xyz,dimensions,key,collision,yaw,cue=cue)

    def lamp(self, name, xyz, intensity, radius, color=(1,.86,.67), cast=False):
        a = self.spawn(ue.PointLight,name,xyz)
        c = a.get_component_by_class(ue.PointLightComponent)
        c.set_editor_properties({"mobility":ue.ComponentMobility.MOVABLE,"cast_shadows":cast,
                                 "use_inverse_squared_falloff":False,"source_radius":19})
        c.set_light_color(ue.LinearColor(*color,1))
        c.set_intensity(intensity)
        c.set_attenuation_radius(radius)

    def furniture(self, model, name, center, size, yaw=0):
        mesh = ue.load_asset(f"/Game/Prologue/Furniture/{model}/{model}")
        assert mesh, model
        actor = place_furniture(Placement(model,name,"",center,size,yaw,folder=self.folder),mesh)
        actor.tags = list(actor.tags) + [TAG]
        return actor

    def target(self, label, xyz, yaw=0, tag=None, cue=None):
        a = self.spawn(ue.TargetPoint,label,xyz,yaw,cue=cue)
        if tag:
            a.tags = list(a.tags) + [ue.Name(tag)]
        return a

    def entry(self,pos,yaw=0):
        self.spawn(ue.PlayerStart,"Default player start",pos,yaw)
        self.target("Safe threshold ActEntry",pos,yaw,tag="ActEntry")

    def camera(self,label,pos,look,field=73):
        angle = ue.MathLibrary.find_look_at_rotation(V(*pos),V(*look))
        a = self.spawn(ue.CameraActor,label,pos,angle.yaw,angle.pitch)
        a.get_component_by_class(ue.CameraComponent).set_field_of_view(field)
        return a

    def photo(self,pos,look,field=73):
        a=self.camera("Destination loading photograph",pos,look,field)
        a.tags = list(a.tags) + [ue.Name("ActPhoto")]
        return a

    def use(self, name, action, prompt, pos, extent=(19,36,42), yaw=0):
        a=self.spawn(ue.ActOneInteraction,name,pos,yaw)
        a.set_editor_properties({"action":getattr(ue.ActOneAction,action),"prompt":prompt})
        a.get_editor_property("focus_box").set_box_extent(V(*extent))
        return a

    def room(self, name, x0,x1,y0,y1, floor="wood", wall="plaster", h=290):
        x,y=(x0+x1)/2,(y0+y1)/2
        self.box(name+" floor",(x,y,-12),(x1-x0,y1-y0,24),floor)
        self.box(name+" ceiling",(x,y,h+9),(x1-x0,y1-y0,18),wall)
        for mx in (x0-9,x1+9):
            self.box(name+" end wall",(mx,y,h/2),(18,y1-y0+36,h),wall)
        for my in (y0-9,y1+9):
            self.box(name+" side wall",(x,my,h/2),(x1-x0,18,h),wall)
            self.box("Rubbed baseboard",(x,my+ (11 if my<y else -11),7),(x1-x0,4,14),"dark_wood",collision=False)

    def door_x(self,label,x,y,mat="dark_wood",front=-1):
        self.box(label,(x,y,105),(10,113,212),mat)
        for edge in (-58,58):
            self.box(label+" frame",(x+front*6,y+edge,111),(17,7,222),"charcoal",collision=False)
        self.box(label+" header",(x+front*6,y,222),(18,124,10),"charcoal",collision=False)
        self.mesh("Door knob",(x+front*13,y+38,108),(9,9,8),"brass",shape="Sphere")

    def shelf(self,x,y,z,w,d,h,axis="x"):
        horizontal = (w,d,4) if axis=="x" else (d,w,4)
        for level in (0,.28,.56,.84):
            self.box("Scuffed empty shelf",(x,y,z+h*level),horizontal,"ivory")
        for edge in (-1,1):
            at=(x+edge*w/2,y,z+h/2) if axis=="x" else (x,y+edge*w/2,z+h/2)
            dim=(4,d,h) if axis=="x" else (d,4,h)
            self.box("Steel shelf frame",at,dim,"steel")

    def desk(self,x,y,wide=215,deep=84,key="dark_wood"):
        self.box("Desk worktop",(x,y,78),(deep,wide,6),key)
        for side in (-1,1):
            self.box("Desk support",(x,y+side*(wide/2-22),36),(deep-7,42,72),key)

    def label(self,label,pos,yaw,size,color=(227,217,179),cued=None):
        actor=self.spawn(ue.TextRenderActor,label,pos,yaw,cue=cued)
        text=actor.get_component_by_class(ue.TextRenderComponent)
        text.set_editor_properties({"text":label,"world_size":size,"text_render_color":ue.Color(*color,255),
                                    "horizontal_alignment":ue.HorizTextAligment.EHTA_CENTER})
        return actor

    def framed_photo(self, name, pos, dimensions, texture, vertical_axis="x", crop=False):
        x,y,z=pos
        w,h=dimensions
        depth=6
        material=picture_material(texture,crop)
        if vertical_axis=="x":
            self.box(name+" frame",(x,y,z),(depth,w+5,h+5),"dark_wood",collision=False)
            face=self.mesh(name,(x+3.2,y,z),(w,h,1),material,shape="Plane")
            across=V(0,1,0)
        else:
            self.box(name+" frame",(x,y,z),(w+5,depth,h+5),"dark_wood",collision=False)
            face=self.mesh(name,(x,y+3.2,z),(w,h,1),material,shape="Plane")
            across=V(-1,0,0)
        face.set_actor_rotation(ue.MathLibrary.make_rot_from_xy(across,V(0,0,1)),False)
        return face

    def person(self,name,key,pos,yaw,coat,pants="charcoal",hair="head_black",seated=False,detail=None):
        a=self.spawn(ue.ActOneCast,name,pos,yaw,cue=key)
        rig=a.get_editor_property("pose_root")
        parts={}
        shift=-37 if seated else 0
        angle=radians(yaw)
        def local(dx,dy,dz):
            return a.get_actor_location()+V(dx*cos(angle)-dy*sin(angle),dx*sin(angle)+dy*cos(angle),dz)
        def shape(label,position,dim,material,part=None,group=None,form="Sphere",ang=0):
            actor=self.mesh(label,xyz(local(*position)),dim,material,yaw=yaw,shape=form,pitch=ang)
            attach(actor,group) if group else attach(actor,a,rig)
            if part: parts[ue.Name(part)]=actor
            return actor
        shape("Coat",(0,0,118+shift),(33,46,77),coat,form="Sphere")
        shape("Collar",(12,0,144+shift),(12,25,15),"cloth",form="Cube",ang=9)
        shape("Neck",(0,0,151+shift),(13,14,16),"flesh",form="Cylinder")
        head=shape("Head",(1,0,169+shift),(22,19,27),"flesh","Head")
        shape("Hair",(-4,0,175+shift),(20,20,18),hair,group=head)
        for side in (-1,1):
            shape("Eye",(10,side*4.3,171+shift),(2.4,2.8,2.2),"head_black",group=head)
            shape("Ear",(0,side*8.5,166+shift),(4,5,8),"flesh",group=head)
        shape("Nose",(12,0,167+shift),(8,6.4,5),"alarmed" if detail=="bartender" else "flesh",group=head)
        if detail=="bartender":
            shape("Gauze over broken nose",(15,0,168+shift),(3,13,4),"ivory",group=head,form="Cube",ang=-6)
        if detail in ("veteran","old","captain"):
            shape("Jaw stubble",(7,0,159+shift),(13,18,8),"grey",group=head)
        hands={}
        for side,suffix in ((-1,"L"),(1,"R")):
            shoulder=shape("Coat sleeve",(0,side*24,118+shift),(16,18,56),coat,"Arm"+suffix,ang=(-26 if seated else 0))
            hands[suffix]=shape("Hand",(4,side*25,89+shift),(10,12,12),"flesh",group=shoulder)
            thigh=shape("Trouser leg",(2 if not seated else 15,side*11,44 if not seated else 34),
                        (17,19,88 if not seated else 58),pants,"Leg"+suffix,ang=(44 if seated else 0))
            shape("Boot",(5 if not seated else 36,side*11,6),(24,19,12),"head_black",group=thigh,form="Cube")
        if detail in ("cop","captain","guard","patrol","agent"):
            plate=shape("Brass chest insignia",(15,9,130+shift),(3,9,10),"brass",form="Cube")
            if detail in ("guard","patrol","agent"):
                stencil=self.label("AEGIS",xyz(local(17,-7,133+shift)),yaw,6)
                attach(stencil,a,rig)
        if detail in ("old","bartender"):
            right=parts[ue.Name("ArmR")]
            shape("Green glass bottle",(8,24,85+shift),(8,8,19),"glass",group=right,form="Cylinder",ang=30)
            shape("Bottle neck",(11,24,96+shift),(4,4,10),"glass",group=right,form="Cylinder",ang=30)
        a.set_editor_properties({"parts":parts,"default_pose":
            ue.ActOnePose.SEATED if seated else ue.ActOnePose.SMOKING if detail=="ivan" else
            ue.ActOnePose.WALKING if detail=="patrol" else ue.ActOnePose.IDLE})
        return a

    def rain(self):
        component=self.director.get_editor_property("rain")
        component.set_static_mesh(self.shapes["Cube"])
        component.set_material(0,self.mat("rain"))

    def recorder_hand(self):
        hand=self.director.get_editor_property("smoke_hand")
        hand.set_static_mesh(self.shapes["Sphere"])
        hand.set_material(0,self.mat("flesh"))
        hand.set_editor_property("relative_scale3d",V(.30,.13,.16))


def picture_material(texture,crop):
    name="M_FedorPoster" if crop else "M_FedorPhotograph"
    path=ROOT+"/Materials/"+name
    if ue.EditorAssetLibrary.does_asset_exist(path):
        return ue.load_asset(path)
    m=make_material(ROOT,name,(.62,.59,.52),.9)
    m.set_editor_property("two_sided",True)
    picture=LIB.create_material_expression(m,ue.MaterialExpressionTextureSample,0,0)
    picture.set_editor_property("texture",texture)
    if crop:
        node=LIB.create_material_expression(m,ue.MaterialExpressionTextureCoordinate,-230,-20)
        node.set_editor_properties({"u_tiling":.36,"v_tiling":.60})
        offset=LIB.create_material_expression(m,ue.MaterialExpressionAdd,-100,-20)
        offset.set_editor_property("const_b",.10)
        LIB.connect_material_expressions(node,"",offset,"A")
        LIB.connect_material_expressions(offset,"",picture,"Coordinates")
    LIB.connect_material_property(picture,"RGB",ue.MaterialProperty.MP_BASE_COLOR)
    LIB.recompile_material(m)
    ue.EditorAssetLibrary.save_loaded_asset(m)
    return m


def page_speakers(spec):
    roles={"Guard":"BarGuard","Veteran":"Veteran","Captain":"Krill","Ivan":"IvanStreet"}
    result={key:roles[row["speaker_role"]] for key,row in spec["documents"].items() if row.get("speaker_role") in roles}
    result.update(OldManThanks="OldMan",IvanFedor="IvanFedor")
    return {ue.Name(page):ue.Name(role) for page,role in result.items()}


def weapon(s,name,pos,cue=None,angle=0):
    x,y,z=pos
    a=s.box(name,(x,y,z),(18,4,5),"charcoal",cue,False,angle)
    grip=s.mesh("Grip",(x-5,y,z-4),(5,4,7),"steel",yaw=angle,pitch=-20)
    attach(grip,a)
    return a


def badge(s,name,pos,cue=None):
    x,y,z=pos
    item=s.mesh(name,(x,y,z),(12,8,1.4),"brass",cue=cue)
    letter=s.label("AEGIS",(x,y,z+1),-90,2.5,(40,29,13))
    letter.set_actor_rotation(rot(-90,-90),False)
    attach(letter,item)
    return item


def recorder(s,pos):
    x,y,z=pos
    case=s.box("Cassette recorder case",(x,y,z),(25,41,8),"charcoal",collision=False)
    for dy in (-9,9):
        s.mesh("Reel window",(x,y+dy,z+4.2),(7,7,.8),"steel",shape="Cylinder")
    for dy in (-14,-7,0,7,14):
        s.box("Tape deck key",(x-10,y+dy,z+4),(3,5,2),"ivory",collision=False)
    s.box("Tape deck speaker",(x+7,y,z+4.3),(11,31,1),"seam",collision=False)
    return case


def bench(s,x,y,z,wide=138):
    for n in (-1,0,1):
        s.box("Wood bench slat",(x,y+n*12,z+44),(wide,8,4),"dark_wood")
    for dx in (-wide*.34,wide*.34):
        s.box("Cast bench leg",(x+dx,y,z+21),(8,33,42),"steel")


def apartment(s, portrait):
    # The existing report, furniture and all of the first part stay on the original map.
    report=next(a for a in ACTORS.get_all_level_actors() if a.get_actor_label()=="Seated report camera")
    p=report.get_actor_location()
    desk=next((a for a in ACTORS.get_all_level_actors() if a.get_actor_label() in ("Writing desk","Desk","Work desk")),None)
    if desk:
        d,e=desk.get_actor_bounds(False)
        prop=(d.x+e.x*.39,d.y-e.y*.12,d.z+e.z+4)
    else:
        prop=(-74,315,82)
    recorder(s,prop)
    shot=s.camera("Finale at the desk",xyz(p),(prop[0]-12,prop[1],prop[2]+9),66)
    s.director.set_editor_property("finale_camera",shot)
    s.target("Tape playback button",(prop[0]-10,prop[1],prop[2]+5),cue="FinaleTapeButton")
    s.recorder_hand()
    pistol=(prop[0]-41,prop[1]-17,prop[2]-1)
    weapon(s,"Dima's service pistol",pistol,"Pistol",12)
    s.use("Optional service pistol","PISTOL","Взять служебный пистолет",(pistol[0],pistol[1],pistol[2]+4),(12,15,7))
    s.target("Safe return before the closing scene",(-132,245,98),26,tag="FromFinale")


def neptune(s, portrait):
    s.rain()
    placed=ACTORS.get_all_level_actors()
    for actor in placed:
        if isinstance(actor,ue.StreetPortal):
            label=actor.get_actor_label()
            if label=="Precinct street door":
                actor.tags=list(actor.tags)+([] if actor.actor_has_tag("ActPrecinctEntry") else [ue.Name("ActPrecinctEntry")])
            elif label.startswith("Bar Lighthouse entrance reserved"):
                # Keep the visible door and replace only its old closed interaction.
                actor.get_editor_property("focus_box").set_collision_enabled(ue.CollisionEnabled.NO_COLLISION)
                bp=actor.get_actor_location()
                s.use("Lighthouse exterior entrance","BAR","Зайти в бар «Маяк»",(bp.x,bp.y,bp.z),(15,61,100))
                s.target("Safe sidewalk returning from the bar",(bp.x-153,bp.y,96),180,tag="FromBar")
    s.use("Ask newspaper seller","PRESS","Постучать в киоск",(-1505,-674,151),(94,12,38))
    s.use("Newspaper on the public counter","NEWSPAPER","Читать газету",(-1505,-663,87),(74,22,8))

    # Wall-mounted pushbutton payphone, metal backplate, handset and coin return.
    x,y=548,-437
    s.box("Payphone backplate",(x,y+5,137),(45,9,80),"charcoal",collision=False)
    s.box("Stainless payphone face",(x,y-3,137),(37,12,64),"steel",collision=False)
    s.box("Payphone handset",(x-17,y-16,136),(8,8,45),"charcoal",collision=False)
    for row in range(4):
        for col in range(3):
            s.box("Payphone pushbutton",(x-5+6*col,y-10,136-5*row),(3,2,3),"ivory",collision=False)
    s.box("Coin return",(x+8,y-10,113),(12,3,5),"charcoal",collision=False)
    for j in range(14):
        s.mesh("Coiled payphone cord",(x-17+11*j/13,y-16,109-12*sin(j*3.14159/13)),(4,4,5),"charcoal",shape="Sphere")
    s.use("Street payphone","PAY_PHONE","Позвонить с таксофона",(x,y-18,137),(28,8,42))

    s.person("Veteran outside the flea market","Veteran",(3297,-2684,-9),185,"olive","cloth","grey",detail="veteran")
    s.use("Talk to the veteran","VETERAN","Поговорить со стариком",(3267,-2684,120),(14,28,61))

    x,y=-1430,-2168
    s.box("Grocery entrance frame",(x,y,103),(116,13,220),"charcoal",collision=False)
    s.box("Grocery entrance upper glass",(x,y+9,144),(98,6,119),"glass",collision=False)
    s.box("Grocery entrance wood kickplate",(x,y+9,48),(98,6,72),"dark_wood",collision=False)
    for dx in (-49,49):
        s.box("Grocery brass jamb",(x+dx,y+14,103),(4,5,214),"brass",collision=False)
    s.box("Grocery horizontal pull",(x+26,y+16,106),(12,7,5),"brass",collision=False)
    s.use("Enter grocery from Brighton","GROCERY","Войти в магазин",(x,y+24,104),(56,12,100))
    s.target("Safe sidewalk returning from grocery",(x,-1968,96),90,tag="FromGrocery")

    figure=s.person("Ivan by the precinct","IvanStreet",(1635,-2520,-10),0,"navy","charcoal",detail="ivan")
    s.target("Ivan leaves around the corner",(1645,-2045,-10),cue="IvanStreetExit")
    s.use("Speak to Ivan outside","IVAN_STREET","Поговорить с Иваном",(1668,-2520,135),(17,28,53))
    sedan=s.spawn(ue.StaticMeshActor,"Parked sedan for the drive",(1770,-3178,-26),90)
    car=sedan.get_component_by_class(ue.StaticMeshComponent)
    car.set_static_mesh(ue.load_asset("/Game/Prologue/Street/Meshes/SM_Sedan94"))
    car.set_collision_profile_name(COLLISION)
    s.use("Drive to Fedor's building","RIDE","Сесть в машину",(1886,-3180,67),(18,134,68))


def grocery(s, portrait):
    s.room("Grocery", -530,548,-330,350,"tile","grey_plaster")
    s.entry((-419,-24,104))
    s.photo((-401,42,177),(270,-68,125))
    s.door_x("From the street",-521,-24,front=1)
    s.use("Return to Brighton","LEAVE_GROCERY","Выйти на улицу",(-499,-24,108),(13,63,102))
    for x in (-350,-102,132):
        s.shelf(x,-292,20,208,54,209)
    for y in (-165,98):
        s.shelf(504,y,20,228,54,216,"y")
    s.box("Grocery check-out counter",(237,93,48),(124,246,107),"dark_wood")
    s.box("Faded plastic counter top",(232,93,105),(134,255,9),"steel")
    reg=s.box("Cash register housing",(262,128,121),(43,44,22),"charcoal",collision=False)
    for row in range(4):
        for column in range(4):
            s.box("Register key",(247+column*5,118+row*5,133),(3,3,2),"ivory",collision=False)
    clerk=s.person("Russian shopkeeper","GroceryClerk",(381,64,0),180,"green","cloth",detail="clerk")
    s.box("Marlboro cigarette packet",(208,19,112),(9,6,2.4),"ivory",collision=False)
    s.box("Red Marlboro packet shoulder",(205,19,113.3),(3,6,1),"tobacco",collision=False)
    text=s.label("Marlboro",(210,19,113.6),-90,2,(78,28,20))
    text.set_actor_rotation(rot(-90,-90),False)
    s.use("Marlboro on the counter","CIGARETTES","Купить сигареты Marlboro",(197,19,119),(13,19,12))
    s.box("Wood display board above the till",(535,67,219),(8,205,44),"green",collision=False)
    s.label("BRIGHTON GROCERY",(530,67,228),180,13)
    s.label("CASH ONLY",(175,52,83),180,11)
    for x in (-291,-42,185):
        s.box("Old shelf price strip",(x,-262,96),(150,1.5,4),"paper",collision=False)
    for x in (-264,190):
        s.box("Recessed fluorescent lamp",(x,-9,285),(131,23,9),"light",collision=False)
        s.lamp("Fluorescent light",(x,-9,241),117,570,(.86,.98,.91),x>0)


def bar(s, portrait):
    s.room("Lighthouse", -620,730,-461,479,"wood","soot_brick",300)
    s.entry((-495,146,104))
    s.photo((-438,174,166),(218,-27,132),85)
    s.door_x("Bar entry from Fifth",-610,146,front=1)
    s.use("Street door inside the bar","LEAVE_BAR","Выйти из бара",(-584,146,107),(12,63,96))
    s.box("Long bar front",(7,-304,46),(754,80,101),"dark_wood")
    s.box("Polished brass-edged bar counter",(7,-304,102),(770,101,10),"wood")
    for x in (-307,-189,-55,83,212,330):
        s.mesh("Cast-iron stool base",(x,-232,27),(12,12,58),"charcoal",shape="Cylinder")
        s.mesh("Worn stool seat",(x,-232,58),(42,42,9),"tobacco",True,shape="Cylinder")
    for z in (122,177,232):
        s.box("Bottles backboard",(18,-447,z),(650,41,4),"dark_wood",collision=False)
        for i in range(16):
            x=-289+i*37
            s.mesh("Bar bottle",(x,-438,z+14),(8,8,23),"glass" if i%3 else "ochre",shape="Cylinder")
            s.mesh("Bottle neck",(x,-438,z+29),(4,4,9),"glass",shape="Cylinder")
    s.person("Bartender with broken nose","Bartender",(-25,-394,0),90,"ivory","charcoal",detail="bartender")
    guard=s.person("Aegis security guard","BarGuard",(403,149,0),170,"navy","charcoal",detail="guard")
    s.person("Older immigrant holding a bottle","OldMan",(508,324,0),205,"cloth","grey","grey",detail="old")
    s.target("Old man to the street",(-610,144,0),cue="OldManExit")
    s.target("Old man approaches Dima",(296,246,0),cue="OldManThanks")
    s.use("Break up the altercation","GUARD","Разобраться с дебошем",(365,154,123),(14,45,67))
    arm=guard.get_editor_property("parts")[ue.Name("ArmR")]
    item=weapon(s,"Guard's pistol",xyz(arm.get_actor_location()+V(-7,-2,-24)),"GuardWeapon",180)
    attach(item,arm)
    hide_bundle(item)
    hide_bundle(weapon(s,"Pistol knocked to the floor",(382,175,4),"DroppedWeapon",49))
    for x,y in ((-353,348),(-61,352),(247,373)):
        s.mesh("Round bar table",(x,y,72),(100,100,8),"dark_wood",True,shape="Cylinder")
        s.mesh("Cast pedestal",(x,y,34),(14,14,65),"charcoal",True,shape="Cylinder")
        s.mesh("Half-empty glass",(x-21,y+22,82),(8,8,18),"glass",shape="Cylinder")
        s.box("Loose coaster",(x+23,y-20,76.4),(13,13,.6),"paper",collision=False)
    for x,y in ((-286,-252),(32,-200),(357,108),(-330,277)):
        s.mesh("Pendant lamp hood",(x,y,244),(52,52,14),"brass",shape="Cylinder")
        s.lamp("Amber pool of light",(x,y,216),85,490,(1,.77,.56),x==357)
    s.lamp("Cool light leaking from the door",(-517,166,195),52,430,(.65,.77,1))
    s.lamp("Low ambient reflection in the booths",(411,304,164),26,698,(.77,.70,.61))
    s.box("Wood panel along the booths",(55,474,57),(1340,8,114),"dark_wood",collision=False)
    s.box("Wood wainscot crown",(55,468,115),(1340,8,7),"wood",collision=False)
    s.box("Lighthouse painted board",(721,61,211),(9,176,54),"green",collision=False)
    s.label("THE LIGHTHOUSE",(714,61,218),180,13)
    for x in (-274,-239,-215,-180,-146,82,126,154,189,215):
        s.mesh("Different bottles behind the bar",(x,-426,145),(8,8,23+x%11),"glass",shape="Cylinder")
        s.mesh("Foil bottle neck",(x,-426,158+x%11/2),(4,4,9),"brass",shape="Cylinder")


def hide_bundle(actor):
    actor.set_actor_hidden_in_game(True)
    attached=actor.get_attached_actors(reset_array=True,recursively_include_attached_actors=True)
    for piece in attached:
        piece.set_actor_hidden_in_game(True)


def precinct(s, portrait):
    for actor in list(ACTORS.get_all_level_actors()):
        p=actor.get_actor_location()
        if actor.get_actor_label()=="Precinct lobby exit":
            if not actor.actor_has_tag("ActPrecinctExit"):
                actor.tags=list(actor.tags)+[ue.Name("ActPrecinctExit")]
        if actor.get_actor_label() in ("Reception side plaster","Precinct masonry shell") and abs(p.y+2177)<44 and p.x<1770:
            # Cut the lobby partition and the exterior shell at the same doorway.
            if p.y>-2500 and 1030<p.x<1600:
                assert ACTORS.destroy_actor(actor)
    for x0,x1 in ((806,1427),(1571,1818)):
        s.box("Lobby plaster beside office door",((x0+x1)/2,-2179,130),(x1-x0,42,285),"plaster")
    s.box("Office doorway lintel",(1499,-2179,254),(150,42,62),"plaster")
    s.box("Office floor",(1312,-1736,-23),(1010,886,22),"wood")
    s.box("Office ceiling",(1312,-1736,281),(1010,886,25),"plaster")
    for x in (806,1817):
        s.box("Side wall of captain's office",(x,-1736,129),(23,894,286),"plaster")
    s.box("Back wall of captain's office",(1311,-1296,129),(1010,24,286),"green")
    for x in (1426,1572):
        s.box("Office casing",(x,-2212,99),(7,8,222),"dark_wood",collision=False)
    s.box("Office casing header",(1499,-2212,210),(155,8,8),"dark_wood",collision=False)
    pivot=s.target("Office hinge",(1433,-2181,-11),cue="OfficeLeaf")
    panel=s.box("Captain's office door",(1498,-2181,94),(130,7,210),"dark_wood")
    panel.get_component_by_class(ue.StaticMeshComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    attach(panel,pivot)
    knob=s.mesh("Office door brass handle",(1550,-2188,94),(10,8,8),"brass",shape="Sphere")
    knob.get_component_by_class(ue.StaticMeshComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    attach(knob,pivot)
    s.use("Captain's office door interaction","OFFICE","Открыть кабинет Крилла",(1499,-2200,95),(65,9,102))
    s.label("CAPTAIN KRILL",(1499,-2218,228),-90,10)
    s.label("КАПИТАН КРИЛЛ",(1499,-2218,239),-90,8)
    s.lamp("Office soft fluorescent",(1332,-1690,249),117,720,(.98,.94,.85),True)
    s.lamp("Office desk pool",(1269,-1610,133),49,315,(1,.80,.55))
    s.desk(1255,-1644,237,88)
    s.box("Fedor case file on Krill's desk",(1237,-1660,84),(32,25,4),"ochre",collision=False)
    s.box("Folder stamp",(1242,-1663,86.2),(14,6,.5),"tobacco",collision=False)
    s.box("Brass desk lamp foot",(1291,-1550,86),(23,23,5),"brass",collision=False)
    s.mesh("Desk lamp stem",(1291,-1550,102),(4,4,32),"brass",shape="Cylinder")
    s.mesh("Green glass desk shade",(1291,-1550,118),(45,25,11),"glass",shape="Sphere")
    s.person("Captain Krill seated","Krill",(1254,-1537,-11),-90,"patrol","navy","grey",True,"captain")
    s.use("Talk with Captain Krill","CAPTAIN","Поговорить с Криллом",(1256,-1599,131),(36,22,51))
    hide_bundle(badge(s,"Krill's Aegis offer",(1248,-1616,84),"OfferBadge"))
    s.mesh("Office waste bin",(1131,-1572,16),(35,35,50),"charcoal",True,shape="Cylinder")
    hide_bundle(badge(s,"Badge in waste bin",(1131,-1571,42),"TrashBadge"))
    s.shelf(1689,-1360,38,199,59,207)
    s.box("Cabinet with the Aegis archive index",(1689,-1394,90),(130,12,79),"green")
    s.use("Read authorised archives","ARCHIVES","Посмотреть архивную опись",(1690,-1411,118),(75,13,42))
    s.box("Training exercise cards",(1742,-1855,76),(60,115,7),"steel")
    s.box("Lock timing training handout",(1725,-1854,81),(24,33,2),"paper",collision=False)
    s.use("Training papers on the filing cabinet","TRAINING","Осмотреть учебную карточку",(1710,-1855,86),(19,26,17))
    s.person("Desk sergeant in the lobby","DutyOfficer",(1078,-2844,-10),25,"navy","charcoal",detail="cop")
    s.box("Missing persons board",(889,-2445,168),(13,156,119),"cloth",collision=False)
    photo=s.framed_photo("Fedor missing notice photo",(880,-2445,169),(53,71),portrait,crop=True)
    photo.set_actor_location(V(900,-2445,170),False,True)
    s.label("ПРОПАЛ БЕЗ ВЕСТИ",(897,-2445,218),0,9)
    s.label("MISSING PERSON",(897,-2445,117),0,8)
    for dy in (-62,62):
        s.box("Pinned official notice",(899,-2445+dy,170),(2,23,42),"paper",collision=False)
    s.use("Read Fedor on the noticeboard","MISSING","Осмотреть доску розыска",(913,-2445,166),(11,72,64))


def entrance(s, portrait):
    s.rain()
    s.box("Wet drive and public steps",(238,0,-14),(1575,1135,28),"asphalt")
    s.box("Residential brick shell",(688,0,421),(410,1050,866),"brick")
    s.box("Stoop riser",(476,0,5),(94,247,12),"pavement")
    s.box("Door surround",(477,0,131),(20,184,265),"dark_wood",collision=False)
    leaf=s.target("Sealed door hinge",(460,-62,0),cue="SealedLeaf")
    attach(s.box("Sealed apartment entrance",(460,0,108),(15,124,219),"green"),leaf)
    attach(s.box("Door inset",(450,0,152),(5,85,82),"charcoal",collision=False),leaf)
    tape=s.target("Police seal attachment",(445,0,112),cue="PoliceTape")
    attach(tape,leaf)
    for z in (94,126):
        attach(s.mesh("Police tape",(445,0,z),(3,159,9),"tape",yaw=0,roll=11 if z==94 else -11),tape)
        for stripe in range(-70,71,19):
            attach(s.mesh("Black stripe on the police tape",(443,stripe,z+stripe*(.19 if z==94 else -.19)),(2,7,8),"seam",roll=-12),tape)
    s.box("Apartment entrance riser",(422,0,4),(38,168,8),"pavement",collision=False)
    attach(s.label("23",(444,0,208),180,14),leaf)
    s.use("Sealed door to Fedor","SEAL","Осмотреть опечатанную дверь",(430,0,114),(16,80,101))
    s.person("Corporate patrol on the lookout","Patrol",(359,282,0),-76,"patrol","navy",detail="patrol")
    s.target("Patrol midpoint",(359,282,0),cue="PatrolOrigin")
    alert=s.mesh("Alert light on the landing",(443,107,204),(8,9,12),"alarmed",shape="Sphere",cue="AlarmLamp")
    hide_bundle(alert)
    s.box("Street retaining wall",(114,-544,123),(1120,22,274),"brick")
    s.box("Neighbor's retaining wall",(116,550,123),(1120,22,274),"brick")
    for z in (321,539,751):
        for y in (-389,-217,0,215,389):
            s.box("Upstairs apartment window",(480,y,z),(10,88,102),"glass",collision=False)
            s.box("Stone window sill",(472,y,z-55),(24,105,9),"pavement",collision=False)
    s.box("Entrance porch canopy",(409,0,247),(194,231,12),"charcoal",collision=False)
    s.lamp("Sodium porch light",(423,0,216),124,492,(1,.71,.44),True)
    s.lamp("Reflected blue night light",(-180,-40,333),35,845,(.47,.64,1))
    s.lamp("Sidewalk night lamp",(80,411,415),49,695,(.54,.71,.94))
    s.entry((-410,0,98))
    s.photo((-372,-151,166),(420,15,174),71)


def fedor(s, portrait):
    s.room("Fedor's flat",-520,535,-386,399,"wood","plaster",285)
    s.entry((-417,-150,104))
    s.photo((-387,-195,164),(191,130,116),79)
    s.door_x("Fedor's main door",-510,-150,front=1)
    s.use("Exit Fedor's flat","LEAVE_FEDOR","Выйти из квартиры",(-480,-150,106),(13,62,95))
    s.furniture("Carpet_1","Search-stained woven rug",(43,-30,.6),(310,265,1.1))
    s.box("Floorboard recess",(-204,101,.76),(61,46,1.1),"seam",collision=False)
    board=s.box("Loose floorboard",(-204,101,2.4),(61,46,3.0),"wood",cue="Floorboard",collision=False)
    board.get_component_by_class(ue.StaticMeshComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    s.use("Loose board investigation","FLOORBOARD","Поддеть половицу",(-204,101,8),(36,26,8))
    folder=s.box("Top secret folder under the boards",(-211,102,1.52),(31,23,1.3),"ochre",cue="Folder",collision=False)
    s.box("Red stamp on the file",(-216,98,2.2),(12,7,.5),"tobacco",collision=False)
    s.use("Evidence under the floor","FOLDER","Взять папку «Совершенно секретно»",(-207,101,10),(25,17,10))
    s.box("Former engineering bookshelf",(483,-248,100),(82,186,202),"dark_wood")
    for z in (62,114,169):
        s.box("Shelf with gaps after the search",(422,-247,z),(36,181,6),"ivory",collision=False)
        for n in (0,1,4,6):
            s.mesh("Worn book",(414,-322+n*22,z+12),(18,10,23),("tobacco","olive","cloth")[n%3],roll=n*3)
    s.desk(345,205,215,94)
    s.box("Desk drawer opening",(294,208,58),(14,116,27),"seam",collision=False)
    draw=s.box("Central desk drawer",(287,208,53),(53,103,17),"dark_wood",cue="Drawer",collision=False)
    draw.get_component_by_class(ue.StaticMeshComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    grip=s.box("Drawer pull",(259,208,56),(6,28,4),"brass",collision=False)
    grip.get_component_by_class(ue.StaticMeshComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    attach(grip,draw)
    s.use("Search Fedor's drawer","DRAWER","Выдвинуть ящик",(249,208,55),(14,52,19))
    hide_bundle(badge(s,"Aegis Disposal Division badge",(239,204,64),"DeskBadgeProp"))
    s.use("Badge exposed in the drawer","DESK_BADGE","Осмотреть значок Aegis",(239,204,74),(16,24,10))
    s.box("Dresser with tilted drawers",(-44,-319,42),(137,86,85),"dark_wood")
    for index in range(2):
        s.box("Drawer left open by the search",(-44,-266+index*19,19+index*31),(121,56,12),"dark_wood")
    recorder(s,(-68,-321,89))
    s.box("Found audio cassette",(-16,-305,87),(10,6,1.5),"charcoal",collision=False)
    s.box("Tape label",(-16,-305,88),(7,4,1),"paper",collision=False)
    s.use("Fedor's audio cassette","TAPE","Взять аудиокассету",(-16,-306,95),(15,19,10))
    s.box("Small photo cabinet",(157,-302,38),(92,83,77),"wood")
    s.framed_photo("Old photograph of Fedor",(157,-323,105),(49,33),portrait,"y")
    s.use("Photo evidence","PHOTOGRAPH","Рассмотреть фотографию",(157,-300,104),(33,17,24))
    s.furniture("Bed_King","Searched and half-stripped bed",(-22,315,38),(207,132,76),90)
    s.furniture("NightStand_1","Nightstand against the headboard",(114,315,32),(57,53,64),90)
    s.box("Old steam radiator in front of the window",(-90,-374,37),(162,15,71),"ivory",collision=False)
    for x in range(-157,-17,13):
        s.mesh("Cast iron radiator tube",(x,-365,37),(8,6,64),"steel",shape="Cylinder")
    rng=Random(251)
    for n in range(23):
        x,y=rng.uniform(-170,442),rng.uniform(-251,344)
        s.mesh("Scattered typed sheet",(x,y,1.18+(n%3)*.12),(24,31,.3),"paper",yaw=rng.uniform(-180,180))
    s.person("Ivan waiting in the doorway","IvanFedor",(-442,-155,0),0,"navy","charcoal",detail="ivan")
    s.target("Ivan leaves through the front door",(-500,-155,0),cue="IvanFedorExit")
    s.use("Ivan in Fedor's apartment","IVAN_FEDOR","Поговорить с Иваном",(-404,-150,119),(16,25,53))
    s.lamp("Fedor lamp key",(-73,-184,236),69,667,(1,.86,.65))
    s.lamp("Search aftermath tungsten", (303,147,219),102,640,(.99,.71,.47),True)
    s.lamp("Window reflecting blue night",(-80,-353,154),56,615,(.50,.67,1))
    s.lamp("Light reflected from the hallway",(-335,-170,154),29,433,(.79,.82,1))
    s.lamp("Low bounce on the bed",(-17,308,149),24,409,(.79,.67,.49))


def alley(s, portrait):
    s.rain()
    route=[(-326,0,0),(1020,0,0),(1020,822,0),(2190,822,0),(2190,1620,0),(3450,1620,0)]
    s.box("Whole wet alley foundation",(1535,807,-52),(4390,3160,72),"pavement")
    for a,b in zip(route,route[1:]):
        x,y=(a[0]+b[0])/2,(a[1]+b[1])/2
        sx=abs(a[0]-b[0])+420
        sy=abs(a[1]-b[1])+420
        s.box("Wet pavement through the alley",(x,y,-8),(sx,sy,16),"asphalt")
    buildings=(
        (-505,-305,1260,-211),( -510,210,810,764),
        (1232,-274,1980,611),(1230,1033,1969,1510),
        (2434,578,3790,1406),(2442,1836,3833,2240),
        (1430,1890,1990,2310),(570,1055,2070,1220),
    )
    for index,(x0,y0,x1,y1) in enumerate(buildings):
        h=550+93*(index%3)
        s.box("Back walls of walk-up apartments",((x0+x1)/2,(y0+y1)/2,h/2),(x1-x0,y1-y0,h),"brick")
        edge=y1+2 if index in (0,2,4) else y0-2
        n=max(1,round((x1-x0)/174))
        for j in range(n):
            for z in (175,392):
                x=x0+(j+.5)*(x1-x0)/n
                s.box("Rear alley window",(x,edge,z),(91,6,104),"glass",collision=False)
                s.box("Stone window sill",(x,edge,z-55),(104,18,8),"pavement",collision=False)
    s.box("Rear exit gate",(3510,1620,137),(18,417,279),"charcoal")
    for y in range(1427,1815,19):
        s.box("Gate bars",(3500,y,163),(6,6,218),"steel",collision=False)
    s.box("Entry retaining wall",(-548,0,178),(18,425,362),"brick")
    s.entry((-365,0,104))
    s.photo((-222,-136,166),(1045,0,137),75)
    s.person("Aegis watcher on the run","Agent",(268,0,0),0,"patrol","charcoal",detail="agent")
    path=s.director.get_editor_property("pursuit_route")
    path.clear_spline_points(False)
    for index, point in enumerate(route):
        path.add_spline_point(V(*point),ue.SplineCoordinateSpace.WORLD,False)
        path.set_spline_point_type(index,ue.SplinePointType.LINEAR,False)
    path.update_spline()
    hide_bundle(badge(s,"Badge dropped by the watcher",(3156,1545,2),"ChaseBadge"))
    s.use("Pick up the badge dropped in the chase","CHASE_BADGE","Подобрать значок Aegis",(3156,1545,11),(20,23,12))
    for x,y in ((190,95),(991,631),(1550,839),(2208,1377),(3020,1732)):
        s.mesh("Night alley lantern",(x,y,320),(28,33,14),"light")
        s.lamp("Cool rain light",(x,y,294),80,740,(.45,.61,1) if x%2 else (1,.73,.48),x in (190,2208))
    for x,y in ((571,-172),(1175,500),(1730,660),(2017,1405),(2820,1439)):
        s.mesh("Back-alley metal trash can",(x,y,39),(54,54,78),"steel",True,shape="Cylinder")
        s.mesh("Trash can lid",(x,y,80),(59,59,8),"charcoal",shape="Cylinder")


BUILDERS={
    "Apartment":apartment, "Street":neptune, "Grocery":grocery, "Bar":bar,
    "Precinct":precinct, "Entrance":entrance, "Fedor":fedor, "Alley":alley,
}
