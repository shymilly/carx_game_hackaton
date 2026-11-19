"""Import the relocated source library into /Game/ImportedAssets, with resumable records.

UnrealEditor-Cmd Project.uproject -run=pythonscript -script=Scripts/ImportDesktopAssets.py
Optional: -AssetLibraryPhase=probe|textures|models|all|validate (default all).
"""
from pathlib import Path
import json,re,traceback

PACKS={
 'Fenixapple Retro American Posters vol2':'Posters/AmericanRetro',
 'Pack of 7 Posters':'Posters/PackOf7',
 'Industrial_exterior_v1':'Industrial/ExteriorPack',
 'OFFICE':'Office',
 'RetroUrbanFree':'RetroUrban',
 'psx-first-person-arms-free-game-assets':'FirstPersonArms',
 'SBS - Tiny Texture Pack - 128x128':'TinyTextures/Size128',
 'SBS - Tiny Texture Pack - 256x256':'TinyTextures/Size256',
 'SBS - Tiny Texture Pack - 512x512':'TinyTextures/Size512',
}
BASE='/Game/ImportedAssets'

def safe(value):
 value=re.sub(r'[^a-zA-Z0-9_]+','_',value).strip('_')
 return ('Asset_'+value) if not value or value[0].isdigit() else value

def import_plan(project):
 source=project/'SourceAssets/DesktopAssets'
 assert source.is_dir(),source
 files=sorted(p for p in source.rglob('*') if p.is_file() and not any(q.lower().endswith('.fbm') for q in p.relative_to(source).parts[:-1]))
 plans=[];alternates=[];source_only=[]
 for file in files:
  relative=file.relative_to(source);ext=file.suffix.lower()
  if ext not in ('.png','.jpg','.jpeg','.fbx','.glb'):
   source_only.append(relative.as_posix());continue
  if ext=='.glb' and file.with_suffix('.fbx').is_file():
   alternates.append(relative.as_posix());continue
  parts=list(relative.parts)
  pack=PACKS.get(parts[0])
  if pack:
   parts=parts[1:]
   # Remove the duplicated archive wrapper folders, retaining meaningful categories.
   while len(parts)>1 and (parts[0]==relative.parts[0] or parts[0]=='Industrial_exterior_v2'):
    parts=parts[1:]
   folder=BASE+'/'+pack
   if len(parts)>1:folder+='/'+'/'.join(safe(p) for p in parts[:-1])
  else:
   folder=BASE+('/Nature/Trees' if file.stem=='trees' else '/Industrial/ExteriorV2')
  kind='texture' if ext in ('.png','.jpg','.jpeg') else 'model'
  skeletal=ext=='.fbx' and relative.parts[0]=='psx-first-person-arms-free-game-assets'
  # A separate model subfolder isolates material names from unrelated source models.
  if kind=='model':folder+='/'+safe(file.stem)
  name=('T_' if kind=='texture' else 'SK_' if skeletal else 'SM_')+safe(file.stem)
  plans.append(dict(source=relative.as_posix(),kind=kind,skeletal=skeletal,folder=folder,name=name,
                    combine=relative.parts[0]=='OFFICE'))
 return dict(files=len(files),bytes=sum(f.stat().st_size for f in files),imports=plans,
             alternate_formats=alternates,source_only=source_only)

