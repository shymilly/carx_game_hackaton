"""Retile the large surfaces and relight the playable passage and night exteriors."""
from datetime import datetime
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project / "Tools"))
from BrightonUpgrade import ACTORS, ASSETS, LEVELS, Builder, P, V, save
from StreetMasonry import street_bricks, tiled_surface

STREET = "/Game/Prologue/Street"
BRIGHTON = "/Game/Prologue/Brighton"
REFINEMENT = "/Game/StreetRefinement"
FINISHES = "/Game/Prologue/ModernFinishes"
TAG = ue.Name("BrightonRelighting")
FOLDER = "Brighton/Passage and night lighting"
backup = project / "Saved/Backups" / datetime.now().strftime("BrightonRelighting_%Y%m%d_%H%M%S")
maps = ("L_DimaApartmentInterior", "L_NeptuneStreet", "L_PolicePrecinct", "L_BrightonGrocery",
        "L_LighthouseBar", "L_FedorEntry", "L_FedorApartment", "L_BrightonAlley")


def preserve(uri, extension=".uasset"):
    relative = Path("Content") / (uri.removeprefix("/Game/").split(".", 1)[0] + extension)
    target = backup / relative
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(project / relative, target)


def retile():
    surfaces = (
        ("GreyPaintedPlaster", (144, 144), (1, 1, 1), .87),
        ("FadedOchreRender", (160, 160), (1, 1, 1), .89),
        ("WeatheredConcrete", (226, 226), (1, 1, 1), .83),
    )
    for name, span, tint, roughness in surfaces:
        source = REFINEMENT + "/Textures/T_" + name
        tiled(REFINEMENT + "/Materials/M_" + name, source + "_Color", source + "_Normal", span, tint, roughness)
    for name, tint, siding in (("PaintedSage", (.70, .94, .74), False), ("WarmPaintedMasonry", (.99, .83, .63), False),
                               ("BlueClapboard", (.54, .79, .91), True), ("CreamClapboard", (1.12, 1.03, .81), True)):
        source = REFINEMENT + "/Textures/T_GreyPaintedPlaster"
        tiled(BRIGHTON + "/Materials/M_" + name, source + "_Color", source + "_Normal",
              (144, 144), tint, .87, siding=siding)
    weather = ue.load_asset(BRIGHTON + "/Materials/MPC_Weather")
    assert weather
    for folder, name, source, span, wet in (
        (STREET, "concrete", STREET + "/Textures/T_concrete", (220, 220), False),
        (BRIGHTON, "Wet_concrete", STREET + "/Textures/T_concrete", (220, 220), True),
        (BRIGHTON, "Wet_WeatheredConcrete", REFINEMENT + "/Textures/T_WeatheredConcrete", (226, 226), True),
        (BRIGHTON, "Wet_asphalt", STREET + "/Textures/T_asphalt", (280, 280), True),
        (BRIGHTON, "Wet_NeptuneAsphalt", STREET + "/Textures/T_NeptuneAsphalt", (280, 280), True),
    ):
        albedo = source + "_Color" if ASSETS.does_asset_exist(source + "_Color") else source
        normal = source + "_Normal"
        tiled(folder + "/Materials/M_" + name, albedo, normal if ASSETS.does_asset_exist(normal) else None,
              span, (1, 1, 1), .85, weather=weather if wet else None)
    plaster = FINISHES + "/T_plaster"
    for uri, tint in ((FINISHES + "/Materials/M_plaster_wall", (1, 1, 1)),
                      (STREET + "/Materials/M_plaster_lobby", (.83, .84, .78)),
                      ("/Game/Story/ActOne/Materials/M_plaster", (.84, .81, .72))):
        tiled(uri, plaster + "_Albedo", plaster + "_Normal", (155, 155), tint, .85, pbr={
            P.MP_AMBIENT_OCCLUSION: plaster + "_AO", P.MP_ROUGHNESS: plaster + "_Roughness",
        })


def tiled(uri, *args, **kw):
    preserve(uri)
    tiled_surface(uri, *args, **kw)
    ue.log("QUALITY_TILED " + uri)


def spawn(cls, label, point, rotation=None):
    a = ACTORS.spawn_actor_from_class(cls, V(*point), rotation or ue.Rotator())
    assert a, label
    a.set_actor_label(label)
    a.set_folder_path(ue.Name(FOLDER))
    a.tags = list(a.tags) + [TAG]
    return a


def point(label, at, intensity, radius, tint, shadows=False):
    actor = spawn(ue.PointLight, label, at)
    light = actor.get_component_by_class(ue.PointLightComponent)
    local_light(light, intensity, radius, tint, shadows)
    return actor


