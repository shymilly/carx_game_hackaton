"""Active-map visual and sidewalk correction; original hand-built Cyrillic vector letters."""
from pathlib import Path
from math import sin,cos,sqrt,tau
from random import Random
import json
import unreal as ue
from NeptuneSignFont import write_obj
from ApartmentScene import make_material
from ApartmentFinishes import mapped_coordinates
from StreetArtwork import png

ROOT='/Game/StreetRefinement'
FOLDER='Street/03 Shops and cross street'
TAG='StreetVisuals1994_v1'
V=ue.Vector
R=lambda yaw=0:ue.Rotator(pitch=0,yaw=yaw,roll=0)
ASSETS=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
ACTORS=ue.get_editor_subsystem(ue.EditorActorSubsystem)
LIB=ue.MaterialEditingLibrary
P=ue.MaterialProperty
PROJECT=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
STAGE=PROJECT/'Resources/StreetRefinement'
LEFT=['Grocery walk-up','Pharmacy walk-up','Corner row house','South block brownstones','South block walk-up','South fork left residence']
RIGHT=['Corner apartments beside Dima','Opposite press end wall','South extension brick walk-up','South extension brownstone','Fork perspective townhouses']
FAR=['Weathered tenement west','Weathered tenement east','Tall apartment opposite Neptune','Cross-street apartments','Bar Lighthouse shell','Far east cross-street block','Eastbound perspective row']
NEAR=['Cross-street depth row']
CORRIDORS=[(-9200,1635,-2080,-1740),(-9200,1635,-770,-451),(1635,1950,-8000,-1740),(1635,1950,-770,8000),(2910,3250,-8000,8000)]
def save(a):
    assert ASSETS.save_loaded_asset(a,False),a.get_path_name()
def bounds(a):
    p,e=a.get_actor_bounds(False)
    return [p.x-e.x,p.x+e.x,p.y-e.y,p.y+e.y,p.z-e.z,p.z+e.z]
def tag(a):a.tags=list(a.tags)+([] if a.actor_has_tag(TAG) else [ue.Name(TAG)])
def move(a,d):a.set_actor_location(a.get_actor_location()+d,False,True)
def overlap(b,r):return min(b[1],r[1])-max(b[0],r[0])>.8 and min(b[3],r[3])-max(b[2],r[2])>.8
def group_for(p,groups):
    options=[g for g in groups if abs(p.x*g['t'][0]+p.y*g['t'][1]-g['c'])<=g['w']/2+58 and g['front']-g['d']-65<=p.x*g['n'][0]+p.y*g['n'][1]<=g['front']+185 and -50<=p.z<=g['h']+245]
    return min(options,key=lambda g:abs(p.x*g['t'][0]+p.y*g['t'][1]-g['c'])/g['w']) if options else None
