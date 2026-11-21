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
    void SetEntries(const FActOneStatistics& Statistics, int32 Cash, const FText& InNotes);

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;

private:
    void Close();

    UPROPERTY(Transient) TObjectPtr<UTexture2D> BookTexture;
    FSlateBrush BookBrush;
    TArray<TPair<FText, FText>> Entries;
    FText Notes;
};
