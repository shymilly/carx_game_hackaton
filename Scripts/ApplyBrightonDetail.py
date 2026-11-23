"""Save the Citizens cast, Forest Scene planting and neighborhood dressing in the active maps."""
from pathlib import Path
import sys

import unreal as ue


project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(project/'Tools'))
from BrightonCitizens import dress_cast, limit_texture_sizes, profiles
from BrightonDistrictDetail import alley, fedor_stairwell, paint_materials, street
from BrightonForest import assets, plant_neighborhood, replace


levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
cast = profiles()
plants = assets()
graffiti = paint_materials()
maps = ('L_NeptuneStreet','L_DimaApartmentInterior','L_PolicePrecinct','L_BrightonGrocery',
        'L_LighthouseBar','L_FedorEntry','L_FedorApartment','L_BrightonAlley')
for name in maps:
    assert levels.load_level('/Game/Locations/'+name),name
    npcs = dress_cast(cast)
    foliage = replace(plants)
    if name in ('L_NeptuneStreet','L_DimaApartmentInterior'):
        interior = name == 'L_DimaApartmentInterior'
        plant_neighborhood(plants,interior)
        street(graffiti,interior)
    elif name == 'L_FedorEntry':
        fedor_stairwell(graffiti)
    elif name == 'L_BrightonAlley':
        alley(graffiti)
    assert levels.save_current_level(),name
    ue.log(f'BRIGHTON_DETAIL_SAVED {name} npc={npcs} foliage_replaced={foliage}')
limit_texture_sizes()
ue.log('BRIGHTON_DETAIL_OK')
