"""Compile only new street materials. Run in UnrealEditor with a renderer, not NullRHI."""
import unreal as ue
assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
for folder in ('/Game/StreetRefinement/Materials','/Game/Prologue/Street/RefinedFactory/Materials'):
 for path in assets.list_assets(folder,recursive=True,include_folder=False):
  material=ue.load_asset(path)
  if not isinstance(material,ue.Material):continue
  if 'Factory_' in material.get_name():material.set_editor_property('used_with_instanced_static_meshes',True)
  errors=ue.MaterialEditingLibrary.recompile_material(material)
  assert not errors,(path,errors)
  assert assets.save_loaded_asset(material,False)
ue.log('STREET_MATERIALS_COMPILED')
