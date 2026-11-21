#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/ActorComponent.h"
#include "DocumentWindow.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Actor.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "DimaApartmentStory.generated.h"
class AHUD;
class APlayerController;
class UAudioComponent;
class UBoxComponent;
class UInteractionDocument;
class USoundBase;

UENUM(BlueprintType)
enum class EDimaApartmentPhase : uint8 { AwaitingReport, Exploring, Ringing, Calling, ReadyToExit };

struct FDimaApartmentProgress
{
    EDimaApartmentPhase Phase = EDimaApartmentPhase::AwaitingReport;
    TSet<FName> Inspected;
    void FinishReport() { if (Phase == EDimaApartmentPhase::AwaitingReport) Phase = EDimaApartmentPhase::Exploring; }
    void Inspect(FName Tag) { if (Phase == EDimaApartmentPhase::Exploring) Inspected.Add(Tag); }
    bool CanRing(const TArray<FName>& Required) const
    {
        if (Phase != EDimaApartmentPhase::Exploring || Required.IsEmpty()) return false;
        for (FName Tag : Required) if (!Inspected.Contains(Tag)) return false;
        return true;
    }
    bool TryRing(const TArray<FName>& Required, bool bBusy)
    {
        if (bBusy || !CanRing(Required)) return false;
        Phase = EDimaApartmentPhase::Ringing;
        return true;
    }
    bool PickUp()
    {
        if (Phase != EDimaApartmentPhase::Ringing) return false;
        Phase = EDimaApartmentPhase::Calling;
        return true;
    }
    void FinishCall() { if (Phase == EDimaApartmentPhase::Calling) Phase = EDimaApartmentPhase::ReadyToExit; }
};

UCLASS(BlueprintType)
class DOSTOEVSKY_API UDimaApartmentScenario : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FName ApartmentMap = TEXT("L_DimaApartmentRefined");
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FName> RequiredInspections;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UInteractionDocument> Television;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UInteractionDocument> Fridge;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UInteractionDocument> Wardrobe;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UInteractionDocument> FloorLamp;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UInteractionDocument> RingNotice;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TObjectPtr<UInteractionDocument>> PhoneConversation;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USoundBase> Ambient;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USoundBase> PhoneRing;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USoundBase> WashWater;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0",ClampMax="1")) float AmbientVolume = 0.4f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0",ClampMax="1")) float PhoneVolume = 0.8f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0",ClampMax="1")) float WaterVolume = 0.7f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="2",ClampMax="3")) float WashDuration = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FText ExploreObjective;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FText PhoneObjective;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FText ExitObjective;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UWorld> StreetMap;
};

UCLASS()
class DOSTOEVSKY_API UDimaStoryDialogueWindow : public UDocumentWindow
{
    GENERATED_BODY()
protected:
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry,const FKeyEvent& Event) override;
};

UCLASS()
class DOSTOEVSKY_API UDimaWashOverlay : public UUserWidget
{
    GENERATED_BODY()
protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
};

UCLASS()
class DOSTOEVSKY_API ADimaStoryFocusProxy : public AActor
{
    GENERATED_BODY()
public:
    ADimaStoryFocusProxy();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UBoxComponent> FocusBox;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<AActor> SourceActor;
};

UCLASS(ClassGroup=(Narrative))
class DOSTOEVSKY_API UDimaApartmentStoryComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UDimaApartmentStoryComponent();
    FDimaApartmentProgress GetTravelProgress() const { return Progress; }
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TSoftObjectPtr<UDimaApartmentScenario> ScenarioAsset;
    void InitializeStory();
    bool TryInteract(FName Tag);
    FString Objective(const FString& Fallback) const;
    FString Prompt(FName Tag,const FString& Fallback) const;
    UFUNCTION(BlueprintPure, Category="Story") bool IsBusy() const { return bDialogueLocked || bWashing; }
    UFUNCTION(BlueprintPure, Category="Story") EDimaApartmentPhase GetPhase() const { return Progress.Phase; }
    UFUNCTION(BlueprintCallable, Category="Story") void AdvanceDialogue();
    virtual void TickComponent(float Delta,ELevelTick TickType,FActorComponentTickFunction* TickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    UPROPERTY(Transient) TObjectPtr<UDimaApartmentScenario> Scenario;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> AmbientAudio;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> RingAudio;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> WaterAudio;
    UPROPERTY(Transient) TObjectPtr<UDimaStoryDialogueWindow> Dialogue;
    UPROPERTY(Transient) TObjectPtr<UDimaWashOverlay> WashOverlay;
    UPROPERTY(Transient) TArray<TObjectPtr<UInteractionDocument>> Pages;
    TWeakObjectPtr<APlayerController> Player;
    struct FMovingDoorSound
    {
        TWeakObjectPtr<AActor> Leaf;
        FName TargetProperty;
        FName ProgressProperty;
        double PreviousProgress=0;
        bool bPlayed=false;
        bool bFridge=false;
    };
    TArray<FMovingDoorSound, TInlineAllocator<3>> DoorSounds;
    FDimaApartmentProgress Progress;
    FName PendingInspection;
    int32 PageIndex = 0;
    float WashElapsed = 0;
    bool bInitialized = false;
    bool bActive = false;
    bool bSharedStreet = false;
    bool bOutside = false;
    bool bDialogueLocked = false;
    bool bPhoneSequence = false;
    bool bPreviousCursor = false;
    bool bWashing = false;
    bool bWaitingForFridge = false;
    bool StartDialogue(const TArray<TObjectPtr<UInteractionDocument>>& Documents,FName Inspection,bool bPhone = false);
    bool ShowDocument(UInteractionDocument* Document,FName Inspection);
    void ShowPage();
    void FinishDialogue();
    void StartWash();
    void FinishWash();
    void RingPhone();
    void Hint(const FText& Text);
    void UpdateDoorSounds();
};

UCLASS()
class DOSTOEVSKY_API UDimaApartmentStoryLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Story", meta=(DefaultToSelf="HUD",HidePin="HUD")) static void InitializeStory(AHUD* HUD);
    UFUNCTION(BlueprintCallable, Category="Story", meta=(DefaultToSelf="HUD",HidePin="HUD")) static bool TryInteract(AHUD* HUD,FName Tag);
    UFUNCTION(BlueprintPure, Category="Story", meta=(DefaultToSelf="HUD",HidePin="HUD")) static bool IsBusy(AHUD* HUD);
    UFUNCTION(BlueprintPure, Category="Story", meta=(DefaultToSelf="HUD",HidePin="HUD")) static FString Objective(AHUD* HUD,const FString& Fallback);
    UFUNCTION(BlueprintPure, Category="Story", meta=(DefaultToSelf="HUD",HidePin="HUD")) static FString InteractionPrompt(AHUD* HUD,FName Tag,const FString& Fallback);
    UFUNCTION(BlueprintCallable, Category="Story|Editor") static bool ValidateScenario();
};
