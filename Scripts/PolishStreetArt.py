from pathlib import Path
import unreal as ue
root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
lv=ue.get_editor_subsystem(ue.LevelEditorSubsystem);assert lv.load_level('/Game/Locations/L_NeptuneStreet')
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem);assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem);lib=ue.MaterialEditingLibrary

def flip_uv(material,sample):
 uv=lib.create_material_expression(material,ue.MaterialExpressionTextureCoordinate,-500,-50)
 arg=ue.CustomInput();arg.set_editor_property('input_name',ue.Name('UV'))
 flip=lib.create_material_expression(material,ue.MaterialExpressionCustom,-250,-50)
 flip.set_editor_properties(dict(inputs=[arg],code='return float2(UV.x,1-UV.y);',output_type=ue.CustomMaterialOutputType.CMOT_FLOAT2))
 assert lib.connect_material_expressions(uv,'',flip,'UV')
 assert lib.connect_material_expressions(flip,'',sample,'UVs')

sign=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='BEACON lighthouse sign')
comp=sign.get_component_by_class(ue.StaticMeshComponent);mat=comp.get_material(0)
sample=lib.get_material_property_input_node(mat,ue.MaterialProperty.MP_BASE_COLOR)
flip_uv(mat,sample)
mat.set_editor_property('shading_model',ue.MaterialShadingModel.MSM_UNLIT)
glow=lib.create_material_expression(mat,ue.MaterialExpressionMultiply,0,300);glow.set_editor_property('const_b',.80)
assert lib.connect_material_expressions(sample,'RGB',glow,'A')
assert lib.connect_material_property(glow,'',ue.MaterialProperty.MP_EMISSIVE_COLOR)
assert not lib.recompile_material(mat);assert assets.save_loaded_asset(mat,False)
sign.set_actor_location(ue.Vector(3264,1290,425),False,True)

path='/Game/StreetArtPass/Materials/M_WallAdvert'
master=ue.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Game/ImportedAssets/Posters/Shared/M_Poster',path)
sample=lib.get_material_property_input_node(master,ue.MaterialProperty.MP_BASE_COLOR)
flip_uv(master,sample);assert not lib.recompile_material(master);assert assets.save_loaded_asset(master,False)
for a in actors.get_all_level_actors():
 if not a.actor_has_tag('PreservedImageAspect'):continue
 mi=a.get_component_by_class(ue.StaticMeshComponent).get_material(0)
 lib.set_material_instance_parent(mi,master);lib.update_material_instance(mi);assert assets.save_loaded_asset(mi,False)

ground=next((a for a in actors.get_all_level_actors() if a.get_actor_label()=='Distant neighborhood ground'),None)
if not ground:
 ground=actors.spawn_actor_from_class(ue.StaticMeshActor,ue.Vector(0,0,-44))
 ground.set_actor_label('Distant neighborhood ground');ground.set_folder_path('Street/Art pass');ground.tags=[ue.Name('StreetArtPass_v1')]
 ground.set_actor_scale3d(ue.Vector(800,800,800))
 c=ground.get_component_by_class(ue.StaticMeshComponent);c.set_static_mesh(ue.load_asset('/Engine/BasicShapes/Plane'))
 c.set_material(0,ue.load_asset('/Game/StreetArtPass/Materials/M_RoadAsphalt'));c.set_collision_profile_name('NoCollision')
 c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False));c.set_cull_distance(100000)
assert lv.save_current_level()
ue.log('STREET_ART_POLISH_PASSED UV orientation, illuminated BEACON, distant ground')
