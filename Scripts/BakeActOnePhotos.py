"""Capture and import loading-screen photographs from the five new maps."""
from hashlib import sha256
from pathlib import Path
import time
import traceback

import unreal as ue


ROOT = '/Game/Story/ActOne'
MAPS = ('L_BrightonGrocery', 'L_LighthouseBar', 'L_FedorEntry', 'L_FedorApartment', 'L_BrightonAlley')
OUT = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())) / 'Resources/ActOne/Transitions'
OUT.mkdir(parents=True, exist_ok=True)
levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
state = dict(index=0, stage='open', deadline=time.monotonic()+210, busy=False)


def file_for(map_name):
    return OUT / ('T_Act_'+map_name.removeprefix('L_')+'.png')


def import_photos():
    tasks = []
    paths = [file_for(name) for name in MAPS]
    assert len({sha256(path.read_bytes()).digest() for path in paths}) == len(MAPS)
    for path in paths:
        task = ue.AssetImportTask()
        task.set_editor_properties(dict(filename=str(path), destination_path=ROOT+'/Art',
            destination_name=path.stem, automated=True, replace_existing=True, save=False))
        tasks.append(task)
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    data = ue.load_asset(ROOT+'/DA_ActOne')
    photos = {}
    for name, path in zip(MAPS, paths):
        texture = ue.load_asset(ROOT+'/Art/'+path.stem)
        assert texture, path
        texture.set_editor_properties(dict(lod_group=ue.TextureGroup.TEXTUREGROUP_UI,
            mip_gen_settings=ue.TextureMipGenSettings.TMGS_NO_MIPMAPS, never_stream=True))
        assert assets.save_loaded_asset(texture, False)
        photos[ue.Name(name)] = texture
    data.set_editor_property('photos', photos)
    assert assets.save_loaded_asset(data, False)


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
        output = file_for(name)
        if state['stage'] == 'open':
            assert levels.load_level('/Game/Locations/'+name), name
            view = next(a for a in actors.get_all_level_actors() if a.actor_has_tag('ActPhoto'))
            camera = actors.spawn_actor_from_class(ue.SceneCapture2D, view.get_actor_location(), view.get_actor_rotation())
            capture = camera.get_component_by_class(ue.SceneCaptureComponent2D)
            world = editor.get_editor_world()
            render = ue.RenderingLibrary.create_render_target2d(world, 1280, 720, ue.TextureRenderTargetFormat.RTF_RGBA8)
            lens = view.get_component_by_class(ue.CameraComponent)
            capture.set_editor_properties(dict(fov_angle=lens.get_editor_property('field_of_view'),
                texture_target=render, capture_source=ue.SceneCaptureSource.SCS_FINAL_COLOR_LDR,
                capture_every_frame=False, capture_on_movement=False))
            state.update(camera=camera, render=render, at=time.monotonic()+1.2, stage='capture')
        elif time.monotonic() >= state['at']:
            state['camera'].get_component_by_class(ue.SceneCaptureComponent2D).capture_scene()
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
