#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/ActorComponent.h"
#include "Engine/DataAsset.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "JournalUI.generated.h"
class AHUD;
class APlayerController;
class UInteractionDocument;
class UDocumentWindow;
class SVerticalBox;
class SBox;
class UJournalPresenterComponent;

USTRUCT(BlueprintType)
struct FJournalEntry
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FName DiscoveryFlag;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UInteractionDocument> Document;
};

UCLASS(BlueprintType)
class DOSTOEVSKY_API UJournalCatalog : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FJournalEntry> Entries;
};

UCLASS()
class DOSTOEVSKY_API UJournalOverlayWidget : public UUserWidget
{
    GENERATED_BODY()
public:
    TWeakObjectPtr<UJournalPresenterComponent> Presenter;
    void RefreshEntries();
    void ShowEntry(UInteractionDocument* Document);
    void ClearSelection();
    bool HasSelection() const { return SelectedWindow != nullptr; }
protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
    virtual void ReleaseSlateResources(bool bReleaseChildren) override;
private:
    UPROPERTY(Transient) TObjectPtr<UDocumentWindow> SelectedWindow;
    TSharedPtr<SVerticalBox> EntryList;
    TSharedPtr<SBox> DocumentHost;
};

UCLASS(ClassGroup=(UI))
class DOSTOEVSKY_API UJournalPresenterComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UJournalPresenterComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Journal") TSoftObjectPtr<UJournalCatalog> CatalogAsset;
    void Present();
    UFUNCTION(BlueprintCallable, Category="Journal") void SelectEntry(int32 CatalogIndex);
    UFUNCTION(BlueprintPure, Category="Journal") TArray<int32> VisibleEntries() const;
    UInteractionDocument* GetEntry(int32 CatalogIndex) const;
    UFUNCTION(BlueprintCallable, Category="Journal") void CloseJournal();
    virtual void TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    UPROPERTY(Transient) TObjectPtr<UJournalCatalog> Catalog;
    UPROPERTY(Transient) TObjectPtr<UJournalOverlayWidget> Overlay;
    TWeakObjectPtr<APlayerController> ModalPlayer;
    TArray<int32> PreviousVisibleEntries;
    bool bPreviousCursor = false;
    bool bWarnedMissingCatalog = false;
};

UCLASS()
class DOSTOEVSKY_API UJournalUILibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Journal", meta=(DefaultToSelf="HUD", HidePin="HUD"))
    static void PresentJournal(AHUD* HUD);
    UFUNCTION(BlueprintCallable, Category="Journal|Editor") static int32 UpgradeJournalUI(UObject* BlueprintAsset);
    UFUNCTION(BlueprintCallable, Category="Journal|Editor") static bool ValidateJournalUI();
    UFUNCTION(BlueprintCallable, Category="Journal|Editor") static bool ValidateJournalBlueprint(UObject* BlueprintAsset);
};
