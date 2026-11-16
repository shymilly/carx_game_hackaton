"""Run in Unreal Python with the editor closed; adds story assets/proxies, preserving scene visuals."""
from datetime import datetime
from pathlib import Path
import json
import shutil
import sys
import unreal as ue

root = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
spec = json.loads((root/'Docs/Scenario/DimaApartment.json').read_text(encoding='utf-8'))
folder = '/Game/Story/DimaApartment'
hud_path = folder+'/BP_DimaApartmentStoryHUD'
map_path = '/Game/Prologue/'+spec['apartment_map']
assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
tools = ue.AssetToolsHelpers.get_asset_tools()
levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)

backup = root/'Saved/Backups'/('DimaScenario_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True, exist_ok=True)
existing = [root/'Content/Prologue'/f"{spec['apartment_map']}.umap",
            root/'Content/FirstPerson/Blueprints/BP_FirstPersonGameMode.uasset']
for subfolder in ('Story/DimaApartment','Audio/DimaApartment'):
    existing.extend((root/'Content'/subfolder).rglob('*.uasset'))
for path in existing:
    destination=backup/path.relative_to(root)
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,destination)
ue.log('DIMA_SCENARIO_BACKUP '+str(backup))

def save(asset):
    if not assets.save_loaded_asset(asset, False):
        raise RuntimeError('Could not save '+asset.get_path_name())

def data_asset(path, cls):
    value=ue.load_asset(path) if assets.does_asset_exist(path) else None
    if value:
        if not isinstance(value,cls):
            raise RuntimeError('Unexpected type: '+path)
        return value
    parent,name=path.rsplit('/',1)
    factory=ue.DataAssetFactory()
    factory.set_editor_property('data_asset_class',cls)
    value=tools.create_asset(name,parent,cls,factory)
    if not value:
        raise RuntimeError('Cannot create '+path)
    return value

sounds={}
for entry in spec['audio']:
    destination='/Game/Audio/DimaApartment/'+entry['asset']
    sound=ue.load_asset(destination) if assets.does_asset_exist(destination) else None
    if sound is None:
        task=ue.AssetImportTask()
        task.set_editor_properties(dict(filename=str(root/'Resources/Audio/DimaApartment'/entry['source']),
            destination_path='/Game/Audio/DimaApartment',destination_name=entry['asset'],
            automated=True,save=True,replace_existing=False))
        tools.import_asset_tasks([task])
        sound=ue.load_asset(destination)
    if not isinstance(sound,ue.SoundWave) or sound.get_editor_property('duration') <= 0:
        raise RuntimeError('Audio import failed: '+entry['source'])
    sound.set_editor_property('looping',True)
    save(sound)
    sounds[entry['role']]=sound
    ue.log('DIMA_AUDIO_IMPORTED '+entry['asset']+' duration='+str(sound.get_editor_property('duration')))

documents={}
for entry in spec['documents']:
    document=data_asset(folder+'/Documents/DA_'+entry['id'],ue.InteractionDocument)
    document.set_editor_properties(dict(title=entry['title'],body=entry['body'],
        close_label='Продолжить · E / клик'))
    save(document)
    documents[entry['id']]=document

scenario=data_asset(folder+'/DA_DimaApartmentScenario',ue.DimaApartmentScenario)
scenario.set_editor_properties(dict(apartment_map=ue.Name(spec['apartment_map']),
    required_inspections=[ue.Name(tag) for tag in spec['required_inspections']],
    television=documents['Television'],fridge=documents['Fridge'],wardrobe=documents['Wardrobe'],
    floor_lamp=documents['FloorLamp'],ring_notice=documents['RingNotice'],
    phone_conversation=[documents[f'Phone{i:02}'] for i in range(1,10)],
    ambient=sounds['ambient'],phone_ring=sounds['phone_ring'],wash_water=sounds['wash_water'],
    explore_objective=spec['explore_objective'],phone_objective=spec['phone_objective'],
    exit_objective=spec['exit_objective'],wash_duration=spec['wash_duration']))
# Preserve an assigned StreetMap when the content script is rerun.
save(scenario)

sys.path.insert(0,str(root/'Tools'))
# The existing graph generator resolves editor menu actions by their English identifiers.
# This commandlet-local culture change is not saved to the team's editor preferences.
ue.InternationalizationLibrary.set_current_culture('en',False)
from ApartmentGameplay import build_gameplay
if not assets.does_asset_exist(hud_path):
    build_gameplay(folder,'BP_DimaApartmentStoryHUD')
else:
    # Do not overwrite hand-edited Blueprint graphs on a repeated import.
    mode=ue.load_asset('/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode')
    ue.get_default_object(ue.BlueprintEditorLibrary.generated_class(mode)).set_editor_property(
        'hud_class',ue.BlueprintEditorLibrary.generated_class(ue.load_asset(hud_path)))
    save(mode)

if not levels.load_level(map_path):
    raise RuntimeError('Cannot load apartment: '+map_path)
placed={actor.get_actor_label():actor for actor in actors.get_all_level_actors()}
targets=[('Wardrobe','Wardrobe shelves',ue.Vector(30,72,100)),
         ('Television','Curved CRT screen',ue.Vector(6,28,22)),
         ('Phone','SM_Telephone',ue.Vector(14,16,12))]
for tag,label,minimum in targets:
    source=placed.get(label)
    if not source:
        raise RuntimeError('Missing story prop: '+label)
    proxy_label='Story focus '+tag
    proxy=placed.get(proxy_label)
    center,extent=source.get_actor_bounds(False)
    extent=ue.Vector(max(extent.x+2,minimum.x),max(extent.y+2,minimum.y),max(extent.z+2,minimum.z))
    if proxy is None:
        proxy=actors.spawn_actor_from_class(ue.DimaStoryFocusProxy,center)
    if not isinstance(proxy,ue.DimaStoryFocusProxy):
        raise RuntimeError('Unexpected focus actor type: '+proxy_label)
    proxy.set_actor_label(proxy_label)
    proxy.set_folder_path(ue.Name('Story interactions'))
    proxy.set_actor_location(center,False,False)
    proxy.set_editor_property('tags',[ue.Name(tag)])
    proxy.set_editor_property('source_actor',source)
    proxy.get_editor_property('focus_box').set_box_extent(extent,False)
    tag_sources=[source]
    if tag=='Wardrobe' and 'Wardrobe shelves collision' in placed:
        tag_sources.append(placed['Wardrobe shelves collision'])
    if tag=='Television' and 'Molded CRT case' in placed:
        tag_sources.append(placed['Molded CRT case'])
    for obj in tag_sources:
        tags=list(obj.tags)
        if ue.Name(tag) not in tags:
            obj.set_editor_property('tags',tags+[ue.Name(tag)])
if not levels.save_current_level():
    raise RuntimeError('Could not save apartment story bindings')

exec((root/'Scripts/CheckDimaApartmentScenario.py').read_text(encoding='utf-8'),{'__file__':str(root/'Scripts/CheckDimaApartmentScenario.py')})
ue.log('DIMA_APARTMENT_SCENARIO_APPLIED')
