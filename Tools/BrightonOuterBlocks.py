"""Residential frontage and collision-free scenery behind the Brighton boundaries."""
from math import atan2, cos, degrees, radians, sin
from random import Random

import unreal as ue

from BrightonEntrances import FACADES, build_entries, label, saved_anchors
from BrightonRoadTurns import CORNERS, SIDEWALK, SIDEWALK_WIDTH, STREET_MATERIALS
from BrightonUpgrade import ACTORS, LIB, V, save
from CityLifeEnvironment import CityLayout
from IndustrialRail import Y as INDUSTRIAL_LINE_Y

TAG = ue.Name('BrightonBlockDressing')
GROUND = -43.9
RETIRED = {'Road continues past the playable boundary', 'Distant raised sidewalk', 'Distant Brighton residential block',
           'Distant lane marking', 'Far city road', 'Far city sidewalks', 'Faded far lane marks', 'Far roadside trees'}




def xyz(v):
    return v.x, v.y, v.z


class OuterBlocks(CityLayout):
    def __init__(self, shift):
        models = {key: ue.load_asset('/Game/Prologue/CityLife/Meshes/SM_' + key)
                  for key in ('OakGreen', 'OakAmber', 'BirchGold', 'Bush', 'Dumpster', 'TrashCan')}
        assert all(models.values())
        super().__init__(models, shift)
        self.materials = {key: ue.load_asset(STREET_MATERIALS + key) for key in (
            'brick', 'stone', 'dark_stone', 'wood', 'frame', 'steel', 'dark_glass', 'lamp_glass',
            'green_canvas', 'burgundy_canvas', 'blue_canvas')}
        self.materials.update({key: ue.load_asset('/Game/StreetArtPass/Materials/M_Wall_' + name) for key, name in (
            ('red_brick', 'AgedRedBrick'), ('brown_brick', 'SootBrownBrick'), ('cream_brick', 'PaleLimeBrick'),
            ('stucco', 'FadedOchreRender'), ('painted', 'GreyPaintedPlaster'), ('concrete', 'WeatheredConcrete'))})
        self.materials['pavement'] = ue.load_asset('/Game/StreetArtPass/Materials/M_Pavement')
        assert all(self.materials.values())

    def actor(self, cls, name, position=(0, 0, 0), rotation=None):
        actor = super().actor(cls, name, position, rotation)
        actor.tags = [TAG]
        folder = 'Brighton/Street frontage and turns'
        actor.set_folder_path(ue.Name(folder + ('/Third-floor view' if self.offset.z else '')))
        return actor

    def part(self, label, position, size, material, yaw=0, pitch=0, cull=20000):
        self.box(label, position, size, self.materials[material], yaw, pitch, cull=cull)

    def grounded(self, label, key, position, scale, yaw=0, cull=23000):
        bounds = self.models[key].get_bounding_box()
        x, y, z = position
        self.instance(label, key, (x, y, z - bounds.min.z*scale), (scale,)*3, yaw, cull=cull)

    def solid(self, label, position, size, material, yaw=0):
        actor = self.actor(ue.StaticMeshActor, label, position, ue.Rotator(yaw=yaw))
        component = actor.get_component_by_class(ue.StaticMeshComponent)
        component.set_static_mesh(self.cube)
        component.set_material(0, self.materials[material])
        component.set_collision_profile_name('NoCollision' if self.offset.z else 'BlockAll')
        actor.set_actor_scale3d(V(*(dimension/100 for dimension in size)))
        return actor


