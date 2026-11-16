"""Author the runtime HUD and interaction state machine as a compiled Blueprint."""
import unreal as ue

from PlanApartment import DESK_VIEW, DOORS, DOOR_FOOTPRINTS, MAP_NAME

BP = ue.BlueprintEditorLibrary
PIN = ue.BlueprintGraphPinLibrary
ENGINE = "/Script/Engine."
MATH = "KismetMathLibrary"
GAME = "GameplayStatics"
STR = "KismetStringLibrary"
STORY = "/Script/Dostoevsky.DimaApartmentStoryLibrary"
NAVIGATION = "/Script/Dostoevsky.StreetNavigationLibrary"
TITLE = "ОТГОЛОСКИ ПРОШЛОГО"
DIMAS_MAP = "/Game/Prologue/" + MAP_NAME
STREET_MAP = "L_DimaApartmentStreet"
FATHERS_MAP = "/Game/Prologue/L_Apartment"
FOCUS_SOUND = "/Game/Prologue/Audio/S_FocusClick.S_FocusClick"
FOR_EACH_LOOP = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop"
WORLD = "/Script/Dostoevsky.PrologueWorldLibrary"
WALK_SPEED = "360"
SPRINT_SPEED = "650"
SPRINT_COST = "24"
JUMP_COST = "20"
RECOVERY_RATE = "30"

START, WALK, INSPECT, LETTER, IVAN, KEY, END, REPORT, SITTING = -1, 0, 1, 2, 3, 7, 8, 9, 10

CLUES = (
    ("Note", "Записка Фёдора", "Они знают. Уходи. Не ищи меня."),
    ("Folder", "Совершенно секретно", "В описи — номер партии и печать Aegis. Лист с подписью вырван."),
    ("Radio", "Радиоприёмник", "На шкале карандашом отмечена частота. Рядом приписка: «После полуночи»."),
    ("Map", "Карта СССР", "Отец обвёл город и провёл линию к порту. На полях стоит 1987 год."),
    ("Photo", "Фотография", "Фёдор стоит среди людей в форме. На обороте — «Смена № 4»."),
)
DIALOGUE = (
    ("Иван", "Отец всегда был шпионом, Дима. Ты думал, он просто инженер?"),
    ("Дима", "Я спросил, где он. Ты знаешь?"),
    ("Иван", "Он работал на КГБ. Потом — на Aegis. А теперь его убрали."),
    ("Иван", "Возьми ключ от склада. Если хочешь знать правду, иди туда."),
)
INTRO_DOCUMENTS = (
    ("Report", "Патрульный отчёт", "Бар на 4-й улице. Охрана Aegis требует доступ к записям.\nЗаявление передано дежурному. Подпись: Д. Огнев."),
    ("Newspaper", "Промышленный вестник", "Aegis объявила о новом контракте с правительством.\nЗавод на восточной окраине расширит ночную смену."),
)
DOCUMENTS = INTRO_DOCUMENTS + CLUES[:2]
STORY_OBJECTS = (
    ("Television", "Посмотреть новости", ""),
    ("Wardrobe", "Осмотреть шкаф", ""),
    ("Phone", "Ответить на звонок", ""),
)
ROOM_SWITCHES = {
    "LivingSwitch": "LivingRoomLight",
    "KitchenSwitch": "KitchenRoomLight",
    "BathSwitch": "BathRoomLight",
}
LIGHTS = {**ROOM_SWITCHES, "DeskLamp": "DeskLampLight", "FloorLamp": "FloorLampLight"}
WATER = {"Tap": "TapWater", "KitchenTap": "KitchenTapWater", "ShowerTap": "ShowerWater"}
SEATS = {
    "SofaSeat": "Сесть на диван",
    "DeskSeat": "Сесть за письменный стол",
    "KitchenSeat": "Сесть за кухонный стол",
}
FIXTURES = {
    "KitchenDoor": ("Открыть дверь кухни", "Закрыть дверь кухни"),
    "BathDoor": ("Открыть дверь ванной", "Закрыть дверь ванной"),
    "FridgeDoor": ("Открыть холодильник", "Закрыть холодильник"),
    "DeskLamp": ("Выключить лампу", "Включить лампу"),
    "FloorLamp": ("Осмотреть торшер", "Осмотреть торшер"),
    "LivingSwitch": ("Выключить свет в комнате", "Включить свет в комнате"),
    "KitchenSwitch": ("Выключить свет на кухне", "Включить свет на кухне"),
    "BathSwitch": ("Выключить свет в ванной", "Включить свет в ванной"),
    "Tap": ("Умыться", "Умыться"),
    "KitchenTap": ("Открыть кран", "Закрыть кран"),
    "ShowerTap": ("Включить душ", "Выключить душ"),
    **{tag: (action, action) for tag, action in SEATS.items()},
    "Bed": ("Отдохнуть", "Отдохнуть"),
}


def connect(a, b):
    if not PIN.is_valid(a) or not PIN.is_valid(b) or not PIN.try_create_connection(a, b):
        def name(pin):
            if not PIN.is_valid(pin):
                return "missing pin"
            return f"{BP.get_node_title(PIN.get_owning_node(pin))}.{PIN.get_pin_name(pin)}"
        raise RuntimeError(f"Cannot connect {name(a)} to {name(b)}")


