"""Exercise apartment interactions in PIE via their gameplay Blueprint functions."""
import math
import os
from pathlib import Path
import sys
import time

import unreal as ue

sys.path.insert(0, str(Path(__file__).parent))
from ApartmentGameplay import INTRO_DOCUMENTS, LIGHTS, ROOM_SWITCHES, SEATS, WATER
from PlanApartment import DOORS, MAP_NAME


class ApartmentPlaytest:
    def __init__(self):
        self.levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
        self.editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
        self.deadline = time.monotonic() + 45
        self.next_stage_at = 0
        self.world = None
        self.pc = None
        self.player = None
        self.hud = None
        self.stage = self.start
        self.callback = None
        self.doors = {}
        self.peak = {}
        self.seat_tags = iter(SEATS)
        self.seated_camera = None
        self.start_spot = ue.Vector(-130, 245, 100)
        self.frame_times = []
        self.preview = os.environ.get("DIMA_TEST_PREVIEW")
        self.report_preview = os.environ.get("DIMA_REPORT_PREVIEW")

    def actors(self, tag):
        actors = ue.GameplayStatics.get_all_actors_with_tag(self.world, tag)
        assert actors, f"Missing actor tag {tag}"
        return actors

    def property(self, name):
        return self.hud.get_editor_property(name)

    def activate(self, tag):
        self.hud.call_method("Activate" + tag)

    def wait_for(self, stage, delay=0):
        self.stage = stage
        self.next_stage_at = time.monotonic() + delay

    def document_windows(self):
        return [window for window in ue.ObjectIterator(ue.DocumentWindow)
                if window.is_in_viewport() and window.get_owning_player() == self.pc]

    def start(self):
        self.world = self.editor.get_game_world()
        if self.world is None:
            return
        self.pc = ue.GameplayStatics.get_player_controller(self.world, 0)
        self.player = ue.GameplayStatics.get_player_character(self.world, 0)
        self.hud = self.pc.get_hud() if self.pc else None
        if self.player is None or self.hud is None or self.property("State") != 9:
            return
        self.wait_for(self.check_report, .2)

    def check_report(self):
        assert self.pc.get_view_target().actor_has_tag("ReportView"), "Wrong opening camera"
        assert len(self.actors("Exit")) == 1
        assert not self.hud.get_component_by_class(ue.ExplorationHUDComponent), "Tutorial started during the report"
        window, = self.document_windows()
        document = window.get_editor_property("document")
        _, title, body = INTRO_DOCUMENTS[0]
        assert str(document.get_editor_property("title")) == title
        assert str(document.get_editor_property("body")) == body
        ue.log("APARTMENT_STYLED_REPORT_OK")
        if self.report_preview:
            self.capture(self.report_preview)
            self.wait_for(self.finish_report, .5)
        else:
            self.finish_report()

    def finish_report(self):
        self.hud.call_method("FinishReport")
        assert self.property("ReportFound"), "Report did not enter the journal"
        self.wait_for(self.check_fixtures, .8)

    def check_fixtures(self):
        assert not self.document_windows(), "Report window stayed visible after closing"
        assert self.pc.get_view_target() == self.player, "Report view did not return to first person"
        assert not self.player.is_move_input_ignored(), "Movement stayed locked after report"
        tutorial = self.hud.get_component_by_class(ue.ExplorationHUDComponent)
        assert tutorial and not tutorial.is_tutorial_complete(), "Tutorial did not start after the report"
        assert any(widget.is_in_viewport() and widget.get_owning_player() == self.pc
                   for widget in ue.ObjectIterator(ue.ExplorationOverlayWidget)), "Exploration HUD is missing from the viewport"
        ue.log("APARTMENT_EXPLORATION_HUD_OK")
        self.check_interaction_traces()
        for control, tag in LIGHTS.items():
            lights = tuple(actor.get_component_by_class(ue.LightComponent) for actor in self.actors(tag))
            assert all(lights) and all(light.is_visible() for light in lights), f"{control} lights do not start on"
            self.activate(control)
            assert not any(light.is_visible() for light in lights), f"{control} left lights on"
            if control in ROOM_SWITCHES:
                rocker, = self.actors(control + "Rocker")
                assert abs(rocker.get_actor_rotation().pitch + 12) < .2, f"{control} rocker stayed on"
            self.activate(control)
            assert all(light.is_visible() for light in lights), f"{control} left lights off"
            if control in ROOM_SWITCHES:
                assert abs(rocker.get_actor_rotation().pitch - 12) < .2, f"{control} rocker stayed off"
            ue.log(f"APARTMENT_LIGHT_OK {tag} count={len(lights)}")
        for control, tag in WATER.items():
            effects = self.actors(tag)
            assert all(effect.get_editor_property("hidden") for effect in effects), f"{tag} water starts running"
            for effect in effects:
                collision = effect.get_component_by_class(ue.StaticMeshComponent).get_collision_enabled()
                assert collision == ue.CollisionEnabled.NO_COLLISION, f"{tag}/{effect.get_name()} collision: {collision}"
            self.activate(control)
            assert not any(effect.get_editor_property("hidden") for effect in effects), f"{tag} water stayed off"
            self.activate(control)
            assert all(effect.get_editor_property("hidden") for effect in effects), f"{tag} water stayed on"
            ue.log(f"APARTMENT_WATER_OK {tag} count={len(effects)}")
        lamp, = self.actors("FloorLamp")
        bulb, = self.actors("FloorLampLight")
        body = lamp.get_component_by_class(ue.StaticMeshComponent)
        assert body.is_simulating_physics(), "Floor lamp has no simulated body"
        assert math.isclose(body.get_mass(), 7.5, abs_tol=.15), "Wrong floor lamp mass"
        assert bulb.get_attach_parent_actor() == lamp, "Floor lamp light is detached"
        ue.log(f"APARTMENT_LAMP_PHYSICS_OK mass_kg={body.get_mass():.2f}")
        if os.environ.get("DIMA_TEST_KEY"):
            self.aim_at_living_switch()
        else:
            self.wait_for(self.sit)

    def ray(self, start, end):
        hit = ue.SystemLibrary.line_trace_single(self.world, start, end, ue.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                False, [self.player], ue.DrawDebugTrace.NONE, True)
        if isinstance(hit, tuple):
            found, hit = hit
            assert found, f"No geometry along {start} → {end}"
        assert hit is not None, f"No geometry along {start} → {end}"
        result = hit.to_tuple()  # FHitResult uses its native BreakHitResult function for the Python tuple.
        assert result[0], f"No blocking geometry along {start} → {end}"
        return result[9], result[5]  # HitActor and ImpactPoint

    def check_interaction_traces(self):
        vector = ue.Vector
        for tag, sign in (("LivingSwitch", 1), ("KitchenSwitch", -1), ("BathSwitch", 1)):
            rocker, = self.actors(tag + "Rocker")
            position = rocker.get_actor_location()
            hit, _ = self.ray(position + vector(sign * 70, 0, 25), position)
            assert hit.actor_has_tag(tag), f"{tag} trace blocked"
        sofa, = self.actors("SofaSeat")
        center = sofa.get_actor_location()
        hit, _ = self.ray(vector(-22, center.y, 122), vector(62, center.y, 49))
        assert hit == sofa, "Sofa interaction trace missed"
        for x, y in ((-130, 174), (130, 85), (-577.5, 289), (595, -172)):
            for epsilon in (-.02, 0, .02):
                _, impact = self.ray(vector(x + epsilon, y, 6), vector(x + epsilon, y, -8))
                assert abs(impact.z) < .1, (x, y, epsilon, impact.z)
        ue.log("APARTMENT_TRACE_OK room switches, sofa, floor seams")

    def aim_at_living_switch(self):
        self.player.set_actor_location(ue.Vector(-276, 76, 100), False, True)
        rocker, = self.actors("LivingSwitchRocker")
        camera = ue.GameplayStatics.get_player_camera_manager(self.world, 0)
        target = rocker.get_actor_location()
        self.pc.set_control_rotation(ue.MathLibrary.find_look_at_rotation(camera.get_camera_location(), target))
        self.wait_for(self.correct_aim, .2)

    def correct_aim(self):
        rocker, = self.actors("LivingSwitchRocker")
        camera = ue.GameplayStatics.get_player_camera_manager(self.world, 0)
        self.pc.set_control_rotation(ue.MathLibrary.find_look_at_rotation(camera.get_camera_location(),
                                                                          rocker.get_actor_location()))
        self.wait_for(self.press_interact, .2)

    def press_interact(self):
        focus = self.property("Focus")
        if focus != "LivingSwitch":
            camera = ue.GameplayStatics.get_player_camera_manager(self.world, 0)
            position = camera.get_camera_location()
            view = camera.get_camera_rotation()
            end = position + ue.MathLibrary.get_forward_vector(view) * 260
            hit, impact = self.ray(position, end)
            raise RuntimeError(f"Expected living switch, Focus={focus!r}, from {position} towards {view}, "
                               f"collision={hit.get_name()} at {impact}")
        ue.SystemLibrary.execute_console_command(self.world, "Input.+key E", self.pc)
        self.wait_for(self.release_interact, .18)

    def release_interact(self):
        ue.SystemLibrary.execute_console_command(self.world, "Input.-key E", self.pc)
        assert self.property("LivingSwitchToggled"), "E did not switch the focused room light off"
        self.activate("LivingSwitch")
        self.player.set_actor_location(self.start_spot, False, True)
        ue.log("APARTMENT_KEY_OK E on wall switch")
        self.wait_for(self.sit, .4)

    def sit(self):
        tag = next(self.seat_tags, None)
        if tag is None:
            self.wait_for(self.open_doors)
            return
        self.actors(tag)
        self.seated_camera, = self.actors(tag + "View")
        self.activate(tag)
        assert self.property("State") == 10, f"{tag} could not be used"
        assert self.player.is_move_input_ignored(), f"{tag} left movement enabled"
        self.wait_for(self.capture_sofa if self.preview and tag == "SofaSeat" else self.stand, .55)

    def capture_sofa(self):
        self.capture(self.preview)
        self.wait_for(self.stand, .6)

    def capture(self, filename):
        output = Path(filename).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        ue.SystemLibrary.execute_console_command(self.world, f'Shot SHOWUI filename="{output.as_posix()}" -nosuffix',
                                                 self.pc)

    def stand(self):
        assert self.pc.get_view_target() == self.seated_camera, "Seat did not select its camera"
        ue.log(f"APARTMENT_SEAT_OK {self.seated_camera.get_name()}")
        self.hud.call_method("StandUp")
        assert self.property("State") == 0 and not self.player.is_move_input_ignored(), "Seat left controls locked"
        self.wait_for(self.sit, .55)

    def open_doors(self):
        self.player.set_actor_location(self.start_spot, False, True)
        for tag in DOORS:
            door, = self.actors(tag)
            component = door.get_component_by_class(ue.StaticMeshComponent)
            assert component.get_editor_property("mobility") == ue.ComponentMobility.MOVABLE, tag
            assert component.get_editor_property("cast_dynamic_shadow"), tag
            self.doors[tag] = (door, door.get_actor_location(), door.get_actor_rotation().yaw)
            self.peak[tag] = 0
            self.activate(tag)
        self.wait_for(self.close_doors)

    def close_doors(self):
        for tag, (door, _, yaw) in self.doors.items():
            turn = abs((door.get_actor_rotation().yaw - yaw + 180) % 360 - 180)
            self.peak[tag] = max(self.peak[tag], turn if turn < 89 else 0)
        if not all(self.property(tag + "Progress") >= .9999 for tag in self.doors):
            return
        for tag, (door, origin, yaw) in self.doors.items():
            difference = (door.get_actor_rotation().yaw - yaw + 180) % 360 - 180
            assert math.isclose(difference, DOORS[tag][3], abs_tol=.15), (tag, difference)
            assert self.peak[tag] > 12, (tag, self.peak[tag])
            assert abs(door.get_actor_location().z - origin.z) < .05, tag
            self.activate(tag)
        # This point lies in the kitchen door's swing, clear of the open slab.
        self.player.set_actor_location(ue.Vector(-435, 167, 100), False, True)
        self.wait_for(self.check_obstruction, 1.4)

    def check_obstruction(self):
        progress = self.property("KitchenDoorProgress")
        assert .015 < progress < .99, f"Kitchen door did not pause around the capsule: {progress}"
        self.player.set_actor_location(self.start_spot, False, True)
        self.wait_for(self.check_closed)

    def check_closed(self):
        if not all(self.property(tag + "Progress") < .0001 for tag in self.doors):
            return
        for tag, (door, origin, yaw) in self.doors.items():
            assert (door.get_actor_location() - origin).length() < .1, tag
            assert abs((door.get_actor_rotation().yaw - yaw + 180) % 360 - 180) < .15, tag
            ue.log(f"APARTMENT_DOOR_OK {tag}")
        self.finish(True)

    def tick(self, delta):
        try:
            now = time.monotonic()
            if now > self.deadline:
                raise RuntimeError("Timed out")
            if self.world and self.stage.__name__ != "start" and delta > 0:
                self.frame_times.append(1000 * delta)
            if now >= self.next_stage_at:
                self.stage()
        except Exception as error:
            ue.log_error(f"APARTMENT_PLAYTEST_FAILED {self.stage.__name__}: {error}")
            self.finish(False)

    def finish(self, success):
        if success:
            if self.frame_times:
                ordered = sorted(self.frame_times)
                p50 = ordered[len(ordered) // 2]
                p95 = ordered[math.ceil(.95 * len(ordered)) - 1]
                ue.log(f"APARTMENT_PIE_FRAME_SAMPLE count={len(ordered)} p50_ms={p50:.2f} p95_ms={p95:.2f}")
            ue.log("APARTMENT_PLAYTEST_OK")
        ue.unregister_slate_post_tick_callback(self.callback)
        self.levels.editor_request_end_play()
        ue.EditorPythonScripting.set_keep_python_script_alive(False)

    def run(self):
        if not self.levels.load_level(f"/Game/Prologue/{MAP_NAME}"):
            raise RuntimeError(f"Could not load {MAP_NAME} for PIE")
        ue.EditorPythonScripting.set_keep_python_script_alive(True)
        self.callback = ue.register_slate_post_tick_callback(self.tick)
        self.levels.editor_request_begin_play()


ApartmentPlaytest().run()