def fill_apartment_frontage(city):
    # The ground-floor shell inherited cutouts from the old shared apartment map.
    for name, midpoint, size in (
        ('Courtyard wall brick infill', (-20, 510, 172), (227.4, 9, 129.4)),
        ('Kitchen return wall brick infill', (-558, 76, 170), (159.4, 9, 123.4)),
        ('Side wall brick infill', (-402, -238, 169.5), (9, 161.4, 128.4)),
    ):
        city.solid(name, midpoint, size, 'brick')

    # Close the reveals between the door slab and the masonry set back at Y=-414.
    # The leaf overlaps the stops, while the interaction volume stays in front of the frame.
    for x in (-251.16, -136.84):
        city.solid('Dima entrance deep stone jamb', (x, -431, 106.35), (6.2, 44, 215.3), 'stone')
    city.solid('Dima entrance sealed head', (-194, -431, 212.65), (119, 44, 5.4), 'stone')
    city.solid('Dima entrance dressed sill', (-194, -435.5, .1), (118.6, 48, 3.6), 'dark_stone')
    city.solid('Pavement from Dima facade to the sidewalk', (207, -433.7, -24.4), (1198, 37.4, 25), 'pavement')
    for x in (-252.8, -135.2):
        city.part('Dima entrance front casing', (x, -453.6, 106.5), (7.2, 2.6, 217), 'dark_stone', cull=7000)
    city.part('Dima entrance casing lintel', (-194, -453.6, 214), (125, 2.6, 6), 'dark_stone', cull=7000)




def lot_clear(placed, x, y, width, depth, yaw, routes):
    angle = radians(yaw)
    ex = (abs(cos(angle))*width + abs(sin(angle))*depth)/2
    ey = (abs(sin(angle))*width + abs(cos(angle))*depth)/2
    if abs(x+8145) < ex+205 or abs(y-INDUSTRIAL_LINE_Y) < ey+205:
        return False
    for route, points in routes:
        if any(abs(x-px) < ex+route.width*.52 and abs(y-py) < ey+route.width*.52 for px, py, _ in points):
            return False
    for other in placed:
        ox, oy, rx, ry = other
        if abs(x-ox) < ex+rx+70 and abs(y-oy) < ey+ry+70:
            return False
    placed.append((x, y, ex, ey))
    return True


def distant_building(city, x, y, yaw, width, depth, stories, variant):
    # The long face runs along local X. Its doors and window trim face local -Y.
    angle = radians(yaw)
    fx, fy = cos(angle), sin(angle)
    height = 82 + stories*287
    wall = ('red_brick', 'stucco', 'brown_brick', 'painted', 'cream_brick')[variant % 5]

    def part(name, u, v, z, size, surface):
        city.part(name, (x+u*fx-v*fy, y+u*fy+v*fx, z), size, surface, yaw, cull=33000)

    part('Outer walk-up continuous masonry', 0, 0, GROUND+height/2, (width, depth, height), wall)
    part('Walk-up plinth', 0, 0, 15, (width+8, depth+8, 118), 'dark_stone')
    part('Walk-up roof cornice', 0, 0, GROUND+height-14, (width+25, depth+25, 31), 'stone')
    part('Roof parapet', 0, 0, GROUND+height+14, (width-4, depth-4, 35), wall)
    if variant % 2:
        part('Brick rooftop stair bulkhead', -width*.21, depth*.21, GROUND+height+75, (176, 162, 143), wall)
    front = -depth/2
    part('Footpath against outer frontage', 0, front-18, -28, (width, 41, 32), 'pavement')
    part('Terracotta rear utility panel', width*.22, depth/2+6, 90, (81, 14, 155), 'wood')
    windows = max(3, round((width-105)/164))
    spacing = (width-120)/windows
    door_bay = windows//2
    for floor in range(stories):
        for bay in range(windows):
            u = (bay-(windows-1)/2)*spacing
            z = 143 + floor*287
            if floor == 0 and bay == door_bay:
                part('Outer walk-up entry surround', u, front-6, 107, (115, 14, 235), 'stone')
                part('Closed outer walk-up door', u, front-14, 101, (92, 9, 220), 'wood' if variant%3 else 'frame')
                part('Door transom', u, front-19, 194, (72, 1.5, 26), 'dark_glass')
                part('Outer building sill step', u, front-27, -4, (130, 57, 15), 'stone')
                continue
            part('Window masonry surround', u, front-3, z, (106, 8, 144), 'stone')
            part('Dark window panes', u, front-7.6, z, (89, 2, 126), 'dark_glass')
            part('Window vertical sash', u, front-9, z, (4.4, 3, 126), 'frame')
            part('Window meeting rail', u, front-9, z, (90, 3, 4.4), 'frame')
            part('Low stone window sill', u, front-11, z-74, (117, 20, 8), 'stone')
        # The gable and courtyard sides are visible around the curve and from Dima's floor.
        for side in (-1, 1):
            end = side*width/2
            z = 143 + floor*287
            for v in (-depth*.23, depth*.23):
                part('Window masonry surround', end+side*3, v, z, (8, 105, 142), 'stone')
                part('Dark window panes', end+side*7.6, v, z, (2, 89, 126), 'dark_glass')
                part('Window vertical sash', end+side*9, v, z, (3, 4.4, 126), 'frame')
                part('Low stone window sill', end+side*11, v, z-74, (20, 117, 8), 'stone')
        if floor:
            for bay in (-.29, -.075, .18):
                part('Window masonry surround', width*bay, depth/2+3, z, (106, 8, 142), 'stone')
                part('Dark window panes', width*bay, depth/2+7.6, z, (89, 2, 126), 'dark_glass')
                part('Window vertical sash', width*bay, depth/2+9, z, (4.4, 3, 126), 'frame')
    part('Metal rainwater downpipe', width/2+3.5, -depth*.38, GROUND+height/2, (8, 8, height), 'steel')


