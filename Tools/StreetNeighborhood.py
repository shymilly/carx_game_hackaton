"""Lay out Neptune Avenue from the hand-drawn plan. All distances are centimeters."""
from math import atan2, cos, degrees, hypot, radians, sin
from random import Random

import unreal as ue

from StreetMaterials import ASSETS, ROOT, save
from StreetScene import ROAD_Z, SIDEWALK_Z, R, V


# +X points toward the top of the paper, +Y points to the right.
STEM_LEFT, STEM_RIGHT = -1740, -770
CROSS_NEAR, CROSS_FAR = 1950, 2910
PLAY_SOUTH, PLAY_NORTH = -6720, 4510
PLAY_LEFT, PLAY_RIGHT = -5420, 5160
PRESS = (-1505, -535)
PORTAL_IMAGES = {
    "StreetCard": "T_Transition_Neptune",
    "ApartmentCard": "T_Transition_Apartment",
    "PrecinctCard": "T_Transition_Precinct",
    "BarCard": "T_Transition_Bar",
}


def preview(key):
    path = f"{ROOT}/Transitions/{PORTAL_IMAGES[key]}"
    return ue.load_asset(path) if ASSETS.does_asset_exist(path) else None


def block_boundary(b, label, location, dimensions):
    actor = b.block(label, location, dimensions, "frame")
    actor.set_actor_hidden_in_game(True)
    component = actor.get_component_by_class(ue.StaticMeshComponent)
    component.set_collision_profile_name(ue.Name("StreetPawnBoundary"))
    component.set_editor_properties({"cast_shadow": False, "affect_distance_field_lighting": False})
    return actor


def pave_segment(b, label, lo, hi, width):
    dx, dy = hi[0]-lo[0], hi[1]-lo[1]
    b.block(label, ((lo[0]+hi[0])/2, (lo[1]+hi[1])/2, ROAD_Z-5),
            (hypot(dx,dy), width, 10), "asphalt", rotation=(0,0,degrees(atan2(dy,dx))))


def roads(b):
    b.folder = "Street/01 Pavement"
    b.slab("Block foundation", -9310, 7100, -6920, 6850, -36, 96, "asphalt")
    b.slab("Neptune Avenue • stem", -8810, CROSS_NEAR, STEM_LEFT, STEM_RIGHT, ROAD_Z, 12, "asphalt")
    b.slab("West Sixteenth • cross street", CROSS_NEAR, CROSS_FAR, -6700, 6670, ROAD_Z, 12, "asphalt")
    pave_segment(b, "South fork west spur", (-7570,-1350), (-8840,-3190), 736)
    pave_segment(b, "South fork east spur", (-7570,-1090), (-8840,590), 710)
    b.slab("Left sidewalk", -7930, CROSS_NEAR, -2080, STEM_LEFT, SIDEWALK_Z, 25, "concrete")
    b.slab("Dima sidewalk", -7930, CROSS_NEAR, STEM_RIGHT, -451, SIDEWALK_Z, 25, "concrete")
    b.slab("Door step", -271, -118, -515, -440, -.4, 17, "stone")
    for lo, hi in ((-6630, STEM_LEFT), (STEM_RIGHT, 6640)):
        b.slab("Cross-street near sidewalk", 1635, CROSS_NEAR, lo, hi, SIDEWALK_Z, 25, "concrete")
    b.slab("Cross-street far sidewalk", CROSS_FAR, 3250, -6630, 6670, SIDEWALK_Z, 25, "concrete")

    # Coarse staining, aggregate and repairs repeat at independent world-space scales.
    for x, y, length, width, angle in (
        (-2980,-1000,215,108,-4), (-1130,-1455,510,161,4), (-45,-1130,145,170,12),
        (1090,-970,310,190,-6), (2847,-1827,81,620,4), (2210,1530,144,225,-14),
        (-6030,-1610,370,127,-5), (-4660,-1060,248,175,13),
    ):
        b.detail((x,y,ROAD_Z+.11), (length,width,.16), "asphalt_repair", (0,0,angle))
    for offset in (-6, 6):
        b.detail((-2650,-1255+offset,ROAD_Z+.26), (7530,7,.24), "yellow_line")
        for y0,y1 in ((-6000,-1795), (-715,6005)):
            b.detail((2424+offset,(y0+y1)/2,ROAD_Z+.26), (7,y1-y0,.24), "yellow_line")
    for y in range(STEM_LEFT+56, STEM_RIGHT-16, 73):
        b.detail((1760,y,ROAD_Z+.26), (164,34,.23), "white_line")
    for y in (-1885,-635):
        for x in range(CROSS_NEAR+54,CROSS_FAR-25,73):
            b.detail((x,y,ROAD_Z+.27), (34,158,.25), "white_line")
    for x in range(-6640, 1925, 180):
        for y in (STEM_LEFT+1, STEM_RIGHT-1):
            b.detail((x,y,-18), (178,13,13), "stone")
    for y in range(-6280, 6210, 181):
        b.detail((CROSS_FAR-2,y,-18), (13,178,13), "stone")
        if not STEM_LEFT < y < STEM_RIGHT:
            b.detail((CROSS_NEAR+2,y,-18), (13,178,13), "stone")
    for x,y in ((-3003,-1532), (-842,-940), (534,-1416), (2200,-3010), (2520,1040)):
        b.detail((x,y,ROAD_Z+.31), (62,62,.28), "steel", shape="Cylinder")
        for slot in (-12,0,12):
            b.detail((x,y+slot,ROAD_Z+.48), (25,2.6,.18), "frame")

    block_boundary(b, "Invisible limit before south fork", (PLAY_SOUTH, -100, 296), (30,10900,650))
    block_boundary(b, "Invisible north limit behind buildings", (PLAY_NORTH, -100, 296), (28,10900,650))
    for y in (PLAY_LEFT, PLAY_RIGHT):
        block_boundary(b, "Invisible cross-street limit", (-1105,y,296), (11250,28,650))


