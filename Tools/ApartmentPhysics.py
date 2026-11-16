"""Collision and physical materials used on the apartment map."""
import unreal as ue


SURFACES = {
    # Dynamic friction, static friction, restitution, density in g/cm³.
    "wood": (.44, .58, .08, .68),
    "tile": (.49, .65, .04, 2.28),
    "metal": (.31, .45, .12, 7.7),
    "fabric": (.70, .82, .03, .35),
    "rubber": (.79, .94, .05, 1.20),
    "plaster": (.56, .72, .03, 1.43),
    "polymer": (.43, .58, .09, 1.18),
}

# These furnishings stay anchored. Each gets one box for pawn/physics contact and
# retains the detailed original mesh for the interaction trace.
FURNITURE_BOXES = {
    "Bed": ("fabric", 79), "Sofa facing TV": ("fabric", 83),
    "TV stand": ("wood", 38), "Wardrobe shelves": ("wood", 57),
    "Fridge cabinet": ("metal", 68), "Kitchen sink": ("tile", 42),
    "Cooker": ("metal", 58), "Kitchen drawers": ("wood", 36),
    "Washing machine": ("metal", 70), "Potted plant": ("tile", 7),
}
KINEMATIC_MASS = {"KitchenDoor": 24, "BathDoor": 22, "FridgeDoor": 12}
ACTOR_SURFACE = {"tile": "tile", "ceramic": "tile", "oak": "wood", "ink": "polymer",
                 "paper": "fabric", "painted": "polymer", "dark_metal": "metal"}


def create_physical_materials(root):
    assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    tools = ue.AssetToolsHelpers.get_asset_tools()
    result = {}
    for surface, (friction, static_friction, restitution, density) in SURFACES.items():
        path = f"{root}/Physics"
        name = f"PM_{surface}"
        target = f"{path}/{name}"
        material = ue.load_asset(target) if assets.does_asset_exist(target) else tools.create_asset(
            name, path, ue.PhysicalMaterial, ue.PhysicalMaterialFactoryNew())
        material.set_editor_properties({"friction": friction, "static_friction": static_friction,
                                        "restitution": restitution, "density": density})
        if not assets.save_loaded_asset(material, False):
            raise RuntimeError(f"Could not save {name}.")
        result[surface] = material
    return result


def configure_prop(actor, component, materials, finish, collision, tag):
    if not collision:
        component.set_collision_profile_name(ue.Name("NoCollision"))
        actor.set_actor_enable_collision(False)
        return
    surface = finish.removesuffix("_wall")
    component.set_phys_material_override(materials.get(surface, materials[ACTOR_SURFACE.get(surface, "polymer")]))
    if tag in ("Report", "Newspaper", "LivingSwitch", "KitchenSwitch", "BathSwitch", "ShowerTap"):
        component.set_collision_profile_name(ue.Name("ApartmentFocus"))


def configure_furniture(actor, component, item, mesh, props, physical_materials):
    if item.tag in KINEMATIC_MASS:
        surface = "metal" if item.tag == "FridgeDoor" else "wood"
        component.set_phys_material_override(physical_materials[surface])
        component.set_mass_override_in_kg(ue.Name(), KINEMATIC_MASS[item.tag])
    elif item.tag == "FloorLamp":
        configure_floor_lamp(component, mesh, physical_materials["rubber"])
    elif item.label in FURNITURE_BOXES:
        surface, mass = FURNITURE_BOXES[item.label]
        center, extents = actor.get_actor_bounds(False)
        dims = tuple(2 * side for side in (extents.x, extents.y, extents.z))
        finish = {"metal": "dark_metal", "tile": "tile", "wood": "oak", "fabric": "fabric"}[surface]
        proxy = props(item.label + " collision", (center.x, center.y, center.z), dims, finish, "08 Simple collision")
        proxy.set_actor_hidden_in_game(True)
        collider = proxy.get_component_by_class(ue.StaticMeshComponent)
        collider.set_editor_properties({"cast_shadow": False, "visible": False})
        collider.set_phys_material_override(physical_materials[surface])
        collider.set_mass_override_in_kg(ue.Name(), mass)
        collider.set_collision_profile_name(ue.Name("ApartmentFurniture"))
        component.set_collision_profile_name(ue.Name("ApartmentFocus"))
    elif item.model.startswith("Carpet_"):
        component.set_collision_profile_name(ue.Name("NoCollision"))
    else:
        surface = ("tile" if item.model.startswith("Bathroom_") else "metal" if item.model.startswith("Light_")
                   else "wood")
        component.set_phys_material_override(physical_materials[surface])


