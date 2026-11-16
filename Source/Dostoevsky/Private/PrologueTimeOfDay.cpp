#include "PrologueTimeOfDay.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/GameInstance.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "InteractionDocument.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "NarrativeSubsystem.h"

namespace
{
constexpr float LieSeconds = 1.35f;
constexpr float FadeSeconds = .45f;
constexpr float WakeAt = 2.19f;
constexpr float RiseSeconds = 1.24f;
constexpr float SleepHours[] = {6, 12, 18, 0};

double EaseMotion(double Position)
{
    const double T = FMath::Clamp(Position, 0.0, 1.0);
    return T * T * T * (T * (6.0 * T - 15.0) + 10.0);
}

struct FStreetLightKey
{
    FLinearColor Horizon;
    FLinearColor Zenith;
    FLinearColor Direct;
    FLinearColor Ambient;
    float Illuminance;
    float SkyIntensity;
    float Pitch;
    float Yaw;
    float SunDisc;
    float WindowGlow;
};

const FStreetLightKey StreetKeys[] = {
    {{.032f,.067f,.14f}, {.007f,.015f,.047f}, {.39f,.54f,.88f}, {.49f,.66f,1}, .30f, .31f, -27, 25, 0, 1},
    {{.60f,.35f,.24f}, {.12f,.29f,.57f}, {1,.61f,.39f}, {1,.82f,.68f}, 2.15f, .71f, -11, 182, .52f, .20f},
    {{.60f,.73f,.91f}, {.106f,.31f,.67f}, {1,.94f,.82f}, {.85f,.91f,1}, 4.1f, .97f, -60, 252, .78f, 0},
    {{.58f,.24f,.115f}, {.059f,.15f,.369f}, {1,.54f,.27f}, {.97f,.75f,.69f}, 1.95f, .69f, -13, 334, .65f, .47f},
};

APlayerController* OwningPlayer(AHUD* HUD)
{
    return HUD ? HUD->GetOwningPlayerController() : nullptr;
}

APrologueTimeOfDay* TimeController(AHUD* HUD)
{
    UWorld* World = HUD ? HUD->GetWorld() : nullptr;
    if (!World) return nullptr;
    for (TActorIterator<APrologueTimeOfDay> It(World); It; ++It) return *It;
    return nullptr;
}

UNarrativeSubsystem* Narrative(APlayerController* Player)
{
    UGameInstance* Instance = Player ? Player->GetGameInstance() : nullptr;
    return Instance ? Instance->GetSubsystem<UNarrativeSubsystem>() : nullptr;
}
}

APrologueTimeOfDay::APrologueTimeOfDay()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
}

void APrologueTimeOfDay::BeginPlay()
{
    Super::BeginPlay();
    WorldHours = FMath::Clamp(OpeningHour, 0.f, 23.999f);
    if (SkyDome) SkyMaterial = SkyDome->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0);
    if (HourHand) HourHandBase = HourHand->GetActorQuat();
    if (MinuteHand) MinuteHandBase = MinuteHand->GetActorQuat();
    for (ALight* Light : StreetLights)
        StreetLightIntensity.Add(Light ? Light->GetLightComponent()->Intensity : 0.f);
    ApplyTime();
}

void APrologueTimeOfDay::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (SleepPlayer.IsValid())
    {
        AdvanceSleep(DeltaSeconds);
        return;
    }
    // The time shown in the menu stays stable while the player chooses.
    if (const UNarrativeSubsystem* UI = Narrative(MenuPlayer.Get()); UI && UI->IsDocumentOpen()) return;
    WorldHours += DeltaSeconds * ClockRate / 3600.0;
    LightUpdateRemaining -= DeltaSeconds;
    if (LightUpdateRemaining <= 0.f)
    {
        ApplyTime();
        LightUpdateRemaining = .3f;
    }
}

float APrologueTimeOfDay::GetClockHour() const { return static_cast<float>(FMath::Fmod(WorldHours, 24.0)); }
int32 APrologueTimeOfDay::GetDayIndex() const { return FMath::FloorToInt(WorldHours / 24.0); }