class Graph:
    def __init__(self, blueprint, function=None):
        self.graph = (ue.BlueprintGraphEditor.create_and_edit_function_graph(blueprint, function) if function
                      else ue.BlueprintGraphEditor.get_graph_editor(BP.find_event_graph(blueprint)))
        if self.graph is None:
            raise RuntimeError(f"Could not open Blueprint graph {function or 'EventGraph'}.")
        self.column = 0
        self.row = 0

    def place(self, node):
        if node is None:
            raise RuntimeError("Could not create Blueprint node.")
        BP.set_node_pos(node, ue.IntPoint(self.column * 300, self.row * 360))
        self.column += 1
        return node

    def input(self, node, name, value):
        for pin in BP.list_input_pins(node):
            if str(PIN.get_pin_name(pin)).lower() == name.lower():
                if isinstance(value, str):
                    if isinstance(node, ue.K2Node_PromotableOperator):
                        # Promotable pins can silently discard a literal while still wildcard.
                        literal = "MakeLiteralInt" if value.lstrip("-").isdigit() else "MakeLiteralDouble"
                        connect(self.pure("KismetSystemLibrary", literal, Value=value), pin)
                        return
                    if not PIN.set_pin_value(pin, value):
                        raise RuntimeError(f"Cannot set {name} on {BP.get_node_title(node)} to {value!r}")
                else:
                    connect(value, pin)
                return
        raise RuntimeError(f"No {name} on {BP.get_node_title(node)}")

    def output(self, node, name="ReturnValue"):
        for pin in BP.list_output_pins(node):
            if str(PIN.get_pin_name(pin)).replace(" ", "").lower() == name.replace(" ", "").lower():
                return pin
        raise RuntimeError(f"No {name} on {BP.get_node_title(node)}")

    def call(self, cls, method, /, **params):
        path = cls if cls.startswith("/") else ENGINE + cls
        node = self.graph.add_call_function_node(f"{path}:{method}")
        if node is None:
            raise RuntimeError(f"Cannot create {cls}.{method}")
        self.place(node)
        for name, value in params.items():
            self.input(node, name, value)
        return node

    def pure(self, cls, method, /, **params):
        return self.output(self.call(cls, method, **params))

    def execute(self, previous, cls, method, /, **params):
        node = self.call(cls, method, **params)
        connect(previous, BP.find_execute_pin(node))
        return BP.find_then_pin(node)

    def invoke(self, previous, function):
        node = self.place(self.graph.add_call_function_node(function))
        connect(previous, BP.find_execute_pin(node))
        return BP.find_then_pin(node)

    def singleton_array(self, value):
        actions = self.graph.list_available_nodes([])
        action = next((name for name in actions if name.endswith("|MakeArray")), None)
        if action is None:
            raise RuntimeError("Could not resolve the Blueprint Make Array node.")
        node = self.place(self.graph.create_node_from_name(action, ue.Vector2D(), []))
        item, = BP.list_input_pins(node)
        connect(value, item)
        return self.output(node, "Array")

    def branch(self, previous, condition):
        node = self.place(self.graph.add_branch_node())
        connect(previous, BP.find_execute_pin(node))
        connect(condition, BP.find_condition_pin(node))
        return BP.find_then_pin(node), BP.find_else_pin(node)

    def get(self, name, owner=None, target=None):
        node = self.place(self.graph.add_get_member_variable_node(name, ENGINE + owner if owner else ""))
        if target is not None:
            self.input(node, "self", target)
        return self.output(node, name)

    def set(self, previous, name, value, owner=None, target=None):
        node = self.place(self.graph.add_set_member_variable_node(name, ENGINE + owner if owner else ""))
        if target is not None:
            self.input(node, "self", target)
        self.input(node, name, value)
        connect(previous, BP.find_execute_pin(node))
        return BP.find_then_pin(node)

    def draw(self, previous, text, y, scale=1, color="(R=0.95,G=0.87,B=0.72,A=1)", x="30"):
        return self.execute(previous, "HUD", "DrawText", Text=text, TextColor=color, ScreenX=x,
                            ScreenY=y, Scale=str(scale))

    def panel(self, previous, y, width, height):
        return self.rect(previous, "0", y, width, str(height), "(R=0.012,G=0.017,B=0.025,A=0.88)")

    def document(self, previous, heading, body, controls):
        presentation = "/Script/Dostoevsky.DialoguePresentationLibrary"
        previous = self.execute(previous, presentation, "BeginStyledDialogue")
        for part in (heading, body, controls):
            previous = self.execute(previous, presentation, "AppendStyledDialogue", Text=part)
        return previous

    def rect(self, previous, x, y, width, height, color):
        return self.execute(previous, "HUD", "DrawRect", RectColor=color,
                            ScreenX=x, ScreenY=y, ScreenW=width, ScreenH=height)

    def view(self, previous, pc, target, blend):
        return self.execute(previous, "PlayerController", "SetViewTargetWithBlend", self=pc,
                            NewViewTarget=target, BlendTime=str(blend), BlendFunc="VTBlend_EaseInOut",
                            BlendExp="2.3", bLockOutgoing="true")

    def equals(self, left, value):
        return self.pure(MATH, "EqualEqual_IntInt", A=left, B=str(value))

    def choose(self, yes, no, condition):
        return self.pure(MATH, "SelectFloat", A=yes, B=no, bPickA=condition)

    def and_(self, a, b):
        return self.pure(MATH, "BooleanAND", A=a, B=b)

    def or_(self, a, b):
        return self.pure(MATH, "BooleanOR", A=a, B=b)

    def not_(self, value):
        return self.pure(MATH, "Not_PreBool", A=value)

    def arithmetic(self, op, a, b):
        params = {"A": a, "B": b}
        for pin, value in params.items():
            if isinstance(value, str):
                params[pin] = str(float(value))
        return self.pure(MATH, f"{op}_DoubleDouble", **params)

    def offset(self, value, amount):
        if isinstance(value, str):
            return str(float(value) + amount)
        return self.arithmetic("Add", value, str(amount))

    def string_choice(self, yes, no, condition):
        return self.pure(MATH, "SelectString", A=yes, B=no, bPickA=condition)

    def line(self, index):
        self.row = index
        self.column = 0


