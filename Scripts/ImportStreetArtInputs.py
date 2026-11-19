from pathlib import Path
import unreal as ue
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
for name in ('S_TrafficHorn','S_TrafficDriveBy'):
 task=ue.AssetImportTask();task.set_editor_properties(dict(filename=str(root/'Resources/Audio/Traffic'/(name+'.mp3')),destination_path='/Game/Audio/Traffic',destination_name=name,automated=True,replace_existing=False,save=True))
 ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
 wave=ue.load_asset('/Game/Audio/Traffic/'+name)
 assert isinstance(wave,ue.SoundWave),(name,task.get_objects())
 wave.set_editor_property('looping',False)
 assert ue.get_editor_subsystem(ue.EditorAssetSubsystem).save_loaded_asset(wave,False)
 ue.log('STREET_ART_AUDIO_IMPORTED '+name+' duration='+str(wave.get_editor_property('duration')))
task=ue.AssetImportTask();task.set_editor_properties(dict(filename=str(root/'Resources/StreetArtPass/T_BeaconSign.png'),destination_path='/Game/StreetArtPass/Textures',automated=True,save=True))
ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
assert ue.load_asset('/Game/StreetArtPass/Textures/T_BeaconSign')
ue.log('STREET_ART_INPUTS_PASSED')