def local_light(light, intensity, radius, tint, shadows, source_radius=14):
    light.set_editor_properties(dict(mobility=ue.ComponentMobility.MOVABLE,
        use_inverse_squared_falloff=False, cast_shadows=shadows, source_radius=source_radius,
        volumetric_scattering_intensity=0., indirect_lighting_intensity=.42))
    light.set_intensity(intensity)
    light.set_attenuation_radius(radius)
    light.set_light_color(ue.LinearColor(*tint, 1))


def passage(builder, placed, interior):
    offset = V(0, -48, -640) if interior else V()
    # The enclosed park starts past the street sign at x=-1078, y=-435.
    housing = ue.load_asset(STREET + "/Materials/M_steel")
    lamp = ue.load_asset("/Game/Story/ActOne/Materials/M_light")
    side = (-1336, 55, 235)
    bridge = (-1336, 509, 227)
    for x, y, z in (side, bridge):
        p = V(x, y, z) + offset
        builder.instance("Playground wall lantern housings", p.to_tuple(), (.15, .23, .24), housing)
        builder.instance("Playground frosted lantern glass", (p + V(8, 0, -4)).to_tuple(), (.07, .16, .13), lamp)
    point("Playground entry wall light", (V(-1290, 55, 217) + offset).to_tuple(), 2.2, 550, (1, .78, .59), not interior)
    point("Playground courtyard end fill", (V(-1285, 487, 220) + offset).to_tuple(), 2.7, 690, (.72, .84, 1))
    point("Press kiosk reflected canopy light", (V(-1215, -545, 218) + offset).to_tuple(), 1.35, 340, (1, .87, .72))
    for a in placed:
        if not a.actor_has_tag("WindowProjection"):
            continue
        light = a.get_component_by_class(ue.SpotLightComponent)
        if not light:
            continue
        # Projection uses the window light function. Distant ones do not need a VSM shadow.
        light.set_editor_property("volumetric_scattering_intensity", 0.)
        if interior or "Distant regular windows" in a.get_actor_label():
            light.set_editor_properties(dict(cast_shadows=False, indirect_lighting_intensity=0.))
        if not interior:
            light.set_intensity(min(light.get_editor_property("intensity"), 2.15))
    for a in placed:
        if isinstance(a, ue.SkyLight):
            light = a.get_component_by_class(ue.SkyLightComponent)
            light.set_editor_properties(dict(lower_hemisphere_is_black=True,
                                             lower_hemisphere_color=ue.LinearColor(.043, .054, .075, 1)))


def night_ambient(name, at):
    sky = spawn(ue.SkyLight, name + " sky fill", at)
    fill = sky.get_component_by_class(ue.SkyLightComponent)
    fill.set_editor_properties(dict(mobility=ue.ComponentMobility.MOVABLE, cast_shadows=True,
        intensity=.62, lower_hemisphere_is_black=True,
        lower_hemisphere_color=ue.LinearColor(.026, .034, .053, 1)))
    fill.set_light_color(ue.LinearColor(.66, .77, 1, 1))
    moon = spawn(ue.DirectionalLight, name + " overcast moon", at, ue.Rotator(pitch=-41, yaw=207))
    moonlight = moon.get_component_by_class(ue.DirectionalLightComponent)
    moonlight.set_editor_properties(dict(mobility=ue.ComponentMobility.MOVABLE, cast_shadows=True,
        light_source_angle=4.4, volumetric_scattering_intensity=0.,
        indirect_lighting_intensity=.64))
    moonlight.set_light_color(ue.LinearColor(.58, .70, 1, 1))
    moonlight.set_intensity(.52)
    fog = spawn(ue.ExponentialHeightFog, name + " distant rain haze", (at[0], at[1], 12))
    fog.get_component_by_class(ue.ExponentialHeightFogComponent).set_editor_properties(dict(
        fog_density=.029, fog_height_falloff=.21, start_distance=730.,
        fog_max_opacity=.39, fog_inscattering_luminance=ue.LinearColor(.040, .052, .080, 1),
        enable_volumetric_fog=False))
    post = spawn(ue.PostProcessVolume, name + " night exposure", at)
    settings = post.get_editor_property("settings")
    settings.set_editor_properties(dict(override_auto_exposure_bias=True, auto_exposure_bias=.34,
                                        override_bloom_intensity=True, bloom_intensity=.21))
    post.set_editor_properties(dict(unbound=True, priority=10., settings=settings))