def align_facades(placed):
    if any(a.actor_has_tag(TAG) for a in placed):return
    groups=[]
    for a in placed:
        if str(a.get_folder_path())!=FOLDER:continue
        label=a.get_actor_label();b=bounds(a)
        if label in LEFT:n,t,front,d,w,c,target=(0,1),(1,0),b[3],b[3]-b[2],b[1]-b[0],(b[0]+b[1])/2,-2220
        elif label in RIGHT:n,t,front,d,w,c,target=(0,-1),(1,0),-b[2],b[3]-b[2],b[1]-b[0],(b[0]+b[1])/2,410
        elif label in FAR:n,t,front,d,w,c,target=(-1,0),(0,1),-b[0],b[1]-b[0],b[3]-b[2],(b[2]+b[3])/2,-3390
        elif label.startswith(NEAR[0]):n,t,front,d,w,c,target=(1,0),(0,1),b[1],b[1]-b[0],b[3]-b[2],(b[2]+b[3])/2,1500
        else:continue
        groups.append(dict(a=a,n=n,t=t,front=front,d=d,w=w,c=c,h=b[5],delta=V(n[0]*(target-front),n[1]*(target-front),0)))
    for a in placed:
        if str(a.get_folder_path())!=FOLDER:continue
        c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
        if c:
            for i in range(c.get_instance_count()):
                tr=c.get_instance_transform(i,True);g=group_for(tr.translation,groups)
                if g:tr.translation=tr.translation+g['delta'];c.update_instance_transform(i,tr,True,True,True)
        else:
            g=group_for(a.get_actor_location(),groups)
            if g:move(a,g['delta'])
    bar=next((g for g in groups if g['a'].get_actor_label()=='Bar Lighthouse shell'),None)
    for a in placed:
        if a.get_actor_label().startswith('Bar Lighthouse entrance') and bar:move(a,bar['delta'])
    # Correct the park's perimeter massing without pushing it across the handball court.
    north=(1635,2300,350,2690,1700,1485,130/545)
    east=(440,1790,2520,3335,498.5,498.5,(1620-498.5)/1231)
    for a in placed:
        f=str(a.get_folder_path());label=a.get_actor_label()
        if f=='Street/05 Enclosed courtyard':
            c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
            if c:
                for i in range(c.get_instance_count()):
                    tr=c.get_instance_transform(i,True);p=tr.translation
                    zone=next((z for z in (north,east) if z[0]<p.x<z[1] and z[2]<p.y<z[3] and p.z>0),None)
                    if zone:
                        p.x=zone[5]+(p.x-zone[4])*zone[6];tr.translation=p
                        q=tr.rotation;scale=tr.scale3d
                        if abs(1-2*(q.y*q.y+q.z*q.z))>.7:scale.x*=zone[6]
                        else:scale.y*=zone[6]
                        tr.scale3d=scale;c.update_instance_transform(i,tr,True,True,True)
                    elif p.x>1420 and 418<p.y<2500:tr.translation=p-V(100,0,0);c.update_instance_transform(i,tr,True,True,True)
                    elif -1240<p.x<-920 and -455<p.y<-420 and p.z>100:tr.translation=p+V(0,16,0);c.update_instance_transform(i,tr,True,True,True)
            elif label=='Park north perimeter terraces':
                p=a.get_actor_location();p.x=1485+(p.x-1700)*north[6];a.set_actor_location(p,False,True)
                sc=a.get_actor_scale3d();sc.y*=north[6];a.set_actor_scale3d(sc)
            elif label.startswith('Park east perimeter') and bounds(a)[1]>1630:
                p=a.get_actor_location();p.x=498.5+(p.x-498.5)*east[6];a.set_actor_location(p,False,True)
                sc=a.get_actor_scale3d();sc.x*=east[6];a.set_actor_scale3d(sc)
            elif label=='Park entrance cheek along Dima house':move(a,V(0,14,0))
            elif label=='Park frontage wall below the facade':move(a,V(0,22,0))
            elif label=='Neptune Playground entrance plate':move(a,V(0,16,0))
        elif f=='Street/06 Precinct':move(a,V(-310,0,0))
        elif f=='Street/04 Flea market':move(a,V(40,0,0))
        elif f=='Street/02 Apartment facade':
            if label=='Building entrance hood':
                sc=a.get_actor_scale3d();sc.y=.14;a.set_actor_scale3d(sc)
                p=a.get_actor_location();p.y=-432;a.set_actor_location(p,False,True)
            else:move(a,V(0,48,0))
        elif label=='Door step':
            p=a.get_actor_location();p.y=-441.5;a.set_actor_location(p,False,True)
            sc=a.get_actor_scale3d();sc.y=.03;a.set_actor_scale3d(sc)
        elif label=='Precinct street door':move(a,V(-310,0,0))
        elif a.actor_has_tag('FromPrecinct'):
            p=a.get_actor_location();p.x=1730;a.set_actor_location(p,False,True);a.set_actor_rotation(R(),False)
        if f in (FOLDER,'Street/05 Enclosed courtyard','Street/06 Precinct','Street/04 Flea market','Street/02 Apartment facade') or label in ('Door step','Precinct street door') or a.actor_has_tag('FromPrecinct'):tag(a)

