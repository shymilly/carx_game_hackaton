"""Run with -ExecutePythonScript (full editor): exercise the real PIE HUD, widgets and locks."""
import json,os,time,traceback
from pathlib import Path
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
spec=json.loads((root/'Docs/Scenario/DimaApartment.json').read_text(encoding='utf-8'))
documents={row['id']:row for row in spec['documents']}
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
street=os.environ.get('DIMA_TEST_STREET')=='1'
assert levels.load_level('/Game/Prologue/'+('L_DimaApartmentStreet' if street else spec['apartment_map']))
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state={'step':'start','deadline':time.monotonic()+100,'phone_page':1}

def finish(ok):
    ue.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if ok: ue.log('DIMA_PIE_CHECK_PASSED')

def page(world, expected):
    windows=ue.WidgetLibrary.get_all_widgets_of_class(world,ue.DimaStoryDialogueWindow,True)
    assert len(windows)==1,('Expected one dialogue',len(windows))
    window=windows[0]
    document=window.get_editor_property('document')
    assert str(document.get_editor_property('body'))==documents[expected]['body'],expected
    return window

def keyed(world,pc,key,pressed):
    marker='+' if pressed else '-'
    ue.SystemLibrary.execute_console_command(world,f'Input.{marker}key {key}',pc)

def tagged(world, tag):
    actor,=ue.GameplayStatics.get_all_actors_with_tag(world,ue.Name(tag))
    return actor

