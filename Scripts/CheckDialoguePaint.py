import unreal
if not unreal.DialoguePresentationLibrary.validate_dialogue_painting():
    raise RuntimeError('Dialogue OnPaint regression failed')
unreal.log('DIALOGUE_PAINT_REGRESSION_PASSED: five panel sizes')
