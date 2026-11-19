"""Recover source PBR materials through the material-only Interchange pipeline."""
from pathlib import Path
import json,re,traceback
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
manifest=json.loads((root/'Resources/AssetLibrary/ImportedAssets.json').read_text(encoding='utf-8'))
checkpoint=root/'Resources/AssetLibrary/MaterialBindings.json'
previous=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
done=previous.get('bindings',{}) if previous.get('pipeline_version')==2 else {}
# Skeletal material arrays require assigning the edited struct back into the array.
done={source:value for source,value in done.items() if not manifest['imports'][source].get('skeletal')}
manager=ue.InterchangeManager.get_interchange_manager_scripted()
pipeline=ue.InterchangeGenericAssetsPipeline()
pipeline.get_editor_property('mesh_pipeline').set_editor_properties(dict(import_static_meshes=False,import_skeletal_meshes=False))
pipeline.get_editor_property('animation_pipeline').set_editor_property('import_animations',False)
pipeline.get_editor_property('material_pipeline').set_editor_properties(dict(import_materials=True,create_new_materials=True,reuse_existing_materials=False))
pipeline.get_editor_property('material_pipeline').get_editor_property('texture_pipeline').set_editor_property('allow_non_power_of_two',True)
params=ue.ImportAssetParameters()
params.set_editor_properties(dict(is_automated=True,replace_existing=True,override_pipelines=[ue.SoftObjectPath(pipeline.get_path_name())]))
ue.SystemLibrary.execute_console_command(ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world(),'Interchange.FeatureFlags.Import.FBX 1')
norm=lambda name:re.sub('[^a-z0-9]','',name.lower())
failures=[]
for source,entry in manifest['imports'].items():
 if entry['kind']!='model' or Path(source).suffix.lower()!='.fbx' or source in done:continue
 try:
  meshes=[obj for path in entry['assets'] if isinstance((obj:=ue.load_asset(path)),(ue.StaticMesh,ue.SkeletalMesh))]
  if source.startswith('Industrial_exterior_v1/'):
   folder='/Game/ImportedAssets/Industrial/ExteriorV2'
  else:
   folder=entry['folder']+'/Materials'
   input_file=root/'SourceAssets/DesktopAssets'/source
   if input_file.with_suffix('.glb').exists():input_file=input_file.with_suffix('.glb')
   if not assets.does_directory_exist(folder) or not assets.list_assets(folder,recursive=True,include_folder=False):
    result=manager.import_asset(folder,ue.InterchangeManager.create_source_data(str(input_file)),params)
    assert assets.save_directory(folder,only_if_is_dirty=False,recursive=True)
  materials=[]
  for path in assets.list_assets(folder,recursive=True,include_folder=False):
   obj=ue.load_asset(path)
   if isinstance(obj,ue.MaterialInterface):materials.append(obj)
  assert materials,('No source materials',source)
  mapping={norm(m.get_name()):m for m in materials}
  assigned=[]
  for mesh in meshes:
   prop='static_materials' if isinstance(mesh,ue.StaticMesh) else 'materials'
   slots=mesh.get_editor_property(prop)
   for index,slot in enumerate(slots):
    key=norm(str(slot.material_slot_name))
    material=mapping.get(key) or mapping.get(key+'1')
    if material is None and len(materials)==1:material=materials[0]
    assert material,(source,mesh.get_name(),str(slot.material_slot_name),[m.get_name() for m in materials])
    if isinstance(mesh,ue.StaticMesh):mesh.set_material(index,material)
    else:
     slot.material_interface=material
     slots[index]=slot
    assigned.append(material.get_path_name())
   if isinstance(mesh,ue.SkeletalMesh):mesh.set_editor_property('materials',slots)
   assert assets.save_loaded_asset(mesh,False)
  done[source]=list(dict.fromkeys(assigned))
  checkpoint.write_text(json.dumps(dict(pipeline_version=2,bindings=done),indent=2),encoding='utf-8')
  if len(done)%20==0 or not source.startswith('OFFICE'):ue.log('ASSET_LIBRARY_MATERIALS_BOUND '+str(len(done))+' '+source)
 except Exception:
  detail=traceback.format_exc();failures.append(dict(source=source,error=detail));ue.log_error('ASSET_LIBRARY_MATERIAL_BIND_FAILED '+source+' '+detail)
(root/'Resources/AssetLibrary/MaterialFailures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
assert not failures,('Material binding failures',len(failures))
ue.log('ASSET_LIBRARY_MATERIALS_REPAIRED '+str(len(done)))
