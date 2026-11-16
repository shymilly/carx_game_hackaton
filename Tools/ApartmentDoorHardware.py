"""Place hinge leaves and pins on the same axes as the gameplay doors."""
from math import cos, radians, sin

import unreal as ue

from ApartmentFixtures import dimensions_material


FOLDER = "01 Architecture/Door hardware"


def add_door_hardware(door_specs):
    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    placed = actors.get_all_level_actors()
    previous = [actor for actor in placed if str(actor.get_folder_path()) == FOLDER]
    if previous and not actors.destroy_actors(previous):
        raise RuntimeError("Could not replace old door hardware.")

    cube = ue.load_asset("/Engine/BasicShapes/Cube")
    cylinder = ue.load_asset("/Engine/BasicShapes/Cylinder")
    bronze = dimensions_material("DoorHinge", (.31, .20, .095), .46, .68)
    steel = dimensions_material("ApplianceHinge", (.29, .31, .32), .43, .75)

    def part(label, mesh, material, pos, size, yaw, parent=None):
        actor = actors.spawn_actor_from_class(ue.StaticMeshActor, pos, ue.Rotator(0, 0, yaw))
        actor.set_actor_label(label)
        actor.set_folder_path(ue.Name(FOLDER))
        component = actor.get_component_by_class(ue.StaticMeshComponent)
        component.set_static_mesh(mesh)
        component.set_material(0, material)
        component.set_collision_profile_name(ue.Name("NoCollision"))
        actor.set_actor_enable_collision(False)
        actor.set_actor_scale3d(ue.Vector(*(axis / 100 for axis in size)))
        if parent:
            component.set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
            keep = ue.AttachmentRule.KEEP_WORLD
            if not actor.attach_to_actor(parent, ue.Name(), keep, keep, keep, False):
                raise RuntimeError(f"Could not attach {label}.")
        return actor

    for tag, (closed, hinge, yaw, _) in door_specs.items():
        door = next(actor for actor in placed if actor.actor_has_tag(ue.Name(tag)))
        long_axis = ue.Vector(-sin(radians(yaw)), cos(radians(yaw)), 0)
        leaf_side = ue.Vector(*closed) - ue.Vector(*hinge)
        if sum(a*b for a, b in zip((long_axis.x, long_axis.y), (leaf_side.x, leaf_side.y))) < 0:
            long_axis *= -1
        fridge = tag == "FridgeDoor"
        material = steel if fridge else bronze
        center, extent = door.get_actor_bounds(False)
        heights = (-.66, .67) if fridge else (-.72, .04, .72)
        for index, fraction in enumerate(heights, 1):
            pin = ue.Vector(hinge[0], hinge[1], center.z + fraction * extent.z)
            label = f"{tag} hinge {index}"
            part(label + " pin", cylinder, material, pin, (1.55, 1.55, 8.5), yaw)
            if fridge:
                # The cabinet bracket runs back along the cabinet side from its front hinge.
                part(label + " jamb leaf", cube, material, pin - ue.Vector(2.8, .45, 0), (5.6, 1.15, 7.1), yaw)
            else:
                part(label + " jamb leaf", cube, material, pin - long_axis * 2.6, (1.0, 4.8, 7.1), yaw)
            part(label + " door leaf", cube, material, pin + long_axis * 2.6, (1.0, 4.8, 7.1), yaw, door)
    ue.log(f"APARTMENT_HINGES_OK {len(door_specs)} doors")
