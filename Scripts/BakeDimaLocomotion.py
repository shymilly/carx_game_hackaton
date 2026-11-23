"""Remove exported locomotion travel from the Drifter's pelvis tracks."""
import unreal as ue


assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
profile = ue.load_asset('/Game/Prologue/Characters/HollowNightDrifter/DA_DimaDrifter')
mesh = profile.get_editor_property('mesh')
motions = profile.get_editor_property('motions')

for name in ('Walk', 'Run'):
    clip = motions[ue.Name(name)]
    before = ue.CityCharacterAuthoring.pose_bone_position(mesh, clip, 'Hips', 0)
    end = ue.CityCharacterAuthoring.pose_bone_position(mesh, clip, 'Hips', clip.get_play_length())
    assert ue.CityCharacterAuthoring.remove_locomotion_travel(mesh, clip, 'Hips'), name
    for index in range(33):
        time = clip.get_play_length() * index / 32
        hips = ue.CityCharacterAuthoring.pose_bone_position(mesh, clip, 'Hips', time)
        assert abs(hips.y - before.y) < 2.5, (name, time, hips)
    assert assets.save_loaded_asset(clip, False), name
    ue.log(f'MOTION_IN_PLACE {name} removed {end.y - before.y:.1f} cm per cycle')
