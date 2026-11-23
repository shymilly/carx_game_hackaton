"""Replace the planted scenery while preserving the street's foliage placement and routes."""
from random import Random

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, LIB, P, PROJECT, V, media, node, output, save
from CityLifeEnvironment import CityLayout, STREET_SHIFT


ROOT = '/Game/Prologue/Brighton/Forest'
SOURCE = PROJECT/'Saved/BrightonDetail/ForestAssets'
OLD = {
    'SM_OakAmber':'ConiferMedium', 'SM_OakGreen':'ConiferTall', 'SM_BirchGold':'ConiferSmall',
    'SM_CourtyardBirch':'ConiferTall', 'SM_CourtyardShrub':'Shrub02', 'SM_Bush':'Shrub05',
}
PLANT_TAG = ue.Name('BrightonForestPlanting')


def surface(name, filename, masked=False, normal_file=None):
    texture = media(SOURCE/(filename+'.png'), ROOT+'/Textures')
    material = make_material(ROOT,'Forest'+name,(.15,.20,.07),.83)
    color = LIB.get_material_property_input_node(material, P.MP_BASE_COLOR)
    if isinstance(color,ue.MaterialExpressionTextureSample):
        return material
    color = node(material,ue.MaterialExpressionTextureSample,texture=texture)
    output(color,material,P.MP_BASE_COLOR,'RGB')
    if masked:
        material.set_editor_properties(dict(blend_mode=ue.BlendMode.BLEND_MASKED,two_sided=True,opacity_mask_clip_value=.37))
        output(color,material,P.MP_OPACITY_MASK,'A')
    if normal_file:
        normal = media(SOURCE/(normal_file+'.png'),ROOT+'/Textures')
        normal.set_editor_properties(dict(compression_settings=ue.TextureCompressionSettings.TC_NORMALMAP,
                                          srgb=False, flip_green_channel=True))
        save(normal)
        sample = node(material,ue.MaterialExpressionTextureSample,texture=normal,
                      sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        output(sample,material,P.MP_NORMAL,'RGB')
    LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    LIB.recompile_material(material)
    save(material)
    return material


def assets():
    bark = surface('Bark','T_ForestBark')
    needles = surface('Needles','T_ForestNeedles',True,'T_ForestNeedles_N')
    foliage = {name:surface(name,'T_Forest'+name,True) for name in ('Shrub02','Shrub05','Grass')}
    lods = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    if lods is None:
        ue.load_module('StaticMeshEditor')
        lods = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    models = {}
    for name in sorted(set(OLD.values()) | {'Grass'}):
        mesh_name = 'SM_Forest'+name
        mesh = media(SOURCE/(mesh_name+'.obj'), ROOT+'/Meshes')
        index_lookup = {'Bark':bark,'Needles':needles} if name.startswith('Conifer') else None
        for index,slot in enumerate(mesh.get_editor_property('static_materials')):
            key = str(slot.get_editor_property('material_slot_name'))
            mesh.set_material(index, index_lookup[key] if index_lookup else foliage[name])
        span = mesh.get_bounding_box()
        height = span.max.z-span.min.z
        assert (height > 600 and abs(span.min.z)<.8) if index_lookup else (12<height<200), (name,span)
        if lods and index_lookup and lods.get_lod_count(mesh) < 3:
            settings = [ue.StaticMeshReductionSettings(percent_triangles=ratio,screen_size=size)
                        for ratio,size in ((1,1),(.55,.22),(.29,.09))]
            lods.set_lods(mesh,ue.StaticMeshReductionOptions(auto_compute_lod_screen_size=False,reduction_settings=settings))
        if lods and lods.get_simple_collision_count(mesh):
            lods.remove_collisions(mesh)
        save(mesh)
        models[name] = mesh
        ue.log(f'FOREST_MESH {name} height={height:.1f} lods={lods.get_lod_count(mesh) if lods else "unavailable"}')
    return models


def grounded(old_box, target_box, transform):
    location, scale = transform.translation, transform.scale3d
    old_height = (old_box.max.z-old_box.min.z)*abs(scale.z)
    new_scale = old_height/(target_box.max.z-target_box.min.z)
    location.z += min(old_box.min.z*scale.z,old_box.max.z*scale.z) - target_box.min.z*new_scale
    transform.translation = location
    transform.scale3d = V(new_scale,new_scale,new_scale)
    return transform


def replace(models):
    placed = ACTORS.get_all_level_actors()
    count = replace_split_trees(placed,models['ConiferTall'])
    for actor in ACTORS.get_all_level_actors():
        for component in actor.get_components_by_class(ue.StaticMeshComponent):
            mesh = component.static_mesh
            key = OLD.get(mesh.get_name()) if mesh else None
            if not key:
                continue
            target = models[key]
            has_instances = isinstance(component,ue.InstancedStaticMeshComponent)
            transforms = ([component.get_instance_transform(index,True) for index in range(component.get_instance_count())]
                          if has_instances else [component.get_world_transform()])
            for index in range(component.get_num_materials()):
                component.set_material(index,None)
            component.set_static_mesh(target)
            for index,transform in enumerate(transforms):
                adjusted = grounded(mesh.get_bounding_box(), target.get_bounding_box(), transform)
                if has_instances:
                    assert component.update_instance_transform(index,adjusted,True,True,True)
                else:
                    component.set_world_transform(adjusted,False,True)
            count += len(transforms)
    return count


def replace_split_trees(placed, tree):
    groups = {actor.get_actor_label():actor for actor in placed if isinstance(actor,ue.StreetMeshInstances)}
    leaves = []
    count = 0
    for label,actor in groups.items():
        if not label.startswith('Imported tree bark'):
            continue
        canopy = groups[label.replace('tree bark','tree canopy')]
        components = [part.get_component_by_class(ue.InstancedStaticMeshComponent) for part in (actor,canopy)]
        bark, branches = components
        assert bark.get_instance_count() == branches.get_instance_count(),label
        bounds = bark.static_mesh.get_bounding_box()
        base = (bounds.min+bounds.max)*.5
        base.z = bounds.min.z
        top = branches.static_mesh.get_bounding_box().max.z
        target = tree.get_bounding_box()
        positions = []
        for index in range(bark.get_instance_count()):
            transform = bark.get_instance_transform(index,True)
            ground = ue.MathLibrary.transform_location(transform,base)
            scale = (top-base.z)*abs(transform.scale3d.z)/(target.max.z-target.min.z)
            ground.z -= target.min.z*scale
            positions.append(ue.Transform(location=ground,scale=V(scale,scale,scale)))
        bark.clear_instances()
        for index in range(bark.get_num_materials()):
            bark.set_material(index,None)
        bark.set_static_mesh(tree)
        for position in positions:
            bark.add_instance(position,True)
        actor.set_actor_label(label.replace('Imported tree bark','Forest Scene tree'))
        leaves.append(canopy)
        count += len(positions)
    if leaves:
        assert ACTORS.destroy_actors(leaves)
    return count


class Planting(CityLayout):
    def actor(self, cls, label, position=(0,0,0), rotation=None):
        actor = super().actor(cls,label,position,rotation)
        actor.tags = [PLANT_TAG]
        actor.set_folder_path('Brighton/Forest Scene')
        return actor

    def plant(self, name, position, height, yaw, cull):
        mesh = self.models[name]
        bounds = mesh.get_bounding_box()
        scale = height/(bounds.max.z-bounds.min.z)
        point = (position[0],position[1],position[2]-bounds.min.z*scale)
        self.instance('Forest '+name,mesh,point,(scale,scale,scale),yaw,cull=cull)


def plant_neighborhood(models, facade_view):
    old = [actor for actor in ACTORS.get_all_level_actors() if actor.actor_has_tag(PLANT_TAG)]
    if old:
        assert ACTORS.destroy_actors(old)
    city = Planting(models,STREET_SHIFT if facade_view else (0,0,0))
    lawns = [actor for actor in ACTORS.get_all_level_actors()
             if actor.get_actor_label().removeprefix('Third-floor view ') == 'Park lawn']
    rng = Random(199410)
    for index,lawn in enumerate(lawns):
        center,extent = lawn.get_actor_bounds(False)
        x,y,z = (center-city.offset).to_tuple()
        z += extent.z
        for px,py in ((x-.71*extent.x,y+.71*extent.y),(x+.70*extent.x,y-.69*extent.y)):
            model = 'ConiferMedium' if index%2 else 'ConiferSmall'
            city.plant(model,(px,py,z),rng.uniform(330,465),rng.randrange(360),14800)
        for cluster in range(12):
            side = 1 if cluster%2 else -1
            px = x+rng.uniform(-.82,.82)*extent.x
            py = y+side*rng.uniform(.58,.94)*extent.y
            if cluster%3 == 0:
                city.plant('Shrub02' if side>0 else 'Shrub05',(px,py,z),rng.uniform(37,72),rng.randrange(360),5500)
            for _ in range(7):
                city.plant('Grass',(px+rng.uniform(-29,29),py+rng.uniform(-18,18),z-.5),
                           rng.uniform(10,24),rng.randrange(360),2800)
    wells = [actor for actor in ACTORS.get_all_level_actors()
             if actor.get_actor_label().removeprefix('Third-floor view ') == 'Unglazed street tree wells']
    for well in wells:
        soil = well.get_component_by_class(ue.InstancedStaticMeshComponent)
        for index in range(soil.get_instance_count()):
            x,y,z = (soil.get_instance_transform(index,True).translation-city.offset).to_tuple()
            for dx,dy in ((-27,-24),(21,-27),(-17,27),(25,12)):
                city.plant('Grass',(x+dx,y+dy,z+.4),rng.uniform(8,16),rng.randrange(360),2400)
    for (label,*_),instances in city.batches.items():
        if label == 'Forest Grass':
            instances.set_editor_property('cast_shadow',False)
    ue.log('FOREST_PARK_OK '+str(len(lawns)))
