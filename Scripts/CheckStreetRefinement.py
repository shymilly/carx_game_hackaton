"""Read-only audit of the saved street. Run with UnrealEditor-Cmd -run=pythonscript."""
import hashlib,json,sys
from pathlib import Path
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(root/'Tools'))
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
assert levels.load_level('/Game/Locations/L_NeptuneStreet')
from RefineStreetVisuals import SIGNS,audit
from BrightonStreetDetails import FACTORY_PIVOT,FACTORY_SCALE
report=audit()
assert not report['sidewalk_violations'],report['sidewalk_violations']
assert len(report['signs'])==8,report['signs']
assert all(s['positive_scale'] for s in report['signs'])
assert {s['text']:s['font'] for s in report['signs']}=={s.text:s.family for s in SIGNS.values()}
assert len({s['font'] for s in report['signs']})==len(report['signs'])

baseline=json.loads((root/'Resources/StreetRefinement/SmokeBaseline.json').read_text(encoding='utf-8'))
smoke_path=root/'Content/Prologue/Street/Materials/M_AegisSmoke.uasset'
assert hashlib.sha256(smoke_path.read_bytes()).hexdigest()==baseline['material_sha256']
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
smoke=[a for a in actors if a.get_actor_label().startswith('Animated factory stack plume')]
assert len(smoke)==3
for a in smoke:
 before=next(b for b in baseline['actors'] if b['label']==a.get_actor_label())
 p,r,s=a.get_actor_location(),a.get_actor_rotation(),a.get_actor_scale3d()
 actual=(p.x,p.y,p.z,r.pitch,r.yaw,r.roll,s.x,s.y,s.z)
 expected=[o+(v-o)*FACTORY_SCALE for o,v in zip(FACTORY_PIVOT,before['pos'])]+before['rot']+[v*FACTORY_SCALE for v in before['scale']]
 assert a.actor_has_tag('BrightonEnlargedFactory') and all(abs(x-y)<.002 for x,y in zip(actual,expected)),a.get_actor_label()
 c=a.get_component_by_class(ue.StaticMeshComponent)
 assert c.get_material(0).get_path_name()==before['materials'][0]
 assert c.static_mesh.get_path_name()==before['mesh']

factory=[a for a in actors if str(a.get_folder_path())=='Street/08 Industrial horizon/Refined works']
assert len(factory)<=16
instances=0
for a in factory:
 c=a.get_component_by_class(ue.InstancedStaticMeshComponent)
 assert c and not a.get_component_by_class(ue.LightComponent)
 assert str(c.get_collision_profile_name())=='NoCollision'
 assert not c.get_editor_property('cast_shadow')
 assert a.actor_has_tag('BrightonEnlargedFactory')
 mat=c.get_material(0)
 assert mat.get_editor_property('shading_model')==ue.MaterialShadingModel.MSM_DEFAULT_LIT,mat
 assert ue.MaterialEditingLibrary.get_material_property_input_node(mat,ue.MaterialProperty.MP_BASE_COLOR)
 instances+=c.get_instance_count()
assert 400<=instances<=1000,instances
photo_hashes=[]
for name in ('Apartment','Neptune','Precinct'):
 path=root/'Resources/Presentation'/('T_Transition_'+name+'.png')
 photo_hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
 assert ue.load_asset('/Game/Prologue/Street/Transitions/T_Transition_'+name)
assert len(set(photo_hashes))==3
for path in ue.get_editor_subsystem(ue.EditorAssetSubsystem).list_assets('/Game/StreetRefinement/Textures',recursive=True,include_folder=False):
 t=ue.load_asset(path)
 if isinstance(t,ue.Texture2D):
  assert t.blueprint_get_size_x()<=256 and t.blueprint_get_size_y()<=256,path

assert levels.load_level('/Game/Locations/L_PolicePrecinct')
plaque,=[a for a in ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
        if a.get_actor_label()=='60 Precinct fascia']
precinct=SIGNS['SM_NeighborhoodPrecinct']
assert plaque.actor_has_tag(ue.Name('SignText:'+precinct.text))
assert plaque.actor_has_tag(ue.Name('SignFont:'+precinct.family))
assert plaque.get_component_by_class(ue.StaticMeshComponent).static_mesh.get_name()=='SM_N94_SM_NeighborhoodPrecinct'
result=dict(sidewalk_violations=0,architectural_groups=report['building_count'],signs=len(report['signs']),factory_batches=len(factory),factory_instances=instances,factory_scale=FACTORY_SCALE,smoke_aligned=True,unique_photos=3)
(root/'Saved/StreetRefinementCheck.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
ue.log('STREET_REFINEMENT_CHECK_PASSED '+str(result))