def street_lamp(city, corner, station, lateral, bank):
    x, y, _ = corner.point(station, lateral, SIDEWALK)
    _, (fx, fy) = corner.frame(station)
    yaw = degrees(atan2(fy, fx))
    city.cylinder_part('Outer-block flanged lamp feet', (x, y, SIDEWALK+4), (38, 38, 8), city.materials['stone'])
    city.cylinder_part('Outer-block streetlight poles', (x, y, SIDEWALK+208), (12, 12, 416), city.materials['steel'], cull=22500)
    city.part('Outer-block streetlight arms', corner.point(station, lateral-bank*35, SIDEWALK+411),
              (9, 74, 7), 'steel', yaw, cull=22500)
    city.part('Outer-block lamp reflector', corner.point(station, lateral-bank*68, SIDEWALK+404),
              (28, 52, 13), 'frame', yaw)
    city.part('Outer-block lamp lens', corner.point(station, lateral-bank*70, SIDEWALK+396),
              (20, 37, 4), 'lamp_glass', yaw)


def dress_road_turns(city, models, existing):
    rng = Random(41994)
    routes = [(route, [route.point(i, 0, 0) for i in range(0, int(route.length), 175)]) for route in CORNERS]
    lots = []
    # Respect near scenery and the imports already added to the current map.
    for actor in existing:
        position, extent = actor.get_actor_bounds(False)
        point = position-city.offset
        if actor.get_class() == ue.StaticMeshActor.static_class() and 100<extent.z<2500 and 110<extent.x<3500 and 110<extent.y<3500:
            lots.append((point.x, point.y, extent.x, extent.y))
    for y in (-1898, -612):
        city.part('Sidewalk after the southern fork', (-8612, y, -28), (386, 316, 32), 'pavement', cull=19000)
    for index, route in enumerate(CORNERS):
        mesh_actor = city.individual(route.name + ' curved road and sidewalks', models[route.name], (*route.start, 0))
        mesh_actor.get_component_by_class(ue.StaticMeshComponent).set_cull_distance(37000)
        for station in range(570, int(route.length)-215, 995):
            _, (fx, fy) = route.frame(station)
            heading = degrees(atan2(fy, fx))
            for bank in (-1, 1):
                block_width = rng.randrange(760, 991, 20)
                depth = rng.randrange(550, 750, 25)
                x, y, _ = route.point(station, bank*(route.width/2+SIDEWALK_WIDTH+depth/2+32), GROUND)
                yaw = heading if bank == 1 else heading+180
                if lot_clear(lots, x, y, block_width, depth, yaw, routes):
                    distant_building(city, x, y, yaw, block_width, depth, rng.choice((3, 3, 4, 5)), rng.randrange(5))
            if station % 2:
                street_lamp(city, route, station-195, -(route.width/2+97), -1)
            else:
                street_lamp(city, route, station-195, route.width/2+97, 1)
        for index_in_row, station in enumerate(range(695, int(route.length)-195, 657)):
            bank = (-1, 1)[(index_in_row+index)%2]
            lateral = bank*(route.width/2+115)
            position = route.point(station, lateral, SIDEWALK)
            if abs(position[0]+8145)<270 or abs(position[1]-INDUSTRIAL_LINE_Y)<270:
                continue
            if index_in_row % 3 == 0:
                city.grounded('Outer street tree grates', 'OakGreen' if index%2 else 'OakAmber', position, .78, rng.randrange(360))
            else:
                city.grounded('Outer street curb trash cans', 'TrashCan', position, .94, rng.randrange(360))
            if index_in_row % 4 == 1:
                pad = route.point(station+78, bank*(route.width/2+267), SIDEWALK)
                city.grounded('Dumpster beside outer loading entrance', 'Dumpster', pad, .87, 90+index*90)

        fx, fy = route.forward
        distance = route.approach + route.radius + route.width/2 + 1270
        x, y = (route.start[0]+fx*distance, route.start[1]+fy*distance)
        yaw = degrees(atan2(fy, fx))-90
        # A building on the former sightline sits behind the turn, clear of its through lanes.
        if lot_clear(lots, x, y, 1270, 850, yaw, routes):
            distant_building(city, x, y, yaw, 1270, 850, 5, index+2)
        for bank in (-1, 1):
            dx, dy = -fy*bank, fx*bank
            other_x, other_y = (x+dx*1460+fx*438, y+dy*1460+fy*438)
            if lot_clear(lots, other_x, other_y, 930, 770, yaw, routes):
                distant_building(city, other_x, other_y, yaw, 930, 770, 3+((index+bank)%2), index+bank+4)

    # Back-of-block props continue into the industrial side and the existing background rows.
    for x, y, turns in ((5640, 4320, 0), (5660, 5920, 0), (5220, -5720, 90), (-6260, 5800, 0),
                        (-9460, -4650, 0), (-12960, -2910, 90), (-2490, 6810, 90), (5020, 7510, 90)):
        city.part('Backstreet loading apron', (x, y, GROUND+6), (378, 299, 12), 'concrete', turns)
        city.grounded('Service yard dumpster', 'Dumpster', (x+42, y, GROUND+12), 1.04, turns)
        city.grounded('Service yard waste bin', 'TrashCan', (x-117, y+31, GROUND+12), .96, turns)
        city.grounded('Behind the service yards', 'BirchGold', (x+215, y+138, GROUND), .82, rng.randrange(360))
        city.grounded('Shrubs behind the street boundary', 'Bush', (x-189, y+159, GROUND), .89, rng.randrange(360))