def run():
 import unreal as ue
 project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
 raw=project/'SourceAssets/DesktopAssets'
 records=project/'Resources/AssetLibrary';records.mkdir(parents=True,exist_ok=True)
 plan=import_plan(project)
 (records/'ImportPlan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
 manifest=records/'ImportedAssets.json'
 saved=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else dict(imports={})
 assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
 tools=ue.AssetToolsHelpers.get_asset_tools()
 command=ue.SystemLibrary.get_command_line()
 phase_match=re.search(r'-AssetLibraryPhase=(\w+)',command)
 phase=phase_match.group(1) if phase_match else 'all'
 selected=plan['imports']
 if phase in ('textures','models'):selected=[p for p in selected if p['kind']==phase[:-1]]
 if phase=='probe':
  selected=[next(p for p in selected if p['kind']=='texture'),
            next(p for p in selected if p['combine']),
            next(p for p in selected if p['source']=='Industrial_exterior_v2.glb')]
 failures=[]
 if phase!='validate':
  editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
  ue.SystemLibrary.execute_console_command(editor.get_editor_world(),'Interchange.FeatureFlags.Import.FBX 0')
  for index,item in enumerate(selected):
   previous=saved['imports'].get(item['source'])
   if previous and previous.get('assets') and all(assets.does_asset_exist(p) for p in previous['assets']):continue
   try:
    task=ue.AssetImportTask()
    source_file=raw/item['source']
    if source_file.suffix.lower() in ('.jpg','.jpeg') and source_file.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
     derived=project/'SourceAssets/AssetLibraryProcessed'/Path(item['source']).with_suffix('.png')
     derived.parent.mkdir(parents=True,exist_ok=True);derived.write_bytes(source_file.read_bytes());source_file=derived
    task.set_editor_properties(dict(filename=str(source_file),destination_path=item['folder'],
     destination_name=item['name'],automated=True,replace_existing=True,save=True))
    if Path(item['source']).suffix.lower()=='.fbx':
     options=ue.FbxImportUI()
     options.set_editor_properties(dict(automated_import_should_detect_type=False,
      mesh_type_to_import=ue.FBXImportType.FBXIT_SKELETAL_MESH if item['skeletal'] else ue.FBXImportType.FBXIT_STATIC_MESH,
      import_as_skeletal=item['skeletal'],import_mesh=True,import_materials=True,import_textures=True,
      import_animations=item['skeletal'],create_physics_asset=False))
     if item['skeletal']:
      options.get_editor_property('anim_sequence_import_data').set_editor_properties(dict(
       use_default_sample_rate=True,snap_to_closest_frame_boundary=True))
     else:
      options.get_editor_property('static_mesh_import_data').set_editor_properties(dict(
       combine_meshes=item['combine'],auto_generate_collision=True))
     task.set_editor_property('options',options)
    tools.import_asset_tasks([task])
    objects=list(task.get_objects())
    paths=list(task.get_editor_property('imported_object_paths'))
    paths.extend(o.get_path_name() for o in objects if o.get_path_name().startswith(BASE))
    paths=list(dict.fromkeys(str(p) for p in paths))
    assert paths,('Importer returned no assets',item['source'])
    if item['kind']=='texture':
     for obj in objects:
      if not isinstance(obj,ue.Texture2D):continue
      stem=Path(item['source']).stem.lower()
      if stem.endswith(('_n','_normal','_norm','_nrm')):
       obj.set_editor_properties(dict(compression_settings=ue.TextureCompressionSettings.TC_NORMALMAP,srgb=False))
      assert assets.save_loaded_asset(obj,False)
    if item['kind']=='model':
     meshes=[o for o in objects if isinstance(o,(ue.StaticMesh,ue.SkeletalMesh))]
     assert meshes,('No usable mesh returned',item['source'],paths)
     if item['skeletal']:assert any(isinstance(o,ue.SkeletalMesh) for o in meshes),item['source']
    saved['imports'][item['source']]=dict(assets=paths,folder=item['folder'],kind=item['kind'],skeletal=item['skeletal'])
    manifest.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    if index%20==0 or item['kind']=='model':ue.log('ASSET_LIBRARY_IMPORTED '+str(index+1)+'/'+str(len(selected))+' '+item['source'])
   except Exception:
    detail=traceback.format_exc();failures.append(dict(source=item['source'],error=detail))
    ue.log_error('ASSET_LIBRARY_ITEM_FAILED '+item['source']+' '+detail)
  (records/'ImportFailures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')
  assert not failures,('Import failures',len(failures))
  if phase=='probe':ue.log('ASSET_LIBRARY_PROBE_PASSED');return
  if phase=='all':
   import sys
   sys.path.insert(0,str(project/'Scripts'))
   import RepairAssetMaterials
   import BindPosterTextures
 if phase in ('all','validate'):
  missing=[i['source'] for i in plan['imports'] if i['source'] not in saved['imports'] or not all(assets.does_asset_exist(p) for p in saved['imports'][i['source']]['assets'])]
  assert not missing,('Missing imported sources',missing)
  registry=ue.AssetRegistryHelpers.get_asset_registry()
  catalog=registry.get_assets_by_path(BASE,recursive=True)
  classes={}
  for entry in catalog:
   name=str(entry.asset_class_path.asset_name);classes[name]=classes.get(name,0)+1
  summary=dict(source_files=plan['files'],source_bytes=plan['bytes'],imported_sources=len(plan['imports']),
    source_alternates=len(plan['alternate_formats']),source_only=len(plan['source_only']),assets=len(catalog),classes=classes)
  (records/'Summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
  ue.log('ASSET_LIBRARY_VALIDATED '+str(summary))
 else:ue.log('ASSET_LIBRARY_PHASE_PASSED '+phase+' imported='+str(len(saved['imports'])))

if __name__=='__main__':run()