def configure_floor_lamp(component, source_mesh, physical_material):
    assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    path = "/Game/Prologue/Physics/SM_FloorLamp_Physics"
    mesh = ue.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_loaded_asset(source_mesh, path)
    if not mesh:
        raise RuntimeError("Could not create floor lamp collision mesh.")
    mesh_editor = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    mesh.get_editor_property("body_setup").set_editor_property(
        "collision_trace_flag", ue.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    mesh_editor.remove_collisions(mesh)
    shape = mesh_editor.add_simple_collisions(mesh, ue.ScriptCollisionShapeType.NDOP26)
    if shape < 0 or not assets.save_loaded_asset(mesh, False):
        raise RuntimeError("Could not save the floor lamp's simple collision.")
    component.set_static_mesh(mesh)
    component.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
    component.set_linear_damping(.42)
    component.set_angular_damping(1.1)
    component.set_collision_profile_name(ue.Name("PhysicsActor"))
    component.set_collision_response_to_channel(ue.CollisionChannel.ECC_VISIBILITY, ue.CollisionResponseType.ECR_BLOCK)
    component.set_phys_material_override(physical_material)
    component.set_mass_override_in_kg(ue.Name(), 7.5)
    component.set_simulate_physics(True)
    component.set_center_of_mass(ue.Vector(0, 0, -34))


def stabilize_lamp(component):
    mesh = component.static_mesh
    setup = mesh.get_editor_property("body_setup")
    geometry = setup.get_editor_property("agg_geom")
    parts = []
    # Local dimensions from the Light_Floor2 mesh: foot, pedestal, stem, and shade.
    for center, width, depth, height in ((1.45, 11.2, 11.2, 2.9), (6.4, 28.4, 28.4, 7.6),
                                         (25.3, 6.0, 6.0, 36.2), (59.2, 28.0, 30.4, 32.0)):
        box = ue.KBoxElem()
        box.set_editor_properties({"center": ue.Vector(0, 0, center), "x": width, "y": depth, "z": height})
        parts.append(box)
    component.set_simulate_physics(False)
    for name in ("sphere_elems", "sphyl_elems", "convex_elems"):
        geometry.set_editor_property(name, [])
    geometry.set_editor_property("box_elems", parts)
    setup.set_editor_property("agg_geom", geometry)
    setup.set_editor_property("collision_trace_flag", ue.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    if not ue.get_editor_subsystem(ue.EditorAssetSubsystem).save_loaded_asset(mesh, False):
        raise RuntimeError("Could not save the lamp's compound collision.")
    component.set_linear_damping(.65)
    component.set_angular_damping(2.0)
    body = component.get_editor_property("body_instance")
    body.set_editor_properties({"start_awake": False, "use_ccd": True})
    component.set_mass_override_in_kg(ue.Name(), 7.5)
    component.set_simulate_physics(True)
    component.set_center_of_mass(ue.Vector(0, 0, -34))


def tune_street_apartment_props():
    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    placed = {actor.get_actor_label(): actor for actor in actors.get_all_level_actors()}
    lamp = placed["Floor lamp"]
    stabilize_lamp(lamp.get_component_by_class(ue.StaticMeshComponent))

    chair = placed.get("Chair_2")
    duplicate = placed.get("Chair_3")
    if chair and duplicate and (chair.get_actor_location() - duplicate.get_actor_location()).length() < .02:
        primary = chair.get_component_by_class(ue.StaticMeshComponent)
        secondary = duplicate.get_component_by_class(ue.StaticMeshComponent)
        if primary.static_mesh == secondary.static_mesh:
            if not actors.destroy_actor(duplicate):
                raise RuntimeError("Could not remove the overlapping chair duplicate.")
            ue.log("APARTMENT_DUPLICATE_CHAIR_REMOVED")
    if chair:
        tags = list(chair.tags)
        if ue.Name("DeskSeat") not in tags:
            chair.set_editor_property("tags", tags + [ue.Name("DeskSeat")])

    for tag, seat, table, height in (("DeskSeatView", chair, placed["Writing desk"], 121),
                                     ("KitchenSeatView", placed["Kitchen chair"], placed["Kitchen table"], 117)):
        if not seat:
            continue
        camera = next(actor for actor in placed.values() if ue.SystemLibrary.is_valid(actor) and actor.actor_has_tag(ue.Name(tag)))
        foot = seat.get_actor_location()
        center, extent = table.get_actor_bounds(False)
        eye = ue.Vector(foot.x, foot.y, height)
        tabletop = ue.Vector(center.x, center.y, center.z + extent.z)
        camera.set_actor_location(eye, False, False)
        camera.set_actor_rotation(ue.MathLibrary.find_look_at_rotation(eye, tabletop), False)

    desk_lamp = placed["Desk lamp"]
    desk_bulb = placed["Desk lamp bulb"]
    transform = desk_lamp.get_actor_transform()
    emitter = ue.MathLibrary.transform_location(transform, ue.Vector(0, -24, 39))
    aim = ue.MathLibrary.transform_location(transform, ue.Vector(0, -45, 3))
    desk_bulb.set_actor_location(emitter, False, False)
    desk_bulb.set_actor_rotation(ue.MathLibrary.find_look_at_rotation(emitter, aim), False)
    keep = ue.AttachmentRule.KEEP_WORLD
    if desk_bulb.get_attach_parent_actor() != desk_lamp and not desk_bulb.attach_to_actor(
        desk_lamp, ue.Name(), keep, keep, keep, False
    ):
        raise RuntimeError("Could not attach the desk light to its lamp.")
    ue.log("APARTMENT_PROP_PHYSICS_OK compound floor lamp, chair fit and lamp attachment")
