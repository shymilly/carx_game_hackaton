"""Author proportional architecture and dress the street from the imported library."""
from pathlib import Path
from random import Random
import hashlib,json,math,sys
import unreal as ue

ROOT=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(ROOT/'Tools'))
AS=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
ACT=ue.get_editor_subsystem(ue.EditorActorSubsystem)
LV=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
LIB=ue.MaterialEditingLibrary
TOOLS=ue.AssetToolsHelpers.get_asset_tools()
V=ue.Vector
TAG=ue.Name('StreetArtPass_v1')
BASE='/Game/StreetArtPass'
IND='/Game/ImportedAssets/Industrial/ExteriorV2/Industrial_exterior_v2/Industrial_exterior_v2/StaticMeshes/'
TREE='/Game/ImportedAssets/Nature/Trees/trees/trees/StaticMeshes/'
ART=ROOT/'Resources/StreetArtPass';ART.mkdir(parents=True,exist_ok=True)
assert LV.load_level('/Game/Locations/L_NeptuneStreet')

def save(obj):assert AS.save_loaded_asset(obj,False),obj.get_path_name()
def n(mat,cls,**values):
 obj=LIB.create_material_expression(mat,cls,0,0)
 if values:obj.set_editor_properties(values)
 return obj
def connect(a,b,pin='',out=''):assert LIB.connect_material_expressions(a,out,b,pin),(a.get_class().get_name(),out,b.get_class().get_name(),pin)
def output(a,mat,pin,out=''):assert LIB.connect_material_property(a,out,pin)
def const(mat,value):return n(mat,ue.MaterialExpressionConstant,r=value)
def rgb(mat,value):return n(mat,ue.MaterialExpressionConstant3Vector,constant=ue.LinearColor(*value,1))
def custom(mat,code,inputs,kind):
 args=[]
 for name in inputs:
  entry=ue.CustomInput();entry.set_editor_property('input_name',ue.Name(name));args.append(entry)
 obj=n(mat,ue.MaterialExpressionCustom,inputs=args,code=code,output_type=kind)
 for name,value in inputs.items():connect(value,obj,name)
 return obj
def material(name):
 path=BASE+'/Materials/'+name
 return ue.load_asset(path) if AS.does_asset_exist(path) else TOOLS.create_asset(name,BASE+'/Materials',ue.Material,ue.MaterialFactoryNew())

