"""Import the Brighton photograph and create the game's lightweight startup map."""
from pathlib import Path
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project/'Tools'))
from BrightonUpgrade import ACTORS, ASSETS, LEVELS, media, save

photo = media(project/'Resources/Presentation/T_MainMenuBrighton.png','/Game/UI/Menu')
assert isinstance(photo,ue.Texture2D)
photo.set_editor_properties(dict(lod_group=ue.TextureGroup.TEXTUREGROUP_UI,
    mip_gen_settings=ue.TextureMipGenSettings.TMGS_NO_MIPMAPS,never_stream=True))
save(photo)

path = '/Game/Locations/L_MainMenu'
if ASSETS.does_asset_exist(path):
    assert LEVELS.load_level(path)
else:
    assert LEVELS.new_level(path,False)
world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
settings = ue.GameplayStatics.get_actor_of_class(world,ue.WorldSettings)
assert settings
settings.set_editor_property('default_game_mode',ue.DostoevskyMenuGameMode.static_class())
if not any(isinstance(actor,ue.PlayerStart) for actor in ACTORS.get_all_level_actors()):
    ACTORS.spawn_actor_from_class(ue.PlayerStart,ue.Vector(0,0,90),ue.Rotator())
assert LEVELS.save_current_level()
ue.log('MENU_MAP_READY')
