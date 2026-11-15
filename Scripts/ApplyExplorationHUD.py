"""Migrate existing HUD shortcuts; keep the original gameplay, journal and dialogue logic."""
from datetime import datetime
from pathlib import Path
import shutil
import unreal

root = Path(unreal.Paths.project_dir())
backup = root / 'Saved' / 'Backups' / ('ExplorationHUD_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True, exist_ok=True)
for name in ('BP_ApartmentHUD', 'BP_PrologueHUD'):
    disk = root / 'Content' / 'Prologue' / (name + '.uasset')
    shutil.copy2(disk, backup / disk.name)
    asset = unreal.load_asset('/Game/Prologue/' + name)
    count = unreal.ExplorationHUDLibrary.upgrade_exploration_hud(asset)
    expected = 2 if name == 'BP_ApartmentHUD' else 1
    if count not in (0, expected):
        raise RuntimeError('Unexpected upgrade/compile result for ' + name + ': ' + str(count))
    if count and not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Could not save ' + name)
    unreal.log('EXPLORATION_HUD_UPGRADED ' + name + ' shortcuts=' + str(count))
unreal.log('EXPLORATION_HUD_BACKUP ' + str(backup))
if not unreal.ExplorationHUDLibrary.validate_exploration_hud():
    raise RuntimeError('Exploration HUD regression failed')
unreal.log('EXPLORATION_HUD_CHECK_PASSED')
