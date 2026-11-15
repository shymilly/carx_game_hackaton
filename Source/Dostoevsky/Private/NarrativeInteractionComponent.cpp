#include "NarrativeInteractionComponent.h"
#include "NarrativeSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

bool UNarrativeInteractionComponent::ActivateInteraction(APlayerController* Player)
{
    if (!Player || !Player->IsLocalController() || !GetWorld()) return false;
    UNarrativeSubsystem* Narrative = GetWorld()->GetGameInstance()->GetSubsystem<UNarrativeSubsystem>();
    if (bExitToStreet) return Narrative->TravelToStreet(StreetMap, StreetTitle);
    return Narrative->ShowDocument(Player, Document, WindowClass);
}