WALLS=[('AgedRedBrick',(143,86,65),'brick',108),('SootBrownBrick',(109,89,76),'brick',108),('PaleLimeBrick',(171,150,115),'brick',108),('GreyPaintedPlaster',(153,158,149),'plaster',160),('FadedOchreRender',(178,148,108),'plaster',160),('WeatheredConcrete',(140,143,140),'concrete',200)]
def wall_material(name,color,kind,span):
    path=ROOT+'/Materials/M_'+name
    if ASSETS.does_asset_exist(path):return ue.load_asset(path)
    size=256;rng=Random(name);pixels=bytearray();heights=[]
    for y in range(size):
        row=[]
        for x in range(size):
            n=rng.uniform(-5,5)+sin(x*tau/size*3+y*tau/size)*9+cos(y*tau/size*4-x*tau/size)*4
            if kind=='brick':
                mortar=y%16<2 or (x+(y//16%2)*32)%64<2
                c=(112,109,98) if mortar else color
                n+=((y//16*37+(x+(y//16%2)*32)//64*19)%23)-11
                h=-.7 if mortar else n*.02
            else:
                joint=kind=='concrete' and (x%128<2 or y%128<2)
                c=color;n-=joint*22;h=n*.014-joint*.5
            pixels.extend(max(0,min(255,round(v+n))) for v in c);row.append(h)
        heights.append(row)
    normal=bytearray()
    for y in range(size):
        for x in range(size):
            dx=(heights[y][(x-1)%size]-heights[y][(x+1)%size])*.4;dy=(heights[(y-1)%size][x]-heights[(y+1)%size][x])*.4;l=sqrt(1+dx*dx+dy*dy)
            normal.extend(round(127.5*(1+v/l)) for v in (dx,dy,1))
    textures=[]
    for suffix,data in (('Color',pixels),('Normal',normal)):
        asset='T_'+name+'_'+suffix;file=STAGE/(asset+'.png');png(file,size,size,data)
        task=ue.AssetImportTask();task.set_editor_properties(dict(filename=str(file),destination_path=ROOT+'/Textures',automated=True,save=False))
        ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]);tex=ue.load_asset(ROOT+'/Textures/'+asset);assert tex
        tex.set_editor_property('max_texture_size',256)
        if suffix=='Normal':tex.set_editor_properties(dict(compression_settings=ue.TextureCompressionSettings.TC_NORMALMAP,srgb=False))
        save(tex);textures.append(tex)
    m=make_material(ROOT,name,(.3,.3,.3),.86)
    uv=mapped_coordinates(m,LIB,True);uv.set_editor_property('const_b',1/span)
    for channel,tex,sampler in ((P.MP_BASE_COLOR,textures[0],ue.MaterialSamplerType.SAMPLERTYPE_COLOR),(P.MP_NORMAL,textures[1],ue.MaterialSamplerType.SAMPLERTYPE_NORMAL)):
        node=LIB.create_material_expression(m,ue.MaterialExpressionTextureSample,0,0);node.set_editor_properties(dict(texture=tex,sampler_type=sampler))
        LIB.connect_material_expressions(uv,'',node,'Coordinates');LIB.connect_material_property(node,'RGB',channel)
    LIB.recompile_material(m);save(m);return m

SIGNS={'SM_NeighborhoodGrocery':('ПРОДУКТЫ',42,700,0),'SM_NeighborhoodPharmacy':('АПТЕКА',42,680,0),'SM_NeighborhoodBar':('БАР «МАЯК»',38,680,90),'SM_NeighborhoodFlea':('БАРАХОЛКА',38,435,90),'SM_NeighborhoodPrecinct':('ПОЛИЦИЯ / УЧАСТОК 60',28,575,-90),'SM_NeighborhoodPark':('ДЕТСКАЯ ПЛОЩАДКА',20,246,180),'SM_SignStreet':('УЛ. НЕПТУН',11,102,180)}
def sign_mesh(name,text,height,width):
    asset=ROOT+'/Signs/SM_N94_'+name
    if ASSETS.does_asset_exist(asset):return ue.load_asset(asset)
    file=STAGE/('SM_N94_'+name+'.obj');metrics=write_obj(file,text,height,width)
    options=ue.FbxImportUI();options.set_editor_properties(dict(import_materials=False,import_textures=False,import_as_skeletal=False))
    task=ue.AssetImportTask();task.set_editor_properties(dict(filename=str(file),destination_path=ROOT+'/Signs',automated=True,save=False,options=options))
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]);mesh=ue.load_asset(asset);assert mesh,asset
    mesh.set_material(0,make_material(ROOT,'SignIvoryEnamel',(.79,.74,.59),.66));save(mesh)
    ue.log('STREET_SIGN_MESH '+text+' '+str(metrics));return mesh
