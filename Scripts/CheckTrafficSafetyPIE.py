"""Run with -ExecutePythonScript in a separate editor. Runtime-only safety/impact test."""
import time,traceback
import unreal as ue

levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assert levels.load_level('/Game/Locations/L_NeptuneStreet')
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state=dict(step='ready',deadline=time.monotonic()+100,positions={},lanes=set(),finished=set())

def place(pawn,pos):
    motion=pawn.get_component_by_class(ue.CharacterMovementComponent)
    motion.stop_movement_immediately()
    pawn.set_actor_location(pos,False,True)

def finish(ok):
    ue.unregister_slate_post_tick_callback(state['handle'])
    world=editor.get_game_world()
    if world:
        ue.GameplayStatics.set_global_time_dilation(world,1)
        ue.SystemLibrary.execute_console_command(world,'t.MaxFPS 0')
    levels.editor_request_end_play()
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if ok:ue.log('TRAFFIC_SAFETY_PIE_PASSED')

def tick(delta):
    try:
        assert time.monotonic()<state['deadline'],('Traffic test timeout',state['step'])
        world=editor.get_game_world()
        if not world:return
        pawn=ue.GameplayStatics.get_player_character(world,0)
        pc=ue.GameplayStatics.get_player_controller(world,0)
        if not pawn or not pc:return
        flow=ue.GameplayStatics.get_actor_of_class(world,ue.StreetTrafficFlow)
        if not flow:return
        step=state['step']
        if step=='ready':
            hud=pc.get_hud()
            if not hud:return
            if hud.get_editor_property('State')==-1:hud.call_method('ReceiveDrawHUD',(1280,720))
            assert flow.validate_route_clearance(),('Route enters a wall or curb',flow.get_route_obstruction_count())
            assert flow.get_route_obstruction_count()==0
            place(pawn,ue.Vector(-2200,-515,101))
            state['started']=ue.GameplayStatics.get_time_seconds(world)
            state['prior_spawns']=flow.get_total_spawned()
            state['prior_blocks']=flow.get_blocked_moves()
            ue.GameplayStatics.set_global_time_dilation(world,2)
            state['step']='route'
        elif step=='route':
            cars=ue.GameplayStatics.get_all_actors_of_class(world,ue.StreetTrafficCar)
            assert len(cars)<=8 and flow.get_active_count()<=8,'Traffic pool grew without limit'
            for car in cars:
                name=car.get_name()
                if car.get_editor_property('hidden'):
                    if name in state['positions']:state['finished'].add(name)
                    state['positions'].pop(name,None)
                    continue
                location=car.get_actor_location()
                # Remove the fixed collider center offset to compare with actual lane centerlines.
                road=ue.Vector(location.x,location.y,location.z-75)
                lanes=[flow.get_lane(index) for index in range(flow.get_route_count())]
                distances=[lane.find_location_closest_to_world_location(road,ue.SplineCoordinateSpace.WORLD).distance(road) for lane in lanes]
                assert min(distances)<3.5,('Vehicle drifted off its route',name,location,distances)
                state['lanes'].add(distances.index(min(distances)))
                state['positions'][name]=(location.x,location.y)
            assert flow.get_blocked_moves()==state['prior_blocks'],'A car hit static scenery or another car on an empty road'
            if ue.GameplayStatics.get_time_seconds(world)-state['started']<60:return
            assert state['lanes']=={0,1,2,3},state['lanes']
            assert len(state['finished'])>=2,('Both lanes did not finish a route',state['finished'])
            assert flow.get_total_spawned()-state['prior_spawns']>=7
            ue.GameplayStatics.set_global_time_dilation(world,1)
            ue.log('TRAFFIC_ROUTES_OK: full static swept audit, 60 game seconds, four active routes, pooled cars, no scenery contact')
            state['step']='choose_impact'
        elif step=='choose_impact':
            cars=ue.GameplayStatics.get_all_actors_of_class(world,ue.StreetTrafficCar)
            chosen=next((car for car in cars if not car.get_editor_property('hidden') and -5300<car.get_actor_location().x<1000 and abs(ue.MathLibrary.get_forward_vector(car.get_actor_rotation()).x)>.99),None)
            if chosen is None:return
            center=chosen.get_actor_location()
            forward=ue.MathLibrary.get_forward_vector(chosen.get_actor_rotation())
            body=chosen.get_component_by_class(ue.BoxComponent)
            half=body.get_scaled_box_extent().x
            place(pawn,ue.Vector(center.x+forward.x*(half+82),center.y+forward.y*(half+82),80))
            state['prior_impacts']=flow.get_impact_count()
            state['impact_wait']=time.monotonic()+2
            state['step']='impact'
        elif step=='impact':
            if flow.get_impact_count()==state['prior_impacts']:
                assert time.monotonic()<state['impact_wait'],'Moving car did not trigger impact against the player capsule'
                return
            velocity=pawn.get_velocity()
            # LaunchCharacter queues its velocity until CharacterMovement's next tick.
            if (velocity.x*velocity.x+velocity.y*velocity.y)**.5<=180 and velocity.z<=150:
                if 'launch_deadline' not in state:state['launch_deadline']=time.monotonic()+.25
                assert time.monotonic()<state['launch_deadline'],('No physical launch response',velocity)
                return
            assert flow.get_blocked_moves()>state['prior_blocks']
            ue.log('TRAFFIC_IMPACT_OK: actual moving car sweep -> player capsule, launch velocity='+str(velocity))
            state['impact_count']=flow.get_impact_count()
            state['wait']=time.monotonic()+.25
            state['step']='cooldown'
        elif step=='cooldown':
            if time.monotonic()<state['wait']:return
            assert flow.get_impact_count()==state['impact_count'],'Repeated impact while the same car was braking'
            place(pawn,ue.Vector(-2200,-515,101))
            ue.SystemLibrary.execute_console_command(world,'t.MaxFPS 12')
            state['slow_until']=time.monotonic()+3
            state['blocks_before_slow']=flow.get_blocked_moves()
            state['step']='slow'
        elif step=='slow':
            if time.monotonic()<state['slow_until']:return
            assert flow.get_blocked_moves()==state['blocks_before_slow'],'Low frame rate caused a collision with scenery'
            assert flow.validate_route_clearance()
            ue.log('TRAFFIC_LOW_FPS_OK: 12 FPS, bounded swept substeps, no curb/building contact')
            finish(True)
    except Exception:
        ue.log_error('TRAFFIC_SAFETY_FAILED '+traceback.format_exc())
        finish(False)

state['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
