"""Build prop LODs and bind photographs captured from the actual maps.

Run with -ExecutePythonScript in a separate, rendered Unreal Editor process.
"""
from pathlib import Path
import sys
import time

import unreal as ue

sys.path.insert(0, str(Path(__file__).parent))
from StreetMaterials import ROOT, TOOLS, save
from StreetNeighborhood import PORTAL_IMAGES


MAP = "/Game/Prologue/L_DimaApartmentStreet"
OUTPUT = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir())) / "Street" / "Neighborhood"


def install_lods():
    editor = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    for name, medium, low in (("SM_Sedan94",.48,.20),("SM_BookKiosk",.52,.23),
                              ("SM_CourtyardBirch",.56,.24),("SM_PressBundles",.51,.24)):
        mesh = ue.load_asset(f"{ROOT}/Meshes/{name}")
        if mesh.get_num_lods() < 3:
            options = ue.StaticMeshReductionOptions()
            levels = []
            for fraction, size in ((1,1), (medium,.23), (low,.076)):
                item = ue.StaticMeshReductionSettings()
                item.set_editor_properties({"percent_triangles":fraction,"screen_size":size})
                levels.append(item)
            options.set_editor_properties({"auto_compute_lod_screen_size":False,"reduction_settings":levels})
            if editor.set_lods(mesh, options) < 3:
                raise RuntimeError(f"LOD reduction failed for {name}.")
            save(mesh)
        if name in ("SM_Sedan94","SM_BookKiosk"):
            bound = mesh.get_bounding_box()
            box = ue.KBoxElem()
            # The sedan's parked instances and the press booth use one cheap box each.
            dims = bound.max - bound.min
            center = (bound.max + bound.min) * .5
            if name == "SM_BookKiosk":
                center, dims = ue.Vector(0,0,112), ue.Vector(262,184,224)
            box.set_editor_properties({"center":center,"x":dims.x,"y":dims.y,"z":dims.z})
            setup = mesh.get_editor_property("body_setup")
            geometry = setup.get_editor_property("agg_geom")
            for key in ("convex_elems","sphere_elems","sphyl_elems"):
                geometry.set_editor_property(key, [])
            geometry.set_editor_property("box_elems", [box])
            setup.set_editor_property("agg_geom", geometry)
            setup.set_editor_property("collision_trace_flag",ue.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
            save(mesh)
        ue.log(f"NEPTUNE_LOD {name}: {[mesh.get_num_triangles(i) for i in range(3)]}")


def import_photos():
    folder = f"{ROOT}/Transitions"
    textures = {}
    for key, name in PORTAL_IMAGES.items():
        task = ue.AssetImportTask()
        task.set_editor_properties({"filename":str(OUTPUT / (name + ".png")),"destination_path":folder,
                                    "automated":True,"replace_existing":True,"save":False})
        TOOLS.import_asset_tasks([task])
        texture = ue.load_asset(f"{folder}/{name}")
        if not isinstance(texture, ue.Texture2D):
            raise RuntimeError(f"Could not import photo {name}.")
        texture.set_editor_properties({"lod_group":ue.TextureGroup.TEXTUREGROUP_UI,
                                       "mip_gen_settings":ue.TextureMipGenSettings.TMGS_NO_MIPMAPS,
                                       "never_stream":True})
        save(texture)
        textures[key] = texture
    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem).get_all_level_actors()
    threshold, = [entry for entry in actors if isinstance(entry,ue.StreetDoorThreshold)]
    threshold.modify()
    threshold.set_editor_properties({"street_photo":textures["StreetCard"],"apartment_photo":textures["ApartmentCard"]})
    gates = {"Precinct street door":"PrecinctCard","Precinct lobby exit":"StreetCard",
             "Bar Lighthouse entrance reserved for a future level":"BarCard"}
    for actor in actors:
        key = gates.get(actor.get_actor_label())
        if isinstance(actor,ue.StreetPortal) and key:
            actor.modify()
            actor.set_editor_property("destination_photo",textures[key])
    ue.log(f"NEPTUNE_PHOTOS {len(textures)} local photographs assigned")