def tick(delta):
    try:
        if not state.get('tick_logged'):
            ue.log('DIMA_PIE_TICK_STARTED')
            state['tick_logged']=True
        assert time.monotonic()<state['deadline'],('PIE timeout',state['step'])
        world=editor.get_game_world()
        if not world: return
        if not state.get('world_logged'):
            ue.log('DIMA_PIE_WORLD '+world.get_name())
            state['world_logged']=True
        pc=ue.GameplayStatics.get_player_controller(world,0)
        if not pc or not pc.get_hud(): return
        hud=pc.get_hud()
        story=hud.get_component_by_class(ue.DimaApartmentStoryComponent)
        if not story:
            # NullRHI does not draw the viewport, so deliver its first HUD event explicitly.
            if not state.get('hud_initialized'):
                ue.log('DIMA_PIE_HUD '+hud.get_class().get_path_name())
                hud.call_method('ReceiveDrawHUD',(1280,720))
                state['hud_initialized']=True
                story=hud.get_component_by_class(ue.DimaApartmentStoryComponent)
            if not story: return
        step=state['step']
        if step!=state.get('last_step'):
            ue.log('DIMA_PIE_STEP '+step)
            state['last_step']=step
        if step=='start':
            assert hud.get_editor_property('State')==9,('Expected initial report',hud.get_editor_property('State'))
            assert story.get_phase()==ue.DimaApartmentPhase.AWAITING_REPORT
            if street:
                for tag in ('Wardrobe','Television','Phone'):
                    proxies=[actor for actor in ue.GameplayStatics.get_all_actors_with_tag(world,ue.Name(tag))
                             if isinstance(actor,ue.DimaStoryFocusProxy)]
                    assert len(proxies)==1 and proxies[0].get_editor_property('source_actor').get_world()==world,tag
            hud.call_method('FinishReport')
            state['step']='explore'
        elif step=='explore':
            if story.get_phase()!=ue.DimaApartmentPhase.EXPLORING: return
            assert not pc.is_move_input_ignored()
            ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('Phone'))
            assert story.get_phase()==ue.DimaApartmentPhase.EXPLORING
            assert ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('StreetDoor' if street else 'Exit'))
            if street: assert not hud.get_editor_property('StreetDoorToggled')
            ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('Wardrobe'))
            assert story.is_busy() and pc.is_move_input_ignored() and pc.is_look_input_ignored()
            page(world,'Wardrobe').request_close()
            state['step']='television'
        elif step in ('television','lamp'):
            tag='Television' if step=='television' else 'FloorLamp'
            ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name(tag))
            page(world,tag).request_close()
            assert not story.is_busy() and not pc.is_move_input_ignored()
            state['step']='lamp' if step=='television' else 'fridge'
        elif step=='fridge':
            assert not ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('FridgeDoor'))
            hud.call_method('ActivateFridgeDoor')
            state['step']='fridge_wait'
        elif step=='fridge_wait':
            if not story.is_busy(): return
            assert hud.get_editor_property('FridgeDoorProgress')>=0.85
            page(world,'Fridge').request_close()
            assert story.get_phase()==ue.DimaApartmentPhase.EXPLORING
            ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('Tap'))
            assert story.is_busy() and pc.is_move_input_ignored()
            state['wash_start']=ue.GameplayStatics.get_time_seconds(world)
            state['step']='wash_wait'
        elif step=='wash_wait':
            if story.get_phase()!=ue.DimaApartmentPhase.RINGING: return
            elapsed=ue.GameplayStatics.get_time_seconds(world)-state['wash_start']
            assert 2.9<=elapsed<4.0,('Wash timing',elapsed)
            assert not ue.WidgetLibrary.get_all_widgets_of_class(world,ue.DimaWashOverlay,True)
            page(world,'RingNotice').request_close()
            assert not story.is_busy() and not pc.is_move_input_ignored()
            state['ring_wait']=time.monotonic()+0.3
            state['step']='pickup'
        elif step=='pickup':
            if time.monotonic()<state['ring_wait']: return
            assert story.get_phase()==ue.DimaApartmentPhase.RINGING
            ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('Phone'))
            assert story.get_phase()==ue.DimaApartmentPhase.CALLING
            state['step']='conversation'
        elif step=='conversation':
            assert story.is_busy() and pc.is_move_input_ignored() and pc.is_look_input_ignored()
            page(world,f"Phone{state['phone_page']:02}").request_close()
            state['phone_page']+=1
            if state['phone_page']>9: state['step']='completed'
        elif step=='completed':
            assert story.get_phase()==ue.DimaApartmentPhase.READY_TO_EXIT
            assert not story.is_busy() and not pc.is_move_input_ignored() and not pc.is_look_input_ignored()
            assert ue.DimaApartmentStoryLibrary.objective(hud,'')==spec['exit_objective']
            assert not pc.get_editor_property('show_mouse_cursor')
            ue.log('DIMA_PIE_FLOW: report, early pickup/exit, 5 props, animated fridge, 3-second wash, ring, 9 pages, restored input, exit goal')
            if not street:
                finish(True)
                return
            assert not ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('StreetDoor'))
            player=ue.GameplayStatics.get_player_character(world,0)
            player.set_actor_location(ue.Vector(-194,-335,100),False,True)
            door=tagged(world,'StreetDoor')
            all_parts=ue.GameplayStatics.get_all_actors_of_class(world,ue.StaticMeshActor)
            pinned={actor.get_actor_label():actor for actor in all_parts if ' hinge ' in actor.get_actor_label()}
            assert len(pinned)==33,len(pinned)
            moving=pinned['StreetDoor hinge 1 door leaf']
            pin=pinned['StreetDoor hinge 1 pin']
            assert moving.get_attach_parent_actor()==door
            state['hinges']=(moving,moving.get_actor_location(),pin,pin.get_actor_location())
            lamp=tagged(world,'FloorLamp')
            body=lamp.get_component_by_class(ue.StaticMeshComponent)
            geometry=body.static_mesh.get_editor_property('body_setup').get_editor_property('agg_geom')
            assert len(geometry.get_editor_property('box_elems'))==4
            assert body.is_simulating_physics() and abs(body.get_mass()-7.5)<.05
            assert (lamp.get_actor_location()-ue.Vector(140,-182,0)).length()<1
            assert len([actor for actor in all_parts if actor.get_actor_label() in ('Chair_2','Chair_3')])==1
            body.add_impulse_at_location(ue.Vector(900,0,0),lamp.get_actor_location()+ue.Vector(0,0,8))
            state['lamp_body']=body
            state['lamp']=lamp
            camera=ue.GameplayStatics.get_player_camera_manager(world,0)
            pc.set_control_rotation(ue.MathLibrary.find_look_at_rotation(camera.get_camera_location(),
                                                                        door.get_actor_location()))
            state['aim_at']=time.monotonic()+.2
            state['step']='door_aim'
        elif step=='door_aim':
            if time.monotonic()<state['aim_at']: return
            assert hud.get_editor_property('Focus')=='StreetDoor'
            keyed(world,pc,'E',True)
            state['open_at']=time.monotonic()+.2
            state['step']='door_opens'
        elif step=='door_opens':
            if time.monotonic()<state['open_at']: return
            if not state.get('released'):
                keyed(world,pc,'E',False)
                assert 0<hud.get_editor_property('StreetDoorProgress')<1
                state['released']=True
            if hud.get_editor_property('StreetDoorProgress')<.9999:
                assert time.monotonic()-state['open_at']<3,hud.get_editor_property('StreetDoorProgress')
                return
            moving,initial,pin,pin_initial=state['hinges']
            assert (moving.get_actor_location()-initial).length()>1
            assert (pin.get_actor_location()-pin_initial).length()<.01
            player=ue.GameplayStatics.get_player_character(world,0)
            player.set_actor_location(ue.Vector(-194,-648,player.get_actor_location().z),True,False)
            assert ue.PrologueWorldLibrary.is_outside_apartment(hud)
            assert player.get_actor_location().y<-640 and player.get_world()==world
            assert hud.get_editor_property('ReportFound')
            keyed(world,pc,'J',True)
            state['journal_at']=time.monotonic()
            state['step']='street_journal'
        elif step=='street_journal':
            journals=ue.WidgetLibrary.get_all_widgets_of_class(world,ue.JournalOverlayWidget,True)
            if not journals:
                assert time.monotonic()-state['journal_at']<3,hud.get_editor_property('JournalOpen')
                return
            assert pc.is_move_input_ignored() and pc.get_editor_property('show_mouse_cursor')
            keyed(world,pc,'J',False)
            hud.get_component_by_class(ue.JournalPresenterComponent).close_journal()
            assert not pc.is_move_input_ignored()
            ue.log('DIMA_PIE_STREET_OK: hinge parts move with the door, exit and journal in the same world')
            state['return_at']=time.monotonic()
            state['step']='walk_back'
        elif step=='walk_back':
            player=ue.GameplayStatics.get_player_character(world,0)
            if player.get_actor_location().y < -348:
                assert time.monotonic()-state['return_at']<3,player.get_actor_location()
                player.add_movement_input(ue.Vector(0,1,0),1,False)
                return
            assert not ue.PrologueWorldLibrary.is_outside_apartment(hud)
            player.get_component_by_class(ue.CharacterMovementComponent).stop_movement_immediately()
            player.set_actor_location(ue.Vector(-194,-497,100),False,True)
            hud.call_method('ActivateStreetDoor')
            state['close_at']=time.monotonic()+1.2
            state['step']='door_obstructed'
        elif step=='door_obstructed':
            if time.monotonic()<state['close_at']: return
            assert .02<hud.get_editor_property('StreetDoorProgress')<.99
            player=ue.GameplayStatics.get_player_character(world,0)
            player.set_actor_location(ue.Vector(132,340,100),False,True)
            state['sleep_at']=time.monotonic()+1
            state['choice']=0
            state['step']='sleep_menu'
        elif step=='sleep_menu':
            if time.monotonic()<state['sleep_at']: return
            hud.call_method('ActivateBed')
            windows=ue.WidgetLibrary.get_all_widgets_of_class(world,ue.DocumentWindow,True)
            menu,=[window for window in windows if window.get_choice_count()==4]
            assert menu.choose_option(state['choice']) and pc.is_move_input_ignored()
            state['step']='sleep_wait'
        elif step=='sleep_wait':
            clock=ue.GameplayStatics.get_actor_of_class(world,ue.PrologueTimeOfDay)
            if clock.is_asleep(): return
            hour=(6,12,18,0)[state['choice']]
            assert abs(clock.get_clock_hour()-hour)<.09 and not pc.is_move_input_ignored()
            if state['choice']<3:
                state['choice']+=1
                state['sleep_at']=time.monotonic()+.2
                state['step']='sleep_menu'
                return
            assert state['lamp_body'].get_physics_linear_velocity().length()<5
            assert (state['lamp'].get_actor_location()-ue.Vector(140,-182,0)).length()<55
            ue.log('DIMA_PIE_SLEEP_PHYSICS_OK: four wake times and the lamp settles after impulse')
            finish(True)
    except Exception:
        ue.log_error('DIMA_PIE_FAILED '+traceback.format_exc())
        finish(False)

state['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