def alley(builder, placed):
    night_ambient("Alley", (1535, 807, 1600))
    shell = ue.load_asset(STREET + "/Materials/M_dark_stone")
    steel = ue.load_asset(STREET + "/Materials/M_steel")
    glass = ue.load_asset(STREET + "/Materials/M_dark_glass")
    amber = ue.load_asset(STREET + "/Materials/M_lit_window")
    brick = ue.load_asset(REFINEMENT + "/Materials/M_SootBrownBrick")
    wet_ground = ue.load_asset(BRIGHTON + "/Materials/M_Wet_asphalt")
    assert all((shell, steel, glass, amber, brick, wet_ground))
    fixtures = (
        ((190, 202, 270), (0, -1), (1, .76, .55), 4.9, True),
        ((816, 570, 277), (1, 0), (.64, .76, 1), 3.9, False),
        ((1550, 1025, 278), (0, -1), (1, .77, .56), 4.1, False),
        ((1981, 1377, 275), (1, 0), (.68, .80, 1), 4.5, True),
        ((3020, 1828, 263), (0, -1), (1, .79, .61), 4.5, True),
    )
    lights = sorted((a for a in placed if a.get_actor_label() == "Cool rain light"), key=lambda a: a.get_actor_location().x)
    lanterns = sorted((a for a in placed if a.get_actor_label() == "Night alley lantern"), key=lambda a: a.get_actor_location().x)
    for light, lantern, (position, axis, tint, intensity, shadows) in zip(lights, lanterns, fixtures, strict=True):
        origin = V(*position)
        normal = V(*axis, 0)
        light.set_actor_location(origin + normal * 34 - V(0, 0, 16), False, True)
        local_light(light.get_component_by_class(ue.PointLightComponent), intensity, 635, tint, shadows)
        lantern.set_actor_location(origin, False, True)
        lantern.set_actor_scale3d(V(.16, .29, .18) if axis[0] else V(.29, .16, .18))
        lantern_comp = lantern.get_component_by_class(ue.StaticMeshComponent)
        lantern_comp.set_material(0, shell)
        lantern_comp.set_cast_shadow(False)
        builder.instance("Mounted lantern diffusers", (origin + normal * 9 - V(0, 0, 3)).to_tuple(),
                         (.055, .23, .11) if axis[0] else (.23, .055, .11), amber)
    light_walls = (-209, 613, 1408)
    for i, a in enumerate(sorted((a for a in placed if a.get_actor_label() == "Rear alley window"),
                                 key=lambda a: a.get_actor_location().to_tuple())):
        x, y, z = a.get_actor_location().to_tuple()
        sign = 1 if any(abs(y - wall) < 2 for wall in light_walls) else -1
        a.get_component_by_class(ue.StaticMeshComponent).set_material(0, amber if i % 13 == 5 else glass)
        outer = y + 4 * sign
        for dx in (-44, 0, 44):
            builder.instance("Alley window vertical frames", (x+dx, outer, z), (.046, .04, 1.055), shell)
        for dz in (-51, 8, 51):
            builder.instance("Alley window lintels and bars", (x, outer, z+dz), (.91, .04, .047), shell)
    for a in placed:
        name = a.get_actor_label()
        if name == "Rear exit gate":
            # Keep the original solid blocker, with an open view through the rendered fencing.
            a.set_actor_hidden_in_game(True)
        if name == "Gate bars":
            a.get_component_by_class(ue.StaticMeshComponent).set_material(0, steel)
        if name == "Back walls of walk-up apartments":
            bounds, extent = a.get_actor_bounds(False)
            builder.instance("Back-building rain coping", (bounds.x, bounds.y, bounds.z+extent.z+3),
                             ((2*extent.x+14)/100, (2*extent.y+14)/100, .09), shell)
            if extent.y > 190:
                for face in (-1, 1):
                    x = bounds.x + face * (extent.x + 3)
                    for offset in (-114, 114):
                        for z in (184, 405):
                            y = bounds.y + offset
                            is_lit = z == 184 and face * offset < 0
                            builder.instance("Walk-up return windows", (x, y, z), (.065, .86, 1.09),
                                             amber if is_lit else glass)
                            builder.instance("Walk-up return sills", (x+face*5, y, z-54), (.14, 1.01, .09), shell)
                            builder.instance("Walk-up return mullions", (x+face*3, y, z), (.06, .055, 1.10), shell)
    for z in (75, 267):
        builder.instance("Gate horizontal bracing", (3500, 1620, z), (.10, 4.17, .08), steel)
    builder.box("Street surface continuing beyond the gate", (4390, 1575, -55), (1940, 3900, 108), wet_ground)
    for x, y, h, width, depth in ((4190, 870, 575, 780, 750), (4350, 2240, 695, 940, 790), (5100, 1605, 830, 760, 1050),
                                   (120, 2720, 765, 1080, 690), (1870, 2810, 824, 1110, 730)):
        builder.box("Adjacent backstreet walk-up", (x, y, h/2-6), (width, depth, h), brick)
        builder.instance("Backstreet coping", (x, y, h-6), ((width+18)/100, (depth+18)/100, .15), shell)
        for floor in range(2, int(h//240)+1):
            for j in range(3):
                builder.instance("Backstreet windows", (x-width/2-2, y+(j-1)*178, floor*200-64),
                                 (.045, .84, 1.14), amber if (j+floor)%5==0 else glass)
    point("Sky bounce on the first corner", (850, 64, 565), 4.3, 1280, (.63, .77, 1))
    point("Cool fill along the chase turn", (1590, 852, 470), 2.7, 975, (.65, .79, 1))
    point("Sky bounce over the rear passage", (3150, 1600, 540), 4.1, 1320, (.65, .77, 1))
    point("Reflected lamp beyond the iron gate", (3875, 1580, 482), 4.5, 1210, (.87, .79, .71))
    point("Distant walk-up reflected sky", (4450, 1600, 487), 3.5, 1180, (.66, .79, 1))


def entrance(placed):
    night_ambient("Fedor entry", (20, 0, 1300))
    brick = ue.load_asset(STREET + "/Materials/M_ochre_brick")
    for a in placed:
        name = a.get_actor_label()
        if name.startswith("Street retaining wall"):
            mesh = a.get_component_by_class(ue.StaticMeshComponent)
            mat = mesh.get_material(0)
            if mat and mat.get_name() == "T_ochre_brick_Color_Mat":
                mesh.set_material(0, brick)
        if name in ("Sodium porch light", "Reflected blue night light"):
            porch = name == "Sodium porch light"
            local_light(a.get_component_by_class(ue.PointLightComponent), 5.2 if porch else 1.25,
                        486 if porch else 710, (1, .78, .61) if porch else (.64, .78, 1), porch)


def mark_and_trim(builder, placed):
    changed = False
    for a in ACTORS.get_all_level_actors():
        if str(a.get_folder_path()) == FOLDER:
            a.tags = [tag for tag in a.tags if str(tag) != "BrightonUpgrade_v1" and tag != TAG] + [TAG]
            changed = True
        for kind in (ue.BillboardComponent, ue.MaterialBillboardComponent, ue.ArrowComponent):
            for component in a.get_components_by_class(kind):
                if not component.get_editor_property("hidden_in_game"):
                    component.set_hidden_in_game(True, False)
                    changed = True
        if isinstance(a, ue.StreetPortal):
            focus = a.get_editor_property("focus_box")
            if not focus.get_editor_property("hidden_in_game"):
                focus.set_hidden_in_game(True, False)
                changed = True
    for batch in builder.batches.values():
        batch.set_editor_properties(dict(affect_distance_field_lighting=False, cast_shadow=False))
    for a in placed:
        name = a.get_actor_label()
        if name not in {"Smoker's cigarette", "Cigarette", "Cigarette ember"} or not a.get_attach_parent_actor():
            continue
        parent = a.get_attach_parent_actor()
        while parent and not isinstance(parent, ue.ActOneCast):
            parent = parent.get_attach_parent_actor()
        if parent and parent.get_editor_property("default_pose") == ue.ActOnePose.SMOKING:
            assert ACTORS.destroy_actor(a), name
            changed = True
    return changed


retile()
street_bricks()
for name in maps:
    uri = "/Game/Locations/" + name
    assert LEVELS.load_level(uri)
    preserve(uri, ".umap")
    placed = ACTORS.get_all_level_actors()
    old = [a for a in placed if a.actor_has_tag(TAG)]
    if old:
        assert ACTORS.destroy_actors(old)
        placed = ACTORS.get_all_level_actors()
    builder = Builder(FOLDER)
    if name in ("L_NeptuneStreet", "L_DimaApartmentInterior"):
        passage(builder, placed, name == "L_DimaApartmentInterior")
    if name == "L_BrightonAlley":
        alley(builder, placed)
    if name == "L_FedorEntry":
        entrance(placed)
    if mark_and_trim(builder, placed):
        assert LEVELS.save_current_level(), name
        ue.log("QUALITY_RELIGHTED " + name)

logo_uri = "/Game/Characters/Mannequins/Textures/Shared/T_UE_Logo_M"
logo = ue.load_asset(logo_uri)
preserve(logo_uri)
logo.set_editor_properties(dict(never_stream=False, max_texture_size=512))
save(logo)
ue.log("QUALITY_RENDER_ASSETS_OK")
