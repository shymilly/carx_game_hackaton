#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Styling/SlateBrush.h"
#include "DocumentWindow.generated.h"
class UInteractionDocument;
class SScrollBox;
struct FKey;

DECLARE_DELEGATE_OneParam(FDocumentChoice, int32);
DECLARE_DELEGATE_RetVal_TwoParams(bool,FDocumentKeyInput,const FKey&,bool);

// Approved shared dialogue UI. Preserve this design for all future interactions; see Docs/DialogueStyle.md.
UCLASS(Blueprintable)
class DOSTOEVSKY_API UDocumentWindow : public UUserWidget
{
    GENERATED_BODY()
public:
    FSimpleDelegate OnCloseRequested;
    FDocumentKeyInput OnKeyInput;
    bool bRequireChoice = false;
    UPROPERTY(BlueprintReadOnly, Category="Document") TObjectPtr<UInteractionDocument> Document;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Style") FLinearColor PanelColor = FLinearColor::FromSRGBColor(FColor(255, 231, 157));
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Style") FLinearColor TextColor = FLinearColor::Black;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Style") FLinearColor AccentColor = FLinearColor::FromSRGBColor(FColor(255, 185, 0));
    UFUNCTION(BlueprintCallable, Category="Document") void RequestClose();
    void SetChoices(TArray<FText> InChoices, FDocumentChoice InChoice);
    UFUNCTION(BlueprintPure, Category="Document") int32 GetChoiceCount() const { return Choices.Num(); }
    UFUNCTION(BlueprintCallable, Category="Document") bool ChooseOption(int32 Index);
protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
private:
    TArray<FText> Choices;
    FDocumentChoice OnChoice;
    int32 SelectedChoice = 0;
    TWeakPtr<SScrollBox> ChoiceList;
    TArray<TWeakPtr<SWidget>> ChoiceButtons;
    FSlateBrush IllustrationBrush;
    TSharedRef<SWidget> BuildNewspaper(const FText& Close);
    TSharedRef<SWidget> BuildCredits();
};