GEOMETRIC='float3 g=normalize(cross(ddx(W.xyz),ddy(W.xyz))+float3(1e-8,1e-8,1e-8)); if(dot(g,C)<0)g=-g; float3 a=abs(g); '
def world_surface(name,color_tex,normal_tex=None,rough_tex=None,span=(108,108),tint=(1,1,1),wet=False):
 mat=material(name)
 LIB.delete_all_material_expressions(mat)
 mat.set_editor_properties(dict(shading_model=ue.MaterialShadingModel.MSM_DEFAULT_LIT,
  tangent_space_normal=False,used_with_instanced_static_meshes=True))
 world=n(mat,ue.MaterialExpressionWorldPosition);camera=n(mat,ue.MaterialExpressionCameraVectorWS)
 uv=custom(mat,GEOMETRIC+f'float2 p=a.z>max(a.x,a.y)?float2(W.x*sign(g.z),W.y):(a.x>a.y?float2(-W.y*sign(g.x),-W.z):float2(W.x*sign(g.y),-W.z)); return p/float2({span[0]:.5f},{span[1]:.5f});',{'W':world,'C':camera},ue.CustomMaterialOutputType.CMOT_FLOAT2)
 color=n(mat,ue.MaterialExpressionTextureSample,texture=ue.load_asset(color_tex));assert color.texture,color_tex
 connect(uv,color,'UVs')
 shade=n(mat,ue.MaterialExpressionMultiply);connect(color,shade,'A','RGB');connect(rgb(mat,tint),shade,'B')
 rough=const(mat,.87)
 if rough_tex:
  tex=ue.load_asset(rough_tex);assert tex
  tex.set_editor_properties(dict(srgb=False,compression_settings=ue.TextureCompressionSettings.TC_MASKS));save(tex)
  rough=n(mat,ue.MaterialExpressionTextureSample,texture=tex,sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_MASKS);connect(uv,rough,'UVs')
 rough_pin='R' if rough_tex else ''
 if wet:
  collection=ue.load_asset('/Game/Prologue/Brighton/Materials/MPC_Weather')
  damp=n(mat,ue.MaterialExpressionCollectionParameter,collection=collection,parameter_name=ue.Name('Wetness'))
  darkness=n(mat,ue.MaterialExpressionLinearInterpolate,const_a=1,const_b=.67);connect(damp,darkness,'Alpha')
  dark=n(mat,ue.MaterialExpressionMultiply);connect(shade,dark,'A');connect(darkness,dark,'B');shade=dark
  puddle=custom(mat,'float2 p=W.xy/730.; float k=sin(p.x+.45*sin(p.y*1.6))*sin(p.y*.86+.34*cos(p.x)); return smoothstep(.16,.69,k);',{'W':world},ue.CustomMaterialOutputType.CMOT_FLOAT1)
  damp_mask=n(mat,ue.MaterialExpressionMultiply);connect(puddle,damp_mask,'A');connect(damp,damp_mask,'B')
  wet_rough=n(mat,ue.MaterialExpressionLinearInterpolate,const_b=.16);connect(rough,wet_rough,'A',rough_pin);connect(damp_mask,wet_rough,'Alpha');rough=wet_rough;rough_pin=''
 output(shade,mat,ue.MaterialProperty.MP_BASE_COLOR)
 output(rough,mat,ue.MaterialProperty.MP_ROUGHNESS,rough_pin)
 if normal_tex:
  normal=n(mat,ue.MaterialExpressionTextureSample,texture=ue.load_asset(normal_tex),sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_NORMAL);assert normal.texture
  connect(uv,normal,'UVs')
  bump=custom(mat,GEOMETRIC+'float3 t,b; if(a.z>max(a.x,a.y)){t=float3(sign(g.z),0,0);b=float3(0,1,0);}else if(a.x>a.y){t=float3(0,-sign(g.x),0);b=float3(0,0,-1);}else{t=float3(sign(g.y),0,0);b=float3(0,0,-1);} float2 q=N.xy*.46; return normalize(g*sqrt(saturate(1-dot(q,q)))+t*q.x+b*q.y);',{'W':world,'C':camera,'N':normal},ue.CustomMaterialOutputType.CMOT_FLOAT3)
  connect(normal,bump,'N','RGB');output(bump,mat,ue.MaterialProperty.MP_NORMAL)
 else:
  normal=custom(mat,GEOMETRIC+'return g;',{'W':world,'C':camera},ue.CustomMaterialOutputType.CMOT_FLOAT3)
  output(normal,mat,ue.MaterialProperty.MP_NORMAL)
 errors=LIB.recompile_material(mat);assert not errors,(name,errors);save(mat)
 return mat

def box_bounds(actor):
 p,e=actor.get_actor_bounds(False);return [p.x-e.x,p.x+e.x,p.y-e.y,p.y+e.y,p.z-e.z,p.z+e.z]
def mark(a,label=None):
 if label:a.set_actor_label(label)
 a.set_folder_path(ue.Name('Street/Art pass'))
 a.tags=[*a.tags,TAG]
 return a
def signature():
 result=[]
 for a in ACT.get_all_level_actors():
  if not a.get_actor_label().startswith('Animated factory stack plume'):continue
  p,r,s=a.get_actor_location(),a.get_actor_rotation(),a.get_actor_scale3d()
  c=a.get_component_by_class(ue.StaticMeshComponent)
  result.append(dict(label=a.get_actor_label(),values=[p.x,p.y,p.z,r.pitch,r.yaw,r.roll,s.x,s.y,s.z],material=c.get_material(0).get_path_name()))
 return result
before=signature()
smoke_hash=hashlib.sha256((ROOT/'Content/Prologue/Street/Materials/M_AegisSmoke.uasset').read_bytes()).hexdigest()
old=[a for a in ACT.get_all_level_actors() if a.actor_has_tag(TAG)]
if old:assert ACT.destroy_actors(old)