def build_gameplay(root, asset_name=None, *, street_door=None):
    street = street_door is not None
    map_name = STREET_MAP if street else MAP_NAME
    door_specs = {**DOORS, "StreetDoor": street_door} if street else DOORS
    fixtures = {**FIXTURES, "Bed": ("Выбрать время сна", "Выбрать время сна"),
                "StreetDoor": ("Открыть дверь на улицу", "Закрыть дверь")} if street else FIXTURES
    documents = INTRO_DOCUMENTS if street else DOCUMENTS
    asset_name = asset_name or ("BP_PrologueStreetHUD" if street else "BP_PrologueApartmentHUD")
    path = f"{root}/{asset_name}"
    blueprint = BP.create_blueprint_asset_with_parent(path, ue.HUD.static_class())
    if not blueprint:
        raise RuntimeError(f"Could not create {path}")
    g = Graph(blueprint)
    variables = [
        ("State", "int", str(START)), ("ClueTitle", "string", ""), ("ClueText", "string", ""),
        ("Stamina", "real", "100"), ("RecoverAt", "real", "0"), ("Exhausted", "bool", "false"),
        ("AtDimas", "bool", "false"), ("Focus", "string", ""), ("JournalOpen", "bool", "false"),
        ("HintUntil", "real", "0"), ("Hint", "string", ""),
    ]
    if street:
        for action in ("Interact", "Journal"):
            variables.extend(((action + "Held", "bool", "false"), (action + "Pressed", "bool", "false")))
    # The shared journal catalog reads these flags on every map.
    variables.extend((tag + "Found", "bool", "false") for tag, _, _ in DOCUMENTS)
    variables.extend((tag + "Toggled", "bool", "false") for tag in (*door_specs, *LIGHTS, *WATER))
    variables.extend((tag + "Progress", "real", "0") for tag in door_specs)
    variables.extend((tag + "Velocity", "real", "0") for tag in door_specs)
    for name, type_name, initial in variables:
        if not g.graph.add_member_variable(name, BP.get_basic_type_by_name(type_name), initial):
            raise RuntimeError(f"Cannot create {name}")
    build_fixture_functions(blueprint, fixtures, door_specs, street)

    event = BP.add_event_override(blueprint, "ReceiveDrawHUD", ue.IntPoint(-350, 0))
    start = BP.find_then_pin(event)
    width = g.output(event, "SizeX")
    height = g.output(event, "SizeY")
    pc = g.pure(GAME, "GetPlayerController", PlayerIndex="0")
    player = g.pure(GAME, "GetPlayerCharacter", PlayerIndex="0")
    active, _ = g.branch(start, g.pure("KismetSystemLibrary", "IsValid", Object=player))
    if street:
        for action, key_name in (("Interact", "E"), ("Journal", "J")):
            held = g.pure("PlayerController", "IsInputKeyDown", self=pc, Key=key_name)
            pressed = g.and_(held, g.not_(g.get(action + "Held")))
            active = g.set(active, action + "Pressed", pressed)
            active = g.set(active, action + "Held", held)
        _, active = g.branch(active, g.pure(WORLD, "IsWorldInteractionModal"))
        active = g.invoke(active, "RecoverAfterSleep")
    state = g.get("State")
    at_dimas = g.get("AtDimas")
    now = g.pure(GAME, "GetTimeSeconds")
    starting, active = g.branch(active, g.equals(state, START))
    initialize(g, starting, pc, now, map_name, street)
    restart = g.pure("PlayerController", "WasInputKeyJustPressed", self=pc, Key="R")
    reset, active = g.branch(active, restart)
    g.execute(reset, GAME, "OpenLevel", LevelName=f"/Game/Prologue/{map_name}")

    g.line(4)
    j = (g.get("JournalPressed") if street else
         g.pure("PlayerController", "WasInputKeyJustPressed", self=pc, Key="J"))
    journal, active = g.branch(active, g.get("JournalOpen"))
    draw_journal(g, journal, pc, j)
    opening, active = g.branch(active, g.and_(j, g.not_(g.pure(STORY, "IsBusy"))))
    opening = g.set(opening, "Focus", "")
    opening = g.set(opening, "JournalOpen", "true")
    lock_controls(g, opening, pc, True)

    if not street:
        g.line(14)
        finish, active = g.branch(active, g.equals(state, END))
        finish = g.panel(finish, "0", width, 5000)
        finish = g.draw(finish, TITLE, "104", 2)
        finish = g.draw(finish, "У подъезда кто-то говорит в рацию. У Димы в кармане ключ от склада.", "166", 1.2)
        g.draw(finish, "Конец тестового эпизода   •   J — журнал   •   R — начать заново", "218")

    key = (g.get("InteractPressed") if street else
           g.pure("PlayerController", "WasInputKeyJustPressed", self=pc, Key="E"))
    width_double = g.pure(MATH, "Conv_IntToDouble", InInt=width)
    height_double = g.pure(MATH, "Conv_IntToDouble", InInt=height)
    center_x = g.arithmetic("Multiply", width_double, "0.5")
    center_y = g.arithmetic("Multiply", height_double, "0.5")
    footer = g.offset(height, -50)

    g.line(15)
    seated, active = g.branch(active, g.equals(state, REPORT))
    seated = g.draw(seated, TITLE + "   /   Квартира Димы   /   1994", "24", 1.15)
    _, report_title, report_body = INTRO_DOCUMENTS[0]
    seated = g.document(seated, report_title, report_body, "[E]  Закончить отчёт и встать    [J]  Журнал")
    rise, _ = g.branch(seated, key)
    g.invoke(rise, "FinishReport")

    g.line(21)
    sitting, active = g.branch(active, g.equals(state, SITTING))
    sitting = g.draw(sitting, "[E]  Встать", g.offset(center_y, -44), 1.15,
                     x=g.offset(center_x, -46))
    sitting = g.draw(sitting, "[J]  Журнал", footer)
    stand, _ = g.branch(sitting, key)
    g.invoke(stand, "StandUp")

    if not street:
        for i, (speaker, dialogue) in enumerate(DIALOGUE, IVAN):
            g.line(16 + i)
            current, active = g.branch(active, g.equals(state, i))
            current = g.document(current, speaker, dialogue,
                                 "[E]  Получить ключ" if i == KEY - 1 else "[E]  Продолжить")
            advance, _ = g.branch(current, key)
            advance = g.set(advance, "State", str(i + 1))
            if i == KEY - 1:
                advance = g.view(advance, pc, player, 0.55)
                advance = lock_controls(g, advance, pc, False)
                show_hint(g, advance, now, "Ключ получен. Вернитесь к входной двери.", 7)

    g.line(24)
    inspecting, active = g.branch(active, g.equals(state, INSPECT))
    inspecting = g.document(inspecting, g.get("ClueTitle"), g.get("ClueText"), "[E]  Закрыть    [J]  Журнал")
    close, _ = g.branch(inspecting, key)
    g.set(close, "State", str(WALK))

    if not street:
        g.line(25)
        letter, active = g.branch(active, g.equals(state, LETTER))
        letter = g.document(letter, CLUES[0][1], CLUES[0][2], "[E]  Обернуться на голос    [J]  Журнал")
        meet, _ = g.branch(letter, key)
        meet = g.set(meet, "State", str(IVAN))
        meet = lock_controls(g, meet, pc, True)
        switch_to_scene_camera(g, meet, pc, 0.55)

    g.line(28)
    _, active = g.branch(active, g.pure(STORY, "IsBusy"))
    active = update_stamina(g, active, pc, player, now)
    active = draw_stamina(g, active, height)
    if street:
        goal = g.pure(STORY, "Objective", Fallback="Выйдите на улицу.")
        goal = g.string_choice("Американский квартал   /   1994", goal, g.pure(WORLD, "IsOutsideApartment"))
    else:
        father_goal = g.string_choice("Вернитесь к входной двери.", "Найдите записку Фёдора.", g.equals(state, KEY))
        goal = g.pure(STORY, "Objective",
                      Fallback=g.string_choice("Осмотрите комнату или выйдите из квартиры.", father_goal, at_dimas))
    active = g.draw(active, goal, "24", 1.12)
    hint = g.string_choice(g.get("Hint"), "", g.pure(MATH, "Less_DoubleDouble", A=now, B=g.get("HintUntil")))
    active = g.draw(active, hint, g.offset(center_y, -95), 1.13)
    active = g.execute(active, "/Script/Dostoevsky.ExplorationHUDLibrary", "PresentExplorationHUD")
    g.line(31)
    cam = g.pure(GAME, "GetPlayerCameraManager", PlayerIndex="0")
    position = g.pure("PlayerCameraManager", "GetCameraLocation", self=cam)
    direction = g.pure("PlayerCameraManager", "GetCameraRotation", self=cam)
    forward = g.pure(MATH, "GetForwardVector", InRot=direction)
    reach = g.pure(MATH, "Multiply_VectorFloat", A=forward, B="260.0")
    end = g.pure(MATH, "Add_VectorVector", A=position, B=reach)
    trace = g.call("KismetSystemLibrary", "LineTraceSingle", Start=position, End=end,
                   TraceChannel="TraceTypeQuery1", ActorsToIgnore=g.singleton_array(player), bIgnoreSelf="true")
    connect(active, BP.find_execute_pin(trace))
    hit = g.output(g.call(GAME, "BreakHitResult", Hit=g.output(trace, "OutHit")), "HitActor")
    pointing, empty = g.branch(BP.find_then_pin(trace), g.pure("KismetSystemLibrary", "IsValid", Object=hit))
    empty = draw_idle_reticle(g, empty, center_x, center_y)
    g.set(empty, "Focus", "")
    render_focus(g, pointing, hit, state, pc, key, center_x, center_y, fixtures, documents, street)

    build_door_tick(g, blueprint, player, door_specs)

    if not BP.compile_blueprint(blueprint):
        raise RuntimeError("Apartment HUD Blueprint failed to compile.")
    assets = ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    if not assets.save_loaded_asset(blueprint):
        raise RuntimeError(f"Could not save {path}.")

    mode = ue.load_asset("/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode")
    if street:
        mode_path = f"{root}/BP_PrologueStreetGameMode"
        mode = ue.load_asset(mode_path) if assets.does_asset_exist(mode_path) else assets.duplicate_loaded_asset(mode, mode_path)
        if not mode:
            raise RuntimeError("Could not create the street game mode.")
    defaults = ue.get_default_object(BP.generated_class(mode))
    hud_class = BP.generated_class(blueprint)
    if defaults.get_editor_property("hud_class") != hud_class:
        defaults.set_editor_property("hud_class", hud_class)
        if not assets.save_loaded_asset(mode):
            raise RuntimeError("Could not set the template game mode's HUD.")
    return BP.generated_class(mode)