void APrologueTimeOfDay::ApplyTime()
{
    const float Hour = GetClockHour();
    const int32 Segment = FMath::Clamp(FMath::FloorToInt(Hour / 6.f), 0, 3);
    const float Weight = FMath::SmoothStep(0.f, 1.f, Hour / 6.f - Segment);
    const FStreetLightKey& A = StreetKeys[Segment];
    const FStreetLightKey& B = StreetKeys[(Segment + 1) % UE_ARRAY_COUNT(StreetKeys)];
    const FRotator Rotation(FMath::Lerp(A.Pitch, B.Pitch, Weight),
        A.Yaw + FMath::FindDeltaAngleDegrees(A.Yaw, B.Yaw) * Weight, 0.f);
    if (Sun)
    {
        Sun->SetActorRotation(Rotation);
        ULightComponent* Light = Sun->GetLightComponent();
        Light->SetIntensity(FMath::Lerp(A.Illuminance, B.Illuminance, Weight));
        Light->SetLightColor(FMath::Lerp(A.Direct, B.Direct, Weight));
    }
    if (SkyMaterial)
    {
        SkyMaterial->SetVectorParameterValue(TEXT("HorizonTint"), FMath::Lerp(A.Horizon, B.Horizon, Weight));
        SkyMaterial->SetVectorParameterValue(TEXT("ZenithTint"), FMath::Lerp(A.Zenith, B.Zenith, Weight));
        SkyMaterial->SetVectorParameterValue(TEXT("SolarTint"), FMath::Lerp(A.Direct, B.Direct, Weight));
        SkyMaterial->SetVectorParameterValue(TEXT("SunDirection"), FLinearColor(-Rotation.Vector()));
        SkyMaterial->SetScalarParameterValue(TEXT("SunGlow"), FMath::Lerp(A.SunDisc, B.SunDisc, Weight));
    }
    if (AmbientSky)
    {
        USkyLightComponent* Light = AmbientSky->GetLightComponent();
        Light->SetLightColor(FMath::Lerp(A.Ambient, B.Ambient, Weight));
        Light->SetIntensity(FMath::Lerp(A.SkyIntensity, B.SkyIntensity, Weight));
    }
    const float WindowGlow = FMath::Lerp(A.WindowGlow, B.WindowGlow, Weight);
    for (int32 Index = 0; Index < StreetLights.Num(); ++Index)
        if (ALight* Light = StreetLights[Index])
            Light->GetLightComponent()->SetIntensity(StreetLightIntensity[Index] * WindowGlow);
    if (StreetLightParameters)
        GetWorld()->GetParameterCollectionInstance(StreetLightParameters)->SetScalarParameterValue(TEXT("StreetGlow"), WindowGlow);

    if (HourHand) HourHand->SetActorRotation(FQuat(FVector::YAxisVector, -Hour / 12.0 * UE_TWO_PI) * HourHandBase);
    if (MinuteHand) MinuteHand->SetActorRotation(FQuat(FVector::YAxisVector, -FMath::Frac(Hour) * UE_TWO_PI) * MinuteHandBase);
}

bool APrologueTimeOfDay::OpenSleepMenu(APlayerController* Player)
{
    if (!Player || !PillowView || IsAsleep()) return false;
    ACharacter* Character = Cast<ACharacter>(Player->GetPawn());
    if (!Character || !Character->GetCharacterMovement()->IsMovingOnGround() ||
        FVector::DistSquared2D(PillowView->GetActorLocation(), Character->GetActorLocation()) > FMath::Square(360.0)) return false;
    UNarrativeSubsystem* UI = Narrative(Player);
    if (!UI || UI->IsDocumentOpen()) return false;
    UInteractionDocument* Document = NewObject<UInteractionDocument>(UI);
    Document->Title = NSLOCTEXT("Dostoevsky", "SleepTitle", "Сон");
    const int32 Minutes = FMath::FloorToInt(GetClockHour() * 60);
    Document->Body = FText::Format(NSLOCTEXT("Dostoevsky", "SleepNow", "Сейчас {0}"),
        FText::FromString(FString::Printf(TEXT("%02d:%02d"), Minutes / 60, Minutes % 60)));
    Document->CloseLabel = NSLOCTEXT("Dostoevsky", "SleepCancel", "Отмена · Esc");
    TArray<FText> Choices = {
        NSLOCTEXT("Dostoevsky", "SleepMorning", "Поспать до утра · 06:00"),
        NSLOCTEXT("Dostoevsky", "SleepNoon", "Поспать до дня · 12:00"),
        NSLOCTEXT("Dostoevsky", "SleepEvening", "Поспать до вечера · 18:00"),
        NSLOCTEXT("Dostoevsky", "SleepNight", "Поспать до ночи · 00:00"),
    };
    MenuPlayer = Player;
    return UI->ShowChoices(Player, Document, MoveTemp(Choices), FDocumentChoice::CreateUObject(this, &ThisClass::BeginSleep));
}