def street_fronts(b):
    b.folder = "Street/03 Shops and cross street"
    # Left of the stem. The police desk is around the corner at the T.
    for title,x,front,width,depth,height,finish,shop in (
        ("Grocery walk-up", -1630,-2089,900,575,967,"ochre_brick",("SM_NeighborhoodGrocery","burgundy_canvas")),
        ("Pharmacy walk-up", -597,-2085,900,645,1125,"brick",("SM_NeighborhoodPharmacy","green_canvas")),
        ("Corner row house", 290,-2094,730,595,916,"ochre_brick",None),
        ("South block brownstones", -2780,-2094,1130,630,943,"brick",None),
        ("South block walk-up", -4010,-2112,1190,710,1080,"ochre_brick",None),
        ("South fork left residence", -5590,-2202,1370,800,1030,"brick",None),
    ):
        b.building(title, x, front, 1, width, depth, height, finish, shop)
    # Right side of the stem, including the borrowed visual depth toward the extension.
    for title,x,front,width,depth,height,finish in (
        ("Corner apartments beside Dima", 1296,-459,850,862,1034,"ochre_brick"),
        ("Opposite press end wall", -2095,-445,868,625,913,"ochre_brick"),
        ("South extension brick walk-up", -3415,-453,1440,740,1084,"brick"),
        ("South extension brownstone", -5125,-445,1390,744,903,"ochre_brick"),
        ("Fork perspective townhouses", -7200,-448,1380,872,839,"brick"),
    ):
        b.building(title,x,front,-1,width,depth,height,finish)

    with b.rotated(90):
        # The cross street's far side reads left to right as in the plan.
        for title,y,front,width,depth,height,finish,shop in (
            ("Weathered tenement west", -4320, -3214, 970, 652, 837, "ochre_brick", None),
            ("Weathered tenement east", -3240, -3218, 982, 690, 1017, "brick", None),
            ("Tall apartment opposite Neptune", -1040, -3230, 1018, 790, 1484, "ochre_brick", None),
            ("Cross-street apartments", 146, -3240, 1065, 900, 1125, "brick", None),
            ("Bar Lighthouse shell", 1290, -3270, 824, 854, 734, "brick", ("SM_NeighborhoodBar", "blue_canvas")),
            ("Far east cross-street block", 2735, -3240, 1536, 808, 968, "ochre_brick", None),
            ("Eastbound perspective row", 4530, -3257, 1770, 845, 923, "brick", None),
        ):
            b.building(title,y,front,1,width,depth,height,finish,shop)
        for y in (-4710,-4424,-3900,-3600,-3015):
            b.detail((y,-3190,128), (76,5,124), "ply")
            for dz in (-32,7,41):
                b.detail((y,-3186,128+dz), (86,4,7), "dark_stone", (0,0,-3))
        b.block("Bar closed entrance", (1290,-3236,100), (116,17,222), "frame")
        b.detail((1290,-3225,150), (69,8,86), "dark_glass")
        b.detail((1335,-3216,93), (6,9,19), "steel")
        b.detail((1290,-3207,212), (154,18,9), "lamp_glass")
        for y,width in ((-5070,760),(3980,950),(5100,1100)):
            b.building("Cross-street depth row", y,-1628,-1,width,660,877,"brick")


