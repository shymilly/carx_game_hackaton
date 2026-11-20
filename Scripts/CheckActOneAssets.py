"""Validate all authored story text, sound, journal, maps and UI regressions."""
from pathlib import Path
import json
import runpy

import unreal as ue


root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
spec=json.loads((root/'Docs/Scenario/ActOne.json').read_text(encoding='utf-8'))
data=ue.load_asset('/Game/Story/ActOne/DA_ActOne')
assert data
documents=data.get_editor_property('documents')
assert len(documents)==len(spec['documents'])
for key,source in spec['documents'].items():
    document=documents[ue.Name(key)]
    for field in ('title','body'):
        assert str(document.get_editor_property(field))==source[field],(key,field)
    if source.get('illustration'):
        assert document.get_editor_property('illustration'),key
    if source.get('layout')=='newspaper':
        for index,article in enumerate(document.get_editor_property('articles')):
            for field,value in source['articles'][index].items():
                assert str(article.get_editor_property(field))==value,(key,index,field)
for name,sound in data.get_editor_property('sounds').items():
    assert isinstance(sound,ue.SoundWave) and sound.get_editor_property('duration')>0,name
registry=ue.AssetRegistryHelpers.get_asset_registry()
assert not any(str(asset.asset_name).startswith('Voice_')
               for asset in registry.get_assets_by_path('/Game/Story/ActOne/Audio',recursive=True)), 'Legacy TTS packages'
photos=data.get_editor_property('photos')
assert len(photos)==5
for area in ('Grocery','Bar','Entrance','Fedor','Alley'):
    assert photos[ue.Name(spec['levels'][area])],area
catalog=ue.load_asset('/Game/UI/Journal/DA_JournalCatalog')
entries=catalog.get_editor_property('entries')
flags=[str(entry.get_editor_property('discovery_flag')) for entry in entries]
assert len(flags)==len(set(flags)), 'Duplicate journal entries'
assert all(key in flags for key in spec['journal'])
for script in ('CheckDialoguePaint.py','CheckExplorationHUD.py','CheckJournalUI.py',
               'CheckDimaApartmentScenario.py','CheckSeparateLocationMaps.py'):
    runpy.run_path(str(root/'Scripts'/script),run_name='__main__')
ue.log('ACT_ONE_ASSETS_OK')
