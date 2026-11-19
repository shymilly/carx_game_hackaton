"""Exercise approach audio, warning horn and spatial settings in a real PIE world."""
import time,traceback
import unreal as ue
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem);editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assert levels.load_level('/Game/Locations/L_NeptuneStreet')
state=dict(phase='start',deadline=time.monotonic()+70)
ue.EditorPythonScripting.set_keep_python_script_alive(True)
def done(ok):
 ue.unregister_slate_post_tick_callback(state['handle']);levels.editor_request_end_play();ue.EditorPythonScripting.set_keep_python_script_alive(False)
 if ok:ue.log('TRAFFIC_AUDIO_PIE_PASSED')
def tick(delta):
 try:
  assert time.monotonic()<state['deadline'],state['phase']
  world=editor.get_game_world()
  if not world:return
  pawn=ue.GameplayStatics.get_player_pawn(world,0)
  if not pawn:return
  flow=next(a for a in ue.GameplayStatics.get_all_actors_of_class(world,ue.StreetTrafficFlow))
  if state['phase']=='start':
   assert flow.get_editor_property('drive_by_sound') and flow.get_editor_property('horn_sound')
   assert flow.validate_route_clearance(),flow.get_route_obstruction_count()
   lane=flow.get_lane(0);p=lane.get_location_at_distance_along_spline(2500,ue.SplineCoordinateSpace.WORLD)
   pawn.set_actor_location(p+ue.Vector(0,220,130),False,True)
   state.update(phase='approach',baseline=flow.get_drive_by_count())
  elif state['phase']=='approach':
   if flow.get_drive_by_count()<=state['baseline']:return
   ue.log('TRAFFIC_AUDIO_APPROACH_OK count='+str(flow.get_drive_by_count()))
   cars=[a for a in ue.GameplayStatics.get_all_actors_of_class(world,ue.StreetTrafficCar) if not a.get_editor_property('hidden')]
   if not cars:return
   def squared_distance(a):
    d=a.get_actor_location()-pawn.get_actor_location()
    return d.x*d.x+d.y*d.y+d.z*d.z
   car=min(cars,key=squared_distance)
   pawn.set_actor_location(car.get_actor_location()+car.get_actor_forward_vector()*1000+ue.Vector(0,0,55),False,True)
   state.update(phase='horn',horn_before=flow.get_horn_count(),car=car)
  elif state['phase']=='horn':
   if flow.get_horn_count()<=state['horn_before']:return
   ue.log('TRAFFIC_AUDIO_HORN_OK count='+str(flow.get_horn_count()))
   car=state['car']
   # Audio components belong to the vehicle and have spatial attenuation and no looping.
   audio=car.get_editor_property('drive_by_audio');horn=car.get_editor_property('horn_audio')
   assert audio.get_editor_property('override_attenuation') and horn.get_editor_property('override_attenuation')
   assert not flow.get_editor_property('drive_by_sound').get_editor_property('looping')
   assert not flow.get_editor_property('horn_sound').get_editor_property('looping')
   done(True)
 except Exception:
  ue.log_error('TRAFFIC_AUDIO_FAILED '+traceback.format_exc());done(False)
state['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