def dress_exterior(road_models, shift=(0, 0, 0)):
    city = OuterBlocks(shift)
    actors = ACTORS.get_all_level_actors()
    entries = saved_anchors(actors,city.offset)
    old = [a for a in actors if a.actor_has_tag(TAG) or label(a) in RETIRED or label(a).startswith('Distant regular windows ')]
    if old:
        assert ACTORS.destroy_actors(old)
    placed = ACTORS.get_all_level_actors()
    fill_apartment_frontage(city)
    build_entries(city, placed, entries)
    placed = ACTORS.get_all_level_actors()
    dress_road_turns(city, road_models, placed)
    for actor in placed:
        if label(actor) == 'Industrial distance haze':
            fog = actor.get_component_by_class(ue.ExponentialHeightFogComponent)
            fog.set_editor_properties(dict(fog_density=.028, start_distance=7200.0))
    materials = set()
    for component in city.batches.values():
        for slot in range(component.get_num_materials()):
            material = component.get_material(slot)
            while isinstance(material, ue.MaterialInstance):
                material = material.get_editor_property('parent')
            if isinstance(material, ue.Material) and not material.get_editor_property('used_with_instanced_static_meshes'):
                materials.add(material)
    for material in materials:
        LIB.set_material_usage(material, ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        save(material)
    ue.log(f'QUALITY_STREET_DETAILS {len(CORNERS)} modeled turns, {len(FACADES)} residential doors, {len(city.batches)} instanced groups')
