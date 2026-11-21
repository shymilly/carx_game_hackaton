"""Update only the residential entrances in the live street and its apartment view."""
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(project/'Tools'))
from BrightonEntrances import FACADES, TAG, build_entries, clear_old_entries, saved_anchors
from BrightonEntranceMeshes import make_entry_meshes
from BrightonOuterBlocks import OuterBlocks
from BrightonUpgrade import ACTORS, LEVELS
from CityLifeEnvironment import STREET_SHIFT


backup = project/'Saved/Backups/BrightonEntrances'
backup.mkdir(parents=True,exist_ok=True)
meshes = make_entry_meshes()
for name, shift in (('L_NeptuneStreet',(0,0,0)), ('L_DimaApartmentInterior',STREET_SHIFT)):
    package = name+'.umap'
    if not (backup/package).exists():
        copy2(project/'Content/Locations'/package,backup/package)
    assert LEVELS.load_level('/Game/Locations/'+name)
    placed = ACTORS.get_all_level_actors()
    city = OuterBlocks(shift)
    anchors = saved_anchors(placed,city.offset)
    clear_old_entries(placed)
    build_entries(city,ACTORS.get_all_level_actors(),anchors,meshes)
    repairs = [a for a in ACTORS.get_all_level_actors() if a.actor_has_tag(TAG)]
    assert len(repairs)==2*len(FACADES)
    for entry in (a for a in repairs if a.get_actor_label().endswith(' entrance')):
        parts = entry.get_attached_actors(True,False)
        assert len(parts)==1 and parts[0].get_editor_property('hidden'), entry
        assert str(parts[0].get_component_by_class(ue.StaticMeshComponent).get_collision_profile_name()) == (
            'NoCollision' if shift[2] else 'BlockAll')
    assert LEVELS.save_current_level(), name
    ue.log('ENTRANCE_SAVED '+name)
ue.log('ENTRANCE_REPAIR_OK')
