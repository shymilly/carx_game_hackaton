from pathlib import Path
import json,sys
import unreal as ue
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(root/'Scripts'))
from ImportDesktopAssets import import_plan
assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
manifest=json.loads((root/'Resources/AssetLibrary/ImportedAssets.json').read_text(encoding='utf-8'))
plan=import_plan(root)
for item in plan['imports']:
 assert item['source'] in manifest['imports'],item['source']
 assert all(assets.does_asset_exist(p) for p in manifest['imports'][item['source']]['assets']),item['source']
meshes=0;skeletal=0;bad=[];poster_materials=set()
for source,entry in manifest['imports'].items():
 if entry['kind']!='model':continue
 for path in entry['assets']:
  obj=ue.load_asset(path)
  if not isinstance(obj,(ue.StaticMesh,ue.SkeletalMesh)):continue
  meshes+=1;skeletal+=isinstance(obj,ue.SkeletalMesh)
  prop='static_materials' if isinstance(obj,ue.StaticMesh) else 'materials'
  mats=[slot.material_interface for slot in obj.get_editor_property(prop)]
  if not mats or any(not m or not m.get_path_name().startswith('/Game/ImportedAssets/') for m in mats):bad.append(path)
  for m in mats:
   if m:
    package=m.get_path_name().split('.')[0].replace('/Game/','Content/')+'.uasset'
    assert (root/package).is_file(),m.get_path_name()
    if source.startswith(('Fenixapple','Pack of 7')):poster_materials.add(m.get_path_name())
assert not bad,('Unassigned materials',bad)
assert skeletal==2 and meshes>=390,(meshes,skeletal)
for path in poster_materials:
 material=ue.load_asset(path)
 textures=[]
 while isinstance(material,ue.MaterialInstance):
  textures.extend(p.parameter_value for p in material.get_editor_property('texture_parameter_values') if p.parameter_value)
  material=material.get_editor_property('parent')
 if isinstance(material,ue.Material):textures.extend(ue.MaterialEditingLibrary.get_used_textures(material))
 assert any(t.get_path_name().startswith('/Game/ImportedAssets/') for t in textures),('Poster has no source texture',path)
registry=ue.AssetRegistryHelpers.get_asset_registry()
catalog=registry.get_assets_by_path('/Game/ImportedAssets',recursive=True)
classes={}
for entry in catalog:
 name=str(entry.asset_class_path.asset_name);classes[name]=classes.get(name,0)+1
summary=dict(source_files=plan['files'],source_bytes=plan['bytes'],imported_sources=len(plan['imports']),
 source_alternates=len(plan['alternate_formats']),source_only=len(plan['source_only']),assets=len(catalog),classes=classes,
 meshes=meshes,skeletal_meshes=skeletal,missing_materials=0,poster_materials_with_textures=len(poster_materials))
(root/'Resources/AssetLibrary/Summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(root/'Resources/AssetLibrary/MaterialAudit.json').write_text(json.dumps(dict(meshes=meshes,skeletal=skeletal,default_material_meshes=[],unsaved_materials=[]),indent=2),encoding='utf-8')
ue.log('ASSET_LIBRARY_FINAL_CHECK_PASSED '+str(summary))
