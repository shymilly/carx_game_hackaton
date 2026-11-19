"""Read-only regression audit for the Brighton presentation update and existing story/UI."""
from pathlib import Path
import runpy
import sys
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(root/'Tools'))
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
scenario=ue.load_asset('/Game/Story/DimaApartment/DA_DimaApartmentScenario')
assert scenario.get_editor_property('ambient').get_path_name().startswith('/Game/Audio/DimaApartment/S_DimaApartmentAmbient.')
data=ue.load_asset('/Game/Prologue/Brighton/DA_Environment')
assert data and data.get_editor_property('weather_parameters')
surfaces=data.get_editor_property('footsteps')
assert {str(key) for key in surfaces}=={'Wood','Tile','Asphalt','Wet'}
for group in surfaces.values():
    assert len(group.get_editor_property('variations'))==4
    assert all(sound.get_editor_property('duration')>0 for sound in group.get_editor_property('variations'))

assert levels.load_level('/Game/Locations/L_BrightonGrocery')
stock=[a.get_editor_property('instances') for a in actors.get_all_level_actors()
       if isinstance(a,ue.StreetMeshInstances) and a.actor_has_tag('BrightonUpgrade_v1')]
assert sum(component.get_instance_count() for component in stock)==155
for key in ('green_can_obj','soda_bottle_obj','chocolate_bar_obj','cash_register_obj'):
    mesh=ue.load_asset('/Game/Prologue/Furniture/Grocery/'+key+'/SM_'+key)
    assert mesh,key
    assert all(slot.get_editor_property('material_interface') for slot in mesh.get_editor_property('static_materials')),key
    assert mesh.get_bounding_box().min.z>=-.05,key
assert not any(a.get_actor_label()=='Cash register housing' for a in actors.get_all_level_actors())

assert levels.load_level('/Game/Locations/L_NeptuneStreet')
street_actors=actors.get_all_level_actors()
boundaries=[a for a in street_actors if a.get_actor_label().startswith('Invisible ') and 'limit' in a.get_actor_label()]
assert len(boundaries)==4
assert all(a.get_editor_property('hidden') and a.get_actor_enable_collision() for a in boundaries)
far_houses=[a for a in street_actors if a.get_actor_label().startswith('Distant Brighton residential block')]
assert len(far_houses)==42
assert all(str(a.get_component_by_class(ue.StaticMeshComponent).get_collision_profile_name())=='NoCollision' for a in far_houses)
lights=[a for a in street_actors if a.actor_has_tag('WindowProjection')]
assert len(lights)>10
assert all(a.get_component_by_class(ue.SpotLightComponent).get_editor_property('light_function_material') and
           a.get_component_by_class(ue.SpotLightComponent).get_editor_property('max_draw_distance')==2600 for a in lights)
assert any(a.actor_has_tag('SignText:4-я БРАЙТОН-БИЧ / 4th Brighton beach') for a in street_actors)
road=next(a for a in street_actors if a.get_actor_label()=='Neptune Avenue • stem')
assert road.get_component_by_class(ue.StaticMeshComponent).get_material(0).get_name().startswith('M_Wet_')
original_roads=[(a.get_actor_label(),a.get_actor_location()) for a in street_actors
                if a.get_actor_label().startswith('Road continues past the playable boundary')]

assert levels.load_level('/Game/Locations/L_DimaApartmentInterior')
apartment_actors=actors.get_all_level_actors()
for name,at in original_roads:
    candidates=[a for a in apartment_actors if a.get_actor_label()=='Third-floor view '+name]
    copy=min(candidates,key=lambda a:(a.get_actor_location()-(at+ue.Vector(0,-48,-640))).length())
    shifted=copy.get_actor_location()-at
    assert abs(shifted.x)<.01 and abs(shifted.z+640)<.01 and abs(shifted.y+48)<.01,(name,shifted)
    assert str(copy.get_component_by_class(ue.StaticMeshComponent).get_collision_profile_name())=='NoCollision'
assert any(a.get_actor_label()=='North curtain drawn to the right' for a in apartment_actors)
assert any(a.actor_has_tag('StreetDoor') for a in apartment_actors)
assert next(a for a in apartment_actors if isinstance(a,ue.ActOneDirector)).get_editor_property('environment')
for name in ('L_NeptuneStreet','L_FedorEntry','L_BrightonAlley'):
    assert levels.load_level('/Game/Locations/'+name)
    director=next(a for a in actors.get_all_level_actors() if isinstance(a,ue.ActOneDirector))
    assert director.get_editor_property('environment')
    for field in ('rain','rain_splashes'):
        component=director.get_editor_property(field)
        assert component.static_mesh and component.get_material(0),(name,field)
        assert component.get_collision_enabled()==ue.CollisionEnabled.NO_COLLISION

runpy.run_path(str(root/'Scripts/CheckActOneAssets.py'),run_name='__main__')
runpy.run_path(str(root/'Scripts/CheckStreetRefinement.py'),run_name='__main__')
ue.log('BRIGHTON_ASSETS_OK: source models, 155 items, four surfaces, 42 background houses, window light masks, third-floor offset and existing story/UI')
