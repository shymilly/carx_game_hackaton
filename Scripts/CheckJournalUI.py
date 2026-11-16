import unreal
if not unreal.JournalUILibrary.validate_journal_ui():
    raise RuntimeError('Journal selection/input validation failed')
for name in ('BP_PrologueHUD','BP_PrologueApartmentHUD','BP_PrologueStreetHUD'):
    if not unreal.JournalUILibrary.validate_journal_blueprint(unreal.load_asset('/Game/Prologue/'+name)):
        raise RuntimeError('Journal blueprint validation failed: '+name)
unreal.log('JOURNAL_UI_CHECK_PASSED')
