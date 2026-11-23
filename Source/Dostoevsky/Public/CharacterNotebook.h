#pragma once

#include "Blueprint/UserWidget.h"
#include "Styling/SlateBrush.h"
#include "CharacterNotebook.generated.h"

struct FActOneStatistics;
class UTexture2D;

UCLASS()
class DOSTOEVSKY_API UCharacterNotebook : public UUserWidget
{
    GENERATED_BODY()

public:
    explicit UCharacterNotebook(const FObjectInitializer& ObjectInitializer);
    void SetEntries(const FActOneStatistics& Statistics, int32 Cash, const FText& InNotes);

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual void NativeConstruct() override;
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;

private:
    void Close();

    UPROPERTY(Transient) TObjectPtr<UTexture2D> BookTexture;
    FSlateBrush BookBrush;
    TArray<FText> Entries;
    FText Notes;
};
