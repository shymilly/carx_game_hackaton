"""Run via Unreal Python after compiling the module. Changes only old dialogue drawing calls."""
from datetime import datetime
from pathlib import Path
import shutil
import unreal

root = Path(unreal.Paths.project_dir())
backup = root / 'Saved' / 'Backups' / ('DialogueStyle_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True, exist_ok=True)
for name in ('BP_ApartmentHUD', 'BP_PrologueHUD'):
    disk_path = root / 'Content' / 'Prologue' / (name + '.uasset')
    shutil.copy2(disk_path, backup / disk_path.name)
    asset = unreal.load_asset('/Game/Prologue/' + name)
    count = unreal.DialoguePresentationLibrary.upgrade_legacy_hud(asset)
    if count < 0:
        raise RuntimeError('Dialogue upgrade failed to compile: ' + name)
    if count and not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Could not save: ' + name)
    unreal.log('DIALOGUE_UPGRADED ' + name + ' panels=' + str(count))
unreal.log('DIALOGUE_BACKUP ' + str(backup))
