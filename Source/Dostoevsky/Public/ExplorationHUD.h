#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/ActorComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ExplorationHUD.generated.h"
class AHUD;
class UFont;
class UExplorationHUDComponent;

// Six actions: each movement key, jump and either Shift. J is not a tutorial requirement.
struct FExplorationTutorialProgress
{
    uint8 UsedMask = 0;
    static constexpr uint8 CompleteMask = 0x3f;
    bool HasUsed(int32 Index) const { return Index >= 0 && Index < 6 && (UsedMask & (1 << Index)) != 0; }
    bool IsComplete() const { return UsedMask == CompleteMask; }
    void RecordKey(const FKey& Key)
    {
        const FKey Keys[] = {EKeys::W, EKeys::A, EKeys::S, EKeys::D, EKeys::SpaceBar, EKeys::LeftShift};
        for (int32 Index = 0; Index < 6; ++Index)
            if (Key == Keys[Index] || (Index == 5 && Key == EKeys::RightShift)) UsedMask |= 1 << Index;
    }
};

UCLASS()
class DOSTOEVSKY_API UExplorationOverlayWidget : public UUserWidget
{
    GENERATED_BODY()
public:
    TWeakObjectPtr<UExplorationHUDComponent> Presenter;
protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
};

UCLASS(ClassGroup=(UI), meta=(BlueprintSpawnableComponent))
class DOSTOEVSKY_API UExplorationHUDComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UExplorationHUDComponent();
    uint8 GetTravelMask() const { return Progress.UsedMask; }
    void SetTravelMask(uint8 Mask) { Progress.UsedMask = Mask & FExplorationTutorialProgress::CompleteMask; }
    void ObserveHUD(bool bOfferControls);
    bool ShouldShowControls() const;
    bool HasUsed(int32 Index) const { return Progress.HasUsed(Index); }
    UFUNCTION(BlueprintPure, Category="HUD|Tutorial") bool IsTutorialComplete() const { return Progress.IsComplete(); }
    UFUNCTION(BlueprintCallable, Category="HUD|Tutorial") void ResetTutorial() { Progress = FExplorationTutorialProgress(); }
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    UPROPERTY(Transient) TObjectPtr<UExplorationOverlayWidget> Overlay;
    FExplorationTutorialProgress Progress;
    uint64 LastObservedFrame = 0;
    bool bControlsOffered = false;
    bool IsHUDVisible() const;
};

UCLASS()
class DOSTOEVSKY_API UExplorationHUDLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    // Same data pins as the old DrawText calls, so migration preserves exec links.
    UFUNCTION(BlueprintCallable, Category="HUD", meta=(DefaultToSelf="HUD", HidePin="HUD"))
    static void PresentExplorationHUD(AHUD* HUD, const FString& Text, FLinearColor TextColor, float ScreenX, float ScreenY, UFont* Font, float Scale, bool bScalePosition);
    UFUNCTION(BlueprintCallable, Category="HUD", meta=(DefaultToSelf="HUD", HidePin="HUD"))
    static void PresentJournalHUD(AHUD* HUD, const FString& Text, FLinearColor TextColor, float ScreenX, float ScreenY, UFont* Font, float Scale, bool bScalePosition);
    UFUNCTION(BlueprintCallable, Category="HUD|Editor") static int32 UpgradeExplorationHUD(UObject* BlueprintAsset);
    UFUNCTION(BlueprintCallable, Category="HUD|Editor") static bool ValidateExplorationHUD();
};
