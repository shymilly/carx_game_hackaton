"""Full PIE travel test. Keep no UObjects between ticks so OpenLevel can collect the old world."""
import time,traceback
import unreal as ue
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assert levels.load_level('/Game/Locations/L_DimaApartmentInterior')
ue.EditorPythonScripting.set_keep_python_script_alive(True)
s=dict(step='report',deadline=time.monotonic()+65,page=0,route=0)
routes=[('L_NeptuneStreet',(-194,-552,101)),('L_PolicePrecinct',(1602,-2725,101)),
        ('L_NeptuneStreet',(1730,-2725,101)),('L_DimaApartmentInterior',(-194,-330,98))]

def document(world):
    return ue.WidgetLibrary.get_all_widgets_of_class(world,ue.DimaStoryDialogueWindow,True)[0]
def key(world,pc,value,down):
    ue.SystemLibrary.execute_console_command(world,'Input.'+('+' if down else '-')+'key '+value,pc)
def place(pc,pos,yaw):
    pawn=ue.GameplayStatics.get_player_pawn(pc,0)
    pawn.get_component_by_class(ue.CharacterMovementComponent).stop_movement_immediately()
    pawn.set_actor_location(ue.Vector(*pos),False,True)
    pc.set_control_rotation(ue.Rotator(pitch=0,yaw=yaw,roll=0))
def end(ok):
    ue.unregister_slate_post_tick_callback(s['handle'])
    levels.editor_request_end_play()
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if ok: ue.log('LEVEL_TRAVEL_PIE_PASSED')