def market(b):
    b.folder = "Street/04 Flea market"
    b.slab("Flea market paving", 3220,4075,-2730,-1575,SIDEWALK_Z,24,"concrete")
    b.block("Flea market warehouse back", (4035,-2148,355), (152,1141,731), "ochre_brick")
    with b.rotated(90):
        b.block("Flea market sign frame", (-2158,-3240,287), (479,18,54), "dark_stone", collision=False)
        lettering = b.model("Вывеска БАРАХОЛКА", b.meshes["SM_NeighborhoodFlea"], (-2158,-3229,287),180,False)
        lettering.set_actor_scale3d(V(1.8,1,1.4))
        for y in (-2394,-1922):
            b.block("Market entrance post", (y,-3242,137), (12,14,296), "frame")
    rng = Random(47)
    for i, (x,y,cloth) in enumerate(((3455,-2540,"burgundy_canvas"),(3460,-2215,"tan_canvas"),(3455,-1855,"green_canvas"),
                                      (3830,-2450,"blue_canvas"), (3820,-1910,"burgundy_canvas"))):
        for dx in (-106,106):
            for dy in (-119,119):
                b.detail((x+dx,y+dy,115), (7,7,249), "steel")
        for j in range(10):
            b.detail((x,y-128+j*28,239), (245,28.6,3.1), cloth if j%4 != 3 else "faded_white", (0,9,0))
        b.detail((x-121,y,212), (6,283,22), cloth)
        b.block("Market folding table", (x-33,y,72), (81,238,7), "wood")
        for dx in (-68,5):
            for dy in (-101,101):
                b.detail((x+dx,y+dy,28), (5,5,80), "frame")
        for dy in range(-96,100,33):
            r = rng.randrange(4)
            b.detail((x-37,y+dy,80+r*2), (48,27,9+r*3), ("paper","wood","dark_glass","ply")[r])
        if i in (0,2,4):
            b.detail((x-26,y-70,103), (43,50,51), "frame")
            b.detail((x-50,y-70,105), (6,39,37), "store_glass")
        for dy in (-72,70):
            b.detail((x+46,y+dy,12), (62,51,43), "ply")


def vegetation(b, label, x, y, height, shrub=False, yaw=0):
    key = "SM_CourtyardShrub" if shrub else "SM_CourtyardBirch"
    mesh = b.meshes[key]
    bounds = mesh.get_bounding_box()
    ratio = height / max(1, bounds.max.z-bounds.min.z)
    tree = b.model(label, mesh, (x,y,SIDEWALK_Z-bounds.min.z*ratio), yaw, False)
    tree.set_actor_scale3d(V(ratio,ratio,ratio))
    if not shrub:
        b.block("Tree trunk collision", (x,y,77), (17,17,173), "wood").set_actor_hidden_in_game(True)


def bench(b, x, y, yaw=0):
    for offset in (-16,-5,6,17):
        b.detail((x,y+offset,44), (148,9,5), "wood", (0,0,yaw))
    for z in (64,75,86):
        b.detail((x,y+22,z), (148,6,9), "wood", (0,0,yaw))
    for dx in (-56,56):
        b.detail((x+dx,y+17,40), (7,11,89), "frame", (0,0,yaw))
        b.detail((x+dx,y-16,16), (7,9,48), "frame", (0,0,yaw))
    blocker = b.block("Bench contact", (x,y,21), (148,46,46), "frame", rotation=(0,0,yaw))
    blocker.set_actor_hidden_in_game(True)


