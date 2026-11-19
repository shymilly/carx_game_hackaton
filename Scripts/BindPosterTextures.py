from pathlib import Path
import json,re
import unreal as ue
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
tools=ue.AssetToolsHelpers.get_asset_tools();lib=ue.MaterialEditingLibrary
manifest=json.loads((root/'Resources/AssetLibrary/ImportedAssets.json').read_text(encoding='utf-8'))
record=root/'Resources/AssetLibrary/MaterialBindings.json';bindings=json.loads(record.read_text(encoding='utf-8'))
base='/Game/ImportedAssets/Posters/Shared'
path=base+'/M_Poster'
master=ue.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset('M_Poster',base,ue.Material,ue.MaterialFactoryNew())
if not lib.get_material_property_input_node(master,ue.MaterialProperty.MP_BASE_COLOR):
 texture=lib.create_material_expression(master,ue.MaterialExpressionTextureSampleParameter2D,-300,0)
 texture.set_editor_properties(dict(parameter_name=ue.Name('PosterImage'),texture=ue.load_asset('/Game/ImportedAssets/Posters/PackOf7/T_poster_1')))
 assert texture.texture
 lib.connect_material_property(texture,'RGB',ue.MaterialProperty.MP_BASE_COLOR)
 roughness=lib.create_material_expression(master,ue.MaterialExpressionConstant,-300,200);roughness.set_editor_property('r',.86)
 lib.connect_material_property(roughness,'',ue.MaterialProperty.MP_ROUGHNESS)
 master.set_editor_property('two_sided',True);assert not lib.recompile_material(master);assert assets.save_loaded_asset(master,False)
count=0
for source,entry in manifest['imports'].items():
 if entry['kind']!='model' or not source.startswith(('Fenixapple','Pack of 7')):continue
 pack='AmericanRetro' if source.startswith('Fenixapple') else 'PackOf7'
 textures={}
 for filename,item in manifest['imports'].items():
  if item['kind']!='texture' or not filename.startswith('Fenixapple' if pack=='AmericanRetro' else 'Pack of 7'):continue
  if '/colorless/' in filename.lower():continue
  number=re.search(r'(\d+)$',Path(filename).stem)
  if number:textures[int(number.group(1))]=ue.load_asset(item['assets'][0])
 assigned=[]
 for path in entry['assets']:
  mesh=ue.load_asset(path)
  if not isinstance(mesh,ue.StaticMesh):continue
  for index,slot in enumerate(mesh.get_editor_property('static_materials')):
   number=int(re.search(r'(\d+)$',str(slot.material_slot_name)).group(1))
   assert number in textures,(pack,number)
   folder='/Game/ImportedAssets/Posters/'+pack+'/AppliedMaterials';name='MI_Poster_'+str(number).zfill(2)
   mat=ue.load_asset(folder+'/'+name) if assets.does_asset_exist(folder+'/'+name) else tools.create_asset(name,folder,ue.MaterialInstanceConstant,ue.MaterialInstanceConstantFactoryNew())
   lib.set_material_instance_parent(mat,master)
   # UE 5.8's setter always returns false; verify the stored texture with its getter.
   lib.set_material_instance_texture_parameter_value(mat,ue.Name('PosterImage'),textures[number])
   assert lib.get_material_instance_texture_parameter_value(mat,ue.Name('PosterImage'))==textures[number]
   lib.update_material_instance(mat);assert assets.save_loaded_asset(mat,False)
   mesh.set_material(index,mat);assigned.append(mat.get_path_name());count+=1
  assert assets.save_loaded_asset(mesh,False)
 bindings['bindings'][source]=list(dict.fromkeys(assigned))
record.write_text(json.dumps(bindings,indent=2),encoding='utf-8')
ue.log('ASSET_LIBRARY_POSTERS_BOUND_PASSED '+str(count))