def authored_mesh(name,dimensions,quad=False):
 path=BASE+'/Architecture/'+name
 if AS.does_asset_exist(path):
  mesh=ue.load_asset(path)
  if not quad:
   editor=ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem);editor.remove_collisions(mesh);assert editor.add_simple_collisions(mesh,ue.ScriptingCollisionShapeType.BOX)>=0;save(mesh)
  return mesh
 x,y,z=(v/2 for v in dimensions)
 if quad:
  points=[(-x,0,-z),(x,0,-z),(x,0,z),(-x,0,z)];faces=[(1,2,3,4)]
 else:
  points=[(a*x,b*y,c*z) for a,b,c in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
  faces=[(1,4,3,2),(5,6,7,8),(1,2,6,5),(2,3,7,6),(3,4,8,7),(4,1,5,8)]
 file=ART/(name+'.obj')
 lines=['o '+name]+['v %.5f %.5f %.5f'%p for p in points]+['vt 0 1','vt 1 1','vt 1 0','vt 0 0','s off']
 lines+=['f '+' '.join(str(vertex)+'/'+str(i+1) for i,vertex in enumerate(face)) for face in faces]
 file.write_text('\n'.join(lines)+'\n',encoding='ascii')
 options=ue.FbxImportUI();options.set_editor_properties(dict(import_materials=False,import_textures=False,import_as_skeletal=False))
 options.static_mesh_import_data.set_editor_properties(dict(combine_meshes=True,auto_generate_collision=not quad))
 task=ue.AssetImportTask();task.set_editor_properties(dict(filename=str(file),destination_path=BASE+'/Architecture',automated=True,options=options,save=True))
 TOOLS.import_asset_tasks([task]);mesh=ue.load_asset(path);assert mesh,path
 if not quad:
  editor=ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem);editor.remove_collisions(mesh);assert editor.add_simple_collisions(mesh,ue.ScriptingCollisionShapeType.BOX)>=0;save(mesh)
 return mesh

# Every structural volume is authored to real dimensions; its Actor scale becomes 1.
palette=[]
registry=ue.AssetRegistryHelpers.get_asset_registry()
def brick_path(number):
 matches=[str(a.package_name) for a in registry.get_assets_by_path('/Game/ImportedAssets/TinyTextures/Size512',recursive=True)
  if str(a.asset_class_path.asset_name)=='Texture2D' and 'Bricks_%02d_'%number in str(a.asset_name)]
 assert len(matches)==1,matches
 return matches[0]
for key,texture,span,tint in (
 ('AgedRedBrick',brick_path(2),(90,90),(1.10,.76,.64)),
 ('SootBrownBrick',brick_path(3),(90,90),(.74,.67,.62)),
 ('PaleLimeBrick',brick_path(3),(90,90),(1.36,1.25,1.03))):
 palette.append(world_surface('M_Wall_'+key,texture,span=span,tint=tint))
concrete='/Game/ImportedAssets/RetroUrban/Concrete/Concrete_02/T_Concrete_02_'
for key,tint in (('GreyPaintedPlaster',(.77,.81,.80)),('FadedOchreRender',(1.00,.72,.43)),('WeatheredConcrete',(.66,.68,.70))):
 palette.append(world_surface('M_Wall_'+key,concrete+'basecolor',concrete+'normal',concrete+'roughness',(180,180),tint))
