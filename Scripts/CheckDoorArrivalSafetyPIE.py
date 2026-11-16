"""Use -ExecutePythonScript in a separate editor. Tests common loading/arrival pipeline, not story gating."""
import time,traceback
import unreal as ue

levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assert levels.load_level('/Game/Locations/L_NeptuneStreet')
ue.EditorPythonScripting.set_keep_python_script_alive(True)
routes=[
    ('L_DimaApartmentInterior','FromStreet','T_Transition_Apartment'),
    ('L_NeptuneStreet','FromApartment','T_Transition_Neptune'),
    ('L_PolicePrecinct','FromStreet','T_Transition_Precinct'),
    ('L_NeptuneStreet','FromPrecinct','T_Transition_Neptune'),
]
state=dict(step='begin',route=0,deadline=time.monotonic()+45)

def finish(ok):
    ue.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if ok:ue.log('DOOR_ARRIVAL_SAFETY_PASSED')

def tick(delta):
    try:
        assert time.monotonic()<state['deadline'],('Arrival timeout',state)
        world=editor.get_game_world()
        if not world:return
        pc=ue.GameplayStatics.get_player_controller(world,0)
        hud=pc.get_hud() if pc else None
        if not hud:return
        if hud.get_editor_property('State')==-1:hud.call_method('ReceiveDrawHUD',(1280,720))
        instance=ue.GameplayStatics.get_game_instance(world)
        ui=next(obj for obj in ue.ObjectIterator(ue.NarrativeSubsystem) if obj.get_outer()==instance)
        name,tag,photo=routes[state['route']]
        if state['step']=='begin':
            if ui.is_location_transition_active():return
            assert not pc.is_move_input_ignored()
            state['old_world']=world.get_path_name()
            # No photo is passed: validates the common destination-photo resolver too.
            destination=ue.load_asset('/Game/Locations/'+name)
            assert ui.travel_to_street(destination,name,None,ue.Name(tag))
            assert ui.is_location_transition_active(),'Loading UI was not added immediately'
            assert ui.get_location_photo() and ui.get_location_photo().get_name()==photo
            assert pc.is_move_input_ignored() and pc.is_look_input_ignored()
            assert not ui.travel_to_street(destination,name,None,ue.Name(tag)),'Duplicate travel accepted'
            state['step']='arrive'
        else:
            if ue.GameplayStatics.get_current_level_name(world,True)!=name or ui.is_location_transition_active():return
            assert world.get_path_name()!=state['old_world'],'No actual world replacement'
            assert ue.LocationTravelLibrary.was_last_arrival_exact(pc),'Used fallback instead of the exact threshold'
            assert ue.LocationTravelLibrary.is_arrival_point_safe(pc,ue.Name(tag)),'Threshold capsule/ground is unsafe'
            points=ue.GameplayStatics.get_all_actors_with_tag(world,ue.Name(tag))
            assert len(points)==1,('Threshold is missing or duplicated',name,tag)
            marker=points[0]
            pawn=ue.GameplayStatics.get_player_pawn(world,0)
            actual=pawn.get_actor_location()
            target=marker.get_actor_location()
            assert abs(actual.x-target.x)<1 and abs(actual.y-target.y)<1,(name,actual,target)
            difference=(pc.get_control_rotation().yaw-marker.get_actor_rotation().yaw+180)%360-180
            assert abs(difference)<1,('Wrong arrival facing',name,difference)
            assert not pc.is_move_input_ignored() and not pc.is_look_input_ignored()
            assert not pc.get_editor_property('show_mouse_cursor')
            ue.log('DOOR_ARRIVAL_OK '+name+' tag='+tag+' exact XY/facing, ground/capsule, photo, locks, duplicate suppression')
            state['route']+=1
            if state['route']==len(routes):finish(True)
            else:state['step']='begin'
    except Exception:
        ue.log_error('DOOR_ARRIVAL_FAILED '+traceback.format_exc())
        finish(False)

state['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