def lock_controls(g, previous, pc, locked):
    value = "true" if locked else "false"
    previous = g.execute(previous, "Controller", "SetIgnoreMoveInput", self=pc, bNewMoveInput=value)
    return g.execute(previous, "Controller", "SetIgnoreLookInput", self=pc, bNewLookInput=value)


def show_hint(g, previous, now, message, seconds=4):
    previous = g.set(previous, "Hint", message)
    return g.set(previous, "HintUntil", g.offset(now, seconds))


def switch_to_scene_camera(g, previous, pc, blend):
    camera = g.call(GAME, "GetActorOfClass", ActorClass="/Script/Engine.CameraActor")
    connect(previous, BP.find_execute_pin(camera))
    return g.view(BP.find_then_pin(camera), pc, g.output(camera), blend)


def initialize(g, previous, pc, now, map_name, street):
    previous = g.execute(previous, STORY, "InitializeStory")
    level = g.call(GAME, "GetCurrentLevelName")
    connect(previous, BP.find_execute_pin(level))
    previous = BP.find_then_pin(level)
    at_home = g.pure(STR, "EqualEqual_StrStr", A=g.output(level), B=map_name)
    previous = g.set(previous, "AtDimas", at_home)
    seated, arrived = g.branch(previous, at_home)
    seated = g.set(seated, "State", str(REPORT))
    seated = lock_controls(g, seated, pc, True)
    seated, camera = find_tagged_actor(g, seated, "ReportView")
    camera_found, camera_missing = g.branch(seated, g.pure("KismetSystemLibrary", "IsValid", Object=camera))
    g.view(camera_found, pc, camera, 0)
    switch_to_scene_camera(g, camera_missing, pc, 0)
    if street:
        g.set(arrived, "State", str(WALK))
        return
    g.line(2)
    mode = g.pure(GAME, "GetGameMode")
    options = g.get("OptionsString", "GameModeBase", mode)
    for tag, _, _ in INTRO_DOCUMENTS:
        found = g.pure(GAME, "HasOption", Options=options, InKey=tag)
        arrived = g.set(arrived, tag + "Found", found)
    arrived = g.set(arrived, "State", str(WALK))
    show_hint(g, arrived, now, "Найдите записку Фёдора.", 7)


