"""GPU-render the final street, facade, sign, trees and factory without saving cameras."""
from pathlib import Path
import time,traceback
import unreal as ue
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem);actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
assert levels.load_level('/Game/Locations/L_NeptuneStreet')
assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
for path in assets.list_assets('/Game/StreetArtPass/Materials',recursive=True,include_folder=False):
 material=ue.load_asset(path)
 if isinstance(material,ue.Material):
  errors=ue.MaterialEditingLibrary.recompile_material(material)
  assert not errors,(path,errors)
  assert assets.save_loaded_asset(material,False)
shots=[('Street',(-1300,-1600,240),(1800,-1200,280),86),
 ('Facade',(-1800,-1740,235),(-1630,-2240,520),78),
 ('Beacon',(2730,1290,400),(3349,1290,425),59),
 ('Park',(-300,1450,240),(1260,1800,350),88),
 ('Factory',(2500,-1500,3500),(5900,-1500,2450),108),
 ('Road',(2800,-2000,460),(2180,-3100,-28),77),
 ('Facade_Materials',(-1800,-1740,235),(-1630,-2240,420),78),
 ('Road_Materials',(2680,-2000,460),(2180,-3100,-28),77),
 ('Park_Materials',(-300,1450,240),(1260,1800,350),88)]
advert_yaws=set()
for actor in actors.get_all_level_actors():
 if not actor.actor_has_tag('PreservedImageAspect'):continue
 yaw=round(actor.get_actor_rotation().yaw)
 if yaw in advert_yaws:continue
 p=actor.get_actor_location();camera=p+actor.get_actor_right_vector()*120
 shots.append(('Advert_%d_Materials'%len(advert_yaws),(camera.x,camera.y,camera.z),(p.x,p.y,p.z),65))
 advert_yaws.add(yaw)
 if len(advert_yaws)==2:break
folder=root/'Saved/Reviews/StreetArtPass';folder.mkdir(parents=True,exist_ok=True)
state=dict(index=0,phase='next',deadline=time.monotonic()+300,busy=False)
ue.EditorPythonScripting.set_keep_python_script_alive(True)
def finish(ok):
 ue.unregister_slate_post_tick_callback(state['handle']);ue.EditorPythonScripting.set_keep_python_script_alive(False)
 if ok:ue.log('STREET_ART_RENDER_PASSED')
def tick(delta):
 if state['busy']:return
 state['busy']=True
 try:
  assert time.monotonic()<state['deadline'],state['phase']
  if state['phase']=='next':
   if state['index']==len(shots):finish(True);return
   name,p,target,fov=shots[state['index']]
   cam=actors.spawn_actor_from_class(ue.SceneCapture2D,ue.Vector(*p),ue.MathLibrary.find_look_at_rotation(ue.Vector(*p),ue.Vector(*target)))
   capture=cam.get_component_by_class(ue.SceneCaptureComponent2D)
   world=ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
   render=ue.RenderingLibrary.create_render_target2d(world,1280,720,ue.TextureRenderTargetFormat.RTF_RGBA8)
   source=ue.SceneCaptureSource.SCS_BASE_COLOR if name.endswith('_Materials') else ue.SceneCaptureSource.SCS_FINAL_COLOR_LDR
   capture.set_editor_properties(dict(fov_angle=fov,texture_target=render,capture_source=source,capture_every_frame=False,capture_on_movement=False))
   post=capture.post_process_settings
   post.set_editor_properties(dict(override_auto_exposure_bias=True,auto_exposure_bias=3.5,
    override_auto_exposure_method=True,auto_exposure_method=ue.AutoExposureMethod.AEM_MANUAL,
    override_auto_exposure_apply_physical_camera_exposure=True,auto_exposure_apply_physical_camera_exposure=False))
   capture.set_editor_property('post_process_settings',post)
   state.update(cam=cam,render=render,name=name,at=time.monotonic()+1.4,phase='capture')
  elif state['phase']=='capture':
   if time.monotonic()<state['at']:return
   state['cam'].get_component_by_class(ue.SceneCaptureComponent2D).capture_scene();state.update(phase='export',at=time.monotonic()+.4)
  elif state['phase']=='export':
   if time.monotonic()<state['at']:return
   world=ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
   state['cam'].get_component_by_class(ue.SceneCaptureComponent2D).capture_scene()
   ue.RenderingLibrary.export_render_target(world,state['render'],str(folder),state['name']+'.png')
   ue.log('STREET_ART_REVIEW '+str(folder/(state['name']+'.png')))
   actors.destroy_actor(state.pop('cam'));state.pop('render');state['index']+=1;state['phase']='next'
 except Exception:
  ue.log_error('STREET_ART_RENDER_FAILED '+traceback.format_exc());finish(False)
 finally:state['busy']=False
state['handle']=ue.register_slate_post_tick_callback(tick)
