#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Engine/EngineBaseTypes.h"
#include "DocumentWindow.h"
#include "Engine/TimerHandle.h"
#include "NarrativeSubsystem.generated.h"
class UInteractionDocument;
class UDocumentWindow;
class UAudioComponent;
class USoundBase;
class APlayerController;
class ATargetPoint;
class SWidget;
class UGameViewportClient;
class UTexture2D;

UCLASS()
class DOSTOEVSKY_API UNarrativeSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    UFUNCTION(BlueprintCallable, Category="Narrative")
    bool ShowDocument(APlayerController* Player, UInteractionDocument* Document, TSubclassOf<UDocumentWindow> WindowClass);
    bool ShowChoices(APlayerController* Player, UInteractionDocument* Document, TArray<FText> Choices, FDocumentChoice Selection);
    UFUNCTION(BlueprintCallable, Category="Narrative") void CloseDocument();
    UFUNCTION(BlueprintPure, Category="Narrative") bool IsDocumentOpen() const { return Window != nullptr; }
    UFUNCTION(BlueprintCallable, Category="Narrative|Audio") void StartAmbience(USoundBase* Sound, float Volume = 0.5f);
    UFUNCTION(BlueprintCallable, Category="Narrative|Audio") void StopAmbience(float FadeSeconds = 1.f);
    // Destination is an asset reference, so renames and cooking can track it.
    UFUNCTION(BlueprintCallable, Category="Narrative|Travel")
    bool TravelToStreet(TSoftObjectPtr<UWorld> Destination, FText LocationTitle, UTexture2D* DestinationPhoto = nullptr);
    bool ShowLocationCard(APlayerController* Player, FText LocationTitle, UTexture2D* DestinationPhoto,
        const ATargetPoint* Arrival = nullptr);
    UFUNCTION(BlueprintPure, Category="Narrative|Travel") bool IsLocationTransitionActive() const
    {
        return bTravelling || LocationCard.IsValid();
    }
    UFUNCTION(BlueprintPure, Category="Narrative|Travel") UTexture2D* GetLocationPhoto() const { return LocationPhoto; }
private:
    UPROPERTY(Transient) TObjectPtr<UDocumentWindow> Window;
    UPROPERTY(Transient) TObjectPtr<UInteractionDocument> CurrentDocument;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Voice;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Ambience;
    UPROPERTY(Transient) TObjectPtr<APlayerController> ModalPlayer;
    UPROPERTY(Transient) TObjectPtr<UTexture2D> LocationPhoto;
    TSharedPtr<SWidget> LocationCard;
    TWeakObjectPtr<APlayerController> LocationPlayer;
    TWeakObjectPtr<UGameViewportClient> LocationViewport;
    TWeakObjectPtr<UWorld> LocationWorld;
    FTimerHandle LocationHold;
    bool bPreviousCursor = false;
    bool bTravelling = false;
    FDelegateHandle MapLoadedHandle;
    FDelegateHandle TravelFailureHandle;
    bool OpenDocument(APlayerController* Player, UInteractionDocument* Document,
        TSubclassOf<UDocumentWindow> WindowClass, TArray<FText> Choices, FDocumentChoice Selection);
    void MapLoaded(UWorld* World);
    void TravelFailed(UWorld* World, ETravelFailure::Type Failure, const FString& Error);
    void FinishLocationCard();
};