actors=ACT.get_all_level_actors();groups=[];bodies=0;uniform_houses=0
folders=('Street/03 Shops and cross street','Street/05 Enclosed courtyard','Street/06 Precinct','Street/02 Apartment facade','Brighton/Dima facade')
for a in actors:
 comp=a.get_component_by_class(ue.StaticMeshComponent)
 if not comp or not comp.static_mesh:continue
 if not isinstance(comp,ue.InstancedStaticMeshComponent) and str(a.get_folder_path()) in folders:
  bounds=box_bounds(a);label=a.get_actor_label().lower()
  if (comp.static_mesh.get_path_name().startswith('/Engine/BasicShapes/Cube') or a.actor_has_tag('ProportionalHouseVolume')) and bounds[5]-bounds[4]>450 and min(bounds[1]-bounds[0],bounds[3]-bounds[2])>140:
   s=a.get_actor_scale3d();local=comp.static_mesh.get_bounding_box();size=local.max-local.min;dim=(abs(s.x)*size.x,abs(s.y)*size.y,abs(s.z)*size.z)
   mesh=authored_mesh('SM_HouseVolume_%02d'%bodies,dim)
   comp.set_static_mesh(mesh);a.set_actor_scale3d(V(1,1,1));comp.set_material(0,palette[bodies%len(palette)])
   a.tags=[*a.tags,ue.Name('ProportionalHouseVolume')];bodies+=1
   if str(a.get_folder_path())=='Street/03 Shops and cross street' and 'bar' not in label:
    b=box_bounds(a)
    if b[3]<-2000:normal=(0,1);front=b[3]
    elif b[0]>3000:normal=(-1,0);front=b[0]
    elif b[2]>-500 and b[0]<0:normal=(0,-1);front=b[2]
    else:continue
    groups.append((a,b,normal,front))
 if isinstance(comp,ue.InstancedStaticMeshComponent) and any(name in comp.static_mesh.get_name() for name in ('MarketHouse','WalkupBay','WalkupBrick')):
  local=comp.static_mesh.get_bounding_box();center=(local.min+local.max)*.5
  for i in range(comp.get_instance_count()):
   uniform_houses+=1
   tr=comp.get_instance_transform(i,True);scale=tr.scale3d
   if max(scale.x,scale.y,scale.z)-min(scale.x,scale.y,scale.z)<.001:continue
   old_center=ue.MathLibrary.transform_location(tr,center);old_bottom=tr.translation.z+local.min.z*scale.z
   scalar=min(scale.x,scale.y,scale.z);tr.scale3d=V(scalar,scalar,scalar)
   offset=ue.MathLibrary.transform_location(ue.Transform(rotation=ue.MathLibrary.quat_rotator(tr.rotation),scale=tr.scale3d),center)
   tr.translation=V(old_center.x-offset.x,old_center.y-offset.y,old_bottom-local.min.z*scalar)
   comp.update_instance_transform(i,tr,True,True,True)

road='/Game/ImportedAssets/RetroUrban/Asphalt/Asphalt_03/T_Asphalt_03_'
asphalt=world_surface('M_RoadAsphalt',road+'basecolor',road+'normal',road+'roughness',(230,230),(.82,.85,.89),True)
patch=world_surface('M_AsphaltPatch',road+'basecolor',road+'normal',road+'roughness',(190,190),(.65,.68,.70),True)
paving='/Game/ImportedAssets/RetroUrban/CleanPavement/ConcretePavement_01/T_CleanPavement_01_'
pavement=world_surface('M_Pavement',paving+'basecolor',paving+'normal',paving+'roughness',(200,200),(.82,.84,.85),True)
road_parts=0
for a in actors:
 for comp in a.get_components_by_class(ue.StaticMeshComponent):
  for i in range(comp.get_num_materials()):
   mat=comp.get_material(i);name=mat.get_name().lower() if mat else ''
   if 'asphalt' in name:
    comp.set_material(i,patch if 'repair' in name or 'patch' in name else asphalt);road_parts+=1
   elif str(a.get_folder_path())=='Street/01 Pavement' and name in ('m_concrete','m_wet_concrete','m_pavement','m_wet_pavement'):
    comp.set_material(i,pavement)

# Reuse authored material slots and instance the new models at a uniform scale.
batches={};counts={}
def instance(label,mesh,position,scale=1,yaw=0,anchor=None,cull=14000):
 key=label,mesh.get_path_name()
 if key not in batches:
  a=mark(ACT.spawn_actor_from_class(ue.StreetMeshInstances,V()),label)
  c=a.get_editor_property('instances');c.set_static_mesh(mesh)
  for i,slot in enumerate(mesh.static_materials):c.set_material(i,slot.material_interface)
  c.set_collision_profile_name(ue.Name('NoCollision'));c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False))
  c.set_cull_distances(int(cull*.8),cull);batches[key]=c;counts.setdefault(label,0)
 rotation=ue.Rotator(yaw=yaw)
 anchor=anchor or V()
 offset=ue.MathLibrary.transform_location(ue.Transform(rotation=rotation,scale=V(scale,scale,scale)),anchor)
 tr=ue.Transform(location=V(*position)-offset,rotation=rotation,scale=V(scale,scale,scale))
 batches[key].add_instance(tr,True);counts[label]+=1