void APrologueTimeOfDay::BeginSleep(int32 Choice)
{
    APlayerController* Player = MenuPlayer.Get();
    if (!Player || !PillowView || IsAsleep() || Choice < 0 || Choice >= UE_ARRAY_COUNT(SleepHours)) return;
    APawn* Pawn = Player->GetPawn();
    APlayerCameraManager* View = Player->PlayerCameraManager;
    UNarrativeSubsystem* UI = Narrative(Player);
    if (!Pawn || !View || !UI) return;
    UI->CloseDocument();
    MenuPlayer.Reset();

    StartView = FTransform(View->GetCameraRotation(), View->GetCameraLocation());
    EndView = PillowView->GetActorTransform();
    FActorSpawnParameters Parameters;
    Parameters.ObjectFlags |= RF_Transient;
    SleepCamera = GetWorld()->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), StartView, Parameters);
    if (!SleepCamera) return;
    StartFov = View->GetFOVAngle();
    EndFov = PillowView->GetCameraComponent()->FieldOfView;
    SleepCamera->GetCameraComponent()->SetFieldOfView(StartFov);
    SleepPawn = Pawn;
    SleepPlayer = Player;
    bPawnWasHidden = Pawn->IsHidden();
    Pawn->SetActorHiddenInGame(true);
    if (ACharacter* Character = Cast<ACharacter>(Pawn)) Character->GetCharacterMovement()->StopMovementImmediately();
    Player->SetIgnoreMoveInput(true);
    Player->SetIgnoreLookInput(true);
    Player->SetViewTarget(SleepCamera);

    WakeHours = GetDayIndex() * 24.0 + SleepHours[Choice];
    if (WakeHours <= WorldHours + 0.0001) WakeHours += 24.0;
    SleepElapsed = 0.f;
    bFading = bWokeUp = false;
}

void APrologueTimeOfDay::AdvanceSleep(float DeltaSeconds)
{
    APlayerController* Player = SleepPlayer.Get();
    if (!SleepCamera || !Player || !Player->PlayerCameraManager || !SleepPawn.IsValid())
    {
        FinishSleep(false);
        return;
    }
    SleepElapsed += DeltaSeconds;
    if (SleepElapsed >= WakeAt + RiseSeconds)
    {
        FinishSleep(true);
        return;
    }
    APlayerCameraManager* View = Player->PlayerCameraManager;
    if (!bFading && SleepElapsed >= LieSeconds - .12f)
    {
        View->StartCameraFade(0, 1, FadeSeconds, FLinearColor::Black, false, true);
        bFading = true;
    }
    // Commit the selected time while the camera is completely black.
    if (!bWokeUp && SleepElapsed >= WakeAt)
    {
        WorldHours = WakeHours;
        ApplyTime();
        View->StartCameraFade(1, 0, .65f, FLinearColor::Black, false, false);
        bWokeUp = true;
    }
    const float LinearAlpha = bWokeUp ? 1.f - (SleepElapsed - WakeAt) / RiseSeconds : SleepElapsed / LieSeconds;
    const double Alpha = EaseMotion(LinearAlpha);
    const FVector CurveLift(0, 0, 92.0 * Alpha * (1.0 - Alpha));
    SleepCamera->SetActorLocationAndRotation(FMath::Lerp(StartView.GetLocation(), EndView.GetLocation(), Alpha) + CurveLift,
        FQuat::Slerp(StartView.GetRotation(), EndView.GetRotation(), Alpha));
    SleepCamera->GetCameraComponent()->SetFieldOfView(FMath::Lerp(StartFov, EndFov, static_cast<float>(Alpha)));
}

