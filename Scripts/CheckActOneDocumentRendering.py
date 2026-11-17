"""Render the real shared widgets for visual verification of text and portrait layout."""
from pathlib import Path
import time
import traceback

import unreal as ue

levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))/'Saved/ActOne'
root.mkdir(parents=True,exist_ok=True)
names=('BrightonNewspaper','FedorMissing','FedorPhoto','CaptainKGB','Credits')
state=dict(deadline=time.monotonic()+30,index=0,stage='open',busy=False)

def finish(success):
    ue.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if success:ue.log('ACT_ONE_DOCUMENTS_OK')

def tick(delta):
    if state['busy']:return
    state['busy']=True
    try:
        assert time.monotonic()<state['deadline'],state['stage']
        world=editor.get_game_world()
        player=ue.GameplayStatics.get_player_controller(world,0) if world else None
        if not player or not player.get_hud():return
        instance=ue.GameplayStatics.get_game_instance(world)
        ui=next(obj for obj in ue.ObjectIterator(ue.NarrativeSubsystem) if obj.get_outer()==instance)
        name=names[state['index']]
        if state['stage']=='open':
            document=ue.load_asset('/Game/Story/ActOne/Documents/D_'+name)
            assert ui.show_document(player,document,None),name
            state.update(stage='draw',at=time.monotonic()+.12)
        elif time.monotonic()>=state['at']:
            window=ue.WidgetLibrary.get_all_widgets_of_class(world,ue.DocumentWindow,True)[0]
            for _ in range(3):
                assert ue.ActOneBlueprintLibrary.capture_editor_document(window,str(root/(name+'.png')))
            ui.close_document()
            state.update(stage='open',index=state['index']+1)
            if state['index']==len(names):finish(True)
    except Exception:
        ue.log_error('ACT_ONE_DOCUMENTS_FAILED '+traceback.format_exc())
        finish(False)
    finally:
        state['busy']=False

assert levels.load_level('/Game/Locations/L_NeptuneStreet')
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
