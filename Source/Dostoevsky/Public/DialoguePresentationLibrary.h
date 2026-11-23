#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "DialoguePresentationLibrary.generated.h"
class AHUD;
class UFont;
class UDocumentWindow;
struct FKey;

// Adapter for the existing HUD graph. It forwards the opening report key to the HUD.
UCLASS(Transient)
class DOSTOEVSKY_API ULegacyDialogueBridge : public UActorComponent
{
    GENERATED_BODY()
public:
    ULegacyDialogueBridge();
    void BeginPanel();
    void Append(const FString& Text);
    virtual void TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    UPROPERTY(Transient) TObjectPtr<UDocumentWindow> Window;
    TArray<FString> Parts;
    FString PreviousContent;
    uint64 LastDrawFrame = 0;
    bool bReportInputFocused = false;
    bool HandleReportKey(const FKey& Key,bool bRepeat);
    void ReleaseReportFocus();
};

UCLASS()
class DOSTOEVSKY_API UDialoguePresentationLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Dialogue|Legacy", meta=(DefaultToSelf="HUD", HidePin="HUD"))
    static void BeginStyledDialogue(AHUD* HUD, FLinearColor RectColor, float ScreenX, float ScreenY, float ScreenW, float ScreenH);
    UFUNCTION(BlueprintCallable, Category="Dialogue|Legacy", meta=(DefaultToSelf="HUD", HidePin="HUD"))
    static void AppendStyledDialogue(AHUD* HUD, const FString& Text, FLinearColor TextColor, float ScreenX, float ScreenY, UFont* Font, float Scale, bool bScalePosition);
    // Editor utility used once to migrate only the old 160px dialogue blocks.
    UFUNCTION(BlueprintCallable, Category="Dialogue|Editor")
    static int32 UpgradeLegacyHUD(UObject* BlueprintAsset);
    UFUNCTION(BlueprintCallable, Category="Dialogue|Editor")
    static bool ExportDialoguePreview(const FString& OutputFile);
    UFUNCTION(BlueprintCallable, Category="Dialogue|Editor")
    static bool ValidateDialoguePainting();
};