def tick(delta):
    try:
        assert time.monotonic()<s['deadline'],('Timeout',s)
        world=editor.get_game_world()
        if not world:return
        pc=ue.GameplayStatics.get_player_controller(world,0)
        hud=pc.get_hud() if pc else None
        if not hud:return
        # NullRHI skips viewport rendering; deliver the real HUD event explicitly.
        if hud.get_editor_property('State')==-1 or s['step'] in ('door','pressed','jump','jump_wait'):
            hud.call_method('ReceiveDrawHUD',(1280,720))
        if s.get('logged')!=s['step']:
            ue.log('LEVEL_STEP '+s['step']+' route='+str(s['route']))
            s['logged']=s['step']
        story=hud.get_component_by_class(ue.DimaApartmentStoryComponent)
        instance=ue.GameplayStatics.get_game_instance(world)
        ui=next(obj for obj in ue.ObjectIterator(ue.NarrativeSubsystem) if obj.get_outer()==instance)
        level=ue.GameplayStatics.get_current_level_name(world,True)
        step=s['step']
        if step=='report':
            assert hud.get_editor_property('State')==9
            hud.call_method('FinishReport')
            s['wait']=time.monotonic()+.8
            s['step']='explore'
        elif step=='explore':
            if time.monotonic()<s['wait']:return
            assert story.get_phase()==ue.DimaApartmentPhase.EXPLORING
            ue.DimaApartmentStoryLibrary.try_interact(hud,'StreetDoor')
            assert not ui.is_location_transition_active(),'Door bypassed the phone story gate'
            ue.DimaApartmentStoryLibrary.try_interact(hud,'Wardrobe')
            document(world).request_close()
            s['step']='television'
        elif step in ('television','lamp'):
            ue.DimaApartmentStoryLibrary.try_interact(hud,'Television' if step=='television' else 'FloorLamp')
            document(world).request_close()
            s['step']='lamp' if step=='television' else 'fridge'
        elif step=='fridge':
            assert not ue.DimaApartmentStoryLibrary.try_interact(hud,'FridgeDoor')
            hud.call_method('ActivateFridgeDoor')
            s['step']='fridge_wait'
        elif step=='fridge_wait':
            if not story.is_busy():return
            document(world).request_close()
            ue.DimaApartmentStoryLibrary.try_interact(hud,'Tap')
            s['step']='wash'
        elif step=='wash':
            if story.get_phase()!=ue.DimaApartmentPhase.RINGING:return
            document(world).request_close()
            ue.DimaApartmentStoryLibrary.try_interact(hud,'Phone')
            s['step']='phone'
        elif step=='phone':
            assert pc.is_move_input_ignored()
            document(world).request_close()
            s['page']+=1
            if s['page']==9:s['step']='sleep'
        elif step=='sleep':
            assert story.get_phase()==ue.DimaApartmentPhase.READY_TO_EXIT
            place(pc,(120,200,98),0)
            s['wait']=time.monotonic()+.3
            s['step']='sleep_menu'
        elif step=='sleep_menu':
            if time.monotonic()<s['wait']:return
            ue.PrologueWorldLibrary.open_bed_menu(hud)
            windows=ue.WidgetLibrary.get_all_widgets_of_class(world,ue.DocumentWindow,True)
            assert len(windows)==1
            assert windows[0].choose_option(0)
            s['step']='sleep_wait'
        elif step=='sleep_wait':
            clock=ue.GameplayStatics.get_actor_of_class(world,ue.PrologueTimeOfDay)
            if clock.is_asleep():return
            assert clock.get_day_index()==1
            key(world,pc,'SpaceBar',True)
            s['step']='jump'
        elif step=='jump':
            key(world,pc,'SpaceBar',False)
            s['wait']=time.monotonic()+.15
            s['step']='jump_wait'
        elif step=='jump_wait':
            if time.monotonic()<s['wait']:return
            assert hud.get_editor_property('Stamina')<95,'Jump did not consume stamina'
            place(pc,(-194,-330,98),-90)
            s['wait']=time.monotonic()+.3
            s['step']='door'
        elif step=='door':
            if time.monotonic()<s['wait']:return
            expected='StreetDoor' if s['route']==0 else 'StreetPortal'
            assert str(hud.get_editor_property('Focus'))==expected,('Door is not focusable',s['route'],hud.get_editor_property('Focus'),pc.get_control_rotation())
            key(world,pc,'E',True)
            s['pressed_at']=time.monotonic()
            s['step']='pressed'
        elif step=='pressed':
            if not ui.is_location_transition_active():
                assert time.monotonic()-s['pressed_at']<2,('E did not trigger travel',s['route'],hud.get_editor_property('InteractHeld'),hud.get_editor_property('InteractPressed'),[(p.get_actor_label(),str(p.get_editor_property('destination_map'))) for p in ue.GameplayStatics.get_all_actors_of_class(world,ue.StreetPortal)])
                return
            key(world,pc,'E',False)
            assert pc.is_move_input_ignored() and pc.is_look_input_ignored()
            assert ui.get_location_photo() is not None
            s['captured_stamina']=hud.get_editor_property('Stamina')
            s['source']=world.get_path_name()
            s['step']='travel'
        elif step=='travel':
            expected,pos=routes[s['route']]
            if level!=expected or ui.is_location_transition_active():return
            assert world.get_path_name()!=s['source'],'Transition did not replace the world'
            assert hud.get_editor_property('State')==0,'Replayed the report on arrival'
            assert hud.get_editor_property('ReportFound') and not hud.get_editor_property('NewspaperFound')
            assert abs(hud.get_editor_property('Stamina')-s['captured_stamina'])<4
            assert not pc.is_move_input_ignored() and not pc.is_look_input_ignored()
            assert ue.GameplayStatics.get_actor_of_class(world,ue.PrologueTimeOfDay).get_day_index()==1
            assert ue.GameplayStatics.get_player_pawn(pc,0).get_actor_location().distance(ue.Vector(*pos))<110
            ue.log('LEVEL_TRAVEL_OK '+s['source']+' -> '+level+' journal/time/stamina preserved')
            s['route']+=1
            if s['route']==4:
                assert story.get_phase()==ue.DimaApartmentPhase.READY_TO_EXIT
                assert not story.is_busy()
                end(True)
                return
            if s['route']==1: place(pc,(1730,-2725,101),180)
            elif s['route']==2: place(pc,(1602,-2725,101),0)
            else: place(pc,(-194,-560,101),90)
            s['wait']=time.monotonic()+.3
            s['step']='door'
    except Exception:
        ue.log_error('LEVEL_TRAVEL_FAILED '+traceback.format_exc())
        end(False)

s['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
