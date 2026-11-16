#include "NarrativeSubsystem.h"
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
            SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.012f, 0.014f, 0.016f))[SNew(SOverlay)
                + SOverlay::Slot()
                [
                    SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
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

bool UNarrativeSubsystem::OpenDocument(APlayerController* Player, UInteractionDocument* Document,
    TSubclassOf<UDocumentWindow> WindowClass, TArray<FText> Choices, FDocumentChoice Selection)
{
    if (!Player || !Player->IsLocalController() || !Document || IsLocationTransitionActive()) return false;
    CloseDocument();
    Window = CreateWidget<UDocumentWindow>(Player, WindowClass.Get() ? WindowClass.Get() : UDocumentWindow::StaticClass());
    if (!Window) return false;
    CurrentDocument = Document;
    Window->Document = Document;
    Window->SetChoices(MoveTemp(Choices), MoveTemp(Selection));
    Window->AddToViewport(50);
    ModalPlayer = Player;
    bPreviousCursor = Player->bShowMouseCursor;
    Player->SetIgnoreMoveInput(true);
    Player->SetIgnoreLookInput(true);
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
    if (Window) Window->RemoveFromParent();
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
    LocationPlayer = Player;
    LocationViewport = Viewport;
    LocationWorld = World;
    Player->SetIgnoreMoveInput(true);
    Player->SetIgnoreLookInput(true);
    Player->StopMovement();
    Player->FlushPressedKeys();
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

void UNarrativeSubsystem::FinishLocationCard()
{
    if (UWorld* World = LocationWorld.Get()) World->GetTimerManager().ClearTimer(LocationHold);
    if (LocationCard.IsValid())
    {
        if (UGameViewportClient* Viewport = LocationViewport.Get())
            Viewport->RemoveViewportWidgetContent(LocationCard.ToSharedRef());
        LocationCard.Reset();
    }
    if (APlayerController* Player = LocationPlayer.Get())
    {
        Player->FlushPressedKeys();
        Player->SetIgnoreLookInput(false);
        Player->SetIgnoreMoveInput(false);
    }
    LocationPhoto = nullptr;
    LocationViewport.Reset();
    LocationPlayer.Reset();
    LocationWorld.Reset();
}

bool UNarrativeSubsystem::TravelToStreet(TSoftObjectPtr<UWorld> Destination, FText LocationTitle, UTexture2D* DestinationPhoto)
{
    const FString Package = Destination.ToSoftObjectPath().GetLongPackageName();
    if (IsLocationTransitionActive() || !GetWorld() || Package.IsEmpty() || !FPackageName::DoesPackageExist(Package))
    {
        UE_LOG(LogTemp, Warning, TEXT("Travel rejected: missing map or travel in progress: %s"), *Package);
        return false;
    }
    CloseDocument();
    StopAmbience(0);
    bTravelling = true;
    LocationPhoto = DestinationPhoto;
    if (!IsRunningDedicatedServer() && IsMoviePlayerEnabled() && GetMoviePlayer())
    {
        FLoadingScreenAttributes Screen;
        Screen.bAutoCompleteWhenLoadingCompletes = true;
        Screen.MinimumLoadingScreenDisplayTime = 1.0f;
        Screen.WidgetLoadingScreen = SNew(SLocationCard).Photo(DestinationPhoto).Title(LocationTitle).Loading(true);
        GetMoviePlayer()->SetupLoadingScreen(Screen);
    }
    UGameplayStatics::OpenLevel(GetGameInstance(), FName(*Package));
    return true;
}

void UNarrativeSubsystem::MapLoaded(UWorld* World)
{
    if (World && World->GetGameInstance() == GetGameInstance())
    {
        FinishLocationCard();
        CloseDocument();
        bTravelling = false;
    }
}

void UNarrativeSubsystem::TravelFailed(UWorld* World, ETravelFailure::Type Failure, const FString& Error)
{
    if (!World || World->GetGameInstance() != GetGameInstance()) return;
    bTravelling = false;
    LocationPhoto = nullptr;
    if (GetMoviePlayer()) GetMoviePlayer()->StopMovie();
    UE_LOG(LogTemp, Error, TEXT("Street travel failed (%d): %s"), int32(Failure), *Error);
}
