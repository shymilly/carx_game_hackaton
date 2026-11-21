"""Factory finishes, occupied street lots and the industrial rail branch."""
from math import cos, sin, pi
from random import Random

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, LIB, P, V, color, connect, constant, node, output, save
from CityLifeEnvironment import CityLayout, STREET_SHIFT
from IndustrialRail import industrial_branch
from StreetMaterials import custom_input

FACTORY_SCALE=1.45
FACTORY_PIVOT=(5180,-1425,-55)
DETAIL_TAG=ue.Name("BrightonBlockDetails")


def expression(mat, inputs, code, kind):
    value=node(mat,ue.MaterialExpressionCustom,inputs=[custom_input(name) for name in inputs],
               code=code,output_type=kind)
    for name,source in inputs.items():
        connect(source,value,name)
    return value


def factory_finishes():
    root="/Game/Prologue/Street/RefinedFactory"
    textures="/Game/Prologue/Street/Textures/T_"
    palette={
        "brick":("brick",(1.10,.91,.79),132,.83,0), "ochre":("ochre_brick",(1.04,1.02,.92),132,.85,0),
        "soot":("brick",(.55,.52,.50),132,.90,0), "concrete":("concrete",(.89,.91,.93),320,.84,0),
        "steel":(None,(.21,.25,.25),240,.48,.74), "rust":(None,(.31,.112,.054),150,.82,.26),
        "glass":(None,(.095,.16,.18),160,.30,.12), "glass_warm":(None,(.36,.30,.20),160,.33,.10),
        "black":(None,(.036,.039,.037),200,.87,0),
    }
    result={}
    for name,(stone,tint,span,rough,metal) in palette.items():
        mat=make_material(root,"Factory_"+name,tint,rough)
        LIB.delete_all_material_expressions(mat)
        mat.set_editor_properties(dict(shading_model=ue.MaterialShadingModel.MSM_DEFAULT_LIT,
            used_with_instanced_static_meshes=True))
        world=node(mat,ue.MaterialExpressionWorldPosition)
        if stone:
            uv=expression(mat,{"W":world},f"""
                float3 n=abs(cross(ddx(W.xyz),ddy(W.xyz)));
                float2 p=n.z>max(n.x,n.y) ? W.xy : float2(n.x>n.y ? W.y : W.x,-W.z);
                return p/{float(span)};""",ue.CustomMaterialOutputType.CMOT_FLOAT2)
            sample=node(mat,ue.MaterialExpressionTextureSample,texture=ue.load_asset(textures+stone+"_Color"))
            normal=node(mat,ue.MaterialExpressionTextureSample,texture=ue.load_asset(textures+stone+"_Normal"),
                        sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_NORMAL)
            connect(uv,sample)
            connect(uv,normal)
            output(normal,mat,P.MP_NORMAL,"RGB")
            base=node(mat,ue.MaterialExpressionMultiply)
            connect(sample,base,"A","RGB")
            connect(color(mat,tint),base,"B")
        else:
            base=color(mat,tint)
        weathered=expression(mat,{"C":base,"W":world},"""
            float stain=sin(W.x*.0043+W.y*.0083)*sin(W.z*.0025+W.y*.0009);
            return C.rgb*(.94+.06*stain);""",ue.CustomMaterialOutputType.CMOT_FLOAT3)
        output(weathered,mat,P.MP_BASE_COLOR)
        output(constant(mat,rough),mat,P.MP_ROUGHNESS)
        output(constant(mat,metal),mat,P.MP_METALLIC)
        if name=="glass_warm":
            glow=node(mat,ue.MaterialExpressionCollectionParameter,parameter_name=ue.Name("StreetGlow"),
                      collection=ue.load_asset("/Game/Prologue/Street/Materials/MPC_StreetLighting"))
            lit=node(mat,ue.MaterialExpressionMultiply)
            connect(glow,lit,"A")
            connect(color(mat,(1.8,1.02,.46)),lit,"B")
            output(lit,mat,P.MP_EMISSIVE_COLOR)
        LIB.recompile_material(mat)
        save(mat)
        result[name]=mat
    return result


def enlarge_factory(placed,shift):
    pivot=V(*FACTORY_PIVOT)+V(*shift)
    stamp=ue.Name("BrightonEnlargedFactory")
    for actor in placed:
        label=actor.get_actor_label().removeprefix("Third-floor view ")
        if actor.actor_has_tag(stamp): continue
        if label.startswith("Factory depth "):
            comp=actor.get_editor_property("instances")
            for index in range(comp.get_instance_count()):
                tr=comp.get_instance_transform(index,True)
                tr.translation=pivot+(tr.translation-pivot)*FACTORY_SCALE
                tr.scale3d=tr.scale3d*FACTORY_SCALE
                comp.update_instance_transform(index,tr,True,index+1==comp.get_instance_count(),True)
            comp.set_cull_distances(29000,42000)
        elif label.startswith("Animated factory stack plume"):
            actor.set_actor_location(pivot+(actor.get_actor_location()-pivot)*FACTORY_SCALE,False,True)
            actor.set_actor_scale3d(actor.get_actor_scale3d()*FACTORY_SCALE)
        else:
            continue
        actor.tags=[*actor.tags,stamp]


class BlockLayout(CityLayout):
    def actor(self,cls,label,position=(0,0,0),rotation=None):
        actor=super().actor(cls,label,position,rotation)
        actor.tags=[*actor.tags,DETAIL_TAG]
        actor.set_folder_path(ue.Name("Brighton/Block details"))
        return actor


