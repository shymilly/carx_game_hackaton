"""Generate the apartment map and its runtime Blueprint in Unreal Editor."""
from pathlib import Path
import math
import struct
import sys
import wave

import unreal as ue

sys.path.insert(0, str(Path(__file__).parent))
from ApartmentScene import build_scene
from ApartmentGameplay import DIMAS_MAP, FATHERS_MAP, FOCUS_SOUND, build_gameplay
from ApartmentFinishes import create_finishes
from ImportFurniture import import_meshes
from PlanApartment import PREVIOUS_MAP, build_plan, check_furniture_fit, furniture

ROOT = "/Game/Prologue"
assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)


def import_focus_click():
    if assets.does_asset_exist(FOCUS_SOUND):
        return
    folder = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir())) / "Generated"
    folder.mkdir(parents=True, exist_ok=True)
    filename = folder / "S_FocusClick.wav"
    samples = bytearray()
    for frame in range(4320):
        t = frame / 48000
        attack = min(t / 0.002, 1)
        tone = math.sin(2 * math.pi * 915 * t) + 0.4 * math.sin(2 * math.pi * 1640 * t)
        samples.extend(struct.pack("<h", int(7900 * attack * math.exp(-69 * t) * tone)))
    with wave.open(str(filename), "wb") as sound:
        sound.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        sound.writeframes(samples)
    task = ue.AssetImportTask()
    task.set_editor_properties({
        "filename": str(filename), "destination_path": ROOT + "/Audio", "automated": True, "save": True,
    })
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    if not assets.does_asset_exist(FOCUS_SOUND):
        raise RuntimeError("Could not import the focus click.")


def prepare_level(path, marker, builder):
    opened = levels.load_level(path) if assets.does_asset_exist(path) else levels.new_level(path, False)
    if not opened:
        raise RuntimeError(f"Could not open {path}")
    if not any(actor.get_actor_label() == marker for actor in actors.get_all_level_actors()):
        builder(ROOT)
        if not levels.save_current_level():
            raise RuntimeError(f"Could not save {path}")


def entrance_parts():
    return [actor for actor in actors.get_all_level_actors()
            if actor.get_actor_label() == "Front door" or actor.get_actor_label().startswith("Main south wall")
            or (actor.get_actor_label() == "Baseboard" and abs(actor.get_actor_location().y + 450) < .01
                and actor.get_actor_location().x < 390)]


def entrance_signature():
    signature = []
    for actor in entrance_parts():
        component = actor.get_component_by_class(ue.StaticMeshComponent)
        pos, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
        transform = tuple(round(value, 6) for value in (pos.x, pos.y, pos.z, rot.roll, rot.pitch, rot.yaw,
                                                      scale.x, scale.y, scale.z))
        signature.append((actor.get_actor_label(), transform,
                          str(component.get_editor_property("mobility")),
                          str(component.get_collision_profile_name()), component.static_mesh.get_path_name(),
                          tuple(str(tag) for tag in actor.tags),
                          tuple(component.get_material(i).get_path_name() for i in range(component.get_num_materials()))))
    return sorted(signature)


def prepare_refined_level():
    original = ROOT + "/" + PREVIOUS_MAP
    if not levels.load_level(original):
        raise RuntimeError(f"Could not open original map {original}.")
    before = entrance_signature()
    if not any(part[0] == "Front door" for part in before):
        raise RuntimeError("The original exit door is missing.")

    opened = (levels.load_level(DIMAS_MAP) if assets.does_asset_exist(DIMAS_MAP)
              else levels.new_level_from_template(DIMAS_MAP, original))
    if not opened:
        raise RuntimeError(f"Could not open {DIMAS_MAP}.")
    if entrance_signature() != before:
        raise RuntimeError("Exit door or frame differs from the original map.")
    if "--rebuild" in sys.argv or not any(actor.get_actor_label() == "LivingSwitch plate"
                                         for actor in actors.get_all_level_actors()):
        mesh_paths = {item.model for item in furniture()}
        meshes = import_meshes(mesh_paths)
        keep = set(entrance_parts())
        actors.destroy_actors([actor for actor in actors.get_all_level_actors() if actor not in keep])
        build_plan(meshes, create_finishes())
        if entrance_signature() != before:
            raise RuntimeError("Exit door or frame changed during generation.")
        if not levels.save_current_level():
            raise RuntimeError(f"Could not save {DIMAS_MAP}.")
    ue.log(f"ORIGINAL_ENTRANCE_UNCHANGED {len(before)} parts")


import_focus_click()
prepare_level(FATHERS_MAP, "Ivan briefing camera", build_scene)
prepare_refined_level()
placed = {actor.get_actor_label(): actor for actor in actors.get_all_level_actors()}
check_furniture_fit({item.label: placed[item.label] for item in furniture()})
if not assets.does_asset_exist(ROOT + "/BP_PrologueApartmentHUD"):
    build_gameplay(ROOT)

mapping = ue.load_asset("/Game/Input/IMC_Default")
jump = ue.load_asset("/Game/Input/Actions/IA_Jump")
if any(entry.action == jump for entry in mapping.get_editor_property("mappings")):
    mapping.modify()
    mapping.unmap_all_keys_from_action(jump)
    if not assets.save_loaded_asset(mapping, False):
        raise RuntimeError("Could not update the first-person input mapping.")

ue.log("APARTMENT_GENERATION_OK")
