"""Exercise the built neighborhood, including real player and traffic collision in PIE."""
import time
import traceback

import unreal as ue


V, R = ue.Vector, ue.Rotator
MAP = "/Game/Prologue/L_DimaApartmentStreet"


def wait(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        yield


def until(test, description, timeout=5):
    end = time.monotonic() + timeout
    while not test():
        assert time.monotonic() < end, description
        yield


class NeighborhoodTest:
    def __init__(self):
        self.levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
        self.editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)

    def ready(self):
        self.world = self.editor.get_game_world()
        if not self.world:
            return False
        self.pc = ue.GameplayStatics.get_player_controller(self.world,0)
        self.hud = self.pc.get_hud() if self.pc else None
        return self.hud and self.hud.get_editor_property("State") == 9

    def key(self, key, down):
        action = "+" if down else "-"
        ue.SystemLibrary.execute_console_command(self.world, f"Input.{action}key {key}", self.pc)

    def place(self, x, y, yaw=0, z=102):
        self.motion.stop_movement_immediately()
        self.pawn.set_actor_location(V(x,y,z),False,True)
        self.pc.set_control_rotation(R(0,0,yaw))

    def photo(self, name):
        yield from until(self.ui.is_location_transition_active,f"Did not show {name}.")
        texture = self.ui.get_location_photo()
        assert texture and texture.get_name() == "T_Transition_" + name,(name,texture)
        assert self.pc.is_move_input_ignored() and self.pc.is_look_input_ignored()
        yield from until(lambda: not self.ui.is_location_transition_active(),f"Transition stuck for {name}.")
        assert not self.pc.is_move_input_ignored() and not self.pc.is_look_input_ignored(),name

    def interact_with_door(self):
        yield from until(lambda: self.hud.get_editor_property("Focus") == "StreetPortal","No portal focus.")
        self.key("E",True)
        yield from wait(.18)
        self.key("E",False)

    def transitions(self):
        self.place(-194,-343,-90)
        self.hud.call_method("ActivateStreetDoor")
        yield from until(lambda: self.hud.get_editor_property("StreetDoorProgress") > .999,"Front door did not open.")
        while self.pawn.get_actor_location().y > -481 and not self.ui.is_location_transition_active():
            self.pawn.add_movement_input(V(0,-1,0),1,False)
            yield
        yield from self.photo("Neptune")
        assert self.pawn.get_actor_location().y < -476
        while self.pawn.get_actor_location().y < -420 and not self.ui.is_location_transition_active():
            self.pawn.add_movement_input(V(0,1,0),1,False)
            yield
        yield from self.photo("Apartment")
        assert self.hud.get_editor_property("ReportFound")

        self.place(1937,-2725,180)
        yield from self.interact_with_door()
        yield from self.photo("Precinct")
        assert 1510 < self.pawn.get_actor_location().x < 1660
        self.pc.set_control_rotation(R(0,0,0))
        yield from self.interact_with_door()
        yield from self.photo("Neptune")
        assert 1880 < self.pawn.get_actor_location().x < 1945

        self.place(3090,1290)
        yield from self.interact_with_door()
        yield from until(self.ui.is_document_open,"Closed bar notice did not open.")
        window, = [item for item in ue.ObjectIterator(ue.DocumentWindow)
                   if item.is_in_viewport() and item.get_owning_player() == self.pc]
        assert str(window.get_editor_property("document").get_editor_property("title")) == "Бар «Маяк»"
        assert abs(self.pawn.get_actor_location().x-3090) < 4
        window.request_close()
        assert not self.pc.is_move_input_ignored()
        ue.log("NEPTUNE_TRANSITIONS_OK: both apartment directions, precinct and return, closed bar")

    def paths(self):
        self.place(-1060,-661,90)
        yield from wait(.12)
        self.pawn.set_actor_location(V(-1060,727,102),True,False)
        assert self.pawn.get_actor_location().y > 710,"The entrance between the press and Dima's house is blocked."
        for start, end, axis, sign in (
            ((-1070,1575),(-1950,1575),"x",-1),
            ((1500,1450),(2420,1450),"x",1),
            ((670,2220),(670,3260),"y",1),
            ((748,650),(748,212),"y",-1),
        ):
            self.place(*start,z=112)
            self.pawn.set_actor_location(V(*end,112),True,False)
            assert sign*(end[0 if axis == "x" else 1] - getattr(self.pawn.get_actor_location(),axis)) > 120, (
                "Unexpected opening in the park perimeter",start,end)
        self.place(-6340,-1235,z=103)
        self.pawn.set_actor_location(V(-7070,-1235,103),True,False)
        assert -6720 < self.pawn.get_actor_location().x < -6590,self.pawn.get_actor_location()
        ue.log("NEPTUNE_PATHS_OK: one courtyard passage, closed perimeter and invisible fork limit")

    def traffic(self):
        self.place(-2280,-565)
        flow = ue.GameplayStatics.get_actor_of_class(self.world,ue.StreetTrafficFlow)
        actors = ue.GameplayStatics.get_all_actors_of_class(self.world,ue.StreetTrafficCar)
        assert len(actors) == 6
        prior_count = flow.get_total_spawned()
        start = ue.GameplayStatics.get_time_seconds(self.world)
        directions = set()
        passed_boundary = False
        samples = {}
        ue.GameplayStatics.set_global_time_dilation(self.world,2)
        while ue.GameplayStatics.get_time_seconds(self.world)-start < 60:
            for car in actors:
                active = not car.get_editor_property("hidden")
                if not active:
                    samples.pop(car, None)
                    continue
                point = car.get_actor_location()
                if car in samples and -7920 < point.x < -5810 and abs(point.y+1010) < 5:
                    if samples[car].x < -6720 < point.x:
                        passed_boundary = True
                samples[car] = point
                if -5450 < point.x < 900:
                    if abs(point.y+1010) < 5: directions.add("north")
                    if abs(point.y+1475) < 5: directions.add("south")
            yield
        ue.GameplayStatics.set_global_time_dilation(self.world,1)
        count = flow.get_total_spawned()-prior_count
        assert 7 <= count <= 10,count
        assert directions == {"north","south"} and passed_boundary,(directions,passed_boundary)
        assert flow.get_active_count() <= 6
        yield from until(lambda: any(not c.get_editor_property("hidden") and -5300 < c.get_actor_location().x < 1300
                                    for c in actors),"No occupied lane for the collision check.")
        chosen = next(c for c in actors if not c.get_editor_property("hidden")
                      and -5300 < c.get_actor_location().x < 1300)
        flow.set_actor_tick_enabled(False)
        center = chosen.get_actor_location()
        forward = ue.MathLibrary.get_forward_vector(chosen.get_actor_rotation())
        normal = V(-forward.y,forward.x,0)
        start, end = center+normal*246,center-normal*217
        self.place(start.x,start.y)
        self.pawn.set_actor_location(V(end.x,end.y,102),True,False)
        offset = self.pawn.get_actor_location()-center
        remaining = offset.x*normal.x + offset.y*normal.y
        assert remaining > 117,("Pawn entered the moving car body",remaining)
        self.place(-2200,-515)
        flow.set_actor_tick_enabled(True)
        ue.log(f"NEPTUNE_TRAFFIC_OK: {count} starts/minute, two lanes, border crossing, pooled cars and pawn collision")

    def run_checks(self):
        yield from until(self.ready,"The prologue HUD did not start.",40)
        self.pawn = ue.GameplayStatics.get_player_character(self.world,0)
        self.motion = self.pawn.get_component_by_class(ue.CharacterMovementComponent)
        instance = ue.GameplayStatics.get_game_instance(self.world)
        self.ui = next(obj for obj in ue.ObjectIterator(ue.NarrativeSubsystem) if obj.get_outer() == instance)
        self.hud.call_method("FinishReport")
        yield from until(lambda: self.pc.get_view_target() == self.pawn,"The report did not restore first person.")
        yield from wait(.72)
        yield from self.transitions()
        yield from self.paths()
        yield from self.traffic()

    def finish(self, success):
        ue.unregister_slate_post_tick_callback(self.handle)
        if self.editor.get_game_world():
            ue.GameplayStatics.set_global_time_dilation(self.world,1)
            self.levels.editor_request_end_play()
        ue.EditorPythonScripting.set_keep_python_script_alive(False)
        if success:
            ue.log("NEPTUNE_PLAYTEST_OK")

    def tick(self, _delta):
        try:
            assert time.monotonic() < self.deadline,"Neighborhood playtest timed out."
            next(self.plan)
        except StopIteration:
            self.finish(True)
        except Exception:
            ue.log_error("NEPTUNE_PLAYTEST_ERROR " + traceback.format_exc())
            self.finish(False)

    def run(self):
        assert self.levels.load_level(MAP)
        ue.EditorPythonScripting.set_keep_python_script_alive(True)
        self.plan = self.run_checks()
        self.deadline = time.monotonic()+120
        self.handle = ue.register_slate_post_tick_callback(self.tick)
        self.levels.editor_request_begin_play()


NeighborhoodTest().run()
