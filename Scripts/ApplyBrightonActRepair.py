"""Save the Brighton frontage and traffic fleet, Fedor's stairwell and the revised pursuit."""
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(project/'Tools'))
from BrightonParkFacade import artwork, dress_park_frontage
from BrightonTrafficFleet import load_fleet, replace_parked_cars, right_hand_traffic
from BrightonUpgrade import LEVELS, configure_weather, factory_asset, save, weather_effects
from FedorBuildingAndPursuit import alley, apartment, entrance

backup=project/'Saved/Backups/BrightonFedorAndTraffic'
backup.mkdir(parents=True,exist_ok=True)


def edit_map(name,edit):
    filename=name+'.umap'
    if not (backup/filename).exists():
        copy2(project/'Content/Locations'/filename,backup/filename)
    assert LEVELS.load_level('/Game/Locations/'+name),name
    edit()
    assert LEVELS.save_current_level(),name
    ue.log('BRIGHTON_ACT_MAP_SAVED '+name)


data=ue.load_asset('/Game/Story/ActOne/DA_ActOne')
arms=data.get_editor_property('smoking_arms')
assert arms
clip=factory_asset('/Game/Story/ActOne/Animation','A_DimaStumbles',ue.CityGestureSequence,None)
assert ue.CityCharacterAuthoring.author_first_person_trip(arms,clip)
assert 1.90 < clip.get_play_length() < 2.00
for name in ('Bone','Curve'):
    settings=ue.load_asset('/ACLPlugin/ACLAnim'+name+'CompressionSettings')
    assert settings
    clip.set_editor_property(name.lower()+'_compression_settings',settings)
save(clip)
data.set_editor_property('trip_arms',clip)
save(data)

cars=load_fleet()
art=artwork()
splash,streak=weather_effects()


def street():
    dress_park_frontage(False,art)
    replace_parked_cars(cars)
    right_hand_traffic(cars)
    configure_weather(splash,streak)


def apartment_view():
    dress_park_frontage(True,art)
    replace_parked_cars(cars)


def rainy_entrance():
    entrance()
    configure_weather(splash,streak)


def rainy_alley():
    alley()
    configure_weather(splash,streak)


for name, edit in (('L_NeptuneStreet',street),('L_DimaApartmentInterior',apartment_view),
        ('L_FedorEntry',rainy_entrance),('L_FedorApartment',apartment),('L_BrightonAlley',rainy_alley)):
    edit_map(name,edit)
ue.log('BRIGHTON_ACT_REPAIR_OK')