def model(name):
 mesh=ue.load_asset(IND+name);assert mesh,name
 return mesh
def foot(mesh):
 b=mesh.get_bounding_box();return V((b.min.x+b.max.x)/2,(b.min.y+b.max.y)/2,b.min.z)

# Complete trees consist of matching bark and canopy meshes sharing a source origin.
tree_points=[(-1040,780),(-990,1790),(-870,2730),(1180,900),(1260,1800),(1050,2640),(300,2790),(-350,2750),
 (1260,6270),(1240,-6260),(-350,6420),(-300,-6500),(4650,3460),(4800,-5360),(-6200,-3340),(-4300,-3300),(-7200,880),(-5200,875)]
tree_count=0
for i,(x,y) in enumerate(tree_points):
 suffix='' if i%5==0 else '_%03d'%(i%5)
 bark=ue.load_asset(TREE+'Mesh_0'+suffix);leaves=ue.load_asset(TREE+'Mesh_1'+suffix);assert bark and leaves
 b=bark.get_bounding_box();l=leaves.get_bounding_box();height=max(b.max.z,l.max.z)-b.min.z
 scale=(590+(i%4)*45)/height;anchor=V((b.min.x+b.max.x)/2,(b.min.y+b.max.y)/2,b.min.z)
 # Keep trunks outside authored architecture and entrance thresholds.
 if any(r['b'][0]-65<x<r['b'][1]+65 and r['b'][2]-65<y<r['b'][3]+65 for r in json.loads((ROOT/'Resources/StreetArtPass/SceneBefore.json').read_text(encoding='utf-8')) if r.get('mesh') and not r.get('instances') and r['b'][5]-r['b'][4]>450 and r['b'][1]-r['b'][0]>200 and r['b'][3]-r['b'][2]>200 and r['label']!='Shared sky dome'):
  continue
 for mesh,label in ((bark,'Imported tree bark '+suffix),(leaves,'Imported tree canopy '+suffix)):
  instance(label,mesh,(x,y,-8 if -1400<x<1500 and 500<y<3000 else -12),scale,(i*97)%360,anchor,cull=17000)
 tree_count+=1

props=0
for i,(x,y) in enumerate(((-2210,-2150),(-3350,-2160),(-4610,-2160),(-6350,-2120),(-2600,-370),(-4320,-370),(-5920,-350),(3310,-2600),(3330,1850),(3450,3570),(1420,3110),(-1440,3030))):
 mesh=model(('Box_wood','Barrel_1','Barrel_2')[i%3])
 instance('Street reclaimed '+mesh.get_name(),mesh,(x,y,-12),.78 if i%3==0 else .84,(i*37)%360,foot(mesh),cull=10000);props+=1

# Replace old primitive stack segments, but keep every plume exactly as authored.
caps=[]
for a in actors:
 if a.get_actor_label()=='Factory depth concrete Cylinder':
  c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
  for i in range(c.get_instance_count()):
   tr=c.get_instance_transform(i,True);caps.append((tr.translation.x,tr.translation.y,tr.translation.z+50*tr.scale3d.z))
for a in actors:
 if a.get_actor_label().startswith('Factory depth ') and a.get_component_by_class(ue.InstancedStaticMeshComponent):
  c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
  if c.static_mesh.get_name()=='Cylinder':a.set_actor_hidden_in_game(True);c.set_visibility(False,True)
pipe=model('Pipes_vertical_long');b=pipe.get_bounding_box();pipe_h=b.max.z-b.min.z
for x,y,top in sorted(caps,key=lambda p:p[1]):
 base=575.75;scale=(top-base)/(2*pipe_h)
 for section in range(2):instance('Imported Aegis stacks',pipe,(x,y,base+section*pipe_h*scale),scale,0,foot(pipe),cull=42000)
