import unreal

if not unreal.ExplorationHUDLibrary.validate_exploration_hud():
    raise RuntimeError('Exploration tutorial or notebook paint regression failed')
unreal.log('EXPLORATION_HUD_CHECK_PASSED: six required keys, duplicates, unrelated keys, both Shifts, notebook paint')
