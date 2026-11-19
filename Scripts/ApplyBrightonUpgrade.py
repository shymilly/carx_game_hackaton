"""Apply only the requested Brighton presentation changes, preserving current authored rooms."""
from datetime import datetime
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(project/'Tools'))
from BrightonUpgrade import (
    ACTORS, ASSETS, LEVELS, TAG, ROOT, apartment_city, build_facades, capture_exterior,
    clear_generated, configure_weather, environment_data, extend_city, fill_grocery,
    grocery_meshes, house_groups, projection_material, remove_old_windows, save,
    typography, weather_collection, weather_effects, weather_surfaces,
)

backup=project/'Saved/Backups'/('BrightonApply_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True,exist_ok=True)
maps=('L_DimaApartmentInterior','L_NeptuneStreet','L_BrightonGrocery','L_FedorEntry','L_BrightonAlley')
for name in maps:copy2(project/'Content/Locations'/(name+'.umap'),backup/(name+'.umap'))

collection=weather_collection()
environment_data(collection)
meshes=grocery_meshes()
splash,streak=weather_effects()
projection=projection_material()
hud=ue.load_asset('/Game/Locations/BP_SeparateLocationsHUD')
changed=ue.ExplorationHUDLibrary.upgrade_status_hud(hud)
assert changed>=0,changed
save(hud)
ue.log('BRIGHTON_HUD_UPGRADED '+str(changed))

assert LEVELS.load_level('/Game/Locations/L_BrightonGrocery')
clear_generated()
fill_grocery(meshes)
assert LEVELS.save_current_level()

assert LEVELS.load_level('/Game/Locations/L_NeptuneStreet')
clear_generated()
remove_old_windows()
groups=house_groups()
materials=build_facades(groups,projection)
extend_city(materials)
weather_surfaces(collection)
typography(ACTORS.get_all_level_actors(),reimport=True,storefronts=False)
configure_weather(splash,streak)
for actor in ACTORS.get_all_level_actors():
    if isinstance(actor,ue.StreetPortal) and actor.get_editor_property('destination_map'):
        destination=actor.get_editor_property('destination_map')
        if destination.get_name()=='L_NeptuneStreet':actor.set_editor_property('destination_title','4th Brighton beach')
exterior=capture_exterior()
assert LEVELS.save_current_level()

assert LEVELS.load_level('/Game/Locations/L_DimaApartmentInterior')
clear_generated()
apartment_city(exterior)
configure_weather(splash,streak)
assert LEVELS.save_current_level()

for name in ('L_FedorEntry','L_BrightonAlley'):
    assert LEVELS.load_level('/Game/Locations/'+name)
    configure_weather(splash,streak)
    weather_surfaces(collection)
    assert LEVELS.save_current_level()

assert LEVELS.load_level('/Game/Locations/L_PolicePrecinct')
for actor in ACTORS.get_all_level_actors():
    if isinstance(actor,ue.StreetPortal) and actor.get_editor_property('destination_map'):
        if actor.get_editor_property('destination_map').get_name()=='L_NeptuneStreet':
            actor.set_editor_property('destination_title','4th Brighton beach')
assert LEVELS.save_current_level()
ue.log('BRIGHTON_UPGRADE_OK backup='+str(backup))
