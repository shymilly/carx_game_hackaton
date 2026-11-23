"""Save the revised maps and animation assets through the Unreal Editor."""
from pathlib import Path
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project / "Tools"))

from ActOneSceneCorrections import bar, collision_repairs, exterior, fedor, finale, grocery, grocery_models, recorder_animation
from BrightonUpgrade import LEVELS


recorder_animation()
grocery_models()
for map_name, repair in (("L_BrightonGrocery",grocery), ("L_FedorApartment",fedor),
                         ("L_DimaApartmentInterior",finale), ("L_LighthouseBar",bar)):
    assert LEVELS.load_level("/Game/Locations/" + map_name), map_name
    repair()
    if map_name in ("L_FedorApartment","L_LighthouseBar"):
        collision_repairs(map_name)
    assert LEVELS.save_current_level(), map_name
    ue.log("SCENE_CORRECTION_SAVED " + map_name)

for map_name in ("L_NeptuneStreet","L_FedorEntry","L_BrightonAlley"):
    assert LEVELS.load_level("/Game/Locations/" + map_name), map_name
    exterior(map_name)
    collision_repairs(map_name)
    assert LEVELS.save_current_level(), map_name
    ue.log("SCENE_CORRECTION_SAVED " + map_name)

assert LEVELS.load_level("/Game/Locations/L_PolicePrecinct")
collision_repairs("L_PolicePrecinct")
assert LEVELS.save_current_level()
ue.log("SCENE_CORRECTION_SAVED L_PolicePrecinct")

ue.log("SCENE_CORRECTION_ASSETS_OK")
