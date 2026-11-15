#include "NarrativeSubsystem.h"
#include "DocumentWindow.h"
#include "InteractionDocument.h"
#include "Components/AudioComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/PackageName.h"
#include "MoviePlayer.h"
#include "Styling/CoreStyle.h"
#include "UObject/UObjectGlobals.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Images/SThrobber.h"
#include "Widgets/Text/STextBlock.h"

void UNarrativeSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    MapLoadedHandle = FCoreUObjectDelegates::PostLoadMapWithWorld.AddUObject(this, &ThisClass::MapLoaded);
    if (GEngine) TravelFailureHandle = GEngine->OnTravelFailure().AddUObject(this, &ThisClass::TravelFailed);
}

void UNarrativeSubsystem::Deinitialize()
{
    CloseDocument();
    StopAmbience(0);
    FCoreUObjectDelegates::PostLoadMapWithWorld.Remove(MapLoadedHandle);
    if (GEngine) GEngine->OnTravelFailure().Remove(TravelFailureHandle);
    Super::Deinitialize();
}

bool UNarrativeSubsystem::ShowDocument(APlayerController* Player, UInteractionDocument* Document, TSubclassOf<UDocumentWindow> WindowClass)
{
    if (!Player || !Player->IsLocalController() || !Document || bTravelling) return false;
    CloseDocument();
    Window = CreateWidget<UDocumentWindow>(Player, WindowClass.Get() ? WindowClass.Get() : UDocumentWindow::StaticClass());
    if (!Window) return false;
    CurrentDocument = Document;
    Window->Document = Document;
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

bool UNarrativeSubsystem::TravelToStreet(TSoftObjectPtr<UWorld> Destination, FText LocationTitle)
{
    const FString Package = Destination.ToSoftObjectPath().GetLongPackageName();
    if (bTravelling || !GetWorld() || Package.IsEmpty() || !FPackageName::DoesPackageExist(Package))
    {
        UE_LOG(LogTemp, Warning, TEXT("Travel rejected: missing map or travel in progress: %s"), *Package);
        return false;
    }
    CloseDocument();
    StopAmbience(0);
    bTravelling = true;
    if (!IsRunningDedicatedServer() && IsMoviePlayerEnabled() && GetMoviePlayer())
    {
        FLoadingScreenAttributes Screen;
        Screen.bAutoCompleteWhenLoadingCompletes = true;
        Screen.MinimumLoadingScreenDisplayTime = 1.0f;
        Screen.WidgetLoadingScreen = SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.015f, 0.02f, 0.03f, 1))
            .HAlign(HAlign_Center).VAlign(VAlign_Center)
            [ SNew(SVerticalBox)
              + SVerticalBox::Slot().AutoHeight().Padding(20)
                [ SNew(STextBlock).Text(LocationTitle).Font(FCoreStyle::GetDefaultFontStyle("Bold", 28)) ]
              + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center) [ SNew(SThrobber) ]
              + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(20)
                [ SNew(STextBlock).Text(NSLOCTEXT("Dostoevsky", "Loading", "Загрузка…")) ] ];
        GetMoviePlayer()->SetupLoadingScreen(Screen);
    }
    UGameplayStatics::OpenLevel(GetGameInstance(), FName(*Package));
    return true;
}

void UNarrativeSubsystem::MapLoaded(UWorld* World)
{
    if (World && World->GetGameInstance() == GetGameInstance())
    {
        CloseDocument();
        bTravelling = false;
    }
}

void UNarrativeSubsystem::TravelFailed(UWorld* World, ETravelFailure::Type Failure, const FString& Error)
{
    if (!World || World->GetGameInstance() != GetGameInstance()) return;
    bTravelling = false;
    if (GetMoviePlayer()) GetMoviePlayer()->StopMovie();
    UE_LOG(LogTemp, Error, TEXT("Street travel failed (%d): %s"), int32(Failure), *Error);
}