def draw_journal(g, previous, pc, j):
    closing, browsing = g.branch(previous, j)
    closing = g.set(closing, "JournalOpen", "false")
    lock_controls(g, closing, pc, False)
    # Cursor-driven list; its reader uses the approved common DocumentWindow.
    g.execute(browsing, "/Script/Dostoevsky.JournalUILibrary", "PresentJournal")


def update_stamina(g, previous, pc, player, now):
    movement = g.get("CharacterMovement", "Character", player)
    stamina = g.get("Stamina")
    delta = g.pure(GAME, "GetWorldDeltaSeconds")
    shift = g.or_(*(g.pure("PlayerController", "IsInputKeyDown", self=pc, Key=key)
                    for key in ("LeftShift", "RightShift")))
    on_ground = g.pure("NavMovementComponent", "IsMovingOnGround", self=movement)
    recovered = g.pure(MATH, "GreaterEqual_DoubleDouble", A=stamina, B="25")
    tired = g.and_(g.get("Exhausted"), g.not_(recovered))
    previous = g.set(previous, "Exhausted", tired)
    has_stamina = g.pure(MATH, "Greater_DoubleDouble", A=stamina, B="0")
    can_sprint = g.and_(shift, g.and_(has_stamina, g.not_(tired)))
    previous = g.set(previous, "MaxWalkSpeed", g.choose(SPRINT_SPEED, WALK_SPEED, can_sprint),
                     "CharacterMovementComponent", movement)
    velocity = g.pure("Actor", "GetVelocity", self=player)
    speed = g.pure(MATH, "VSizeXY", A=velocity)
    moving = g.pure(MATH, "Greater_DoubleDouble", A=speed, B="25")
    drain = g.and_(can_sprint, g.and_(on_ground, moving))
    previous = g.set(previous, "RecoverAt", g.choose(g.offset(now, 1), g.get("RecoverAt"), drain))
    ready = g.pure(MATH, "GreaterEqual_DoubleDouble", A=now, B=g.get("RecoverAt"))
    rate = g.choose("-" + SPRINT_COST, g.choose(RECOVERY_RATE, "0", g.and_(on_ground, ready)), drain)
    next_value = g.arithmetic("Add", stamina, g.arithmetic("Multiply", delta, rate))
    previous = g.set(previous, "Stamina", g.pure(MATH, "FClamp", Value=next_value, Min="0", Max="100"))
    depleted = g.pure(MATH, "LessEqual_DoubleDouble", A=stamina, B="0")
    previous = g.set(previous, "Exhausted", g.or_(g.get("Exhausted"), depleted))

    # The stock IA_Jump mapping is cleared so all jump inputs pass this check.
    pressed = g.or_(*(g.pure("PlayerController", "WasInputKeyJustPressed", self=pc, Key=key)
                      for key in ("SpaceBar", "Gamepad_FaceButton_Bottom")))
    enough = g.pure(MATH, "GreaterEqual_DoubleDouble", A=stamina, B=JUMP_COST)
    attempt, idle = g.branch(previous, g.and_(pressed, on_ground))
    can_jump, low = g.branch(attempt, enough)
    show_hint(g, low, now, "Недостаточно выносливости для прыжка.", 2)
    allowed = g.pure("Character", "CanJump", self=player)
    jump, _ = g.branch(can_jump, allowed)
    jump = g.execute(jump, "Character", "Jump", self=player)
    jump = g.set(jump, "Stamina", g.arithmetic("Subtract", stamina, JUMP_COST))
    g.set(jump, "RecoverAt", g.offset(now, 1))
    return idle


