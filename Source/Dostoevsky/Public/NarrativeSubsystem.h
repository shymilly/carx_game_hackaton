#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Engine/EngineBaseTypes.h"
#include "DocumentWindow.h"
#include "Engine/TimerHandle.h"
#include "NarrativeSubsystem.generated.h"
class UInteractionDocument;
struct FActOneStatistics;
class UDocumentWindow;
class UAudioComponent;
class USoundBase;
class AActor;
class APlayerController;
class ATargetPoint;
class SWidget;
class IInputProcessor;
class UGameViewportClient;
class UTexture2D;

UCLASS()
class DOSTOEVSKY_API UNarrativeSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    bool TryOpenPauseMenu(APlayerController* Player);
    UFUNCTION(BlueprintCallable, Category="Narrative")
    bool ShowDocument(APlayerController* Player, UInteractionDocument* Document, TSubclassOf<UDocumentWindow> WindowClass);
    bool ShowChoices(APlayerController* Player, UInteractionDocument* Document, TArray<FText> Choices, FDocumentChoice Selection);
    bool ShowStoryPage(APlayerController* Player, UInteractionDocument* Document, FSimpleDelegate Continue);
    bool ShowRequiredChoices(APlayerController* Player, UInteractionDocument* Document, TArray<FText> Choices, FDocumentChoice Selection);
    bool ShowChallenge(APlayerController* Player, UInteractionDocument* Document, FDocumentKeyInput Input, FSimpleDelegate Cancel);
    bool ShowCharacterNotebook(APlayerController* Player, const FActOneStatistics& Stats, int32 Cash, const FText& Notes);
    UFUNCTION(BlueprintCallable, Category="Narrative") void CloseDocument();
    UFUNCTION(BlueprintPure, Category="Narrative") bool IsDocumentOpen() const { return Window != nullptr; }
    UFUNCTION(BlueprintCallable, Category="Narrative|Audio") void StartAmbience(USoundBase* Sound, float Volume = 0.5f);
    UFUNCTION(BlueprintCallable, Category="Narrative|Audio") void StopAmbience(float FadeSeconds = 1.f);
    // Destination is an asset reference, so renames and cooking can track it.
    UFUNCTION(BlueprintCallable, Category="Narrative|Travel")
    bool TravelToStreet(TSoftObjectPtr<UWorld> Destination, FText LocationTitle, UTexture2D* DestinationPhoto = nullptr,
        FName ArrivalTag = NAME_None, const AActor* OpeningDoor = nullptr);
    bool ShowLocationCard(APlayerController* Player, FText LocationTitle, UTexture2D* DestinationPhoto,
        const ATargetPoint* Arrival = nullptr);
    UFUNCTION(BlueprintPure, Category="Narrative|Travel") bool IsLocationTransitionActive() const
    {
        return bTravelling || LocationCard.IsValid();
    }
    UFUNCTION(BlueprintPure, Category="Narrative|Travel") UTexture2D* GetLocationPhoto() const { return LocationPhoto; }
private:
    UPROPERTY(Transient) TObjectPtr<UUserWidget> Window;
    UPROPERTY(Transient) TObjectPtr<UInteractionDocument> CurrentDocument;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Voice;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Ambience;
    UPROPERTY(Transient) TObjectPtr<APlayerController> ModalPlayer;
    UPROPERTY(Transient) TObjectPtr<UTexture2D> LocationPhoto;
    TSharedPtr<SWidget> LocationCard;
    TSharedPtr<SWidget> PauseMenu;
    TSharedPtr<IInputProcessor> EscapeInput;
    TWeakObjectPtr<APlayerController> PausePlayer;
    TWeakObjectPtr<UGameViewportClient> PauseViewport;
    bool bPauseOwnedByMenu = false;
    void ClosePauseMenu(bool bResume);
    TWeakObjectPtr<APlayerController> LocationPlayer;
    TWeakObjectPtr<UGameViewportClient> LocationViewport;
    TWeakObjectPtr<UWorld> LocationWorld;
    FTimerHandle LocationHold;
    bool bPreviousCursor = false;
    bool bTravelling = false;
    FDelegateHandle MapLoadedHandle;
    FDelegateHandle TravelFailureHandle;
    void PresentModal(APlayerController* Player, UUserWidget* Widget);
    bool OpenDocument(APlayerController* Player, UInteractionDocument* Document,
        TSubclassOf<UDocumentWindow> WindowClass, TArray<FText> Choices, FDocumentChoice Selection,
        bool bRequireChoice = false, FSimpleDelegate Continue = {}, FDocumentKeyInput Input = {});
    FName PendingDestination;
    FTimerHandle TravelBegin;
    double TravelStartedAt = 0;
    double ArrivalWaitStartedAt = 0;
    bool bLocationInputLocked = false;
    bool bLocationPreviousCursor = false;
    void LockLocationPlayer(APlayerController* Player);
    void BeginMapTravel();
    void FinishMapTravel();
    void MapLoaded(UWorld* World);
    void TravelFailed(UWorld* World, ETravelFailure::Type Failure, const FString& Error);
    void FinishLocationCard();
};