def park(b):
    b.folder = "Street/05 Enclosed courtyard"
    b.slab("Single court passage", -1344,-780,-472,654,SIDEWALK_Z,25,"concrete")
    b.slab("Park walkable base", -1344,1690,448,2580,SIDEWALK_Z,25,"concrete")
    # The kitchen and living-room wings form part of the west wall.
    b.block("Courtyard west end beside bathroom", (634,455,163), (488,29,351), "brick")
    b.block("Courtyard west end at corner building", (847,455,157), (46,30,336), "brick")
    b.block("Passage wall behind press kiosk", (-1354,1055,142), (27,3050,309), "ochre_brick")
    b.block("Park entrance cheek along Dima house", (-781,-209,104), (14,496,234), "frame").set_actor_hidden_in_game(True)
    b.block("Park frontage wall below the facade", (-585,-453,142), (390,23,308), "brick")
    for y in range(-421,40,15):
        b.detail((-781,y,112), (3,3,234), "patina")
    for z in (5,217):
        b.detail((-781,-207,z), (8,474,7), "frame")
    b.detail((-1354,1055,298), (45,3070,12), "stone")
    for x,y,width,depth,height in ((-944,2573,830,568,854),(-9,2573,1041,595,1198),
                                   (1114,2573,1231,672,1005)):
        b.building("Park east perimeter walk-up", x,y,-1,width,depth,height,"brick")
    with b.rotated(90):
        b.building("Park north perimeter terraces", 1515,-1700,1,2194,545,927,"ochre_brick")
        b.building("Park south perimeter terrace", 1652,1368,-1,1835,480,818,"ochre_brick")
    # Walkable lawn and a simple New York-style hard court.
    for x0,x1,y0,y1 in ((-1055,38,738,1375),(287,1400,609,1260),(-1010,75,1610,2398)):
        b.slab("Park lawn",x0,x1,y0,y1,SIDEWALK_Z+4.1,20,"grass")
        for y in (y0,y1):
            b.detail(((x0+x1)/2,y,-6.9),(x1-x0,11,15),"stone")
        for x in (x0,x1):
            b.detail((x,(y0+y1)/2,-6.9),(11,y1-y0,15),"stone")
    b.slab("Handball court surface", 350,1400,1535,2350,SIDEWALK_Z+.25,15,"court")
    b.block("Handball practice wall", (1381,1940,147), (42,823,325), "dark_stone")
    for x in (397,807,1135):
        b.detail((x,1940,-11.47),(4,721,.22),"white_line")
    for y in (1578,2302):
        b.detail((881,y,-11.45),(973,4,.22),"white_line")
    for x,y,h,angle in ((-915,944,518,33),(-506,1188,640,101),(-739,2161,584,45),
                         (564,915,611,120),(1170,989,548,210),(1185,2451,507,30),(-1071,2355,502,130)):
        vegetation(b,"Courtyard birch",x,y,h,False,angle)
    for x,y,h in ((-1230,789,61),(-1220,1221,73),(-1190,1735,71),(116,2224,69),(1255,2465,68),
                  (1477,949,87),(1427,1281,66),(-287,2485,73),(-1120,2474,73)):
        vegetation(b,"Courtyard planting",x,y,h,True)
    for x,y in ((-548,1432),(-555,1550),(709,1322),(1084,2475)):
        bench(b,x,y)
    for x,y in ((-1011,493),(121,1500),(1490,2365)):
        b.detail((x,y,123), (8,8,269),"frame",shape="Cylinder")
        b.detail((x,y,263), (22,22,34),"lamp_glass",shape="Cylinder")
        b.detail((x,y,282), (29,29,7),"frame",shape="Cylinder")
    b.detail((-1078,-442,223), (276,13,52), "precinct_green")
    b.model("Neptune Playground entrance plate", b.meshes["SM_NeighborhoodPark"], (-1078,-451,224), collision=False)
    for x in (-1222, -934):
        b.detail((x,-439,115), (9,9,251), "frame")