def draw_stamina(g, previous, height):
    y = g.offset(height, -81)
    previous = g.draw(previous, "ВЫНОСЛИВОСТЬ", g.offset(height, -103), 0.95)
    previous = g.rect(previous, "30", y, "150", "5", "(R=0.2,G=0.2,B=0.2,A=0.9)")
    width = g.arithmetic("Multiply", g.get("Stamina"), "1.5")
    return g.rect(previous, "30", y, width, "5", "(R=0.91,G=0.66,B=0.3,A=1)")


def draw_idle_reticle(g, previous, center_x, center_y):
    return g.draw(previous, "+", g.offset(center_y, -7), 1, x=g.offset(center_x, -4))


def render_focus(g, previous, hit, state, pc, key, center_x, center_y, fixtures, documents, street):
    entries = INTRO_DOCUMENTS + STORY_OBJECTS + tuple((tag, "", "") for tag in fixtures)
    if street:
        entries += (("StreetPortal", "", ""),)
    else:
        entries += CLUES + (("Exit", "Выйти из квартиры", ""),)
    for index, (tag, title, body) in enumerate(entries):
        g.line(33 + index * 2)
        target = g.pure("Actor", "ActorHasTag", self=hit, Tag=tag)
        if tag == "Exit":
            allowed = g.or_(g.get("AtDimas"), g.equals(state, KEY))
            target = g.and_(target, allowed)
        focused, previous = g.branch(previous, target)
        focused = g.draw(focused, "◆", g.offset(center_y, -11), 1.1,
                         color="(R=1,G=0.67,B=0.28,A=1)", x=g.offset(center_x, -6))
        prompt = "[E]  " + title
        if tag in fixtures:
            action, reverse = fixtures[tag]
            prompt = "[E]  " + action if tag == "Bed" or tag in SEATS else (
                g.string_choice("[E]  " + reverse, "[E]  " + action, g.get(tag + "Toggled"))
            )
        if tag == "StreetPortal":
            prompt = g.pure(NAVIGATION, "PortalPrompt", Hit=hit)
        prompt = g.pure(STORY, "InteractionPrompt", Tag=tag, Fallback=prompt)
        focused = g.draw(focused, prompt, g.offset(center_y, -44), 1.15,
                         x=g.offset(center_x, -106))
        changed = g.pure(STR, "NotEqual_StrStr", A=g.get("Focus"), B=tag)
        first_frame, steady = g.branch(focused, changed)
        first_frame = g.set(first_frame, "Focus", tag)
        first_frame = g.execute(first_frame, GAME, "PlaySound2D", Sound=FOCUS_SOUND, VolumeMultiplier="0.65")
        for path in (first_frame, steady):
            use, _ = g.branch(path, key)
            if tag == "StreetPortal":
                g.execute(use, NAVIGATION, "EnterPortal", Hit=hit)
            else:
                interact(g, use, tag, title, body, pc, fixtures, documents)
    g.set(draw_idle_reticle(g, previous, center_x, center_y), "Focus", "")


def interact(g, previous, tag, title, body, pc, fixtures, documents):
    story = g.call(STORY, "TryInteract", Tag=tag)
    connect(previous, BP.find_execute_pin(story))
    _, previous = g.branch(BP.find_then_pin(story), g.output(story))
    if tag in fixtures:
        g.invoke(previous, "Activate" + tag)
        return
    if tag in {entry[0] for entry in STORY_OBJECTS}:
        return
    if tag == "Exit":
        home, end = g.branch(previous, g.get("AtDimas"))
        options = g.string_choice("Report?Newspaper", "Report", g.get("NewspaperFound"))
        g.execute(home, GAME, "OpenLevel", LevelName=FATHERS_MAP, Options=options)
        end = g.set(end, "State", str(END))
        lock_controls(g, end, pc, True)
        return
    if any(tag == document[0] for document in documents):
        previous = g.set(previous, tag + "Found", "true")
    if tag == "Note":
        g.set(previous, "State", str(LETTER))
    else:
        previous = g.set(previous, "ClueTitle", title)
        previous = g.set(previous, "ClueText", body)
        g.set(previous, "State", str(INSPECT))


def find_tagged_actor(g, previous, tag):
    find = g.call(GAME, "GetAllActorsWithTag", Tag=tag)
    connect(previous, BP.find_execute_pin(find))
    lookup = g.call("KismetArrayLibrary", "Array_Get", TargetArray=g.output(find, "OutActors"), Index="0")
    return BP.find_then_pin(find), g.output(lookup, "Item")


