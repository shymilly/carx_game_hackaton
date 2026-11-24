"""Exercise the actual purchase and vendor interactions, then capture the repaired views."""
from pathlib import Path

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
helpers = project / "Scripts/CheckActOnePIE.py"
exec(compile(helpers.read_text(encoding="utf-8").rsplit("\nassert levels.load_level", 1)[0], str(helpers), "exec"))
reviews = project / "Saved/Reviews/Brighton0142"
reviews.mkdir(parents=True, exist_ok=True)
state["deadline"] = time.monotonic() + 125


def command(console):
    ue.SystemLibrary.execute_console_command(world(), console, pc())


def capture(name):
    picture = reviews / (name + ".png")
    picture.unlink(missing_ok=True)
    command('HighResShot 1280x720 filename="' + str(picture) + '"')
    yield from wait(picture.is_file, "Screenshot: " + name, 8)
    ue.log("QUALITY_CAPTURE " + name)


def look(point):
    camera = ue.GameplayStatics.get_player_camera_manager(world(), 0)
    pc().set_control_rotation(ue.MathLibrary.find_look_at_rotation(camera.get_camera_location(), ue.Vector(*point)))


def set_view(position, point):
    place(position)
    yield from pause(.3)
    look(point)
    yield from pause(.55)


def visuals_hidden():
    for kind in (ue.BillboardComponent, ue.MaterialBillboardComponent, ue.ArrowComponent):
        bad = [part.get_path_name() for part in ue.ObjectIterator(kind)
               if part.get_outer() and ":PersistentLevel." in part.get_path_name() and "UEDPIE_" in part.get_path_name()
               and part.is_visible() and not part.get_editor_property("hidden_in_game")]
        assert not bad, bad
    command("showflag.BillboardSprites 0")
    command("showflag.Collision 0")
    command("showflag.Bounds 0")


def player_arms():
    return next((comp for comp in pawn().get_components_by_class(ue.SkeletalMeshComponent)
                 if comp.get_name() == "FirstPersonSmokingArms"), None)


def run_check():
    yield from beginning(False)
    visuals_hidden()
    yield from set_view((-1077, -490, 100), (-1080, 985, 140))
    yield from capture("PlaygroundPassage")
    yield from set_view((1657, -2540, 101), (1480, -2750, 172))
    yield from capture("PrecinctBrick")
    yield from set_view((-2200, -500, 103), (-5840, -1350, 235))
    command("csvprofile frames=180")
    yield from pause(5.)
    yield from capture("BrightonStreet")

    say_step("Vendor text and retained kiosk sound")
    use(action.PRESS, (0, 105))
    yield from wait(windows, "Vendor page")
    vendor = windows()[0].get_editor_property("document")
    assert vendor.get_name() == "D_Vendor" and vendor.get_editor_property("voice") is None
    yield from page("Vendor")

    say_step("Standing NPC by the newsstand")
    actors = ue.GameplayStatics.get_all_actors_of_class(world(), ue.ActOneCast)
    bystander, = [actor for actor in actors if actor.actor_has_tag("KioskBystander")]
    assert bystander.get_editor_property("default_pose") == ue.ActOnePose.IDLE
    assert not bystander.get_editor_property("hidden")
    assert not bystander.get_component_by_class(ue.CigaretteSmokeComponent)
    assert not any(c.get_name() == "HeldCigarette" for c in bystander.get_components_by_class(ue.StaticMeshComponent))
    at = bystander.get_actor_location()
    facing = bystander.get_actor_forward_vector()
    side = bystander.get_actor_right_vector()
    p = at + facing * 165 + side * 76
    yield from set_view((p.x, p.y, at.z + 94), (at.x, at.y, at.z + 122))
    yield from capture("NewsstandBystander")
    ue.log("QUALITY_KIOSK_BYSTANDER_OK")
    del actors, bystander

    say_step("Buy cigarettes and play the first-person montage")
    yield from physical_use(action.GROCERY, (0, 133))
    yield from travel("L_BrightonGrocery", "ActEntry")
    yield from physical_use(action.CIGARETTES, (-132, 0))
    yield from travel(street, "FromGrocery")
    yield from wait(player_arms, "Player smoking arms on the camera", 3)
    rig = player_arms()
    animation = rig.get_anim_instance()
    montage = animation.get_current_active_montage()
    assert montage and montage.get_name() == "AM_DimaSmoke"
    assert "ABP_DimaSmokingArms" in animation.get_class().get_name()
    prop = next(c for c in pawn().get_components_by_class(ue.StaticMeshComponent) if c.get_name() == "HeldCigarette")
    assert str(prop.get_attach_socket_name()) == "CigaretteGrip"
    director = ue.GameplayStatics.get_actor_of_class(world(), ue.ActOneDirector)
    yield from wait(lambda: animation.montage_get_position(montage) > .95, "Raised first-person grip", 2)
    camera = ue.GameplayStatics.get_player_camera_manager(world(), 0)
    offset = prop.get_world_location() - camera.get_camera_location()
    forward = ue.MathLibrary.get_forward_vector(camera.get_camera_rotation())
    screen = ue.GameplayStatics.project_world_to_screen(pc(), prop.get_world_location(), True)
    bounds = ue.SystemLibrary.get_component_bounds(rig)
    ue.log(f"QUALITY_GRIP_CAMERA world_offset={offset} screen={screen} bounds={bounds}")
    assert 12 < offset.dot(forward) < 55, offset
    assert director.get_component_by_class(ue.CigaretteSmokeComponent).is_visible()
    yield from capture("DimaSmokingFirstPerson")
    yield from pages("DispatchBar", "Disposition")
    assert not player_arms() and act().get_statistics().get_editor_property("calm") == 1
    ue.log("QUALITY_PLAYER_SMOKE_OK")

    say_step("Night alley and opaque gate replaced by rendered bars")
    ue.GameplayStatics.open_level(world(), ue.Name("/Game/Locations/L_BrightonAlley"))
    yield from wait(lambda: locate("L_BrightonAlley"), "Alley")
    visuals_hidden()
    assert ue.GameplayStatics.get_actor_of_class(world(), ue.SkyLight)
    assert ue.GameplayStatics.get_actor_of_class(world(), ue.ExponentialHeightFog)
    yield from set_view((-158, 0, 100), (1200, 28, 182))
    yield from capture("AlleyEntry")
    yield from set_view((2560, 1620, 100), (3750, 1590, 215))
    yield from capture("AlleyGate")
    ue.log("QUALITY_RENDER_PIE_OK")


assert levels.load_level("/Game/Locations/" + apartment)
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state["run"] = run_check()
state["handle"] = ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