class PhotoRun:
    def __init__(self):
        self.levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
        self.actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        self.deadline = time.monotonic() + 140
        self.serial = iter((*PORTAL_IMAGES.items(), ("ParkReview","Courtyard"), ("ShopsReview","Shops"),
                            ("PressReview","Press"), ("PlanReview","Plan")))
        self.stage = self.choose
        self.at = 0
        self.busy = False
        self.done = False

    def later(self, action, delay=0):
        self.stage = action
        self.at = time.monotonic() + delay

    def presentation_light(self):
        clock = next(actor for actor in self.actors.get_all_level_actors() if isinstance(actor,ue.PrologueTimeOfDay))
        self.sun = clock.get_editor_property("sun")
        self.key_light = self.sun.get_component_by_class(ue.DirectionalLightComponent)
        self.fill = clock.get_editor_property("ambient_sky").get_component_by_class(ue.SkyLightComponent)
        self.original = (self.sun.get_actor_rotation(), self.key_light.get_editor_property("intensity"),
                         self.key_light.get_editor_property("light_color"), self.fill.get_editor_property("intensity"))
        self.sun.set_actor_rotation(ue.Rotator(0,-46,316),False)
        self.key_light.set_intensity(3.5)
        self.key_light.set_light_color(ue.LinearColor(1,.90,.77,1))
        self.fill.set_intensity(1.10)

    def restore_light(self):
        rotation, intensity, color, fill = self.original
        self.sun.set_actor_rotation(rotation,False)
        self.key_light.set_intensity(intensity)
        self.key_light.set_editor_property("light_color",color)
        self.fill.set_intensity(fill)

    def choose(self):
        item = next(self.serial,None)
        if not item:
            self.bind()
            return
        tag, name = item
        camera, = [actor for actor in self.actors.get_all_level_actors() if actor.actor_has_tag(ue.Name(tag))]
        ue.log(f"NEPTUNE_CAMERA {tag} object={camera.get_name()}")
        self.out = OUTPUT / (name + ".png")
        self.last_capture = self.out.stat().st_mtime_ns if self.out.exists() else 0
        self.task = ue.AutomationLibrary.take_high_res_screenshot(1280,720,str(self.out),camera=camera,delay=.5)
        if not self.task or not self.task.is_valid_task():
            raise RuntimeError(f"Could not request the photograph for {tag}.")
        self.later(self.wait_for_photo, .7)

    def wait_for_photo(self):
        if self.task.is_task_done() and self.out.exists() and self.out.stat().st_mtime_ns != self.last_capture:
            self.later(self.choose, .25)

    def bind(self):
        self.restore_light()
        import_photos()
        if not self.levels.save_current_level():
            raise RuntimeError("Could not save the location photos.")
        self.finish(True)

    def finish(self, ok):
        if self.done:
            return
        self.done = True
        ue.unregister_slate_post_tick_callback(self.handle)
        if not ok:
            self.restore_light()
        ue.EditorPythonScripting.set_keep_python_script_alive(False)
        if ok:
            ue.log("NEPTUNE_PRESENTATION_OK")

    def tick(self, _delta):
        if self.done or self.busy:
            return
        self.busy = True
        try:
            if time.monotonic() > self.deadline:
                raise RuntimeError(f"Timed out during {self.stage.__name__}.")
            if time.monotonic() >= self.at:
                self.stage()
        except Exception as error:
            ue.log_error(f"NEPTUNE_PRESENTATION_ERROR {self.stage.__name__}: {error!r}")
            self.finish(False)
        finally:
            self.busy = False

    def run(self):
        if not self.levels.load_level(MAP):
            raise RuntimeError(f"Could not open {MAP}.")
        install_lods()
        self.presentation_light()
        OUTPUT.mkdir(parents=True,exist_ok=True)
        ue.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = ue.register_slate_post_tick_callback(self.tick)


PhotoRun().run()
