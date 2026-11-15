"""Lighting groups and wall switches for the three rooms."""
import unreal as ue


def build_lighting(actors, prop, materials, floor_lamp):
    vector, rotator = ue.Vector, ue.Rotator
    folder = "06 Lighting"

    def spotlight(label, tag, pos, rotation, lumens, kelvin, radius, cone, source):
        lamp = actors.spawn_actor_from_class(ue.SpotLight, vector(*pos), rotator(0, *rotation))
        lamp.set_actor_label(label)
        lamp.set_folder_path(ue.Name(folder))
        lamp.set_editor_property("tags", [ue.Name(tag)])
        component = lamp.get_component_by_class(ue.SpotLightComponent)
        component.set_editor_properties({"mobility": ue.ComponentMobility.MOVABLE,
                                         "use_inverse_squared_falloff": True,
                                         "intensity_units": ue.LightUnits.LUMENS,
                                         "cast_shadows": True, "cast_dynamic_shadows": True,
                                         "source_radius": source, "soft_source_radius": source * .65,
                                         "contact_shadow_length": .025, "volumetric_scattering_intensity": .35,
                                         "shadow_resolution_scale": .75})
        component.set_intensity(lumens)
        component.set_temperature(kelvin)
        component.set_use_temperature(True)
        component.set_attenuation_radius(radius)
        component.set_outer_cone_angle(cone)
        component.set_inner_cone_angle(cone * .72)
        return lamp

    for label, tag, x, y, power, radius, fill in (
        ("Living north", "LivingRoomLight", -105, 216, 230, 570, (183, 143, 335)),
        ("Living south", "LivingRoomLight", 60, -205, 230, 570, (-228, -145, 288)),
        ("Kitchen", "KitchenRoomLight", -576, 239, 200, 420, (-575, 260, 210)),
        ("Bathroom", "BathRoomLight", 590, -107, 235, 535, (600, -158, 214)),
    ):
        prop(label + " ceiling housing", (x, y, 274), (48, 48, 12), "dark_metal", folder, collision=False)
        prop(label + " satin diffuser", (x, y, 267), (43, 43, 3), "painted", folder, collision=False)
        spotlight(label + " ceiling", tag, (x, y, 261), (-90, 0), power, 4050, radius, 73, 20)
        bx, by, bounce_radius = fill
        bounce = actors.spawn_actor_from_class(ue.PointLight, vector(bx, by, 218))
        bounce.set_actor_label(label + " wall bounce")
        bounce.set_folder_path(ue.Name(folder))
        bounce.set_editor_property("tags", [ue.Name(tag)])
        comp = bounce.get_component_by_class(ue.PointLightComponent)
        comp.set_editor_properties({"mobility": ue.ComponentMobility.MOVABLE,
                                    "use_inverse_squared_falloff": False,
                                    "cast_shadows": False, "cast_dynamic_shadows": False,
                                    "specular_scale": 0., "volumetric_scattering_intensity": 0.})
        comp.set_intensity(1.8)
        comp.set_attenuation_radius(bounce_radius)
        comp.set_light_color(ue.LinearColor(1., .97, .92, 1.))

    spotlight("Desk lamp bulb", "DeskLampLight", (-90, 362, 127), (-64, -30), 22, 2850, 190, 52, 2.5)
    floor_bulb = spotlight("Floor lamp bulb", "FloorLampLight", (140, -182, 126), (-90, 0),
                           48, 2750, 245, 60, 4.)
    keep = ue.AttachmentRule.KEEP_WORLD
    if not floor_bulb.attach_to_actor(floor_lamp, ue.Name(), keep, keep, keep, False):
        raise RuntimeError("Could not attach the light to the simulated lamp.")

    # Approximate US single-gang plate dimensions, 6.99 × 11.43 cm.
    for tag, wall_pos, yaw, room in (
        ("LivingSwitch", (-382.98, 76, 122), 0, "02 Main room"),
        ("KitchenSwitch", (-397.02, 76, 122), 180, "03 Kitchen"),
        ("BathSwitch", (397.02, -379, 122), 0, "04 Bathroom"),
    ):
        x, y, z = wall_pos
        sign = 1 if yaw == 0 else -1
        prop(tag + " plate", (x + sign * .38, y, z), (.8, 7, 11.43), "painted", room, tag)
        prop(tag + " inset", (x + sign * .83, y, z), (.25, 4.1, 7.25), "dark_metal", room, collision=False)
        rocker = prop(tag + " rocker", (x + sign * 1.17, y, z), (.75, 3.45, 6.25), "ceramic", room, tag)
        rocker.get_component_by_class(ue.StaticMeshComponent).set_editor_property("mobility", ue.ComponentMobility.MOVABLE)
        rocker.set_actor_rotation(rotator(0, 12, yaw), False)
        rocker.set_editor_property("tags", [ue.Name(tag), ue.Name(tag + "Rocker")])
