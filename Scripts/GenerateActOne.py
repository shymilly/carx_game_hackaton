"""Import the authored story data and compose the Act One maps in Unreal Editor."""
from datetime import datetime
import json
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(project/"Tools"))
from ActOneScenes import ACTORS, BUILDERS, ROOT, TAG, Scene, page_speakers

assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
directory = project/"Resources"
spec = json.loads((project/"Docs/Scenario/ActOne.json").read_text(encoding="utf-8"))
asset_tools = ue.AssetToolsHelpers.get_asset_tools()


def data_asset(cls,folder,name):
    path=f"{folder}/{name}"
    if assets.does_asset_exist(path):
        return ue.load_asset(path)
    assets.make_directory(folder)
    factory=ue.DataAssetFactory()
    factory.set_editor_property("data_asset_class",cls)
    result=asset_tools.create_asset(name,folder,cls,factory)
    assert result,path
    return result


def save(asset):
    assert asset and assets.save_loaded_asset(asset,False), asset


def import_media(path,folder,name):
    assert path.is_file(),path
    destination=f"{folder}/{name}"
    disk_asset=project/'Content'/destination.removeprefix('/Game/')
    disk_asset=disk_asset.with_suffix('.uasset')
    if assets.does_asset_exist(destination) and disk_asset.is_file() and disk_asset.stat().st_mtime>=path.stat().st_mtime:
        return ue.load_asset(destination)
    task=ue.AssetImportTask()
    task.set_editor_properties({"automated":True,"save":False,"replace_existing":True,"destination_path":folder,
                                "destination_name":name,"filename":str(path)})
    asset_tools.import_asset_tasks([task])
    result=ue.load_asset(destination)
    assert result,(path,destination)
    return result


def art_and_dialogue():
    portrait=import_media(directory/"ActOne/Fedor1987.png",ROOT+"/Art","Fedor1987")
    portrait.set_editor_properties({"max_texture_size":1024})
    save(portrait)
    sounds={}
    for file in sorted((directory/"Audio/ActOne").glob("*.wav")):
        sound=import_media(file,ROOT+"/Audio",file.stem)
        sound.set_editor_property("looping",file.stem in ("Music90","Rain"))
        save(sound)
        sounds[file.stem]=sound
    assert "Music90" in sounds and "Rain" in sounds
    documents={}
    for key,row in spec["documents"].items():
        item=data_asset(ue.InteractionDocument,ROOT+"/Documents","D_"+key)
        layout=row.get("layout","standard")
        close=row.get("close_label","Закрыть · E / Esc" if layout=="newspaper" else "Продолжить · E")
        item.set_editor_properties({"title":row["title"],"body":row["body"],"close_label":close,
                                    "layout":getattr(ue.DocumentLayout,layout.upper()),
                                    "open_sound":sounds.get(row.get("open_sound")),
                                    "illustration":portrait if row.get("illustration") else None,
                                    "crop_to_portrait":row.get("crop",False)})
        if layout=="newspaper":
            items=[]
            for source in row["articles"]:
                article=ue.NewspaperArticle()
                article.set_editor_properties(source)
                items.append(article)
            item.set_editor_properties({"edition":row["edition"],"articles":items})
        save(item)
        documents[key]=item
    configure_apartment_audio()
    append_to_journal(documents)
    data=data_asset(ue.ActOneData,ROOT,"DA_ActOne")
    data.set_editor_property("page_speakers",page_speakers(spec))
    data.set_editor_properties({"documents":{ue.Name(key):doc for key,doc in documents.items()},
                                "sounds":{ue.Name(key):sound for key,sound in sounds.items()}})
    save(data)
    return data,portrait


def configure_apartment_audio():
    apartment=ue.load_asset("/Game/Story/DimaApartment/DA_DimaApartmentScenario")
    assert apartment
    apartment.set_editor_properties({"ambient":ue.load_asset('/Game/Audio/DimaApartment/S_DimaApartmentAmbient'),"ambient_volume":.4})
    save(apartment)


def append_to_journal(documents):
    catalog=ue.load_asset("/Game/UI/Journal/DA_JournalCatalog")
    assert catalog
    entries=[entry for entry in catalog.get_editor_property("entries")
             if str(entry.get_editor_property("discovery_flag")) not in spec["journal"]]
    for key in spec["journal"]:
        entry=ue.JournalEntry()
        entry.set_editor_properties({"discovery_flag":ue.Name(key),"document":documents[key]})
        entries.append(entry)
    catalog.set_editor_property("entries",entries)
    save(catalog)


def make_maps(data,portrait,backup):
    mode=ue.BlueprintEditorLibrary.generated_class(ue.load_asset("/Game/Locations/BP_PrologueStreetGameMode"))
    assert mode
    for area,name in spec["levels"].items():
        uri="/Game/Locations/"+name
        source=project/"Content/Locations"/(name+".umap")
        if source.exists():
            copy2(source,backup/source.name)
            assert levels.load_level(uri),uri
        else:
            assert levels.new_level(uri),uri
        obsolete=[a for a in ACTORS.get_all_level_actors() if a.actor_has_tag(TAG)]
        if obsolete:
            assert ACTORS.destroy_actors(obsolete)
        world=ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
        settings=ue.GameplayStatics.get_actor_of_class(world,ue.WorldSettings)
        assert settings,uri
        settings.set_editor_property("default_game_mode",mode)
        builder=Scene(data,area)
        BUILDERS[area](builder,portrait)
        assert levels.save_current_level(),uri
        ue.log(f"ACT_ONE_MAP_OK {name} {len(ACTORS.get_all_level_actors())} actors")


hud=ue.load_asset("/Game/Locations/BP_SeparateLocationsHUD")
assert ue.ActOneBlueprintLibrary.use_dynamic_objective(hud)
save(hud)
backup=project/"Saved/Backups"/("ActOne_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(parents=True)
data,portrait=art_and_dialogue()
make_maps(data,portrait,backup)
ue.log("ACT_ONE_AUTHORING_OK")
