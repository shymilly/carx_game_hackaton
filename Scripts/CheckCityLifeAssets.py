"""Verify the saved meshes, animation links and exterior layout, then run the story checks."""
from pathlib import Path
import runpy
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
maps=("L_DimaApartmentInterior","L_NeptuneStreet","L_PolicePrecinct","L_BrightonGrocery",
      "L_LighthouseBar","L_FedorEntry","L_FedorApartment","L_BrightonAlley")
total=0
for map_name in maps:
    assert levels.load_level("/Game/Locations/"+map_name),map_name
    placed=actors.get_all_level_actors()
    cast=[a for a in placed if isinstance(a,ue.ActOneCast)]
    for actor in cast:
        profile=actor.get_editor_property("character_profile")
        mesh=actor.get_editor_property("character_mesh")
        assert profile and mesh.get_editor_property("skeletal_mesh_asset")==profile.get_editor_property("mesh"),actor
        motion=profile.get_editor_property("motions")
        assert motion[ue.Name("Idle")].get_play_length()>1,actor
        assert not actor.get_editor_property("parts"),actor
        if actor.get_editor_property("default_pose")==ue.ActOnePose.SMOKING:
            animation=motion[ue.Name("Smoke")]
            assert animation.get_play_length()>5
            asset=profile.get_editor_property("mesh")
            hand=lambda t:ue.CityCharacterAuthoring.pose_bone_position(asset,animation,"MiddleHand.R",t)
            assert (hand(3.0)-hand(.1)).length()>45,actor
        if actor.actor_has_tag("ActOneGenerated"):total+=1
    if map_name in ("L_NeptuneStreet","L_DimaApartmentInterior"):
        train,branch=sorted([a for a in placed if isinstance(a,ue.CityRailTraffic)],key=lambda a:a.get_actor_location().x)
        assert train.get_editor_property("interval")==300 and len(train.get_editor_property("consist"))==6
        assert branch.get_editor_property("interval")==300 and len(branch.get_editor_property("consist"))==4
        assert branch.get_editor_property("first_pass_delay")==95 and branch.get_actor_location().y<-7600
        translation=train.get_actor_location()
        assert translation.x<-6735 and abs(translation.z-(591.65 if map_name=="L_NeptuneStreet" else -48.35))<.001
        buffers=[a.get_editor_property("instances") for a in placed if isinstance(a,ue.StreetMeshInstances)
                 and a.actor_has_tag("CityLifeDressing") and a.get_actor_label()=="Rail segments"]
        assert sum(buffer.get_instance_count() for buffer in buffers)==44
        branch_track=[a.get_editor_property("instances") for a in placed if a.get_actor_label()=="Industrial line rails"]
        assert branch.get_editor_property("covered_ends")
        assert sum(b.get_instance_count() for b in branch_track)==36
        assert {"Bus shelter frame","Wooden shipping cases","Park planting beds"} <= {a.get_actor_label() for a in placed}
        fog,=[a for a in placed if isinstance(a,ue.ExponentialHeightFog)]
        assert fog.get_component_by_class(ue.ExponentialHeightFogComponent).get_editor_property("start_distance")>=3500
    if map_name=="L_DimaApartmentInterior":
        pistol=next(a for a in placed if a.actor_has_tag("ActCue:Pistol"))
        pc,pe=pistol.get_actor_bounds(False)
        tc,te=next(a for a in placed if a.get_actor_label()=="Writing desk").get_actor_bounds(False)
        assert abs(pc.z-pe.z-tc.z-te.z)<.15
        assert pistol.get_component_by_class(ue.StaticMeshComponent).static_mesh.get_name()=="SM_pistol_obj"
        neighbors={"Cassette recorder case","Pencil","Desk lamp","SM_Telephone","Industrial Herald","Patrol report"}
        for item in [a for a in placed if a.get_actor_label() in neighbors]:
            c,e=item.get_actor_bounds(False)
            assert abs(pc.x-c.x)>pe.x+e.x+2 or abs(pc.y-c.y)>pe.y+e.y+2,item.get_actor_label()
    if map_name=="L_LighthouseBar":
        for role in ("BarShotProp","GuardWeapon","DroppedWeapon"):
            prop,=[a for a in placed if a.actor_has_tag("ActCue:"+role)]
            assert prop.get_component_by_class(ue.StaticMeshComponent).static_mesh.get_name()=="SM_pistol_obj"
            if role!="DroppedWeapon":
                assert isinstance(prop.get_attach_parent_actor(),ue.ActOneCast)
                socket="BarPistolGrip" if role=="BarShotProp" else "hand_r"
                assert str(prop.get_attach_parent_socket_name())==socket
            else:
                assert prop.get_component_by_class(ue.StaticMeshComponent).get_editor_property("mobility")==ue.ComponentMobility.MOVABLE
        assert len([a for a in placed if a.actor_has_tag("ActCue:BarShotCamera")])==1
    ue.log("CITY_LIFE_ASSET_MAP "+map_name+" characters="+str(len(cast)))

assert total==11,total
data=ue.load_asset("/Game/Prologue/Brighton/DA_Environment")
assert data.get_editor_property("player_appearance")
for surface,group in data.get_editor_property("footsteps").items():
    sounds=group.get_editor_property("variations")
    assert len(sounds)==4 and all(0.06<sound.get_editor_property("duration")<.43 for sound in sounds),surface
runpy.run_path(str(root/"Scripts/CheckBrightonAssets.py"),run_name="__main__")
ue.log("CITY_LIFE_ASSETS_OK")