def make_vector(g, values):
    return g.pure(MATH, "MakeVector", **dict(zip(("X", "Y", "Z"), map(str, values))))


def build_fixture_functions(blueprint, fixtures, door_specs, street):
    for tag in fixtures:
        g = Graph(blueprint, "Activate" + tag)
        previous = g.graph.find_graph_entry_pin()
        field = tag + "Toggled"
        if tag in door_specs:
            g.set(previous, field, g.not_(g.get(field)))
        elif tag in LIGHTS or tag in WATER:
            toggle_fixture_group(g, previous, tag, field)
        elif tag in SEATS:
            sit_down(g, previous, tag)
        elif tag == "Bed":
            if street:
                valid, _ = g.branch(previous, g.equals(g.get("State"), WALK))
                g.execute(valid, WORLD, "OpenBedMenu")
            else:
                recover_stamina(g, previous)

    if street:
        g = Graph(blueprint, "RecoverAfterSleep")
        rest = g.call(WORLD, "ConsumeBedRest")
        connect(g.graph.find_graph_entry_pin(), BP.find_execute_pin(rest))
        rested, _ = g.branch(BP.find_then_pin(rest), g.output(rest))
        recover_stamina(g, rested)

    g = Graph(blueprint, "StandUp")
    previous, _ = g.branch(g.graph.find_graph_entry_pin(), g.equals(g.get("State"), SITTING))
    previous = g.set(previous, "State", str(WALK))
    pc = g.pure(GAME, "GetPlayerController", PlayerIndex="0")
    player = g.pure(GAME, "GetPlayerCharacter", PlayerIndex="0")
    previous = g.execute(previous, "Actor", "SetActorHiddenInGame", self=player, bNewHidden="false")
    previous = g.view(previous, pc, player, 0.32)
    lock_controls(g, previous, pc, False)

    g = Graph(blueprint, "FinishReport")
    previous, _ = g.branch(g.graph.find_graph_entry_pin(), g.equals(g.get("State"), REPORT))
    previous = g.set(previous, "ReportFound", "true")
    previous = g.set(previous, "State", str(WALK))
    pc = g.pure(GAME, "GetPlayerController", PlayerIndex="0")
    player = g.pure(GAME, "GetPlayerCharacter", PlayerIndex="0")
    # Keep the newspaper on the desk in view when the player stands up.
    desk_view = g.pure(MATH, "MakeRotator", Roll="0", Pitch=str(DESK_VIEW[1]), Yaw=str(DESK_VIEW[0]))
    previous = g.execute(previous, "Controller", "SetControlRotation", self=pc, NewRotation=desk_view)
    previous = g.view(previous, pc, player, 0.65)
    previous = lock_controls(g, previous, pc, False)
    show_hint(g, previous, g.pure(GAME, "GetTimeSeconds"), "Отчёт добавлен в журнал.", 7)


def recover_stamina(g, previous):
    previous = g.set(previous, "Stamina", "100")
    previous = g.set(previous, "Exhausted", "false")
    show_hint(g, previous, g.pure(GAME, "GetTimeSeconds"), "Выносливость восстановлена.", 3)


def toggle_fixture_group(g, previous, tag, field):
    is_light = tag in LIGHTS
    find = g.call(GAME, "GetAllActorsWithTag", Tag=LIGHTS[tag] if is_light else WATER[tag])
    connect(previous, BP.find_execute_pin(find))
    loop = g.place(g.graph.add_macro_node(FOR_EACH_LOOP))
    all_actors = g.output(find, "OutActors")
    g.input(loop, "Array", all_actors)
    # Macro execution pins can be named Exec rather than the ordinary Execute.
    enter, = (pin for pin in BP.list_input_pins(loop) if str(PIN.get_pin_name(pin)) != "Array")
    connect(BP.find_then_pin(find), enter)
    actor = g.output(loop, "Array Element")
    body = g.output(loop, "Loop Body")
    state = g.get(field)
    if is_light:
        component = g.pure("Actor", "GetComponentByClass", self=actor, ComponentClass="/Script/Engine.LightComponent")
        valid, _ = g.branch(body, g.pure("KismetSystemLibrary", "IsValid", Object=component))
        g.execute(valid, "SceneComponent", "SetVisibility", self=component, bNewVisibility=state)
    else:
        g.execute(body, "Actor", "SetActorHiddenInGame", self=actor, bNewHidden=state)
    completed = g.set(g.output(loop, "Completed"), field, g.not_(state))
    if tag in ROOM_SWITCHES:
        completed, rocker = find_tagged_actor(g, completed, tag + "Rocker")
        completed, _ = g.branch(completed, g.pure("KismetSystemLibrary", "IsValid", Object=rocker))
        orientation = g.pure("Actor", "K2_GetActorRotation", self=rocker)
        angles = g.call(MATH, "BreakRotator", InRot=orientation)
        pitch = g.choose("-12", "12", g.get(field))
        rotation = g.pure(MATH, "MakeRotator", Roll=g.output(angles, "Roll"), Pitch=pitch,
                          Yaw=g.output(angles, "Yaw"))
        g.execute(completed, "Actor", "K2_SetActorRotation", self=rocker, NewRotation=rotation)


