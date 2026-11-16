import unreal as ue
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
names=['L_DimaApartmentInterior','L_NeptuneStreet','L_PolicePrecinct']
for name in names:
    assert levels.load_level('/Game/Locations/'+name)
    all=actors.get_all_level_actors()
    assert not any(isinstance(a,ue.StreetDoorThreshold) for a in all)
    for a in all:
        if isinstance(a,ue.StreetPortal) and a.get_actor_label()!='Bar Lighthouse entrance reserved for a future level':
            assert a.get_editor_property('arrival') is None
            dest=a.get_editor_property('destination_map')
            assert dest and dest.get_name() in names,(name,a.get_actor_label())
    if name=='L_DimaApartmentInterior':
        assert any(a.actor_has_tag('StreetDoor') for a in all)
        assert any(a.actor_has_tag('Phone') for a in all)
        assert not any(isinstance(a,ue.StreetTrafficFlow) for a in all)
        assert not any(a.get_actor_label().startswith('Reception') for a in all)
    elif name=='L_NeptuneStreet':
        assert any(isinstance(a,ue.StreetTrafficFlow) for a in all)
        assert not any(a.actor_has_tag('Phone') or a.actor_has_tag('FridgeDoor') for a in all)
        assert not any(a.get_actor_label().startswith('Reception') for a in all)
    else:
        assert any(a.get_actor_label().startswith('Reception') for a in all)
        assert not any(isinstance(a,ue.StreetTrafficFlow) or a.actor_has_tag('Phone') for a in all)
    for a in all:
        if isinstance(a,ue.TargetPoint) and str(a.get_folder_path())=='Location transitions':
            ue.log('LEVEL_ARRIVAL '+name+' '+a.get_actor_label()+' '+str(a.get_actor_rotation()))
    ue.log('LEVEL_STRUCTURE_OK '+name+' actors='+str(len(all)))
hud=ue.load_asset('/Game/Locations/BP_SeparateLocationsHUD')
assert ue.BlueprintEditorLibrary.compile_blueprint(hud)
assert ue.JournalUILibrary.validate_journal_blueprint(hud)
ue.log('LEVEL_CHECK_PASSED')
