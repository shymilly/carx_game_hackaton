"""Refresh the eight loading-screen photographs from their actual destinations."""
from hashlib import sha256
from pathlib import Path
from shutil import copy2
import time
import traceback

import unreal as ue


ROOT = '/Game/Story/ActOne'
LEGACY = '/Game/Prologue/Street/Transitions'
PROJECT = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
OUT = PROJECT/'Saved/LoadingPhotographs'
OUT.mkdir(parents=True, exist_ok=True)
STORY = ('L_BrightonGrocery','L_LighthouseBar','L_FedorEntry','L_FedorApartment','L_BrightonAlley')
CLASSIC = {
    'L_DimaApartmentInterior': ('Apartment',(30,-160,168),(-60,170,118),78),
    'L_NeptuneStreet': ('Neptune',(-230,-645,178),(1900,-1450,330),82),
    'L_PolicePrecinct': ('Precinct',(1602,-2725,170),(1110,-2860,133),80),
}
MAPS = (*CLASSIC,*STORY)
ANGLES = {name: shot[1:] for name,shot in CLASSIC.items()}
ANGLES['L_FedorApartment'] = ((-398,37,168),(225,185,126),83)
levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
state = dict(index=0,stage='open',deadline=time.monotonic()+260,busy=False)


def photo_asset(name):
    if name in CLASSIC:
        return LEGACY,PROJECT/'Resources/Presentation'/('T_Transition_'+CLASSIC[name][0]+'.png')
    return ROOT+'/Art',PROJECT/'Resources/ActOne/Transitions'/('T_Act_'+name.removeprefix('L_')+'.png')


def import_photos():
    tasks = []
    plan = [photo_asset(name) for name in MAPS]
    paths = [OUT/path.name for _,path in plan]
    assert len({sha256(path.read_bytes()).digest() for path in paths}) == len(MAPS)
    for folder,path in plan:
        copy2(OUT/path.name,path)
        task = ue.AssetImportTask()
        task.set_editor_properties(dict(filename=str(path),destination_path=folder,
            destination_name=path.stem, automated=True, replace_existing=True, save=False))
        tasks.append(task)
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    data = ue.load_asset(ROOT+'/DA_ActOne')
    photos = {}
    for name,(folder,path) in zip(MAPS,plan):
        texture = ue.load_asset(folder+'/'+path.stem)
        assert texture, path
        texture.set_editor_properties(dict(lod_group=ue.TextureGroup.TEXTUREGROUP_UI,
            mip_gen_settings=ue.TextureMipGenSettings.TMGS_NO_MIPMAPS, never_stream=True))
        assert assets.save_loaded_asset(texture, False)
        if name in STORY:
            photos[ue.Name(name)] = texture
    data.set_editor_property('photos', photos)
    assert assets.save_loaded_asset(data, False)


def street_daylight(world_actors):
    clock = next(a for a in world_actors if isinstance(a,ue.PrologueTimeOfDay))
    sun = clock.get_editor_property('sun')
    sun.set_actor_rotation(ue.Rotator(pitch=-46,yaw=316),False)
    sun.get_component_by_class(ue.DirectionalLightComponent).set_intensity(3.5)
    sky = clock.get_editor_property('ambient_sky').get_component_by_class(ue.SkyLightComponent)
    sky.set_intensity(1.2)


def camera_pose(name,world_actors):
    if name in ANGLES:
        point,look,fov = ANGLES[name]
        position = ue.Vector(*point)
        return position,ue.MathLibrary.find_look_at_rotation(position,ue.Vector(*look)),fov
    view = next(a for a in world_actors if a.actor_has_tag('ActPhoto'))
    lens = view.get_component_by_class(ue.CameraComponent)
    return view.get_actor_location(),view.get_actor_rotation(),lens.get_editor_property('field_of_view')


def finish(success):
    ue.unregister_slate_post_tick_callback(state['handle'])
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if success:
        ue.log('ACT_ONE_PHOTOS_OK')


def tick(_delta):
    if state['busy']:
        return
    state['busy'] = True
    try:
        assert time.monotonic() < state['deadline'], state['stage']
        if state['index'] == len(MAPS):
            import_photos()
            finish(True)
            return
        name = MAPS[state['index']]
        output = OUT/photo_asset(name)[1].name
        if state['stage'] == 'open':
            output.unlink(missing_ok=True)
            assert levels.load_level('/Game/Locations/'+name), name
            world_actors = actors.get_all_level_actors()
            if name=='L_NeptuneStreet':
                street_daylight(world_actors)
            for actor in world_actors:
                if isinstance(actor,ue.ActOneCast):
                    actor.get_editor_property('character_mesh').set_update_animation_in_editor(True)
            position,rotation,fov = camera_pose(name,world_actors)
            camera = actors.spawn_actor_from_class(ue.SceneCapture2D,position,rotation)
            capture = camera.get_component_by_class(ue.SceneCaptureComponent2D)
            world = editor.get_editor_world()
            render = ue.RenderingLibrary.create_render_target2d(world,1280,720,ue.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
            capture.set_editor_properties(dict(fov_angle=fov,
                texture_target=render, capture_source=ue.SceneCaptureSource.SCS_FINAL_COLOR_LDR,
                capture_every_frame=False,capture_on_movement=False,always_persist_rendering_state=True))
            post = capture.get_editor_property('post_process_settings')
            post.set_editor_properties(dict(override_dynamic_global_illumination_method=True,
                dynamic_global_illumination_method=ue.DynamicGlobalIlluminationMethod.LUMEN,
                override_reflection_method=True,reflection_method=ue.ReflectionMethod.LUMEN,
                override_auto_exposure_bias=True,auto_exposure_bias=.65 if name=='L_NeptuneStreet' else 1.3))
            capture.set_editor_property('post_process_settings',post)
            state.update(camera=camera,render=render,at=time.monotonic()+1.3,stage='capture')
        elif state['stage']=='capture' and time.monotonic()>=state['at']:
            state['camera'].get_component_by_class(ue.SceneCaptureComponent2D).set_editor_property('capture_every_frame',True)
            state.update(at=time.monotonic()+4,stage='export')
        elif state['stage']=='export' and time.monotonic()>=state['at']:
            ue.RenderingLibrary.export_render_target(editor.get_editor_world(), state['render'], str(OUT), output.name)
            assert output.is_file() and output.stat().st_size > 2048, output
            actors.destroy_actor(state.pop('camera'))
            del state['render']
            ue.log('ACT_ONE_PHOTO '+name)
            state.update(index=state['index']+1, stage='open')
    except Exception:
        ue.log_error('ACT_ONE_PHOTOS_FAILED '+traceback.format_exc())
        finish(False)
    finally:
        state['busy'] = False


ue.EditorPythonScripting.set_keep_python_script_alive(True)
state['handle'] = ue.register_slate_post_tick_callback(tick)
