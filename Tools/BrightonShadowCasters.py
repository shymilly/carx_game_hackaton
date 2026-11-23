"""Keep the street's repeated opaque geometry off the non-Nanite VSM queue."""
import re

import unreal as ue

from BrightonUpgrade import ACTORS, ASSETS, LIB, save


MESH_FOLDER = '/Game/Prologue/Brighton/Meshes/Nanite'
GROUND_RECEIVERS = re.compile(
    r'ground below the skyline|distant neighborhood ground|^block foundation$|'
    r'main pavement.*base|asphalt (?:inlay|patch)|rail bed dirt layer', re.I)
OPAQUE = {ue.BlendMode.BLEND_OPAQUE,ue.BlendMode.BLEND_MASKED}
PROTOTYPES = {'Cube','Cylinder','Plane'}
TRANSLUCENT_FENCE = ('/Game/ImportedAssets/Industrial/ExteriorV2/Industrial_exterior_v2/'
                     'Industrial_exterior_v2/StaticMeshes/Fence')


def base_material(material):
    while isinstance(material,ue.MaterialInstance):
        material = material.get_editor_property('parent')
    return material


def fix_imported_fence():
    ue.load_module('StaticMeshEditor')
    editor = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    fence = ue.load_asset(TRANSLUCENT_FENCE)
    assert fence,TRANSLUCENT_FENCE
    settings = editor.get_nanite_settings(fence)
    if settings.enabled:
        settings.enabled = False
        editor.set_nanite_settings(fence,settings,True)
        save(fence)
    ue.log('REPAIR_FENCE_RENDERER_OK translucent fence uses the standard static mesh path')


def optimize_shadows():
    ue.load_module('StaticMeshEditor')
    editor = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    remapped = {}
    materials = set()
    casters = receivers = translucent = 0
    for actor in ACTORS.get_all_level_actors():
        for component in actor.get_components_by_class(ue.StaticMeshComponent):
            model = component.static_mesh
            if not model:
                continue
            original_materials = component.get_materials()
            surfaces = {base_material(asset) for asset in original_materials if asset}
            opaque = bool(surfaces) and all(isinstance(mat,ue.Material) and
                mat.get_editor_property('blend_mode') in OPAQUE and
                mat.get_editor_property('material_domain')==ue.MaterialDomain.MD_SURFACE for mat in surfaces)
            enabled = editor.get_nanite_settings(model).enabled
            if not opaque:
                # Translucent panes and fence overlays need the regular renderer.
                if enabled:
                    component.set_editor_property('disallow_nanite',True)
                    translucent += 1
                continue
            if not component.get_editor_property('cast_shadow') or actor.get_editor_property('hidden'):
                continue
            label = actor.get_actor_label().removeprefix('Third-floor view ')
            if GROUND_RECEIVERS.search(label):
                component.set_cast_shadow(False)
                receivers += 1
                continue
            if enabled:
                materials.update(surfaces)
                continue
            path = model.get_path_name()
            reusable = (
                path.startswith('/Engine/BasicShapes/') and model.get_name() in PROTOTYPES
                or model.get_name().startswith(('SM_HouseVolume','SM_Walkup','SM_MarketHouse','SM_BrightonEntry'))
                or model.get_name().endswith('_RoadTurn')
            )
            if not reusable:
                continue
            updated = remapped.get(path)
            if not updated:
                dest = MESH_FOLDER + '/' + model.get_name() + '_Shadow'
                updated = ue.load_asset(dest) if ASSETS.does_asset_exist(dest) else ASSETS.duplicate_asset(path,dest)
                assert updated,dest
                settings = editor.get_nanite_settings(updated)
                if not settings.enabled:
                    settings.enabled = True
                    editor.set_nanite_settings(updated,settings,True)
                    save(updated)
                remapped[path] = updated
            component.set_static_mesh(updated)
            component.set_editor_property('disallow_nanite',False)
            for index,material in enumerate(original_materials):
                if material and component.get_material(index)!=material:
                    component.set_material(index,material)
            materials.update(surfaces)
            casters += 1
    for material in materials:
        if material.get_path_name().startswith('/Game/'):
            LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_NANITE)
            save(material)
    ue.log(f'REPAIR_VSM_SCENE casters={casters} ground_receivers={receivers} translucent_overrides={translucent}')
