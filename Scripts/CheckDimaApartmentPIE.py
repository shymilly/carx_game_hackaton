"""Run with -ExecutePythonScript (full editor): exercise the real PIE HUD, widgets and locks."""
import json,time,traceback
from pathlib import Path
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
spec=json.loads((root/'Docs/Scenario/DimaApartment.json').read_text(encoding='utf-8'))
documents={row['id']:row for row in spec['documents']}
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assert levels.load_level('/Game/Prologue/'+spec['apartment_map'])
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
        if step=='start':
            assert hud.get_editor_property('State')==9,('Expected initial report',hud.get_editor_property('State'))
            assert story.get_phase()==ue.DimaApartmentPhase.AWAITING_REPORT
            hud.call_method('FinishReport')
            state['step']='explore'
        elif step=='explore':
            if story.get_phase()!=ue.DimaApartmentPhase.EXPLORING: return
            assert not pc.is_move_input_ignored()
            ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('Phone'))
            assert story.get_phase()==ue.DimaApartmentPhase.EXPLORING
            assert ue.DimaApartmentStoryLibrary.try_interact(hud,ue.Name('Exit'))
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
            finish(True)
    except Exception:
        ue.log_error('DIMA_PIE_FAILED '+traceback.format_exc())
        finish(False)

state['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
