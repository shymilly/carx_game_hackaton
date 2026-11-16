"""Create editable journal documents and replace only the old journal branch / control captions."""
import ast
from datetime import datetime
from pathlib import Path
import shutil
import unreal

root = Path(unreal.Paths.project_dir())
tree = ast.parse((root/'Tools/ApartmentGameplay.py').read_text(encoding='utf-8-sig'))
tables = {}
for node in tree.body:
    if isinstance(node,ast.Assign):
        for target in node.targets:
            if isinstance(target,ast.Name) and target.id in ('INTRO_DOCUMENTS','CLUES'):
                tables[target.id] = ast.literal_eval(node.value)
records = tables['INTRO_DOCUMENTS'] + tables['CLUES'][:2]
tools = unreal.AssetToolsHelpers.get_asset_tools()

def data_asset(path, cls):
    value = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if value:
        if not isinstance(value,cls):
            raise RuntimeError('Unexpected asset type: ' + path)
        return value, False
    folder,name = path.rsplit('/',1)
    factory = unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class',cls)
    value = tools.create_asset(name,folder,cls,factory)
    if not value:
        raise RuntimeError('Could not create ' + path)
    return value, True

def save(asset):
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=False):
        raise RuntimeError('Could not save ' + asset.get_path_name())

catalog,created = data_asset('/Game/UI/Journal/DA_JournalCatalog',unreal.JournalCatalog)
entries = list(catalog.get_editor_property('entries'))
existing = {str(e.get_editor_property('discovery_flag')) for e in entries}
for tag,title,body in records:
    flag = tag+'Found'
    if flag in existing:
        continue
    document,is_new = data_asset('/Game/UI/Journal/Documents/DA_'+tag,unreal.InteractionDocument)
    if is_new:
        document.set_editor_property('title',title)
        document.set_editor_property('body',body)
        document.set_editor_property('close_label','Назад к записям')
        save(document)
    entry = unreal.JournalEntry()
    entry.set_editor_property('discovery_flag',unreal.Name(flag))
    entry.set_editor_property('document',document)
    entries.append(entry)
catalog.set_editor_property('entries',entries)
save(catalog)

backup = root/'Saved'/'Backups'/('JournalUI_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True,exist_ok=True)
for name in ('BP_ApartmentHUD','BP_PrologueHUD','BP_PrologueApartmentHUD'):
    path = '/Game/Prologue/'+name
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError('HUD missing: '+path)
    shutil.copy2(root/'Content'/'Prologue'/(name+'.uasset'),backup/(name+'.uasset'))
    changed = unreal.JournalUILibrary.upgrade_journal_ui(asset)
    if changed < 0:
        raise RuntimeError('Blueprint compilation failed: '+name)
    if changed:
        save(asset)
    if name != 'BP_ApartmentHUD' and not unreal.JournalUILibrary.validate_journal_blueprint(asset):
        raise RuntimeError('Old journal branch is still reachable or discovery flags are missing: '+name)
    unreal.log('JOURNAL_UI_UPGRADED '+name+' changes='+str(changed))
if not unreal.JournalUILibrary.validate_journal_ui():
    raise RuntimeError('Journal selection/input regression failed')
unreal.log('JOURNAL_UI_CHECK_PASSED: discovered-only selection, digits disabled, J/Esc navigation, shared reader close callback')
unreal.log('JOURNAL_UI_BACKUP '+str(backup))