def sit_down(g, previous, tag):
    player = g.pure(GAME, "GetPlayerCharacter", PlayerIndex="0")
    valid, _ = g.branch(previous, g.pure("KismetSystemLibrary", "IsValid", Object=player))
    movement = g.get("CharacterMovement", "Character", player)
    ground = g.pure("NavMovementComponent", "IsMovingOnGround", self=movement)
    can_sit = g.and_(g.equals(g.get("State"), WALK), g.and_(g.get("AtDimas"), ground))
    previous, _ = g.branch(valid, can_sit)
    previous, camera = find_tagged_actor(g, previous, tag + "View")
    previous, _ = g.branch(previous, g.pure("KismetSystemLibrary", "IsValid", Object=camera))
    pc = g.pure(GAME, "GetPlayerController", PlayerIndex="0")
    previous = g.set(previous, "State", str(SITTING))
    previous = g.set(previous, "Focus", "")
    previous = g.execute(previous, "MovementComponent", "StopMovementImmediately", self=movement)
    # The seated view can see the avatar's prior position. Hide the standing mesh until exit.
    previous = g.execute(previous, "Actor", "SetActorHiddenInGame", self=player, bNewHidden="true")
    previous = lock_controls(g, previous, pc, True)
    g.view(previous, pc, camera, 0.36)


def build_door_tick(g, blueprint, player, door_specs):
    g.line(83)
    event = BP.add_event_override(blueprint, "ReceiveTick", ue.IntPoint(-350, 83 * 360))
    active, _ = g.branch(BP.find_then_pin(event), g.get("AtDimas"))
    active, _ = g.branch(active, g.pure("KismetSystemLibrary", "IsValid", Object=player))
    actions = g.graph.list_available_nodes([active])
    action = next(name for name in actions if name.endswith("|Sequence"))
    sequence = g.graph.create_node_from_name(action, ue.Vector2D(900, 83 * 360), [])
    if not sequence:
        raise RuntimeError("Cannot create door update sequence.")
    execute = BP.find_execute_pin(sequence)
    if not PIN.is_valid(execute):
        raise RuntimeError("Door update sequence has no execution input.")
    connect(active, execute)
    for _ in range(len(door_specs) - 2):
        if not g.graph.add_node_pin(sequence):
            raise RuntimeError("Cannot add a door update output.")
    delta = g.output(event, "DeltaSeconds")
    for i, (tag, door) in enumerate(door_specs.items()):
        g.line(85 + 3 * i)
        update_door(g, g.output(sequence, f"then_{i}"), tag, door, delta, player)


def update_door(g, previous, tag, door, delta, player):
    closed, hinge, closed_yaw, swing = door
    opening = g.get(tag + "Toggled")
    field = tag + "Progress"
    progress = g.get(field)
    goal = g.choose("1.0", "0.0", opening)
    changing = g.pure(MATH, "NotEqual_DoubleDouble", A=progress, B=goal)
    moving, _ = g.branch(previous, changing)
    moving, slab = find_tagged_actor(g, moving, tag)
    moving, _ = g.branch(moving, g.pure("KismetSystemLibrary", "IsValid", Object=slab))
    velocity = tag + "Velocity"
    step = g.call(WORLD, "StepDoor", Progress=progress, Velocity=g.get(velocity), DeltaSeconds=delta, bOpen=opening)
    connect(moving, BP.find_execute_pin(step))
    proposed = g.output(step)
    angle = g.pure(WORLD, "DoorAngle", Progress=proposed, OpenAngle=str(swing))
    axis = make_vector(g, (0, 0, 1))
    arm = make_vector(g, tuple(center - pivot for center, pivot in zip(closed, hinge)))
    rotated_arm = g.pure(MATH, "RotateAngleAxis", InVect=arm, AngleDeg=angle, Axis=axis)
    location = g.pure(MATH, "Add_VectorVector", A=make_vector(g, hinge), B=rotated_arm)
    yaw = g.offset(angle, closed_yaw)
    rotation = g.pure(MATH, "MakeRotator", Roll="0", Pitch="0", Yaw=yaw)

    # Compare the player with the proposed leaf in its rotated local coordinates.
    player_location = g.pure("Actor", "K2_GetActorLocation", self=player)
    offset = g.pure(MATH, "Subtract_VectorVector", A=player_location, B=location)
    negative_yaw = g.arithmetic("Multiply", yaw, "-1.0")
    local = g.pure(MATH, "RotateAngleAxis", InVect=offset, AngleDeg=negative_yaw, Axis=axis)
    position = g.call(MATH, "BreakVector", InVec=local)
    capsule = g.get("CapsuleComponent", "Character", player)
    radius = g.pure("CapsuleComponent", "GetScaledCapsuleRadius", self=capsule)
    clearance = []
    for axis_name, size in zip(("X", "Y"), DOOR_FOOTPRINTS.get(tag, (15, 109))):
        distance = g.pure(MATH, "Abs", A=g.output(position, axis_name))
        clearance.append(g.pure(MATH, "Greater_DoubleDouble", A=distance, B=g.offset(radius, size / 2 + 1)))
    move, blocked = g.branch(BP.find_then_pin(step), g.or_(*clearance))
    blocked = g.set(blocked, velocity, "0")
    show_hint(g, blocked, g.pure(GAME, "GetTimeSeconds"), "Отойдите от дверцы.", 0.5)
    move = g.execute(move, "Actor", "K2_SetActorLocationAndRotation", self=slab,
                     NewLocation=location, NewRotation=rotation)
    move = g.set(move, velocity, g.output(step, "NewVelocity"))
    g.set(move, field, proposed)
