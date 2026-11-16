"""Update the 1994 neighborhood around the furnished apartment in Unreal Editor."""
from pathlib import Path
import sys

import unreal as ue

sys.path.insert(0, str(Path(__file__).parent))
from ApartmentGameplay import DIMAS_MAP, STREET_MAP, build_gameplay
from ApartmentDoorHardware import add_door_hardware
from ApartmentPhysics import tune_street_apartment_props
from PlanApartment import DOORS
from StreetScene import BLENDER_MESHES, build_street, street_models


ROOT = "/Game/Prologue"
TARGET = f"{ROOT}/{STREET_MAP}"
HUD = f"{ROOT}/BP_PrologueStreetHUD"
GAME_MODE = f"{ROOT}/BP_PrologueStreetGameMode"


def prepare_door(door):
    door.modify()
    door.set_editor_property("tags", [
        tag for tag in door.get_editor_property("tags") if str(tag) not in ("Exit", "StreetDoor")
    ] + [ue.Name("StreetDoor")])
    mesh = door.get_component_by_class(ue.StaticMeshComponent)
    mesh.modify()
    mesh.set_editor_properties({"mobility": ue.ComponentMobility.MOVABLE, "cast_shadow": True,
                                "cast_dynamic_shadow": True})
    mesh.set_collision_profile_name(ue.Name("BlockAllDynamic"))
    center = door.get_actor_location()
    return ((center.x, center.y, center.z), (-249.4, -449.5, center.z), door.get_actor_rotation().yaw, -90)


def generate():
    assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    existing = assets.does_asset_exist(TARGET)
    opened = (levels.load_level(TARGET) if existing
              else levels.new_level_from_template(TARGET, DIMAS_MAP))
    if not opened:
        raise RuntimeError(f"Could not open {TARGET}.")

    placed = actors.get_all_level_actors()
    door = next(actor for actor in placed if actor.get_actor_label() == "Front door")
    bed = next(actor for actor in placed if actor.actor_has_tag("Bed"))
    door_spec = prepare_door(door)
    rebuild = "--rebuild-street" in sys.argv or not any(isinstance(actor, ue.StreetTrafficFlow) for actor in placed)
    time = next((actor for actor in placed if isinstance(actor, ue.PrologueTimeOfDay)), None)
    keep = {"Street/06 Sky and time", "Street/07 Interior additions"}
    reimport = BLENDER_MESHES if "--reimport-street" in sys.argv else ()
    obsolete = [actor for actor in placed if str(actor.get_folder_path()) == "05 Exterior"
                or actor.get_actor_label() in ("Curtains_Double", "Curtains_Double2")
                or (rebuild and str(actor.get_folder_path()).startswith("Street/")
                    and str(actor.get_folder_path()) not in keep)]
    if obsolete and not actors.destroy_actors(obsolete):
        raise RuntimeError("Could not remove the temporary exterior.")
    if rebuild:
        build_street(bed, reimport, time)
    elif reimport:
        street_models(reimport)

    if not existing:
        add_door_hardware({**DOORS, "StreetDoor": door_spec})
        tune_street_apartment_props()
    mode = (ue.BlueprintEditorLibrary.generated_class(ue.load_asset(GAME_MODE))
            if assets.does_asset_exist(HUD) and assets.does_asset_exist(GAME_MODE)
            else build_gameplay(ROOT, street_door=door_spec))
    world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
    settings = ue.GameplayStatics.get_actor_of_class(world, ue.WorldSettings)
    if not settings:
        settings = next(candidate for candidate in ue.ObjectIterator(ue.WorldSettings)
                        if candidate.get_outer().get_outer() == world)
    settings.modify()
    settings.set_editor_property("default_game_mode", mode)
    if not levels.save_current_level():
        raise RuntimeError(f"Could not save {TARGET}.")
    ue.log(f"STREET_GENERATION_OK {TARGET} {mode.get_path_name()}")


generate()