def neighborhood_infill(layout):
    rng=Random(4094)
    iron=ue.load_asset("/Game/Prologue/CityLife/Materials/M_GalvanizedBoothTrim")
    enamel=ue.load_asset("/Game/Prologue/CityLife/Materials/M_BoothOlive")
    timber=ue.load_asset("/Game/Prologue/Street/Materials/M_wood")
    concrete=ue.load_asset("/Game/StreetRefinement/Materials/M_WeatheredConcrete")
    paint=ue.load_asset("/Game/Prologue/Brighton/Materials/M_LanePaint")
    curb_z=-12
    for x,y,direction in ((-4750,-1940,1),(3152,3490,-1),(-3710,-570,-1)):
        layout.box("Bus shelter slab",(x,y,curb_z+3),(209,88,6),concrete)
        for dx in (-90,90):
            for dy in (-32,32):
                layout.box("Bus shelter frame",(x+dx,y+dy,curb_z+110),(5,5,212),iron)
        layout.box("Shelter canopy",(x,y,curb_z+220),(226,106,12),enamel)
        layout.box("Shelter route board",(x+76,y-direction*29,curb_z+134),(28,5,53),enamel)
        for dx in (-48,48):
            layout.box("Bench feet",(x+dx,y,curb_z+24),(6,32,40),iron)
        for slat in (-1,0,1):
            layout.box("Shelter bench slats",(x,y+slat*10,curb_z+47),(149,9,5),timber)
    for i in range(9):
        x=-6270+i*565
        for y,side in ((-1805,-1),(-723,1)):
            if -1550<x<-700 and side>0:continue
            layout.cylinder_part("Parking meter posts",(x,y,42),(5,5,108),iron)
            layout.box("Meter housings",(x,y,106),(20,12,24),enamel)
            layout.box("Meter dials",(x,y+side*6.4,109),(12,1.3,8),concrete)
    for side in (-1,1):
        for index in range(6):
            y=side*(4620+index*1030)
            if abs(y+7650)<750:continue
            for x in (265,5010):
                key=("MarketHouse","WalkupBay","WalkupBrick")[(index+(x>1000))%3]
                layout.instance("Side street rear blocks",key,(x+rng.uniform(-75,75),y,-38),
                                (.60,.61,rng.uniform(.70,1.03)),90 if x<1000 else -90,cull=34000)
            layout.instance("Backstreet trees","BirchGold",(1350,y+146,-30),(.78,.78,.78),rng.randrange(360),cull=23000)
    for x,y in ((3930,4250),(3990,-4760)):
        layout.box("Service yard paving",(x,y,-28),(1060,830,20),concrete,cull=30000)
        for dx in (-335,-143,49,241):
            layout.box("Loading yard parking bays",(x+dx,y,-17.5),(5,426,1),paint,cull=21000)
        for dx,dy in ((-376,-260),(-250,-260),(310,211)):
            layout.instance("Delivery yard dumpsters","Dumpster",(x+dx,y+dy,-17),yaw=90,cull=23000)
        for row in range(2):
            for col in range(3):
                px=x+281+col*58
                py=y-251+row*59
                for layer in range(2 if col==0 else 1):
                    pz=-17+layer*51+25
                    layout.box("Wooden shipping cases",(px,py,pz),(54,55,50),timber,cull=23000)
                    for edge in (-19,19):
                        layout.box("Case straps",(px+edge,py,pz+1),(3,56,51),iron,cull=19000)
    for x,y in ((-686,1670),(1070,1030),(-733,2340)):
        for i in range(5):
            layout.instance("Park planting beds","Bush",(x+i*37,y+rng.uniform(-15,15),-7.6),
                            (.46,.56,.48),rng.randrange(360),cull=11000)


def build_street_details(interior):
    placed=ACTORS.get_all_level_actors()
    old=[actor for actor in placed if actor.actor_has_tag(DETAIL_TAG)]
    shift=STREET_SHIFT if interior else (0,0,0)
    enlarge_factory(placed,shift)
    if old:
        assert ACTORS.destroy_actors(old)
        placed=ACTORS.get_all_level_actors()
    keys=("RailStraight","FreightEngine","FreightGondola","FreightBoxcar","MarketHouse","WalkupBay","WalkupBrick","BirchGold","Bush","Dumpster")
    mesh={key:ue.load_asset("/Game/Prologue/CityLife/Meshes/SM_"+key) for key in keys}
    assert all(mesh.values())
    layout=BlockLayout(mesh,shift)
    industrial_branch(layout)
    neighborhood_infill(layout)
    if not interior:
        solids={"Bus shelter frame","Shelter canopy","Bench feet","Shelter bench slats",
                "Parking meter posts","Meter housings","Shelter route board"}
        for (label,*_),component in layout.batches.items():
            if label in solids:
                component.set_collision_profile_name("BlockAll")
                component.set_collision_enabled(ue.CollisionEnabled.QUERY_ONLY)
                component.set_editor_property("generate_overlap_events",False)
        flow,=[a for a in placed if isinstance(a,ue.StreetTrafficFlow)]
        routes={"northbound":[(2600,-6460),(2600,6450)],"southbound":[(2180,6450),(2180,-6460)],
                "westbound":[(2600,-6460)]+[(1670+930*cos(a*pi/36),-2405+930*sin(a*pi/36)) for a in range(19)]+[(-8640,-1475)]}
        for field,points in routes.items():
            spline=flow.get_editor_property(field)
            spline.clear_spline_points(False)
            for i,(x,y) in enumerate(points):
                spline.add_spline_point(V(x,y,-28),ue.SplineCoordinateSpace.WORLD,False)
                spline.set_spline_point_type(i,ue.SplinePointType.LINEAR,False)
            spline.update_spline()
        flow.set_editor_property("use_cross_street_routes",True)
        flow.set_actor_label("Brighton traffic junction")
