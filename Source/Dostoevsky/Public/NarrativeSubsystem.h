#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Engine/EngineBaseTypes.h"
#include "DocumentWindow.h"
#include "NarrativeSubsystem.generated.h"
class UInteractionDocument;
class UDocumentWindow;
class UAudioComponent;
class USoundBase;
class APlayerController;

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
    bool TravelToStreet(TSoftObjectPtr<UWorld> Destination, FText LocationTitle);
private:
    UPROPERTY(Transient) TObjectPtr<UDocumentWindow> Window;
    UPROPERTY(Transient) TObjectPtr<UInteractionDocument> CurrentDocument;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Voice;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Ambience;
    UPROPERTY(Transient) TObjectPtr<APlayerController> ModalPlayer;
    bool bPreviousCursor = false;
    bool bTravelling = false;
    FDelegateHandle MapLoadedHandle;
    FDelegateHandle TravelFailureHandle;
    bool OpenDocument(APlayerController* Player, UInteractionDocument* Document,
        TSubclassOf<UDocumentWindow> WindowClass, TArray<FText> Choices, FDocumentChoice Selection);
    void MapLoaded(UWorld* World);
    void TravelFailed(UWorld* World, ETravelFailure::Type Failure, const FString& Error);
};
