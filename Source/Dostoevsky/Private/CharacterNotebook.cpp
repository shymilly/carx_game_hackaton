#include "CharacterNotebook.h"

#include "ActOne.h"
#include "DialogueFont.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "InputCoreTypes.h"
#include "NarrativeSubsystem.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "CharacterNotebook"

namespace CharacterNotebookStyle
{
const FLinearColor Ink = FLinearColor::FromSRGBColor(FColor(51, 39, 28));
const FLinearColor Pencil = FLinearColor::FromSRGBColor(FColor(109, 79, 57));
const FLinearColor RedInk = FLinearColor::FromSRGBColor(FColor(148, 60, 39));
const FLinearColor RuledLine = FLinearColor::FromSRGBColor(FColor(170, 139, 95, 108));

TSharedRef<SWidget> Rule()
{
    return SNew(SBox).HeightOverride(1)
        [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(RuledLine)];
}
}

void UCharacterNotebook::SetEntries(const FActOneStatistics& Stats, int32 Cash, const FText& InNotes)
{
    Entries = {
        {LOCTEXT("Calm", "Спокойствие"), FText::AsNumber(Stats.Calm)},
        {LOCTEXT("Anger", "Гнев"), FText::AsNumber(Stats.Anger)},
        {LOCTEXT("Heritage", "Связь с русским наследием"), FText::AsNumber(Stats.Heritage)},
        {LOCTEXT("Trust", "Доверие корпорации"), FText::AsNumber(Stats.CorporateTrust)},
        {LOCTEXT("Neighborhood", "Репутация в квартале"), FText::AsNumber(Stats.Neighborhood)},
        {LOCTEXT("Cash", "Наличные"), FText::Format(LOCTEXT("CashValue", "${0}"), FText::AsNumber(Cash))},
    };
    Notes = InNotes;
}

TSharedRef<SWidget> UCharacterNotebook::RebuildWidget()
{
    using CharacterNotebookStyle::Ink;
    using CharacterNotebookStyle::Pencil;
    using CharacterNotebookStyle::RedInk;
    using CharacterNotebookStyle::Rule;
    SetIsFocusable(true);
    BookTexture = LoadObject<UTexture2D>(nullptr, TEXT("/Game/UI/Notebook/T_HarvestBook.T_HarvestBook"));
    const FVector2D BookSize = BookTexture
        ? FVector2D(BookTexture->GetSizeX(), BookTexture->GetSizeY()) : FVector2D(750, 406);
    BookBrush.SetResourceObject(BookTexture);
    BookBrush.SetImageSize(BookSize);
    BookBrush.DrawAs = ESlateBrushDrawType::Image;

    const FSlateFontInfo Heading = DialogueFont(TEXT("SOUTHGHETTO.ttf"), 22);
    const FSlateFontInfo Hand = DialogueFont(TEXT("CascadiaCode-Light.otf"), 15);
    const FSlateFontInfo Note = DialogueFont(TEXT("CascadiaCode-Light.otf"), 13);
    const FSlateFontInfo Entry = DialogueFont(TEXT("CascadiaCode-Light.otf"), 14);
    const FSlateFontInfo Number = DialogueFont(TEXT("SOUTHGHETTO.ttf"), 19);
    const FSlateFontInfo Small = DialogueFont(TEXT("CascadiaCode-Light.otf"), 12);
    const auto Left = SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 5)
          [SNew(STextBlock).Text(LOCTEXT("Owner", "Дима Огнев")).ColorAndOpacity(RedInk).Font(Hand)]
        + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 11)
          [SNew(STextBlock).Text(LOCTEXT("Title", "Характеристики")).ColorAndOpacity(Ink).Font(Heading)]
        + SVerticalBox::Slot().AutoHeight()[Rule()];

    for (const auto& Row : Entries)
    {
        Left->AddSlot().AutoHeight().Padding(0, 6, 0, 5)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center).Padding(0, 0, 10, 0)
              [SNew(STextBlock).Text(Row.Key).AutoWrapText(true).ColorAndOpacity(Ink).Font(Entry)]
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
              [SNew(STextBlock).Text(Row.Value).ColorAndOpacity(RedInk).Font(Number)]
        ];
        Left->AddSlot().AutoHeight()[Rule()];
    }

    return SNew(SOverlay)
        + SOverlay::Slot()
        [SNew(SBorder).Padding(0).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.025f, 0.018f, 0.013f, .79f))]
        + SOverlay::Slot()
        [
            SNew(SConstraintCanvas)
            + SConstraintCanvas::Slot().Anchors(FAnchors(.09f, .10f, .91f, .90f)).Offset(FMargin(0))
            [
                SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
                [
                    SNew(SBox).WidthOverride(BookSize.X).HeightOverride(BookSize.Y)
                    [
                        SNew(SOverlay)
                        + SOverlay::Slot()
                        [SNew(SImage).Image(&BookBrush).Visibility(EVisibility::HitTestInvisible)]
                        + SOverlay::Slot().Padding(49, 44, 50, 43)
                        [
                            SNew(SHorizontalBox)
                            + SHorizontalBox::Slot().FillWidth(1).Padding(0, 0, 31, 0)
                              [Left]
                            + SHorizontalBox::Slot().FillWidth(1).Padding(31, 0, 0, 0)
                            [
                                SNew(SVerticalBox)
                                + SVerticalBox::Slot().AutoHeight().Padding(0, 14, 0, 11)
                                  [SNew(STextBlock).Text(LOCTEXT("Notes", "На полях")).ColorAndOpacity(Ink).Font(Heading)]
                                + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 12)[Rule()]
                                + SVerticalBox::Slot().FillHeight(1)
                                [
                                    SNew(SScrollBox)
                                    + SScrollBox::Slot().Padding(0, 0, 6, 0)
                                      [SNew(STextBlock).Text(Notes).Font(Note).ColorAndOpacity(Pencil)
                                          .AutoWrapText(true).LineHeightPercentage(1.04f)]
                                ]
                                + SVerticalBox::Slot().AutoHeight().Padding(0, 8, 0, 5)[Rule()]
                                + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)
                                [
                                    SNew(SButton).ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
                                    .IsFocusable(false).ContentPadding(FMargin(4, 3))
                                    .OnClicked_Lambda([this] { Close(); return FReply::Handled(); })
                                    [SNew(STextBlock).Text(LOCTEXT("Close", "Закрыть · K / Esc"))
                                        .Font(Small).ColorAndOpacity(RedInk)]
                                ]
                            ]
                        ]
                    ]
                ]
            ]
        ];
}

FReply UCharacterNotebook::NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
    if (Event.GetKey() == EKeys::K || Event.GetKey() == EKeys::Escape)
    {
        if (!Event.IsRepeat()) Close();
        return FReply::Handled();
    }
    return Super::NativeOnKeyDown(Geometry, Event);
}

void UCharacterNotebook::Close()
{
    if (UGameInstance* Instance = GetGameInstance()) Instance->GetSubsystem<UNarrativeSubsystem>()->CloseDocument();
}

#undef LOCTEXT_NAMESPACE
