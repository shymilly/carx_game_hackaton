"""Bake the updated NPC gestures and dress the existing Lighthouse Bar map."""
from pathlib import Path
from shutil import copy2
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project / 'Tools'))
from BrightonBarDressing import dress_bar, import_bottles
from BrightonUpgrade import ACTORS, ASSETS, LEVELS, factory_asset, save
from CityLifeCharacters import PEOPLE, STYLES, apply_profile


def backup(name):
    package = project / 'Content/Locations' / (name + '.umap')
    folder = project / 'Saved/Backups/BrightonDressing'
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / package.name).exists():
        copy2(package, folder / package.name)


def clip_for(model, base, outfit, gesture):
    factory = ue.AnimSequenceFactory()
    factory.set_editor_properties(dict(target_skeleton=model.get_editor_property('skeleton'), preview_skeletal_mesh=model))
    clip = factory_asset(f'{PEOPLE}/Motions/{outfit}', f'A_{outfit}_{gesture}', ue.CityGestureSequence, factory)
    assert ue.CityCharacterAuthoring.author_gesture(model, base, clip, gesture), (outfit, gesture)
    for channel in ('bone', 'curve'):
        compression = ue.load_asset(f'/ACLPlugin/ACLAnim{channel.title()}CompressionSettings')
        assert compression, channel
        clip.set_editor_property(channel + '_compression_settings', compression)
    tip = 'Palm_R' if outfit != 'Woman' else 'RightHand'
    sample = ue.CityCharacterAuthoring.pose_bone_position
    start = sample(model, clip, tip, 0)
    end = sample(model, clip, tip, clip.get_play_length())
    assert start.length() > 1 and (end - start).length() < .5, (outfit, gesture, start, end)
    save(clip)
    ue.log(f'QUALITY_NPC_CLIP {outfit}/{gesture} {clip.get_play_length():.2f}s seamless endpoints')
    return clip


def update_profiles():
    cache = {}
    for role, (outfit, *_) in STYLES.items():
        if role == 'Dima':
            continue
        destination = ue.load_asset(PEOPLE + '/Profiles/DA_' + role)
        model = destination.get_editor_property('mesh')
        motions = dict(destination.get_editor_property('motions'))
        idle = motions[ue.Name('Idle')]
        # On reruns the source must still be the original idle, not the bottle pose baked from it.
        if role in ('OlderMan', 'Bartender'):
            idle = ue.load_asset(f'{PEOPLE}/Models/{outfit}/Smooth_Male_{outfit}_Anim_HumanArmature_Man_Idle')
        changes = {'Talk': ('Talk', idle), 'Nod': ('Nod', idle)}
        if ue.Name('Sit') in motions:
            changes['SeatedIdle'] = ('SeatedIdle', motions[ue.Name('Sit')])
            changes['SeatedTalk'] = ('SeatedTalk', motions[ue.Name('Sit')])
            changes['SeatedNod'] = ('SeatedNod', motions[ue.Name('Sit')])
        if role in ('Ivan', 'Smoker'):
            changes['Smoke'] = ('Smoke', idle)
        if role in ('OlderMan', 'Bartender'):
            changes.update(Idle=('HoldBottle', idle), Talk=('TalkWithBottle', idle))
        for slot, (gesture, source) in changes.items():
            key = outfit, gesture
            if key not in cache:
                cache[key] = clip_for(model, source, outfit, gesture)
            motions[ue.Name(slot)] = cache[key]
        destination.set_editor_property('motions', motions)
        save(destination)
        if role in ('Ivan', 'Smoker', 'OlderMan', 'Bartender'):
            save(model)


backup('L_LighthouseBar')
update_profiles()
bottles = import_bottles()
assert LEVELS.load_level('/Game/Locations/L_LighthouseBar')
for cast in ACTORS.get_all_level_actors():
    if isinstance(cast, ue.ActOneCast) and not cast.get_editor_property('hidden'):
        apply_profile(cast, cast.get_editor_property('character_profile'))
dress_bar(bottles)
assert LEVELS.save_current_level()
ue.log('QUALITY_BRIGHTON_BAR_CAST_OK')
