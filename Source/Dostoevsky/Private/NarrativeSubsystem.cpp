#include "NarrativeSubsystem.h"
#include "DoorOpeningAudio.h"
#include "DimaApartmentStory.h"
#include "LocationTravel.h"
#include "HAL/PlatformTime.h"
#include "DocumentWindow.h"
#include "InteractionDocument.h"
#include "Components/AudioComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Engine/TargetPoint.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/PackageName.h"
#include "MoviePlayer.h"
#include "Styling/CoreStyle.h"
#include "TimerManager.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/StrongObjectPtr.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
class SLocationCard final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SLocationCard) : _Photo(nullptr), _Loading(false) {}
        SLATE_ARGUMENT(UTexture2D*, Photo)
        SLATE_ARGUMENT(FText, Title)
        SLATE_ARGUMENT(bool, Loading)
    SLATE_END_ARGS()

    void Construct(const FArguments& Args)
    {
        Photo.Reset(Args._Photo);
        if (Photo.IsValid())
        {
            Brush.SetResourceObject(Photo.Get());
            Brush.ImageSize = FVector2D(Photo->GetSizeX(), Photo->GetSizeY());
            Brush.DrawAs = ESlateBrushDrawType::Image;
        }
        ChildSlot
        [
            SNew(SBorder).Padding(0).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.012f, 0.014f, 0.016f))[SNew(SOverlay)
                + SOverlay::Slot()
                [
                    SNew(SScaleBox).Stretch(EStretch::ScaleToFill)
                    [ SNew(SImage).Image(&Brush).Visibility(Photo.IsValid() ? EVisibility::Visible : EVisibility::Collapsed) ]
                ]
                + SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom).Padding(42, 0, 42, 44)
                [
                    SNew(SBorder).Padding(FMargin(16, 10))
                    .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                    .BorderBackgroundColor(FLinearColor(0.012f, 0.014f, 0.016f, .87f))
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [ SNew(STextBlock).Text(Args._Title).Font(FCoreStyle::GetDefaultFontStyle("Bold", 24)) ]
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(STextBlock).Text(NSLOCTEXT("Dostoevsky", "Loading", "Загрузка…"))
                            .Visibility(Args._Loading ? EVisibility::Visible : EVisibility::Collapsed)
                        ]
                    ]
                ]]
        ];
    }

private:
    FSlateBrush Brush;
    TStrongObjectPtr<UTexture2D> Photo;
};
}

void UNarrativeSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    MapLoadedHandle = FCoreUObjectDelegates::PostLoadMapWithWorld.AddUObject(this, &ThisClass::MapLoaded);
    if (GEngine) TravelFailureHandle = GEngine->OnTravelFailure().AddUObject(this, &ThisClass::TravelFailed);
}

void UNarrativeSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(TravelBegin);
    FinishLocationCard();
    CloseDocument();
    StopAmbience(0);
    FCoreUObjectDelegates::PostLoadMapWithWorld.Remove(MapLoadedHandle);
    if (GEngine) GEngine->OnTravelFailure().Remove(TravelFailureHandle);
    Super::Deinitialize();
}

bool UNarrativeSubsystem::ShowDocument(APlayerController* Player, UInteractionDocument* Document, TSubclassOf<UDocumentWindow> WindowClass)
{
    return OpenDocument(Player, Document, WindowClass, {}, {});
}

bool UNarrativeSubsystem::ShowChoices(APlayerController* Player, UInteractionDocument* Document,
    TArray<FText> Choices, FDocumentChoice Selection)
{
    return OpenDocument(Player, Document, UDocumentWindow::StaticClass(), MoveTemp(Choices), MoveTemp(Selection));
}

bool UNarrativeSubsystem::ShowStoryPage(APlayerController* Player, UInteractionDocument* Document, FSimpleDelegate Continue)
{
    return OpenDocument(Player,Document,UDimaStoryDialogueWindow::StaticClass(),{},{},false,MoveTemp(Continue));
}

bool UNarrativeSubsystem::ShowRequiredChoices(APlayerController* Player,UInteractionDocument* Document,
    TArray<FText> Choices,FDocumentChoice Selection)
{
    return OpenDocument(Player,Document,UDocumentWindow::StaticClass(),MoveTemp(Choices),MoveTemp(Selection),true);
}

