"""Apply the brick, two-map railway and doorway assets for 0.14.1."""
from datetime import datetime
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

root = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(root/"Tools"))
from BrightonStreetDetails import BlockLayout
from BrightonUpgrade import ACTORS, LEVELS, media
from CityLifeEnvironment import STREET_SHIFT, save_instance_material_usage
from IndustrialRail import replace_industrial_branch
from StreetMasonry import street_bricks

maps = ("L_NeptuneStreet","L_DimaApartmentInterior")
backup = root/"Saved/Backups"/("StreetRepairs_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(parents=True,exist_ok=True)
for name in maps:
    file = root/"Content/Locations"/(name+".umap")
    copy2(file,backup/file.name)

for file in sorted((root/"Resources/Audio/Doors").glob("S_*.wav")):
    imported = media(file,"/Game/Prologue/Brighton/Audio/Doors")
    assert isinstance(imported,ue.SoundWave) and imported.duration>.2,file

street_bricks()
models = {name:ue.load_asset("/Game/Prologue/CityLife/Meshes/SM_"+name)
          for name in ("RailStraight","FreightEngine","FreightGondola","FreightBoxcar")}
assert all(models.values())
for name in maps:
    assert LEVELS.load_level("/Game/Locations/"+name),name
    offset = STREET_SHIFT if name=="L_DimaApartmentInterior" else (0,0,0)
    replace_industrial_branch(BlockLayout(models,offset))
    if name=="L_NeptuneStreet":
        arrival, = [actor for actor in ACTORS.get_all_level_actors() if actor.actor_has_tag("FromApartment")]
        arrival.set_actor_rotation(ue.Rotator(yaw=-68),False)
    save_instance_material_usage()
    assert LEVELS.save_current_level(),name
    ue.log("FIX_MAP_OK "+name)
ue.log("FIX_APPLY_OK")
