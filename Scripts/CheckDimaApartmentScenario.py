"""Validate imported script/audio, completion gates and active map/HUD without changing content."""
from pathlib import Path
import json
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
spec=json.loads((root/'Docs/Scenario/DimaApartment.json').read_text(encoding='utf-8'))
folder='/Game/Story/DimaApartment'
if not ue.DimaApartmentStoryLibrary.validate_scenario():
    raise RuntimeError('Story prerequisite/audio validation failed')
scenario=ue.load_asset(folder+'/DA_DimaApartmentScenario')
if [str(tag) for tag in scenario.get_editor_property('required_inspections')]!=spec['required_inspections']:
    raise RuntimeError('Required inspection list differs from the source script')
for entry in spec['audio']:
    sound=ue.load_asset('/Game/Audio/DimaApartment/'+entry['asset'])
    if not isinstance(sound,ue.SoundWave) or sound.get_editor_property('duration')<=0 or not sound.get_editor_property('looping'):
        raise RuntimeError('Invalid looping audio: '+entry['asset'])
if not issubclass(ue.DimaStoryDialogueWindow,ue.DocumentWindow):
    raise RuntimeError('Story dialogue must use the approved shared window')
for entry in spec['documents']:
    doc=ue.load_asset(folder+'/Documents/DA_'+entry['id'])
    if not doc or str(doc.get_editor_property('body')) != entry['body'] or str(doc.get_editor_property('title')) != entry['title']:
        raise RuntimeError('Script text mismatch: '+entry['id'])
hud=ue.load_asset(folder+'/BP_DimaApartmentStoryHUD')
if not ue.JournalUILibrary.validate_journal_blueprint(hud):
    raise RuntimeError('Mouse journal regression in story HUD')
if not ue.BlueprintEditorLibrary.compile_blueprint(hud):
    raise RuntimeError('Story HUD compilation failed')
mode=ue.load_asset('/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode')
defaults=ue.get_default_object(ue.BlueprintEditorLibrary.generated_class(mode))
if defaults.get_editor_property('hud_class') != ue.BlueprintEditorLibrary.generated_class(hud):
    raise RuntimeError('GameMode is not using the story HUD')
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
if not levels.load_level('/Game/Prologue/'+spec['apartment_map']):
    raise RuntimeError('Missing apartment map')
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
for tag in spec['required_inspections']+['Phone','Exit']:
    if not any(actor.actor_has_tag(ue.Name(tag)) for actor in actors):
        raise RuntimeError('Missing interaction target: '+tag)
for tag in ('Wardrobe','Television','Phone'):
    proxies=[actor for actor in actors if isinstance(actor,ue.DimaStoryFocusProxy) and actor.actor_has_tag(ue.Name(tag))]
    if len(proxies)!=1 or proxies[0].get_editor_property('source_actor') is None:
        raise RuntimeError('Invalid focus proxy: '+tag)
ue.log('DIMA_SCENARIO_CHECK_PASSED: exact text, 5 prerequisites, duplicate/early inputs, 9 phone pages, looping audio, mouse journal, map targets')