bool UNarrativeSubsystem::ShowChallenge(APlayerController* Player,UInteractionDocument* Document,
    FDocumentKeyInput Input,FSimpleDelegate Cancel)
{
    return OpenDocument(Player,Document,UDocumentWindow::StaticClass(),{},{},false,MoveTemp(Cancel),MoveTemp(Input));
}

bool UNarrativeSubsystem::OpenDocument(APlayerController* Player, UInteractionDocument* Document,
    TSubclassOf<UDocumentWindow> WindowClass, TArray<FText> Choices, FDocumentChoice Selection,
    bool bRequireChoice, FSimpleDelegate Continue, FDocumentKeyInput Input)
{
    if (!Player || !Player->IsLocalController() || !Document || IsLocationTransitionActive()) return false;
    CloseDocument();
    Window = CreateWidget<UDocumentWindow>(Player, WindowClass.Get() ? WindowClass.Get() : UDocumentWindow::StaticClass());
    if (!Window) return false;
    CurrentDocument = Document;
    Window->Document = Document;
    Window->bRequireChoice = bRequireChoice;
    Window->OnCloseRequested = MoveTemp(Continue);
    Window->OnKeyInput = MoveTemp(Input);
    Window->SetChoices(MoveTemp(Choices), MoveTemp(Selection));
    Window->AddToViewport(50);
    ModalPlayer = Player;
    bPreviousCursor = Player->bShowMouseCursor;
    Player->SetIgnoreMoveInput(true);
    Player->SetIgnoreLookInput(true);
    if (APawn* Pawn = Player->GetPawn())
        if (UPawnMovementComponent* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
    Player->bShowMouseCursor = true;
    FInputModeUIOnly Mode;
    Mode.SetWidgetToFocus(Window->TakeWidget());
    Player->SetInputMode(Mode);
    Window->SetKeyboardFocus();
    if (Document->OpenSound) UGameplayStatics::PlaySound2D(Player, Document->OpenSound);
    if (Document->Voice) Voice = UGameplayStatics::SpawnSound2D(Player, Document->Voice);
    return true;
}

void UNarrativeSubsystem::CloseDocument()
{
    if (Voice) { Voice->Stop(); Voice = nullptr; }
    if (Window)
    {
        Window->OnCloseRequested.Unbind();
        Window->OnKeyInput.Unbind();
        Window->RemoveFromParent();
    }
    if (IsValid(ModalPlayer))
    {
        ModalPlayer->SetIgnoreMoveInput(false);
        ModalPlayer->SetIgnoreLookInput(false);
        ModalPlayer->bShowMouseCursor = bPreviousCursor;
        ModalPlayer->FlushPressedKeys();
        ModalPlayer->SetInputMode(FInputModeGameOnly());
        if (CurrentDocument && CurrentDocument->CloseSound)
            UGameplayStatics::PlaySound2D(ModalPlayer, CurrentDocument->CloseSound);
    }
    Window = nullptr;
    ModalPlayer = nullptr;
    CurrentDocument = nullptr;
}

void UNarrativeSubsystem::StartAmbience(USoundBase* Sound, float Volume)
{
    StopAmbience(0);
    if (Sound) Ambience = UGameplayStatics::SpawnSound2D(GetGameInstance(), Sound, FMath::Clamp(Volume, 0.f, 1.f));
}

void UNarrativeSubsystem::StopAmbience(float FadeSeconds)
{
    if (Ambience)
    {
        if (FadeSeconds > 0) Ambience->FadeOut(FadeSeconds, 0);
        else Ambience->Stop();
        Ambience = nullptr;
    }
}

bool UNarrativeSubsystem::ShowLocationCard(APlayerController* Player, FText LocationTitle, UTexture2D* DestinationPhoto,
    const ATargetPoint* Arrival)
{
    UGameViewportClient* Viewport = GetGameInstance()->GetGameViewportClient();
    UWorld* World = GetWorld();
    APawn* Pawn = Player ? Player->GetPawn() : nullptr;
    if (!Viewport || !World || !Pawn || !Player->IsLocalController() || Player->IsMoveInputIgnored() ||
        IsLocationTransitionActive() || IsDocumentOpen()) return false;

    LocationPhoto = DestinationPhoto;
    LocationCard = SNew(SLocationCard).Photo(DestinationPhoto).Title(LocationTitle);
    LockLocationPlayer(Player);
    LocationViewport = Viewport;
    LocationWorld = World;
    Viewport->AddViewportWidgetContent(LocationCard.ToSharedRef(), 250);

    if (Arrival && !Pawn->TeleportTo(Arrival->GetActorLocation(), Arrival->GetActorRotation()))
    {
        FinishLocationCard();
        return false;
    }
    if (Arrival) Player->SetControlRotation(Arrival->GetActorRotation());
    World->GetTimerManager().SetTimer(LocationHold, this, &ThisClass::FinishLocationCard, .9f, false);
    return true;
}

void UNarrativeSubsystem::LockLocationPlayer(APlayerController* Player)
{
    if (LocationPlayer.Get()!=Player)
    {
        if (bLocationInputLocked) if (APlayerController* Previous=LocationPlayer.Get())
        {
            Previous->SetIgnoreLookInput(false);
            Previous->SetIgnoreMoveInput(false);
            Previous->bShowMouseCursor=bLocationPreviousCursor;
        }
        bLocationInputLocked=false;
        LocationPlayer=Player;
    }
    if (!Player || bLocationInputLocked) return;
    bLocationPreviousCursor=Player->bShowMouseCursor;
    Player->bShowMouseCursor=false;
    Player->SetIgnoreMoveInput(true);
    Player->SetIgnoreLookInput(true);
    Player->StopMovement();
    Player->FlushPressedKeys();
    bLocationInputLocked=true;
}

void UNarrativeSubsystem::FinishLocationCard()
{
    if (UWorld* World = LocationWorld.Get()) World->GetTimerManager().ClearTimer(LocationHold);
    if (LocationCard.IsValid())
    {
        if (UGameViewportClient* Viewport = LocationViewport.Get())
            Viewport->RemoveViewportWidgetContent(LocationCard.ToSharedRef());
        LocationCard.Reset();
    }
    if (bLocationInputLocked) if (APlayerController* Player = LocationPlayer.Get())
    {
        Player->FlushPressedKeys();
        Player->SetIgnoreLookInput(false);
        Player->SetIgnoreMoveInput(false);
        Player->bShowMouseCursor=bLocationPreviousCursor;
        Player->SetInputMode(FInputModeGameOnly());
    }
    bLocationInputLocked=false;
    LocationPhoto = nullptr;
    LocationViewport.Reset();
    LocationPlayer.Reset();
    LocationWorld.Reset();
}

bool UNarrativeSubsystem::TravelToStreet(TSoftObjectPtr<UWorld> Destination, FText LocationTitle,
    UTexture2D* DestinationPhoto, FName ArrivalTag, const AActor* OpeningDoor)
{
    // References to an already visited map can carry the PIE package prefix in editor play.
    const FString Package = UWorld::RemovePIEPrefix(Destination.ToSoftObjectPath().GetLongPackageName());
    UWorld* World = GetWorld();
    APlayerController* Player = UGameplayStatics::GetPlayerController(World,0);
    UGameViewportClient* Viewport = GetGameInstance()->GetGameViewportClient();
    if (IsLocationTransitionActive() || !World || !Player || !Viewport || IsDocumentOpen() ||
        Package.IsEmpty() || !FPackageName::DoesPackageExist(Package)) return false;
    ULocationTravelSubsystem* Travel = GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>();
    Travel->Capture(Player->GetHUD());
    // All known public entrances have a deterministic threshold even for legacy callers.
    if (ArrivalTag.IsNone())
    {
        if (Package.EndsWith(TEXT("/L_DimaApartmentInterior")) || Package.EndsWith(TEXT("/L_PolicePrecinct"))) ArrivalTag=TEXT("FromStreet");
        else if (Package.EndsWith(TEXT("/L_NeptuneStreet")))
            ArrivalTag=UGameplayStatics::GetCurrentLevelName(World,true)==TEXT("L_PolicePrecinct") ? TEXT("FromPrecinct") : TEXT("FromApartment");
    }
    Travel->ArrivalTag = ArrivalTag;
    Travel->bLastArrivalExact = ArrivalTag.IsNone();
    StopAmbience(0);
    bTravelling = true;
    PendingDestination = FName(*Package);
    TravelStartedAt = FPlatformTime::Seconds();
    if (!DestinationPhoto)
    {
        const TCHAR* Asset=nullptr;
        if (Package.EndsWith(TEXT("/L_DimaApartmentInterior"))) Asset=TEXT("/Game/Prologue/Street/Transitions/T_Transition_Apartment.T_Transition_Apartment");
        else if (Package.EndsWith(TEXT("/L_NeptuneStreet"))) Asset=TEXT("/Game/Prologue/Street/Transitions/T_Transition_Neptune.T_Transition_Neptune");
        else if (Package.EndsWith(TEXT("/L_PolicePrecinct"))) Asset=TEXT("/Game/Prologue/Street/Transitions/T_Transition_Precinct.T_Transition_Precinct");
        if (Asset) DestinationPhoto=LoadObject<UTexture2D>(nullptr,Asset);
    }
    LocationPhoto = DestinationPhoto;
    LocationCard = SNew(SLocationCard).Photo(DestinationPhoto).Title(LocationTitle).Loading(true);
    LockLocationPlayer(Player);
    LocationViewport = Viewport;
    LocationWorld = World;
    Viewport->AddViewportWidgetContent(LocationCard.ToSharedRef(),250);
    if (!IsRunningDedicatedServer() && IsMoviePlayerEnabled() && GetMoviePlayer())
    {
        FLoadingScreenAttributes Screen;
        Screen.bAutoCompleteWhenLoadingCompletes = true;
        Screen.MinimumLoadingScreenDisplayTime = .35f;
        Screen.WidgetLoadingScreen = SNew(SLocationCard).Photo(DestinationPhoto).Title(LocationTitle).Loading(true);
        GetMoviePlayer()->SetupLoadingScreen(Screen);
    }
    if (OpeningDoor) DoorOpeningAudio::Play(OpeningDoor,EDoorOpeningSound::Entry);
    // Draw the screen immediately, giving a door's latch time to sound before its world unloads.
    World->GetTimerManager().SetTimer(TravelBegin,this,&ThisClass::BeginMapTravel,OpeningDoor ? .32f : .15f,false);
    return true;
}

void UNarrativeSubsystem::BeginMapTravel()
{
    UGameplayStatics::OpenLevel(GetGameInstance(),PendingDestination);
}

void UNarrativeSubsystem::MapLoaded(UWorld* World)
{
    if (!World || World->GetGameInstance() != GetGameInstance()) return;
    if (!bTravelling) { FinishLocationCard(); CloseDocument(); return; }
    LocationWorld = World;
    LockLocationPlayer(UGameplayStatics::GetPlayerController(World,0));
    ArrivalWaitStartedAt=FPlatformTime::Seconds();
    GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->ApplyArrival(World);
    // Keep the overlay until the new world's pawn, ground and capsule placement have been validated.
    World->GetTimerManager().SetTimer(LocationHold,this,&ThisClass::FinishMapTravel,.016f,false);
}

void UNarrativeSubsystem::FinishMapTravel()
{
    UWorld* World=LocationWorld.Get();
    if (!World) return;
    LockLocationPlayer(UGameplayStatics::GetPlayerController(World,0));
    const bool bFallback=FPlatformTime::Seconds()-ArrivalWaitStartedAt>2.5;
    ULocationTravelSubsystem* Travel=GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>();
    if (!Travel->ApplyArrival(World,bFallback))
    {
        if (bFallback)
        {
            TravelFailed(World,ETravelFailure::LoadMapFailure,TEXT("No safe door arrival or PlayerStart"));
            return;
        }
        World->GetTimerManager().SetTimer(LocationHold,this,&ThisClass::FinishMapTravel,.05f,false);
        return;
    }
    const float Remaining=.35f-static_cast<float>(FPlatformTime::Seconds()-TravelStartedAt);
    if (Remaining>0)
    {
        World->GetTimerManager().SetTimer(LocationHold,this,&ThisClass::FinishMapTravel,Remaining,false);
        return;
    }
    FinishLocationCard();
    bTravelling = false;
    PendingDestination = NAME_None;
}

void UNarrativeSubsystem::TravelFailed(UWorld* World, ETravelFailure::Type Failure, const FString& Error)
{
    if (!World || World->GetGameInstance() != GetGameInstance()) return;
    if (GetWorld()) GetWorld()->GetTimerManager().ClearTimer(TravelBegin);
    FinishLocationCard();
    bTravelling = false;
    PendingDestination = NAME_None;
    GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->ArrivalTag = NAME_None;
    LocationPhoto = nullptr;
    if (GetMoviePlayer()) GetMoviePlayer()->StopMovie();
    UE_LOG(LogTemp, Error, TEXT("Street travel failed (%d): %s"), int32(Failure), *Error);
}
