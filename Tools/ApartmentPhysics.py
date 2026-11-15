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