def typography(placed):
    enamel=make_material(ROOT,'Neptune94Ivory',(.79,.74,.59),.66)
    enamel.set_editor_property('shading_model',ue.MaterialShadingModel.MSM_UNLIT)
    if not LIB.get_material_property_input_node(enamel,P.MP_EMISSIVE_COLOR):
        emission=LIB.create_material_expression(enamel,ue.MaterialExpressionConstant3Vector,50,280)
        emission.set_editor_property('constant',ue.LinearColor(.42,.36,.25,1))
        LIB.connect_material_property(emission,'',P.MP_EMISSIVE_COLOR);LIB.recompile_material(enamel);save(enamel)
    for a in placed:
        c=a.get_component_by_class(ue.StaticMeshComponent)
        if not c or not c.static_mesh:continue
        key=next((k for k in SIGNS if c.static_mesh.get_name() in (k,'SM_N94_'+k)),None)
        if not key:continue
        text,h,w,yaw=SIGNS[key];c.set_static_mesh(sign_mesh(key,text,h,w));c.set_collision_profile_name(ue.Name('NoCollision'))
        c.set_material(0,enamel)
        if key=='SM_NeighborhoodBar':
            pos=a.get_actor_location();pos.x=3355;pos.z=365;a.set_actor_location(pos,False,True)
        c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False));c.set_cull_distance(14000 if w>400 else 7600)
        a.set_actor_scale3d(V(1,1,1));a.set_actor_rotation(R(yaw),False)
        a.tags=[t for t in a.tags if not str(t).startswith('SignText:')]+[ue.Name('SignText:'+text)]
    backing=next((a for a in placed if a.get_actor_label()=='Neptune94 bar enamel fascia'),None)
    if not backing:
        backing=ACTORS.spawn_actor_from_class(ue.StaticMeshActor,V(3370,1290,365),R())
        backing.set_actor_label('Neptune94 bar enamel fascia');backing.set_folder_path(ue.Name(FOLDER))
    backing.set_actor_scale3d(V(.12,4.8,.86))
    c=backing.get_component_by_class(ue.StaticMeshComponent);c.set_static_mesh(ue.load_asset('/Engine/BasicShapes/Cube'))
    c.set_material(0,make_material(ROOT,'PressBottleGreenEnamel',(.037,.115,.10),.58));c.set_collision_profile_name(ue.Name('NoCollision'))
    c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False))
    kiosk=next(a for a in placed if a.get_actor_label()=='Газетный киоск КНИГИ / ПРЕССА');p=kiosk.get_actor_location()
    for label,mesh,offset,scale,mat in [('Neptune94 press enamel fascia',ue.load_asset('/Engine/BasicShapes/Cube'),-95,V(2.4,.025,.34),make_material(ROOT,'PressBottleGreenEnamel',(.037,.115,.10),.58)),('Neptune94 press lettering',sign_mesh('Press','КНИГИ / ПРЕССА',18,222),-97,V(1,1,1),None)]:
        a=next((a for a in placed if a.get_actor_label()==label),None)
        if not a:a=ACTORS.spawn_actor_from_class(ue.StaticMeshActor,V(p.x,p.y+offset,220),R(180));a.set_actor_label(label);a.set_folder_path(ue.Name('Street/09 Sidewalk props'))
        a.set_actor_scale3d(scale);c=a.get_component_by_class(ue.StaticMeshComponent);c.set_static_mesh(mesh);c.set_collision_profile_name(ue.Name('NoCollision'))
        c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False));c.set_cull_distance(7600)
        if mat:c.set_material(0,mat)
        else:c.set_material(0,enamel);a.tags=[ue.Name('SignText:КНИГИ / ПРЕССА')]
def safe_traffic_turn():
    flow=next(a for a in ACTORS.get_all_level_actors() if isinstance(a,ue.StreetTrafficFlow));spline=flow.get_editor_property('eastbound')
    route=[(-8640,-1010)]+[(1680+920*cos((-90+90*i/18)*tau/360),-90+920*sin((-90+90*i/18)*tau/360)) for i in range(19)]+[(2600,6450)]
    spline.clear_spline_points(False)
    for i,(x,y) in enumerate(route):spline.add_spline_point(V(x,y,-28),ue.SplineCoordinateSpace.WORLD,False);spline.set_spline_point_type(i,ue.SplinePointType.LINEAR,False)
    spline.update_spline()