for a in actors:
 if a.get_actor_label()=='Factory depth rust Cube':
  c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
  for i in reversed(range(c.get_instance_count())):
   tr=c.get_instance_transform(i,True)
   if any(abs(tr.translation.y-y)<210 and abs(tr.translation.x-x)<480 for x,y,z in caps):c.remove_instance(i)
for i,(x,y) in enumerate(((7800,3400),(7850,-6680))):
 mesh=model('Building_'+str(1+i));b=mesh.get_bounding_box();scale=880/(b.max.z-b.min.z)
 instance('Factory imported service buildings',mesh,(x,y,25),scale,180 if i==0 else 0,foot(mesh),cull=42000)
brick_candidates=[str(a.package_name) for a in ue.AssetRegistryHelpers.get_asset_registry().get_assets_by_path('/Game/ImportedAssets/TinyTextures/Size512',recursive=True) if str(a.asset_class_path.asset_name)=='Texture2D' and 'Bricks_02_' in str(a.asset_name)]
assert brick_candidates,'No imported brick texture'
factory_materials=[world_surface('M_FactoryBrick',brick_candidates[0],span=(90,90),tint=(.86,.65,.52))]
for a in actors:
 if a.get_actor_label() in ('Factory depth brick Cube','Factory depth ochre Cube','Factory depth soot Cube'):
  a.get_component_by_class(ue.InstancedStaticMeshComponent).set_material(0,factory_materials[0])

# Individual paper adverts keep the original image aspect ratio and authored object scale 1.
poster_master=ue.load_asset('/Game/ImportedAssets/Posters/Shared/M_Poster');assert poster_master
poster_count=0
for i,(a,bounds,normal,front) in enumerate(groups[:18]):
 source=ue.load_asset('/Game/ImportedAssets/Posters/AmericanRetro/AppliedMaterials/MI_Poster_'+str(1+i%23).zfill(2))
 if not source:continue
 texture=LIB.get_material_instance_texture_parameter_value(source,ue.Name('PosterImage'));assert texture
 aspect=texture.blueprint_get_size_x()/texture.blueprint_get_size_y();width=43.;height=width/aspect
 target=BASE+'/Textures/T_Advert_'+str(i).zfill(2)
 tex=ue.load_asset(target) if AS.does_asset_exist(target) else AS.duplicate_asset(texture.get_path_name(),target)
 tex.set_editor_property('max_texture_size',1024);save(tex)
 name='MI_Advert_'+str(i).zfill(2);path=BASE+'/Materials/'+name
 mat=ue.load_asset(path) if AS.does_asset_exist(path) else TOOLS.create_asset(name,BASE+'/Materials',ue.MaterialInstanceConstant,ue.MaterialInstanceConstantFactoryNew())
 LIB.set_material_instance_parent(mat,poster_master);LIB.set_material_instance_texture_parameter_value(mat,ue.Name('PosterImage'),tex);LIB.update_material_instance(mat);save(mat)
 nx,ny=normal;span=(bounds[3]-bounds[2]) if nx else (bounds[1]-bounds[0]);center=(bounds[2]+bounds[3])/2 if nx else (bounds[0]+bounds[1])/2
 count=max(2,int((span-90)//180));spacing=min(180,(span-110)/count);tangent=center-(count-2)*spacing/2
 pos=V(front+nx*2,tangent,151) if nx else V(tangent,front+ny*2,151)
 actor=mark(ACT.spawn_actor_from_class(ue.StaticMeshActor,pos,ue.Rotator(yaw=90 if nx<0 else 0 if ny>0 else 180)), 'Vintage wall advert '+str(i).zfill(2))
 c=actor.get_component_by_class(ue.StaticMeshComponent);c.set_static_mesh(authored_mesh('SM_Paper_%d_%d'%(round(width*10),round(height*10)),(width,1,height),True));c.set_material(0,mat);c.set_collision_profile_name('NoCollision');c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False));c.set_cull_distance(4800)
 actor.tags=[*actor.tags,ue.Name('PreservedImageAspect')];poster_count+=1