void APrologueTimeOfDay::FinishSleep(bool bRestored)
{
    if (APawn* Pawn = SleepPawn.Get()) Pawn->SetActorHiddenInGame(bPawnWasHidden);
    if (APlayerController* Player = SleepPlayer.Get())
    {
        if (APawn* Pawn = Player->GetPawn()) Player->SetViewTarget(Pawn);
        if (Player->PlayerCameraManager) Player->PlayerCameraManager->StopCameraFade();
        Player->SetIgnoreMoveInput(false);
        Player->SetIgnoreLookInput(false);
    }
    if (SleepCamera) SleepCamera->Destroy();
    SleepCamera = nullptr;
    SleepPlayer.Reset();
    SleepPawn.Reset();
    bRested = bRestored;
}

bool APrologueTimeOfDay::ConsumeRestRecovery()
{
    const bool bResult = bRested;
    bRested = false;
    return bResult;
}

void APrologueTimeOfDay::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (IsAsleep()) FinishSleep(false);
    if (UNarrativeSubsystem* UI = Narrative(MenuPlayer.Get())) UI->CloseDocument();
    Super::EndPlay(EndPlayReason);
}

void UPrologueWorldLibrary::OpenBedMenu(AHUD* HUD)
{
    if (APrologueTimeOfDay* Time = TimeController(HUD)) Time->OpenSleepMenu(OwningPlayer(HUD));
}

bool UPrologueWorldLibrary::IsWorldInteractionModal(AHUD* HUD)
{
    if (const UNarrativeSubsystem* UI = Narrative(OwningPlayer(HUD)); UI && UI->IsDocumentOpen()) return true;
    const APrologueTimeOfDay* Time = TimeController(HUD);
    return Time && Time->IsAsleep();
}

bool UPrologueWorldLibrary::ConsumeBedRest(AHUD* HUD)
{
    APrologueTimeOfDay* Time = TimeController(HUD);
    return Time && Time->ConsumeRestRecovery();
}

bool UPrologueWorldLibrary::IsOutsideApartment(AHUD* HUD)
{
    const APlayerController* Player = OwningPlayer(HUD);
    const APawn* Pawn = Player ? Player->GetPawn() : nullptr;
    if (!Pawn) return false;
    const FVector Location = Pawn->GetActorLocation();
    return Location.Y < -460 || Location.Y > 457 || Location.X < -772 || Location.X > 807 ||
        (Location.X < -397 && Location.Y < 33) || (Location.X > 397 && Location.Y > 117);
}

double UPrologueWorldLibrary::StepDoor(double Progress, double Velocity, double DeltaSeconds, bool bOpen, double& NewVelocity)
{
    // Bound angular travel per update so an overloaded frame cannot step across the player's capsule.
    const double Step = FMath::Clamp(DeltaSeconds, 0.0, .025);
    const double TargetSpeed = bOpen ? 1.58 : -1.34;
    NewVelocity = Velocity + FMath::Clamp(TargetSpeed - Velocity, -10.0 * Step, 10.0 * Step);
    const double Next = FMath::Clamp(Progress + NewVelocity * Step, 0.0, 1.0);
    if (Next == (bOpen ? 1.0 : 0.0)) NewVelocity = 0.0;
    return Next;
}

double UPrologueWorldLibrary::DoorAngle(double Progress, double OpenAngle)
{
    return EaseMotion(Progress) * OpenAngle;
}

AStreetMeshInstances::AStreetMeshInstances()
{
    Instances = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("StreetInstances"));
    SetRootComponent(Instances);
    Instances->SetMobility(EComponentMobility::Static);
    Instances->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Instances->SetGenerateOverlapEvents(false);
}
