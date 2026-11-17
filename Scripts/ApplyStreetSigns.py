"""Import the Blender lettering and update only the street and precinct signs."""
from datetime import datetime
from pathlib import Path
import json
import shutil
import sys

import unreal as ue

root = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(root / "Tools"))
from RefineStreetVisuals import ACTORS, SIGNS, audit, typography

levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
backup = root / "Saved/Backups" / ("BilingualSigns_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(parents=True)
for name in ("L_NeptuneStreet", "L_PolicePrecinct"):
    shutil.copy2(root / "Content/Locations" / (name + ".umap"), backup)

assert levels.load_level("/Game/Locations/L_NeptuneStreet")
assert typography(ACTORS.get_all_level_actors(), reimport=True) == set(SIGNS)
report = audit()
assert {item["text"]: item["font"] for item in report["signs"]} == {s.text: s.family for s in SIGNS.values()}
assert levels.save_current_level()

assert levels.load_level("/Game/Locations/L_PolicePrecinct")
assert typography(ACTORS.get_all_level_actors(), storefronts=False) == {"SM_NeighborhoodPrecinct"}
assert levels.save_current_level()

(root / "Resources/StreetRefinement/VisualAudit.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
ue.log("BILINGUAL_SIGN_INSTALL_OK")