# Image sign replaces the letter meshes and green panel; the door and quest stay intact.
for a in actors:
 c=a.get_component_by_class(ue.StaticMeshComponent)
 if not c:continue
 text=' '.join(str(t) for t in a.tags).lower();label=a.get_actor_label().lower();mesh=c.static_mesh.get_name().lower() if c.static_mesh else ''
 if 'neptune94 bar enamel' in label or ('signtext:' in text and ('бар' in text or 'lighthouse' in text or 'bar' in mesh)):
  a.set_actor_hidden_in_game(True);c.set_visibility(False,True)
 if isinstance(c,ue.InstancedStaticMeshComponent) and 'bar lighthouse shell' in label:
  for i in reversed(range(c.get_instance_count())):
   tr=c.get_instance_transform(i,True)
   if 1040<tr.translation.y<1540 and 390<tr.translation.z<610:c.remove_instance(i)
beacon=ue.load_asset(BASE+'/Textures/T_BeaconSign');assert beacon
beacon.set_editor_property('max_texture_size',1024);save(beacon)
mat=material('M_BeaconSign');LIB.delete_all_material_expressions(mat)
mat.set_editor_properties(dict(blend_mode=ue.BlendMode.BLEND_MASKED,two_sided=True,opacity_mask_clip_value=.4))
sample=n(mat,ue.MaterialExpressionTextureSample,texture=beacon)
output(sample,mat,ue.MaterialProperty.MP_BASE_COLOR,'RGB');output(sample,mat,ue.MaterialProperty.MP_OPACITY_MASK,'A')
glow=n(mat,ue.MaterialExpressionMultiply,const_b=.14);connect(sample,glow,'A','RGB');output(glow,mat,ue.MaterialProperty.MP_EMISSIVE_COLOR)
output(const(mat,.52),mat,ue.MaterialProperty.MP_ROUGHNESS);assert not LIB.recompile_material(mat);save(mat)
width=420;aspect=1624/969;height=width/aspect
sign=mark(ACT.spawn_actor_from_class(ue.StaticMeshActor,V(3349,1290,425),ue.Rotator(yaw=90)),'BEACON lighthouse sign')
c=sign.get_component_by_class(ue.StaticMeshComponent);c.set_static_mesh(authored_mesh('SM_BeaconSign',(width,1,height),True));c.set_material(0,mat);c.set_collision_profile_name('NoCollision');c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False));c.set_cull_distance(16000)

flow,=[a for a in ACT.get_all_level_actors() if isinstance(a,ue.StreetTrafficFlow)]
flow.set_editor_properties(dict(drive_by_sound=ue.load_asset('/Game/Audio/Traffic/S_TrafficDriveBy'),horn_sound=ue.load_asset('/Game/Audio/Traffic/S_TrafficHorn')))
assert before==signature(),'Smoke transforms/materials changed'
assert smoke_hash==hashlib.sha256((ROOT/'Content/Prologue/Street/Materials/M_AegisSmoke.uasset').read_bytes()).hexdigest()
assert LV.save_current_level()
report=dict(house_volumes_authored=bodies,background_houses_uniform=uniform_houses,road_components=road_parts,trees=tree_count,
 street_details=props,wall_adverts=poster_count,replaced_stacks=len(caps),imported_stack_segments=counts.get('Imported Aegis stacks',0),
 smoke=before,smoke_material_sha256=smoke_hash,instance_counts=counts,sign_reference='T_BeaconSign.png')
(ART/'StreetArtReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
ue.log('STREET_ART_APPLIED '+str({k:v for k,v in report.items() if k not in ('smoke','instance_counts')}))

# Finish the sign/poster UV orientation and background ground.
exec(compile((ROOT/'Scripts/PolishStreetArt.py').read_text(encoding='utf-8'), 'PolishStreetArt.py', 'exec'), {'__name__':'__main__'})
exec(compile((ROOT/'Scripts/PlaceWallAdverts.py').read_text(encoding='utf-8'), 'PlaceWallAdverts.py', 'exec'), {'__name__':'__main__'})
