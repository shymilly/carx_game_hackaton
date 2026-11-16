#include "StreetNavigation.h"

#include "Components/BoxComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/TargetPoint.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "NarrativeSubsystem.h"

namespace
{
UNarrativeSubsystem* Narrative(APlayerController* Player)
{
    UGameInstance* Instance = Player ? Player->GetGameInstance() : nullptr;
    return Instance ? Instance->GetSubsystem<UNarrativeSubsystem>() : nullptr;
}
}

AStreetPortal::AStreetPortal()
{
    FocusBox = CreateDefaultSubobject<UBoxComponent>(TEXT("DoorFocus"));
    SetRootComponent(FocusBox);
    FocusBox->SetBoxExtent(FVector(12, 70, 100));
    FocusBox->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    FocusBox->SetCollisionResponseToAllChannels(ECR_Ignore);
    FocusBox->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    FocusBox->SetGenerateOverlapEvents(false);
    FocusBox->SetCanEverAffectNavigation(false);
    Tags.Add(TEXT("StreetPortal"));
}

bool AStreetPortal::Use(APlayerController* Player) const
{
    UNarrativeSubsystem* UI = Narrative(Player);
    const APawn* Pawn = Player ? Player->GetPawn() : nullptr;
    if (!UI || !Pawn || Player->IsMoveInputIgnored() || Player->GetViewTarget() != Pawn ||
        FVector::DistSquared(Pawn->GetActorLocation(), GetActorLocation()) > FMath::Square(285.0)) return false;
    if (!DestinationMap.IsNull()) return UI->TravelToStreet(DestinationMap, DestinationTitle, DestinationPhoto, DestinationSpawn);
    if (Arrival) return UI->ShowLocationCard(Player, DestinationTitle, DestinationPhoto, Arrival);
    return ClosedNotice && UI->ShowDocument(Player, ClosedNotice, nullptr);
}

AStreetDoorThreshold::AStreetDoorThreshold()
{
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Threshold"));
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = .045f;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
}

void AStreetDoorThreshold::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    APlayerController* Player = UGameplayStatics::GetPlayerController(this, 0);
    APawn* Pawn = Player ? Player->GetPawn() : nullptr;
    if (!Pawn || !Player->IsLocalController() || Player->GetViewTarget() != Pawn) return;
    if (LastPawn.Get() != Pawn)
    {
        LastPawn = Pawn;
        Side = 0;
    }
    const FVector Door = GetActorTransform().InverseTransformPosition(Pawn->GetActorLocation());
    if (FMath::Abs(Door.X) > 180 || FMath::Abs(Door.Y) > 65 || FMath::Abs(Door.Z) > 125)
    {
        Side = 0;
        return;
    }
    const int8 NewSide = Door.X > 26 ? 1 : (Door.X < -26 ? -1 : 0);
    if (!NewSide) return;
    const bool bCrossed = Side && Side != NewSide;
    Side = NewSide;
    UNarrativeSubsystem* UI = Narrative(Player);
    if (bCrossed && UI)
    {
        const bool bOutside = NewSide > 0;
        const FText Title = bOutside ? NSLOCTEXT("Dostoevsky", "StreetArrival", "Улица Нептун")
                                     : NSLOCTEXT("Dostoevsky", "ApartmentArrival", "Квартира Димы");
        UI->ShowLocationCard(Player, Title, bOutside ? StreetPhoto.Get() : ApartmentPhoto.Get());
    }
}

FString UStreetNavigationLibrary::PortalPrompt(AActor* Hit)
{
    const AStreetPortal* Portal = Cast<AStreetPortal>(Hit);
    return Portal ? FString::Printf(TEXT("[E]  %s"), *Portal->Prompt.ToString()) : FString();
}

bool UStreetNavigationLibrary::EnterPortal(AHUD* HUD, AActor* Hit)
{
    const AStreetPortal* Portal = Cast<AStreetPortal>(Hit);
    return HUD && Portal && Portal->Use(HUD->GetOwningPlayerController());
}
