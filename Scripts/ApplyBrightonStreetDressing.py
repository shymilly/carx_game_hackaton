"""Apply the facade and road repairs to the live street and its apartment-window view."""
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project / 'Tools'))
from BrightonOuterBlocks import dress_exterior
from BrightonRoadTurns import make_road_meshes
from BrightonUpgrade import ACTORS, LEVELS
from CityLifeCharacters import apply_profile
from CityLifeEnvironment import STREET_SHIFT


backup = project / 'Saved/Backups/BrightonDressing'
backup.mkdir(parents=True, exist_ok=True)
road_models = make_road_meshes()
for name, shift in (('L_NeptuneStreet', (0, 0, 0)), ('L_DimaApartmentInterior', STREET_SHIFT)):
    package = name + '.umap'
    if not (backup / package).exists():
        copy2(project / 'Content/Locations' / package, backup / package)
    assert LEVELS.load_level('/Game/Locations/' + name)
    dress_exterior(road_models, shift)
    for actor in ACTORS.get_all_level_actors():
        if isinstance(actor, ue.ActOneCast):
            phase = {'Neighbor talking by the sidewalk': .19, 'Neighbor listening and replying': 2.99}.get(actor.get_actor_label())
            if phase is not None:
                actor.set_editor_property('animation_phase', phase)
            profile = actor.get_editor_property('character_profile')
            if profile:
                apply_profile(actor, profile)
        if shift and actor.get_actor_label() == 'Front door' and actor.actor_has_tag('StreetDoor'):
            position = actor.get_actor_location()
            position.y = -450
            assert actor.set_actor_location(position, False, True)
        if shift and actor.get_actor_label() == 'Main south wall threshold':
            scale = actor.get_actor_scale3d()
            scale.z = .024
            actor.set_actor_scale3d(scale)
    assert LEVELS.save_current_level(), name
    ue.log('QUALITY_STREET_DETAILS_SAVED ' + name)
ue.log('QUALITY_BRIGHTON_STREET_DRESSING_OK')
