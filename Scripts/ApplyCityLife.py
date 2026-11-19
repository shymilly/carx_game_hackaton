"""Apply the authored appearances and outdoor additions to the current project maps."""
from datetime import datetime
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

root = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(root/"Tools"))
from BrightonUpgrade import ACTORS, ASSETS, LEVELS, LIB, save
from CityLifeCharacters import PEOPLE, STYLES, create_profiles, update_footsteps, update_story_cast
from CityLifeEnvironment import prop_meshes, rebuild_city, save_instance_material_usage
from CityLifeSky import bake_sky, configure_haze, night_sky, add_night_sky
from RefineStreetVisuals import set_lettering

maps = ("L_DimaApartmentInterior","L_NeptuneStreet","L_PolicePrecinct","L_BrightonGrocery",
        "L_LighthouseBar","L_FedorEntry","L_FedorApartment","L_BrightonAlley")
backup = root/"Saved/Backups"/("CityLife_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(parents=True)
for name in maps:
    copy2(root/"Content/Locations"/(name+".umap"),backup/(name+".umap"))

profiles={}
for name in STYLES:
    path=PEOPLE+"/Profiles/DA_"+name
    if ASSETS.does_asset_exist(path):
        profiles[name]=ue.load_asset(path)
if len(profiles)!=len(STYLES):
    profiles=create_profiles()
update_footsteps(profiles["Dima"])

mesh_assets=prop_meshes()
sky_variant=night_sky(bake_sky())
updated=0
for name in maps:
    assert LEVELS.load_level("/Game/Locations/"+name),name
    count=update_story_cast(profiles)
    updated+=count
    if name in ("L_BrightonAlley","L_FedorEntry"):
        add_night_sky(sky_variant)
    if name in ("L_DimaApartmentInterior","L_NeptuneStreet"):
        interior=name=="L_DimaApartmentInterior"
        rebuild_city(mesh_assets,profiles,interior)
        configure_haze(interior)
        if not interior:
            letters=ue.load_asset("/Game/StreetRefinement/Materials/M_Neptune94Ivory")
            letters.set_editor_property("two_sided",True)
            LIB.recompile_material(letters)
            save(letters)
            keys={"SM_SignStreet","SM_NeighborhoodPark"}
            for actor in ACTORS.get_all_level_actors():
                comp=actor.get_component_by_class(ue.StaticMeshComponent)
                if comp and comp.static_mesh:
                    key=comp.static_mesh.get_name().removeprefix("SM_N94_")
                    if key in keys:
                        set_lettering(actor,key,letters,True)
    save_instance_material_usage()
    assert LEVELS.save_current_level(),name
    ue.log(f"CITY_LIFE_MAP {name} cast={count}")
assert updated==11, updated

ue.log(f"CITY_LIFE_APPLY_OK cast={updated} backup={backup}")