def precinct(b):
    b.folder = "Street/06 Precinct"
    # The street door and the reception share one architectural shell.
    b.slab("Precinct floor", 790,1827,-3240,-2150,SIDEWALK_Z,24,"lino")
    b.slab("Precinct main roof", 773,1834,-3251,-2138,367,28,"roof")
    b.slab("Precinct lobby ceiling", 795,1818,-3236,-2154,289,21,"plaster_lobby")
    for x,y,sx,sy in ((810,-2695,33,1087),(1310,-3225,1022,31),(1310,-2165,1022,31),(1810,-2695,31,1087)):
        b.block("Precinct masonry shell", (x,y,168), (sx,sy,361), "ochre_brick")
    for y in (-3111,-2950,-2421,-2273):
        b.block("Precinct armored window recess", (1829,y,157), (11,118,145), "dark_stone", collision=False)
        b.detail((1837,y,160), (5,95,121), "dark_glass")
        for dy in (-26,0,26):
            b.detail((1840,y+dy,158), (7,3,139), "frame")
    b.detail((1835,-2695,320), (25,1005,25), "stone")
    b.block("Precinct exterior double doors", (1830,-2725,102), (22,169,226), "precinct_green")
    b.slab("Precinct stoop", 1821,1905,-2835,-2618,-1.5,16,"stone")
    for y in (-2769,-2678):
        b.detail((1843,y,150), (6,62,88), "store_glass")
        b.detail((1850,y,89), (6,20,6), "steel")
    for y in (-2839,-2610):
        b.detail((1849,y,186), (30,12,8), "frame")
        b.detail((1864,y,209), (26,26,29), "precinct_green", shape="Cylinder")
        b.detail((1864,y,226), (27,27,7), "lamp_glass", shape="Cylinder")
        b.spot("Precinct entry globe", (1866,y,214), (0,-62,0), 1.25,390,(.48,.78,.57))
    b.detail((1837,-2725,268), (22,622,55), "precinct_green")
    b.model("60 Precinct fascia", b.meshes["SM_NeighborhoodPrecinct"], (1851,-2725,268),-90,False)

    # Distinct reception, seen during the loading card and after entry.
    for y in (-3201,-2189):
        b.block("Reception side plaster", (1311,y,129),(963,30,282),"plaster_lobby")
        b.detail((1311,y+(-19 if y>-2500 else 19),61),(964,8,124),"precinct_green")
    b.block("Reception back plaster", (833,-2690,129),(16,1027,284),"plaster_lobby")
    b.block("Reception front plaster", (1779,-2690,130),(19,1040,285),"plaster_lobby")
    b.block("Reception inner vestibule door", (1765,-2725,103), (19,166,220), "precinct_green")
    b.detail((1754,-2725,153),(5,119,86),"dark_glass")
    b.block("Officer’s counter carcass", (1114,-2860,44), (90,552,110), "wood")
    b.block("Officer’s stone counter", (1115,-2860,102), (112,585,9), "stone")
    b.detail((1054,-3000,132),(42,54,51),"frame")
    b.detail((1076,-2997,132),(7,43,35),"dark_glass")
    for y in (-2884,-2786,-2682):
        b.detail((1128,y,108), (44,56,6), "paper")
    for x in (1321,1533):
        bench(b,x,-3156)
    b.block("Personnel side door", (907,-2337,102),(20,102,221),"wood")
    b.detail((839,-2792,196),(14,199,103),"wood")
    for y in (-2867,-2811,-2755,-2700):
        b.detail((848,y,200),(8,40,68),"paper")
    for x in (1028,1374,1616):
        b.detail((x,-2700,261),(41,239,14),"frame")
        b.detail((x,-2700,254),(32,214,5),"lamp_glass")
        lamp = b.spawn(ue.PointLight,"Reception fluorescent fill",(x,-2700,238))
        light = lamp.get_component_by_class(ue.PointLightComponent)
        light.set_editor_properties({"mobility":ue.ComponentMobility.MOVABLE,"cast_shadows":False,
                                     "use_inverse_squared_falloff":False,"light_falloff_exponent":2.0})
        light.set_light_color(ue.LinearColor(.83,.9,1,1))
        light.set_attenuation_radius(527)
        light.set_intensity(1.24)


