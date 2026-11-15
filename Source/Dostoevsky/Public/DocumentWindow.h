#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "DocumentWindow.generated.h"
class UInteractionDocument;

// Approved shared dialogue UI. Preserve this design for all future interactions; see Docs/DialogueStyle.md.
UCLASS(Blueprintable)
class DOSTOEVSKY_API UDocumentWindow : public UUserWidget
{
    GENERATED_BODY()
public:
    FSimpleDelegate OnCloseRequested;
    UPROPERTY(BlueprintReadOnly, Category="Document") TObjectPtr<UInteractionDocument> Document;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Style") FLinearColor PanelColor = FLinearColor::FromSRGBColor(FColor(255, 231, 157));
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Style") FLinearColor TextColor = FLinearColor::Black;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Style") FLinearColor AccentColor = FLinearColor::FromSRGBColor(FColor(255, 185, 0));
    UFUNCTION(BlueprintCallable, Category="Document") void RequestClose();
protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
};
