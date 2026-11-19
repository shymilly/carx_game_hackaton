# Dostoevsky — Echoes of the Past

Сюжетная игра от первого лица на Unreal Engine 5.8. Текущий прототип включает квартиру Димы и соседний квартал в 1994 году. Маршрут и управление описаны в [инструкции к тестовой сборке](TEST-BUILD.md).

## Получение проекта

```powershell
git clone https://github.com/shymilly/carx_game_hackaton.git
cd carx_game_hackaton
```

Если проект уже склонирован, закройте Unreal Editor и получите изменения в своей рабочей ветке. Для чистой локальной main:

```powershell
git switch main
git pull --ff-only
```

Сохраните собственные незакоммиченные изменения до переключения веток. Не заменяйте целиком папку Content чужой копией проекта.

## Первая сборка после получения изменений

Теперь проект содержит C++. Перед открытием обновлённых Blueprint нужно собрать модуль: иначе Unreal не найдёт их нативные функции и классы.

Нужны Unreal Engine 5.8, Visual Studio Build Tools с MSVC x64/x86, Windows SDK и .NET Framework SDK/Targeting Pack. Проверенная конфигурация: UE 5.8.4, MSVC 14.52, Windows SDK 10.0.26100.0, .NET Framework SDK 4.8. Нужен SDK, одного .NET Runtime недостаточно.

Из корня репозитория:

```powershell
powershell -File Scripts/BuildEditor.ps1 -EngineRoot "D:\UE_5.8"
powershell -File Scripts/OpenEditor.ps1 -EngineRoot "D:\UE_5.8"
```

Укажите собственный путь к движку. `OpenEditor.ps1` открывает именно этот `.uproject` выбранным движком, чтобы не создавать новые копии при выборе версии. После изменений C++ закрывайте редактор перед полной сборкой. Скрипт сборки отключает UBA; скрипт открытия отключает автоматический запуск Live Coding.

Для генерации настроек VS Code:

```powershell
powershell -File Scripts/BuildEditor.ps1 -EngineRoot "D:\UE_5.8" -GenerateVSCode
```

## Утверждённый интерфейс

Все следующие диалоги и окна чтения должны использовать **текущее общее оформление**: жёлтая панель внизу слева, оранжевая пунктирная рамка со скруглениями, чёрный текст, SOUTHGHETTO для имени/названия объекта и Cascadia Code Light для текста. Меняем содержимое и события, сохраняя дизайн.

- [Спецификация интерфейса](Docs/DialogueStyle.md)
- [Управление и значок журнала после вставания](Docs/ExplorationHUD.md)
- [Журнал с выбором записей мышью](Docs/JournalUI.md)
- [Сценарий квартиры Димы](Docs/DimaApartmentScenario.md)
- [Брайтон-Бич: магазин, третий этаж, дождь и HUD](Docs/BrightonPresentation.md)
- [Квартал, персонажи и поезд](Docs/CityLife.md)
- [Подключение текста, озвучки и переходов между картами](Docs/NarrativeIntegration.md)
- [Постоянные правила разработки](AGENTS.md)

Для новых взаимодействий создавайте Data Asset `InteractionDocument`, назначайте его в `NarrativeInteractionComponent` и вызывайте `ActivateInteraction`. Общий `DocumentWindow` покажет текст в утверждённом стиле.

Два существующих HUD Blueprint уже обновлены: 13 старых блоков отрисовки перенаправлены в общее окно. В них продолжение/закрытие работает через прежнюю клавишу E. В новых модальных окнах доступны кнопка закрытия, Escape и прокрутка. Повторно запускать миграцию `ApplyDialogueStyle.py` для получения уже обновлённых HUD не требуется.

Шрифты включены в `Content/UI/Dialogue/Fonts` и в настройки упаковки. Для текущего C++-рендеринга дополнительно импортировать их как Font assets не требуется.

## Проверки и состояние работ

Полная сборка модуля и компиляция обоих обновлённых HUD прошли успешно. Краш при рисовании пунктирного контура исправлен; `CheckDialoguePaint.py` проверяет настоящий OnPaint на пяти размерах с NullRenderer. Запуск проверки из корня проекта:

```powershell
& "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "$PWD\Dostoevsky.uproject" -run=pythonscript "-script=$PWD\Scripts\CheckDialoguePaint.py" -LiveCoding=false -unattended -nullrhi -nosplash -nosound
```

Первый акт проходит через восемь отдельных карт в `Content/Locations`. Стартовая карта — `L_DimaApartmentInterior`. Нажатие E на выходной двери показывает загрузочный экран и загружает улицу. Доступ к бару, участку и квартире Фёдора открывается по сценарию. Время, журнал, характеристики и прогресс сохраняются между загрузками. [Маршрут и механики первого акта](Docs/ActOne.md). [Карты, двери и проверки](Docs/SeparateLocations.md).

## Совместная работа

Работайте над задачами в отдельных ветках и согласовывайте правки одних и тех же `.uasset` / `.umap`: обычный текстовый merge к ним неприменим. Изменённые HUD и соответствующий C++-код передавайте одним коммитом. Движок, сборки, кэш, локальные резервные копии и IDE-файлы в репозиторий не входят.

Сценарий квартиры Димы, реплики, звуки и условия звонка: [Docs/DimaApartmentScenario.md](Docs/DimaApartmentScenario.md).

Доработка улицы, завода, кириллических вывесок, столкновений трафика и безопасных дверей: [Docs/StreetRefinement.md](Docs/StreetRefinement.md).

Библиотека моделей и текстур с рабочего стола: **Content/ImportedAssets**. [Расположение и использование](Docs/AssetLibrary.md).

## Оформление улицы

[Доработка улицы: материалы, ассеты и звук машин](Docs/StreetArtPass.md) — пропорции домов, асфальт, BEACON, деревья, постеры и завод.
