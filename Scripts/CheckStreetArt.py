"""Validate saved geometry, asset proportions, sign/audio bindings and smoke invariants."""
from pathlib import Path
import json,hashlib
import unreal as ue
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem);actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
assert levels.load_level('/Game/Locations/L_NeptuneStreet')
report=json.loads((root/'Resources/StreetArtPass/StreetArtReport.json').read_text(encoding='utf-8'))
before=json.loads((root/'Resources/StreetArtPass/SceneBefore.json').read_text(encoding='utf-8'))
placed=actors.get_all_level_actors();bodies=0;uniform_instances=0;signs=[];posters=[];stacks=0
mesh_editor=ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem);assert mesh_editor
for a in placed:
 c=a.get_component_by_class(ue.StaticMeshComponent)
 if a.actor_has_tag('ProportionalHouseVolume'):
  scale=a.get_actor_scale3d();assert max(abs(v-1) for v in (scale.x,scale.y,scale.z))<.0001
  assert mesh_editor.get_simple_collision_count(c.static_mesh)>0,a.get_actor_label()
  p=a.get_actor_location();old=next(r for r in before if r['label']==a.get_actor_label() and abs(r['p'][0]-p.x)<1 and abs(r['p'][1]-p.y)<1)
  center,extent=a.get_actor_bounds(False);current=[center.x-extent.x,center.x+extent.x,center.y-extent.y,center.y+extent.y,center.z-extent.z,center.z+extent.z]
  assert max(abs(x-y) for x,y in zip(current,old['b']))<.7,(a.get_actor_label(),current,old['b'])
  bodies+=1
 if a.actor_has_tag('StreetArtPass_v1'):
  if isinstance(c,ue.InstancedStaticMeshComponent):
   for i in range(c.get_instance_count()):
    scale=c.get_instance_transform(i,True).scale3d
    assert max(scale.x,scale.y,scale.z)-min(scale.x,scale.y,scale.z)<.0001,a.get_actor_label()
    uniform_instances+=1
   if a.get_actor_label()=='Imported Aegis stacks':stacks+=c.get_instance_count()
  else:
   scale=a.get_actor_scale3d();assert max(scale.x,scale.y,scale.z)-min(scale.x,scale.y,scale.z)<.0001,a.get_actor_label()
  if a.get_actor_label()=='BEACON lighthouse sign':signs.append(a)
  if a.actor_has_tag('PreservedImageAspect'):posters.append(a)
assert bodies==report['house_volumes_authored']>=25
assert len(signs)==1 and len(posters)>=15 and stacks==6
mat=signs[0].get_component_by_class(ue.StaticMeshComponent).get_material(0)
assert mat.get_editor_property('blend_mode')==ue.BlendMode.BLEND_MASKED
for item in report['smoke']:
 a=next(a for a in placed if a.get_actor_label()==item['label'])
 p,r,s=a.get_actor_location(),a.get_actor_rotation(),a.get_actor_scale3d()
 assert [p.x,p.y,p.z,r.pitch,r.yaw,r.roll,s.x,s.y,s.z]==item['values']
 assert a.get_component_by_class(ue.StaticMeshComponent).get_material(0).get_path_name()==item['material']
assert hashlib.sha256((root/'Content/Prologue/Street/Materials/M_AegisSmoke.uasset').read_bytes()).hexdigest()==report['smoke_material_sha256']
flow,=[a for a in placed if isinstance(a,ue.StreetTrafficFlow)]
for prop in ('drive_by_sound','horn_sound'):
 sound=flow.get_editor_property(prop);assert isinstance(sound,ue.SoundWave)
 assert sound.duration>0 and not sound.get_editor_property('looping')
result=dict(houses=bodies,uniform_new_instances=uniform_instances,posters=len(posters),stack_segments=stacks,trees=report['trees'],audio_bound=True,smoke_unchanged=True)
(root/'Resources/StreetArtPass/Validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
ue.log('STREET_ART_VALIDATION_PASSED '+str(result))
