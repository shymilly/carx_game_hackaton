"""Persist the material usage flags reported missing by the DX12 checks."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from shutil import copy2
import re
import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
usage = ue.MaterialUsage
library = ue.MaterialEditingLibrary
materials = {
    "/Game/ImportedAssets/Industrial/ExteriorV2/Industrial_exterior_v2/Industrial_exterior_v2/Materials":
        ("Barrel_1", "Barrel_2", "Box_wood", "Building_1", "Building_2", "Pipes"),
    "/Game/ImportedAssets/Nature/Trees/trees/trees/Materials": ("branches", "leaves"),
}
backup = project / "Saved/Backups" / datetime.now().strftime("BrightonMaterialUsage_%Y%m%d_%H%M%S")
compatible_assets = {}
required_usage = defaultdict(set)
changed = set()


def preserve(material):
    path = Path("Content") / (material.get_path_name().removeprefix("/Game/").split(".")[0] + ".uasset")
    (backup / path).parent.mkdir(parents=True, exist_ok=True)
    copy2(project / path, backup / path)


def editable_chain(material):
    assert isinstance(material, (ue.Material, ue.MaterialInstanceConstant)), material
    original = material.get_path_name()
    if original in compatible_assets:
        return compatible_assets[original]
    if not original.startswith("/Game/"):
        name = material.get_name()
        if isinstance(material, ue.Material):
            name = "M_Brighton_" + name.removeprefix("M_")
        target = "/Game/Prologue/Brighton/Materials/SharedSM6/" + name
        material = ue.load_asset(target) if assets.does_asset_exist(target) else assets.duplicate_asset(original, target)
        assert material, target
        changed.add(material)
    if isinstance(material, ue.MaterialInstanceConstant):
        original_parent = material.get_editor_property("parent")
        parent = editable_chain(original_parent)
        if original_parent != parent:
            if original.startswith("/Game/"):
                preserve(material)
            library.set_material_instance_parent(material, parent)
            changed.add(material)
    compatible_assets[original] = material
    return material


def require(path, flags):
    material = editable_chain(ue.load_asset(path))
    while isinstance(material, ue.MaterialInstanceConstant):
        material = material.get_editor_property("parent")
    required_usage[material].update(flags)


for folder, names in materials.items():
    for name in names:
        require(folder + "/" + name, (usage.MATUSAGE_NANITE, usage.MATUSAGE_INSTANCED_STATIC_MESHES))
require("/Game/ImportedAssets/FirstPersonArms/arms_rig/Materials/Arms", (usage.MATUSAGE_SKELETAL_MESH,))

flags = {"Nanite": usage.MATUSAGE_NANITE, "InstancedStaticMeshes": usage.MATUSAGE_INSTANCED_STATIC_MESHES,
         "SkeletalMesh": usage.MATUSAGE_SKELETAL_MESH}
version = re.search(r"^ProjectVersion=([^\r\n]+)", (project / "Config/DefaultGame.ini").read_text(encoding="utf-8"), re.M)[1]
reports = (project / "Saved/PackageChecks" / version).glob("L_*.log")
needed = set()
for report in reports:
    if "-backup-" in report.stem:
        continue
    needed.update(re.findall(r"Material (/Game/[^ \r\n]+) missing usage flag ([^!]+)! Default Material", 
                             report.read_text(encoding="utf-8", errors="replace")))
for asset, name in sorted(needed):
    assert name in flags, (asset, name)
    require(asset, (flags[name],))

for master, requested in required_usage.items():
    file = project / "Content" / (master.get_path_name().removeprefix("/Game/").split(".")[0] + ".uasset")
    if file.is_file() and master not in changed:
        preserve(master)
    for flag in requested:
        library.set_material_usage(master, flag)
    changed.add(master)
for asset in changed:
    assert assets.save_loaded_asset(asset, False), asset
    ue.log("QUALITY_USAGE_SAVED " + asset.get_path_name())
ue.log(f"QUALITY_NANITE_USAGE_OK {len(needed)} reported pairs, {len(changed)} saved packages")
