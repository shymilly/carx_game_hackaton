"""Sweep asphalt, curbs, sidewalks and markings around the three outer street corners."""
from dataclasses import dataclass
from math import cos, pi, sin, sqrt

import unreal as ue

from BrightonUpgrade import PROJECT, media, save

STREET_MATERIALS = '/Game/Prologue/Street/Materials/M_'
ROAD_MESHES = '/Game/StreetArtPass/OuterBlocks/Meshes'
ASPHALT = -27.92
SIDEWALK = -11.95
SIDEWALK_WIDTH = 316


@dataclass(frozen=True)
class StreetCorner:
    name: str
    start: tuple
    forward: tuple
    approach: float
    radius: float
    turn: int
    departure: float
    width: float

    @property
    def arc_length(self):
        return self.radius * pi / 2

    @property
    def length(self):
        return self.approach + self.arc_length + self.departure

    def frame(self, station):
        fx, fy = self.forward
        rx, ry = -fy, fx
        curve = max(0, min(station - self.approach, self.arc_length))
        angle = curve / self.radius
        along = min(station, self.approach) + self.radius * sin(angle)
        across = self.turn * self.radius * (1 - cos(angle))
        facing = (fx * cos(angle) + rx * self.turn * sin(angle), fy * cos(angle) + ry * self.turn * sin(angle))
        tail = max(0, station - self.approach - self.arc_length)
        position = (self.start[0] + fx * along + rx * across + tail * facing[0],
                    self.start[1] + fy * along + ry * across + tail * facing[1])
        return position, facing

    def point(self, station, lateral, z):
        (x, y), (fx, fy) = self.frame(station)
        return x - fy * lateral, y + fx * lateral, z

    def samples(self):
        divisions = 24
        return [0., self.approach, *(self.approach + self.arc_length * i / divisions for i in range(1, divisions+1)),
                self.length]


# The existing traffic ends before these approaches. West Brighton passes below the elevated railway.
CORNERS = (
    StreetCorner('SouthBrighton', (-8800, -1255), (-1, 0), 1890, 1460, -1, 3900, 970),
    StreetCorner('EastBrighton', (2430, 6638), (0, 1), 1850, 1490, 1, 4400, 960),
    StreetCorner('WestBrighton', (2430, -6628), (0, -1), 1970, 1540, -1, 4650, 960),
)


def corner_mesh(corner, materials):
    name = 'SM_' + corner.name + '_RoadTurn'
    source = PROJECT / 'Saved/BrightonDetail/Roads' / (name + '.obj')
    source.parent.mkdir(parents=True, exist_ok=True)
    lines = ['o ' + name, 's off']
    index = 1

    def ribbon(slot, stations, inner, outer, inner_height, outer_height):
        nonlocal index
        lines.append('usemtl ' + slot)
        for a, b in zip(stations, stations[1:]):
            coords = [corner.point(a, inner, inner_height), corner.point(a, outer, outer_height),
                      corner.point(b, outer, outer_height), corner.point(b, inner, inner_height)]
            # OBJ is right-handed. Interchange reflects Y when it imports the mesh into Unreal.
            verts = [(x - corner.start[0], -(y - corner.start[1]), z) for x, y, z in coords]
            a_x, a_y, a_z = (b - a for a, b in zip(verts[0], verts[1]))
            b_x, b_y, b_z = (b - a for a, b in zip(verts[0], verts[2]))
            normal = (a_y*b_z - a_z*b_y, a_z*b_x - a_x*b_z, a_x*b_y - a_y*b_x)
            length = sqrt(sum(value*value for value in normal))
            normal = tuple(value/length for value in normal)
            if normal[2] < 0:
                verts.reverse()
                normal = tuple(-value for value in normal)
            lines.extend(f'v {x:.5f} {y:.5f} {z:.5f}' for x, y, z in verts)
            lines.extend(f'vt {x/220:.5f} {(y + z)/220:.5f}' for x, y, z in verts)
            # Keep per-face normals, including the vertical edges at the curbs.
            lines.extend(['vn {:.6f} {:.6f} {:.6f}'.format(*normal)] * 4)
            for face in ((0, 1, 2), (0, 2, 3)):
                lines.append('f ' + ' '.join(f'{index+i}/{index+i}/{index+i}' for i in face))
            index += 4

    half = corner.width / 2
    stations = corner.samples()
    ribbon('Asphalt', stations, -half, half, ASPHALT, ASPHALT)
    for bank in (-1, 1):
        edge = bank * half
        ribbon('Curbs', stations, edge, edge, ASPHALT, SIDEWALK)
        ribbon('Curbs', stations, edge, edge + bank * 14, SIDEWALK, SIDEWALK)
        ribbon('Sidewalk', stations, edge + bank * 14, edge + bank * SIDEWALK_WIDTH, SIDEWALK, SIDEWALK)
        ribbon('Curbs', stations, edge + bank * SIDEWALK_WIDTH, edge + bank * SIDEWALK_WIDTH, SIDEWALK, -47)
        for dash in range(42, int(corner.length) - 215, 420):
            ribbon('LanePaint', [dash, dash+199], bank*8-4, bank*8+4, ASPHALT+.22, ASPHALT+.22)

    source.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    model = media(source, ROAD_MESHES)
    seen = set()
    for slot, material in enumerate(model.get_editor_property('static_materials')):
        label = str(material.get_editor_property('imported_material_slot_name'))
        surface = next(key for key in materials if label.lower().endswith(key.lower()))
        model.set_material(slot, materials[surface])
        seen.add(surface)
    assert seen == set(materials), (corner.name, seen)
    box = model.get_bounding_box()
    x, y, _ = corner.point(corner.length, 0, 0)
    assert box.min.x-.1 <= x-corner.start[0] <= box.max.x+.1
    assert box.min.y-.1 <= y-corner.start[1] <= box.max.y+.1, (corner, box)
    save(model)
    return model


def make_road_meshes():
    materials = {
        'Asphalt': ue.load_asset('/Game/StreetArtPass/Materials/M_RoadAsphalt'),
        'Sidewalk': ue.load_asset('/Game/Prologue/Brighton/Materials/M_Wet_WeatheredConcrete'),
        'Curbs': ue.load_asset(STREET_MATERIALS + 'stone'),
        'LanePaint': ue.load_asset(STREET_MATERIALS + 'yellow_line'),
    }
    assert all(materials.values())
    return {corner.name: corner_mesh(corner, materials) for corner in CORNERS}
