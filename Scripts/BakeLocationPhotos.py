"""Render the actual final maps and sign fronts; no image postprocessing or smoke edits."""
import time,traceback
from pathlib import Path
import unreal as ue
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
resources=root/'Resources/Presentation';resources.mkdir(parents=True,exist_ok=True)
reviews=root/'Saved/Reviews/StreetRefinement';reviews.mkdir(parents=True,exist_ok=True)
shots=[
 ('L_DimaApartmentInterior','T_Transition_Apartment',(30,-160,168),(-60,170,118),78,resources),
 ('L_PolicePrecinct','T_Transition_Precinct',(1602,-2725,170),(1110,-2860,133),80,resources),
 ('L_NeptuneStreet','T_Transition_Neptune',(-230,-645,178),(1900,-1450,330),82,resources),
 ('L_NeptuneStreet','Factory',(3000,-1425,3000),(5750,-1425,1380),105,reviews),
 ('L_NeptuneStreet','StreetOverview',(400,-550,220),(2300,-1450,280),84,reviews),
]
state=dict(deadline=time.monotonic()+210,index=0,stage='choose',signs_added=False,at=0,map=None)
ue.EditorPythonScripting.set_keep_python_script_alive(True)

def finish(ok):
    ue.unregister_slate_post_tick_callback(state['handle'])
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if ok:ue.log('REFINE_RENDER_PASSED')

def tick(delta):
    if state.get('busy'):return
    state['busy']=True
    try:
        assert time.monotonic()<state['deadline'],('Photo timeout',state['stage'],state['index'])
        if state['stage']=='choose':
            if state['index']>=len(shots):
                if not state['signs_added']:
                    state['signs_added']=True
                    for a in actors.get_all_level_actors():
                        text=next((str(t)[9:] for t in a.tags if str(t).startswith('SignText:')),None)
                        if not text:continue
                        p,e=a.get_actor_bounds(False)
                        normal=ue.MathLibrary.get_right_vector(a.get_actor_rotation())
                        distance=max(200,2*max(e.x,e.y)*1.25)
                        camera=p+normal*distance
                        shots.append(('L_NeptuneStreet','Sign_'+str(len(shots)),(camera.x,camera.y,camera.z),(p.x,p.y,p.z),58,reviews))
                        ue.log('REFINE_SIGN_VIEW '+str(len(shots)-1)+' '+text+' bounds='+str(e))
                if state['index']>=len(shots):state['stage']='import';return
            mapname,name,position,target,fov,folder=shots[state['index']]
            if state['map']!=mapname:
                assert levels.load_level('/Game/Locations/'+mapname)
                state['map']=mapname
            camera=actors.spawn_actor_from_class(ue.SceneCapture2D,ue.Vector(*position),ue.MathLibrary.find_look_at_rotation(ue.Vector(*position),ue.Vector(*target)))
            capture=camera.get_component_by_class(ue.SceneCaptureComponent2D)
            world=ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
            render=ue.RenderingLibrary.create_render_target2d(world,1280,720,ue.TextureRenderTargetFormat.RTF_RGBA8)
            capture.set_editor_properties(dict(fov_angle=fov,texture_target=render,capture_source=ue.SceneCaptureSource.SCS_FINAL_COLOR_LDR,capture_every_frame=False,capture_on_movement=False))
            post=capture.get_editor_property('post_process_settings')
            post.set_editor_properties(dict(override_auto_exposure_bias=True,auto_exposure_bias=2.0))
            capture.set_editor_property('post_process_settings',post)
            state['render']=render
            state['camera']=camera
            state['output']=folder/(name+'.png')
            state['at']=time.monotonic()+1
            state['stage']='capture'
        elif state['stage']=='capture':
            if time.monotonic()<state['at']:return
            world=ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
            state['camera'].get_component_by_class(ue.SceneCaptureComponent2D).capture_scene()
            state['at']=time.monotonic()+.35
            state['stage']='export'
        elif state['stage']=='export':
            if time.monotonic()<state['at']:return
            world=ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
            state['camera'].get_component_by_class(ue.SceneCaptureComponent2D).capture_scene()
            ue.RenderingLibrary.export_render_target(world,state['render'],str(state['output'].parent),state['output'].name)
            state['stage']='wait'
        elif state['stage']=='wait':
            if not state['output'].exists():return
            ue.log('REFINE_PHOTO '+str(state['output']))
            actors.destroy_actor(state.pop('camera'));state.pop('render')
            state['index']+=1;state['stage']='choose'
        else:
            import hashlib
            assert len({hashlib.sha256((resources/('T_Transition_'+name+'.png')).read_bytes()).hexdigest() for name in ('Apartment','Neptune','Precinct')})==3,'Destination photos must be distinct'
            tasks=[]
            for name in ('Apartment','Neptune','Precinct'):
                filename='T_Transition_'+name
                task=ue.AssetImportTask()
                task.set_editor_properties(dict(filename=str(resources/(filename+'.png')),destination_path='/Game/Prologue/Street/Transitions',destination_name=filename,automated=True,replace_existing=True,save=True))
                tasks.append(task)
            ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
            for name in ('Apartment','Neptune','Precinct'):
                t=ue.load_asset('/Game/Prologue/Street/Transitions/T_Transition_'+name)
                assert t
            # Temporary cameras were destroyed and no map is saved, preserving all authored transforms.
            finish(True)
    except Exception:
        ue.log_error('REFINE_RENDER_FAILED '+traceback.format_exc());finish(False)
    finally:
        state['busy']=False

state['handle']=ue.register_slate_post_tick_callback(tick)
