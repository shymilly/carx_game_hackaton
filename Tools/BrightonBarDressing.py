"""Bar furnishings and game-scale imports of the five supplied bottle meshes."""
from random import Random

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, Builder, LIB, P, PROJECT, V, constant, media, node, output, save

BOTTLES = {'wine': 31.5, 'rum': 27.5, 'vodka': 30., 'whisky': 25., 'champagne': 32.5}
BAR = '/Game/Prologue/Furniture/LighthouseBar'
TAG = ue.Name('LighthouseBarDressing')


class BarFurniture(Builder):
    def actor(self, cls, name, position=(0, 0, 0), rotation=None):
        result = super().actor(cls, name, position, rotation)
        result.tags = [TAG]
        return result


def import_bottles():
    source = PROJECT / 'Resources/Brighton/Bar/alcohol_bottles_obj'
    staging = PROJECT / 'Saved/BrightonDetail/Bottles'
    staging.mkdir(parents=True, exist_ok=True)
    bottles = {}
    for kind, height in BOTTLES.items():
        folder = source / kind
        mesh_name = 'SM_Bottle_' + kind.title()
        lines = (folder / (kind + '.obj')).read_text(encoding='utf-8-sig').splitlines()
        vertices = [tuple(map(float, row.split()[1:4])) for row in lines if row.startswith('v ')]
        minimum = tuple(min(v[i] for v in vertices) for i in range(3))
        maximum = tuple(max(v[i] for v in vertices) for i in range(3))
        base = ((minimum[0] + maximum[0]) / 2, (minimum[1] + maximum[1]) / 2, minimum[2])
        scale = height / (maximum[2] - minimum[2])
        positions = iter(vertices)
        normalized = []
        for row in lines:
            if row.startswith('v '):
                position = next(positions)
                row = 'v ' + ' '.join(f'{(position[i] - base[i])*scale:.6f}' for i in range(3))
            elif row.startswith('o '):
                row = 'o ' + mesh_name
            elif row.startswith('mtllib '):
                # Assign the authored slots explicitly so no duplicate Interchange materials are made.
                continue
            normalized.append(row)
        mesh_file = staging / (mesh_name + '.obj')
        mesh_file.write_text('\n'.join(normalized) + '\n', encoding='utf-8')
        mesh = media(mesh_file, BAR + '/Meshes')
        bounds = mesh.get_bounding_box()
        assert abs(bounds.min.z) < .2 and abs(bounds.max.z - height) < .2, (kind, bounds)

        definitions = {}
        for row in (folder / (kind + '.mtl')).read_text(encoding='utf-8-sig').splitlines():
            columns = row.split()
            if row.startswith('newmtl '):
                slot_name = columns[1]
            elif row.startswith('Kd '):
                definitions[slot_name] = tuple(map(float, columns[1:4]))
        label = media(folder / 'label.png', BAR + '/Textures', 'T_Bottle_' + kind.title())
        seen = set()
        for index, slot in enumerate(mesh.get_editor_property('static_materials')):
            imported_name = str(slot.get_editor_property('imported_material_slot_name'))
            name = next(key for key in definitions if imported_name.lower().endswith(key.lower()))
            seen.add(name)
            tint = definitions[name]
            if name == 'Glass':
                tint = tuple(channel * .60 for channel in tint)
            roughness = {'Glass': .20, 'Cap': .33, 'Label': .62}[name]
            material = make_material(BAR, 'Bottle_' + kind.title() + '_' + name, tint, roughness)
            if name == 'Label':
                base_input = LIB.get_material_property_input_node(material, P.MP_BASE_COLOR)
                if not isinstance(base_input, ue.MaterialExpressionTextureSample):
                    if base_input:
                        LIB.delete_material_expression(material, base_input)
                    output(node(material, ue.MaterialExpressionTextureSample, texture=label), material, P.MP_BASE_COLOR, 'RGB')
            if name == 'Cap' and not LIB.get_material_property_input_node(material, P.MP_METALLIC):
                output(constant(material, .53), material, P.MP_METALLIC)
            LIB.set_material_usage(material, ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
            LIB.recompile_material(material)
            save(material)
            mesh.set_material(index, material)
        assert seen == set(definitions), (kind, seen)
        save(mesh)
        bottles[kind] = mesh
    return bottles


def set_handheld_bottles(placed, bottles):
    roles = {'Bartender with broken nose': 'whisky', 'Older immigrant holding a bottle': 'wine'}
    for character in (actor for actor in placed if actor.get_actor_label() in roles):
        kind = roles[character.get_actor_label()]
        mesh = character.get_editor_property('character_mesh')
        assert mesh.does_socket_exist('BottleGrip'), character
        bottle = next(child for child in character.get_attached_actors(True, True)
                      if child.get_actor_label() == 'Green glass bottle')
        component = bottle.get_component_by_class(ue.StaticMeshComponent)
        component.set_static_mesh(bottles[kind])
        component.set_editor_property('override_materials', [])
        component.set_mobility(ue.ComponentMobility.MOVABLE)
        component.set_collision_profile_name('NoCollision')
        component.set_absolute(False, False, True)
        bottle.set_actor_scale3d(V(1, 1, 1))
        assert bottle.attach_to_component(mesh, 'BottleGrip', ue.AttachmentRule.SNAP_TO_TARGET,
            ue.AttachmentRule.SNAP_TO_TARGET, ue.AttachmentRule.KEEP_WORLD, False)
        socket_scale = mesh.get_socket_transform('BottleGrip').scale3d
        component.set_relative_location(V(0, 2 / socket_scale.y, -.42 * BOTTLES[kind] / socket_scale.z), False, True)


def dress_bar(bottles):
    placed = ACTORS.get_all_level_actors()
    outdated = {'Bar bottle', 'Bottle neck', 'Different bottles behind the bar', 'Foil bottle neck',
                'Cast-iron stool base', 'Worn stool seat'}
    # Retain the existing shelf planks, NPC anchors and interaction volumes.
    old = [actor for actor in placed if actor.actor_has_tag(TAG) or actor.get_actor_label() in outdated]
    if old:
        assert ACTORS.destroy_actors(old)
    set_handheld_bottles(placed, bottles)
    tune_bar_lights(placed)
    layout = BarFurniture('Lighthouse/Backbar and seating')
    rng = Random(1494)
    shelves = sorted((actor for actor in placed if actor.get_actor_label() == 'Bottles backboard'),
                     key=lambda actor: actor.get_actor_location().z)
    assert len(shelves) == 3
    assortments = (('wine', 'whisky', 'rum', 'vodka', 'whisky'),
                   ('rum', 'vodka', 'whisky', 'wine', 'champagne'),
                   ('champagne', 'wine', 'vodka', 'rum', 'champagne'))
    for shelf, assortment in zip(shelves, assortments):
        center, ext = shelf.get_actor_bounds(False)
        for group, kind in enumerate(assortment):
            for index in range(3):
                x = center.x - ext.x + 41 + group * 127 + index * 24
                size = rng.uniform(.96, 1.03)
                layout.instance('Backbar ' + kind, (x, center.y + rng.uniform(-4, 9), center.z + ext.z + .05),
                    (size, size, size), None, -90 + rng.uniform(-9, 9), bottles[kind])

    timber = ue.load_asset('/Game/Prologue/ModernFinishes/Materials/M_oak')
    iron = ue.load_asset('/Game/Prologue/ModernFinishes/Materials/M_dark_metal')
    assert timber and iron
    if not iron.get_editor_property('used_with_instanced_static_meshes'):
        LIB.set_material_usage(iron, ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        save(iron)
    for x in (-311, -94, 126, 347):
        layout.box('Wood uprights for the bottle display', (x, -463, 185), (5, 8, 145), timber)
    for shelf in shelves:
        center, extent = shelf.get_actor_bounds(False)
        layout.box('Rounded edge of the backbar shelf', (center.x, center.y + extent.y + .5, center.z),
                   (651, 4.3, 5.1), timber)

    def furniture(model, positions, height, materials):
        asset = ue.load_asset('/Game/Prologue/Furniture/Pack/' + model)
        assert asset, model
        bounds = asset.get_bounding_box()
        scale = height / (bounds.max.z - bounds.min.z)
        assert 25 < max(bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y)*scale < 110, model
        for x, y, yaw in positions:
            actor = layout.actor(ue.StaticMeshActor, 'Bar ' + model, (x, y, -bounds.min.z * scale), ue.Rotator(yaw=yaw))
            actor.set_actor_scale3d(V(scale, scale, scale))
            component = actor.get_component_by_class(ue.StaticMeshComponent)
            component.set_static_mesh(asset)
            component.set_collision_profile_name('NoCollision')
            for slot in range(component.get_num_materials()):
                component.set_material(slot, materials[slot % len(materials)])
            seat = 66 if model == 'Stool' else 45
            width = min(48, (bounds.max.x - bounds.min.x)*scale)
            depth = min(47, (bounds.max.y - bounds.min.y)*scale)
            collider = layout.box('Bar seat collision', (x, y, seat/2), (width, depth, seat), timber, collision=True)
            collider.set_actor_rotation(ue.Rotator(yaw=yaw), False)
            collider.set_actor_hidden_in_game(True)
            shape = collider.get_component_by_class(ue.StaticMeshComponent)
            shape.set_collision_enabled(ue.CollisionEnabled.QUERY_ONLY)
            shape.set_editor_properties(dict(cast_shadow=False, affect_distance_field_lighting=False))
            assert collider.attach_to_actor(actor, ue.Name(), ue.AttachmentRule.KEEP_WORLD,
                ue.AttachmentRule.KEEP_WORLD, ue.AttachmentRule.KEEP_WORLD, False)

    furniture('Stool', [(x, -224, 0) for x in (-307, -189, -55, 83, 212, 330)], 68, (timber, iron))
    furniture('Chair_3', [(x - 83, y - 8, 0) for x, y in ((-353, 348), (-61, 352), (247, 373))], 87, (timber,))
    furniture('Chair_2', [(x + 81, y + 2, 180) for x, y in ((-353, 348), (-61, 352), (247, 373))], 87, (timber,))

    for kind, x, y, yaw in (('rum', -161, -292, 10), ('whisky', -181, -300, -12),
                            ('vodka', 258, -328, -23), ('wine', 240, -323, 4)):
        layout.instance('Bottles on the counter', (x, y, 107.05), (1, 1, 1), None, -90+yaw, bottles[kind])
    for kind, position in (('wine', (-341, 352, 76.05)), ('whisky', (230, 358, 76.05))):
        layout.instance('Bottle left on a table', position, (1, 1, 1), None, rng.randrange(360), bottles[kind])
    tin = ue.load_asset('/Engine/BasicShapes/Cylinder')
    for x, y in ((-327, 339), (-38, 349), (265, 369), (-276, -273)):
        height = 107 if y < 0 else 76
        layout.instance('Tin ashtray', (x, y, height + 1.2), (.135, .135, .024), iron, mesh=tin)
    ue.log('QUALITY_BAR_BOTTLES 5 models, 45 shelf placements, four counter bottles, two table bottles and two held bottles')


def tune_bar_lights(placed):
    plaster = ue.load_asset('/Game/Story/ActOne/Materials/M_plaster')
    for actor in placed:
        name = actor.get_actor_label()
        if name == 'Lighthouse ceiling':
            actor.get_component_by_class(ue.StaticMeshComponent).set_material(0, plaster)
        elif name in ('Amber pool of light', 'Cool light leaking from the door', 'Low ambient reflection in the booths'):
            light = actor.get_component_by_class(ue.PointLightComponent)
            if name == 'Amber pool of light':
                level, radius, color = 11.5, 410, ue.LinearColor(1., .87, .72, 1.)
            elif name == 'Cool light leaking from the door':
                level, radius, color = 6.4, 340, ue.LinearColor(.66, .79, 1., 1.)
            else:
                level, radius, color = 3.4, 520, ue.LinearColor(.83, .76, .66, 1.)
            light.set_intensity(level)
            light.set_attenuation_radius(radius)
            light.set_light_color(color)