def finish_corner():
    placed=ACTORS.get_all_level_actors()
    body=next(a for a in placed if a.get_actor_label()=='Corner apartments beside Dima')
    if bounds(body)[1]>1610:
        factor=(1600-871)/850
        for a in placed:
            if str(a.get_folder_path())!=FOLDER:continue
            c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
            if c:
                for i in range(c.get_instance_count()):
                    tr=c.get_instance_transform(i,True);p=tr.translation
                    if 820<p.x<1800 and -480<p.y<520:
                        p.x=871+(p.x-871)*factor;tr.translation=p
                        q=tr.rotation;sc=tr.scale3d
                        if abs(1-2*(q.y*q.y+q.z*q.z))>.7:sc.x*=factor
                        else:sc.y*=factor
                        tr.scale3d=sc;c.update_instance_transform(i,tr,True,True,True)
            elif a==body:
                p=a.get_actor_location();p.x=871+(p.x-871)*factor;a.set_actor_location(p,False,True)
                sc=a.get_actor_scale3d();sc.x*=factor;a.set_actor_scale3d(sc)
    for a in placed:
        if str(a.get_folder_path())!='Street/02 Apartment facade':continue
        c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
        if c and c.get_material(0) and 'lamp_glass' in c.get_material(0).get_name():
            for i in range(c.get_instance_count()):
                tr=c.get_instance_transform(i,True);p=tr.translation
                if abs(p.x+194)<30 and p.y<-440 and 214<p.z<230:
                    tr.translation=p+V(0,14,0);c.update_instance_transform(i,tr,True,True,True)
    for a in placed:
        if str(a.get_folder_path())!='Street/05 Enclosed courtyard':continue
        if a.get_actor_label()=='Passage wall behind press kiosk' and bounds(a)[2]<-443:
            b=bounds(a);p=a.get_actor_location();p.y=(b[3]-443)/2;a.set_actor_location(p,False,True)
            sc=a.get_actor_scale3d();sc.y=(b[3]+443)/100;a.set_actor_scale3d(sc)
        c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
        if not c or not c.get_material(0) or 'stone' not in c.get_material(0).get_name():continue
        for i in range(c.get_instance_count()):
            tr=c.get_instance_transform(i,True);p=tr.translation;sc=tr.scale3d;dirty=False
            if -1390<p.x<-1320 and 290<p.z<306 and p.y-sc.y*50<-443:
                end=p.y+sc.y*50;p.y=(end-443)/2;sc.y=(end+443)/100;dirty=True
            if 2540<p.y<2605 and 970<p.z<1005 and sc.x>10 and p.x+sc.x*50>1627:
                p.x-=p.x+sc.x*50-1625;dirty=True
            if dirty:tr.translation=p;tr.scale3d=sc;c.update_instance_transform(i,tr,True,True,True)
def audit():
    violations=[];signs=[];bodies=[]
    for a in ACTORS.get_all_level_actors():
        f=str(a.get_folder_path());label=a.get_actor_label()
        if f in (FOLDER,'Street/06 Precinct','Street/02 Apartment facade','Street/05 Enclosed courtyard','Street/04 Flea market'):
            c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
            if c and c.static_mesh:
                bb=c.static_mesh.get_bounding_box()
                for i in range(c.get_instance_count()):
                    tr=c.get_instance_transform(i,True);pts=[ue.MathLibrary.transform_location(tr,V(x,y,z)) for x in (bb.min.x,bb.max.x) for y in (bb.min.y,bb.max.y) for z in (bb.min.z,bb.max.z)]
                    b=[min(p.x for p in pts),max(p.x for p in pts),min(p.y for p in pts),max(p.y for p in pts),min(p.z for p in pts),max(p.z for p in pts)]
                    if b[5]>5 and any(overlap(b,r) for r in CORRIDORS):violations.append((label,i,[round(q,1) for q in b]))
            elif a.get_component_by_class(ue.StaticMeshComponent):
                b=bounds(a)
                if b[5]>5 and any(overlap(b,r) for r in CORRIDORS):violations.append((label,[round(q,1) for q in b]))
                if label in LEFT+RIGHT+FAR or label.startswith(NEAR[0]) or label.startswith('Park '):bodies.append(label)
        texts=[str(t)[9:] for t in a.tags if str(t).startswith('SignText:')]
        if texts:
            scale=a.get_actor_scale3d();assert min(scale.x,scale.y,scale.z)>0
            signs.append(dict(label=label,text=texts[0],yaw=a.get_actor_rotation().yaw,positive_scale=True))
    return dict(sidewalk_violations=violations,building_count=len(bodies),signs=signs)
def apply():
    STAGE.mkdir(parents=True,exist_ok=True);placed=ACTORS.get_all_level_actors()
    align_facades(placed);finish_corner();safe_traffic_turn()
    mats=[wall_material(*entry) for entry in WALLS]
    buildings=sorted([a for a in placed if a.get_actor_label() in LEFT+RIGHT+FAR or a.get_actor_label().startswith(tuple(NEAR+['Park north perimeter','Park east perimeter','Park south perimeter']))],key=lambda a:a.get_actor_label())
    for i,a in enumerate(buildings):a.get_component_by_class(ue.StaticMeshComponent).set_material(0,mats[i%len(mats)])
    typography(ACTORS.get_all_level_actors());report=audit()
    (STAGE/'VisualAudit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    ue.log('STREET_VISUAL_AUDIT buildings='+str(report['building_count'])+' signs='+str(len(report['signs']))+' violations='+str(len(report['sidewalk_violations'])))
    return report