def location_portals(b):
    b.folder = "Street/07 Location transitions"
    threshold = b.spawn(ue.StreetDoorThreshold,"Dima front door location threshold",(-194,-450,96),(0,0,-90))
    threshold.set_editor_properties({"street_photo":preview("StreetCard"),"apartment_photo":preview("ApartmentCard")})
    inside = b.spawn(ue.TargetPoint,"Precinct reception arrival",(1602,-2725,101),(0,0,180))
    outside = b.spawn(ue.TargetPoint,"Precinct sidewalk arrival",(1914,-2725,101))
    for label,pos,rot,dest,title,key,prompt in (
        ("Precinct street door",(1853,-2725,106),(0,0,0),inside,"Полицейский участок","PrecinctCard","Войти в участок"),
        ("Precinct lobby exit",(1746,-2725,106),(0,0,0),outside,"Улица Нептун","StreetCard","Выйти на улицу"),
    ):
        gate = b.spawn(ue.StreetPortal,label,pos,rot)
        gate.set_editor_properties({"prompt":prompt,"destination_title":title,"arrival":dest,"destination_photo":preview(key)})
    bar = b.spawn(ue.StreetPortal,"Bar Lighthouse entrance reserved for a future level",(3207,1290,103))
    destination = ROOT + "/Transitions/DA_BarClosed"
    notice = ue.load_asset(destination) if ASSETS.does_asset_exist(destination) else None
    if not notice:
        factory = ue.DataAssetFactory()
        factory.set_editor_property("data_asset_class",ue.InteractionDocument)
        notice = ue.AssetToolsHelpers.get_asset_tools().create_asset("DA_BarClosed",ROOT + "/Transitions",
                                                                     ue.InteractionDocument,factory)
    if not notice:
        raise RuntimeError(f"Could not create {destination}.")
    notice.set_editor_properties({"title":"Бар «Маяк»","body":"Дверь заперта.","close_label":"Закрыть · Esc"})
    save(notice)
    bar.set_editor_properties({"prompt":"Проверить дверь бара","destination_title":"Бар «Маяк»",
                               "destination_photo":preview("BarCard"),"closed_notice":notice})


def factory(b):
    b.folder = "Street/08 Industrial horizon"
    card = b.meshes["SM_FactoryCard"]

    def backdrop(label, x, y, bottom, width, height, material):
        actor = b.model(label,card,(x,y,bottom+height/2),collision=False,material=material)
        actor.set_actor_scale3d(V(1,width/100,height/100))
        actor.get_component_by_class(ue.StaticMeshComponent).set_editor_properties({
            "cast_shadow":False,"affect_distance_field_lighting":False})

    backdrop("Aegis skyline behind the works", 6500,-1440,62,9560,3300,"factory_distant")
    x,y,lo,w,h = 5595,-1425,-55,7280,2940
    backdrop("Aegis works painted facade",x,y,lo,w,h,"factory_works")
    for i,(u,v,width,height) in enumerate(((300,69,1260,1160),(458,112,1010,1170),(717,93,1180,1310)),1):
        center = y+(u/1024-.5)*w
        z = lo+(1-v/512)*h
        backdrop(f"Animated factory stack plume {i}", x-21-i*2,center+width*.20,z-28,width,height,"factory_smoke")


