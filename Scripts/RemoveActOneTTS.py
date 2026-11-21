"""Remove only the Act One Windows speech takes after checking package references."""
from datetime import datetime
import json
from pathlib import Path
from shutil import copy2

import unreal as ue

root = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
registry = ue.AssetRegistryHelpers.get_asset_registry()
registry.wait_for_completion()
assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
audio = "/Game/Story/ActOne/Audio"
sources = root / "Resources/Audio/ActOne"
scenario = json.loads((root / "Docs/Scenario/ActOne.json").read_text(encoding="utf-8"))
apartment = json.loads((root / "Docs/Scenario/DimaApartment.json").read_text(encoding="utf-8"))
legacy_names = {"Voice_" + key for key, line in scenario["documents"].items() if line.get("speaker_role")}
legacy_names.update("Voice_Apartment_" + row["id"] for row in apartment["documents"]
                    if row["id"] in {"Television", "Fridge", "Wardrobe", "FloorLamp"}
                    or (row["id"].startswith("Phone") and row["body"] != "-бросила трубку-"))
generated = {str(a.package_name): str(a.asset_name) for a in registry.get_assets_by_path(audio)
             if str(a.asset_class_path.asset_name) == "SoundWave" and str(a.asset_name) in legacy_names}
wav = [sources / (name + ".wav") for name in sorted(legacy_names) if (sources / (name + ".wav")).is_file()]
options = ue.AssetRegistryDependencyOptions()
options.set_editor_properties(dict(include_hard_package_references=True, include_soft_package_references=True,
                                    include_searchable_names=False, include_soft_management_references=False,
                                    include_hard_management_references=False))


def referencers(package):
    return {str(ref) for ref in registry.get_referencers(package, options) or []}


def is_generated(sound):
    return sound is not None and sound.get_path_name().split(".", 1)[0] in generated


backup = root / "Saved/Backups" / datetime.now().strftime("ActOneTTS_%Y%m%d_%H%M%S")


def preserve(file):
    destination = backup / file.relative_to(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy2(file, destination)


before = {pkg: sorted(referencers(pkg)) for pkg in generated}
changed = []
for package in sorted({p for refs in before.values() for p in refs}):
    item = ue.load_asset(package)
    if isinstance(item, ue.InteractionDocument) and is_generated(item.get_editor_property("voice")):
        preserve(root / "Content" / (package.removeprefix("/Game/") + ".uasset"))
        item.set_editor_property("voice", None)
    elif isinstance(item, ue.ActOneData):
        old = item.get_editor_property("sounds")
        new = {name: sound for name, sound in old.items() if not is_generated(sound)}
        if len(new) == len(old):
            continue
        preserve(root / "Content" / (package.removeprefix("/Game/") + ".uasset"))
        item.set_editor_property("sounds", new)
    else:
        continue
    assert assets.save_loaded_asset(item, False), package
    changed.append(package)

if changed:
    registry.scan_modified_asset_files([str(root / "Content" / (name.removeprefix("/Game/") + ".uasset"))
                                       for name in changed])
remaining = {pkg: sorted(referencers(pkg)) for pkg in generated}
assert not any(remaining.values()), ("Generated speech still has package references", remaining)
for package in generated:
    preserve(root / "Content" / (package.removeprefix("/Game/") + ".uasset"))
    assert assets.delete_asset(package), package
for file in wav:
    preserve(file)
    file.unlink()
if backup.exists():
    (backup / "Audit.json").write_text(json.dumps(dict(detached=changed, deleted=before, remaining=remaining),
                                                ensure_ascii=False, indent=2), encoding="utf-8")
ue.log(f"QUALITY_TTS_OK dialogue_assets={len(changed)} soundwaves={len(generated)} source_takes={len(wav)}")