def furnishings(b):
    b.folder = "Street/09 Sidewalk props"
    kiosk = b.model("Газетный киоск КНИГИ / ПРЕССА", b.meshes["SM_BookKiosk"], (*PRESS,SIDEWALK_Z))
    component = kiosk.get_component_by_class(ue.StaticMeshComponent)
    for index, slot in enumerate(component.static_mesh.get_editor_property("static_materials")):
        if str(slot.get_editor_property("imported_material_slot_name")) == "KioskPaint":
            component.set_material(index,b.materials["press_enamel"])
    b.block("Press sidewalk display shelf", (PRESS[0],PRESS[1]-106,80),(132,50,8),"wood")
    b.model("Folded newspaper display",b.meshes["SM_PressBundles"],(PRESS[0],PRESS[1]-111,84),collision=False)
    b.detail((PRESS[0],PRESS[1]-113,232),(90,9,7),"lamp_glass")
    b.spot("Press case light",(PRESS[0],PRESS[1]-129,221),(0,-55,90),1.6,310,(1,.79,.49))
    b.spot("Dima entrance hood light",(-194,-493,217),(0,-76,0),2.3,330,(1,.72,.42),True)
    for x,y,facing in ((-4420,-775,-1),(-2900,-1740,1),(-1480,-1741,1),(550,-772,-1),
                       (1660,-773,-1),(3090,-1441,-1),(2920,2430,1),(2920,-3500,1)):
        b.lamp(x,y,facing)
    for x,y,yaw in ((-2360,-1848,180),(-3930,-666,0),(3188,2260,90)):
        b.model("Parked 1994 sedan",b.meshes["SM_Sedan94"],(x,y,SIDEWALK_Z),yaw)
    for x,y in ((702,-602),(-2000,-1866),(-613,-1914),(-954,-683),(3160,2030)):
        b.detail((x,y,55),(6.5,6.5,123),"steel",shape="Cylinder")
        b.detail((x,y,115),(18,12,25),"galvanized")
        b.detail((x,y+7,116),(11,1.5,14),"dark_glass")
    b.detail((1830,-815,134),(8,8,292),"galvanized",shape="Cylinder")
    b.detail((1830,-815,267),(112,6,30),"precinct_green")
    b.model("Neptune avenue blade",b.meshes["SM_SignStreet"],(1830,-821,267),collision=False)


def traffic(b):
    b.folder = "Street/10 Traffic"
    flow = b.spawn(ue.StreetTrafficFlow,"Neptune Avenue • two traffic lanes")
    mesh = b.meshes["SM_Sedan94"]
    slots = mesh.get_editor_property("static_materials")
    index = next(i for i, s in enumerate(slots) if str(s.get_editor_property("imported_material_slot_name")) == "CarPaint")
    flow.set_editor_properties({"car_mesh":mesh,"paint_slot":index,
                                "paints":[b.materials["sedan_burgundy"],b.materials["sedan_cream"],
                                          mesh.get_material(index)],
                                "spawn_interval":7.0,"pool_capacity":6})

    def arc(cx,cy,r,start,stop):
        return [(cx+r*cos(radians(start+(stop-start)*i/9)),cy+r*sin(radians(start+(stop-start)*i/9)))
                for i in range(10)]

    outgoing = [(-8640,-1010), *arc(1680,-440,570,-90,0),(2250,6450)]
    incoming = [(2250,-6460), *arc(1670,-2055,580,0,90),(-8640,-1475)]
    for prop,path in (("eastbound",outgoing),("westbound",incoming)):
        spline = flow.get_editor_property(prop)
        spline.clear_spline_points(False)
        for i,(x,y) in enumerate(path):
            spline.add_spline_point(V(x,y,ROAD_Z),ue.SplineCoordinateSpace.WORLD,False)
            spline.set_spline_point_type(i,ue.SplinePointType.LINEAR,False)
        spline.update_spline()


def review_views(b):
    b.folder = "Street/11 Review cameras"
    for label,tag,pos,target,fov in (
        ("Neptune Avenue at dusk","StreetCard",(-2730,-1155,221),(2120,-1110,465),77),
        ("Dima's apartment interior","ApartmentCard",(-154,-211,168),(65,293,123),74),
        ("60 Precinct reception","PrecinctCard",(1586,-2500,163),(1040,-2879,133),78),
        ("Closed bar storefront","BarCard",(2630,1120,170),(3253,1290,184),75),
        ("Courtyard level view","ParkReview",(-1091,609,179),(490,1740,153),76),
        ("Shops across Neptune","ShopsReview",(-1095,-935,173),(-1110,-2085,206),92),
        ("Press counter and courtyard entrance","PressReview",(-1990,-1160,171),(-1370,-535,143),76),
        ("Above the T junction","PlanReview",(-3570,-5020,6530),(160,-900,260),74),
    ):
        b.camera(label,tag,pos,target,fov)


def assemble_neighborhood(b):
    roads(b)
    b.apartment_facade()
    street_fronts(b)
    market(b)
    park(b)
    precinct(b)
    location_portals(b)
    factory(b)
    furnishings(b)
    traffic(b)
    review_views(b)
