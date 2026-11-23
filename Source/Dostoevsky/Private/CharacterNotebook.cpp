#include "CharacterNotebook.h"

#include "ActOne.h"
#include "DialogueFont.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "InputCoreTypes.h"
#include "NarrativeSubsystem.h"
#include "Brushes/SlateImageBrush.h"
#include "Layout/ArrangedChildren.h"
#include "Styling/CoreStyle.h"
#include "UObject/ConstructorHelpers.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "CharacterNotebook"

namespace CharacterNotebookStyle
{
const FLinearColor Ink = FLinearColor::FromSRGBColor(FColor(51, 39, 28));
const FLinearColor Pencil = FLinearColor::FromSRGBColor(FColor(109, 79, 57));
const FLinearColor RedInk = FLinearColor::FromSRGBColor(FColor(148, 60, 39));
const FLinearColor RuledLine = FLinearColor::FromSRGBColor(FColor(170, 139, 95, 108));
const FVector2D PageSize(750, 410);

class SNotebookLayout : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SNotebookLayout) {}
        SLATE_DEFAULT_SLOT(FArguments, Content)
    SLATE_END_ARGS()

    void Construct(const FArguments& Arguments)
    {
        ChildSlot[Arguments._Content.Widget];
    }

protected:
    virtual FVector2D ComputeDesiredSize(float LayoutScaleMultiplier) const override
    {
        return PageSize;
    }

    virtual void OnArrangeChildren(const FGeometry& Allotted, FArrangedChildren& Arranged) const override
    {
        const TSharedRef<SWidget> Page = ChildSlot.GetWidget();
        const FVector2D Space = Allotted.GetLocalSize();
        if (!Arranged.Accepts(Page->GetVisibility()) || Space.X <= 0 || Space.Y <= 0)
        {
            return;
        }
        const float Scale = FMath::Min(.82f * Space.X / PageSize.X, .80f * Space.Y / PageSize.Y);
        const FVector2D Offset = (Space - Scale * PageSize) * .5f;
        Arranged.AddWidget(Allotted.MakeChild(Page, PageSize, FSlateLayoutTransform(Scale, Offset)));
    }
};

TSharedRef<SWidget> Rule()
{
    return SNew(SBox).HeightOverride(1)
        [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(RuledLine)];
}
}

UCharacterNotebook::UCharacterNotebook(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    static ConstructorHelpers::FObjectFinder<UTexture2D> Background(TEXT("/Game/UI/Notebook/T_HarvestBook.T_HarvestBook"));
    BookTexture = Background.Object;
}

void UCharacterNotebook::SetEntries(const FActOneStatistics& Stats, int32 Cash, const FText& InNotes)
{
    Entries = {
        FText::AsNumber(Stats.Calm),
        FText::AsNumber(Stats.Anger),
        FText::AsNumber(Stats.Heritage),
        FText::AsNumber(Stats.CorporateTrust),
        FText::AsNumber(Stats.Neighborhood),
        FText::Format(LOCTEXT("CashValue", "${0}"), FText::AsNumber(Cash)),
    };
    Notes = InNotes;
    InvalidateLayoutAndVolatility();
}

void UCharacterNotebook::NativeConstruct()
{
    Super::NativeConstruct();
    ForceLayoutPrepass();
}

TSharedRef<SWidget> UCharacterNotebook::RebuildWidget()
{
    using CharacterNotebookStyle::Ink;
    using CharacterNotebookStyle::PageSize;
    using CharacterNotebookStyle::Pencil;
    using CharacterNotebookStyle::RedInk;
    using CharacterNotebookStyle::Rule;
    using CharacterNotebookStyle::SNotebookLayout;
    SetIsFocusable(true);
    BookBrush = FSlateImageBrush(BookTexture.Get(), PageSize);

    const FSlateFontInfo Heading = DialogueFont(TEXT("SOUTHGHETTO.ttf"), 22);
    const FSlateFontInfo Hand = DialogueFont(TEXT("CascadiaCode-Light.otf"), 15);
    const FSlateFontInfo Note = DialogueFont(TEXT("CascadiaCode-Light.otf"), 13);
    const FSlateFontInfo Entry = DialogueFont(TEXT("CascadiaCode-Light.otf"), 14);
    const FSlateFontInfo Number = DialogueFont(TEXT("SOUTHGHETTO.ttf"), 19);
    const FSlateFontInfo Small = DialogueFont(TEXT("CascadiaCode-Light.otf"), 12);
    const auto Left = SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 7)
          [SNew(STextBlock).Text(LOCTEXT("Owner", "Дима Огнев")).ColorAndOpacity(RedInk).Font(Hand)]
        + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 11)
          [SNew(STextBlock).Text(LOCTEXT("Title", "Характеристики")).ColorAndOpacity(Ink).Font(Heading)]
        + SVerticalBox::Slot().AutoHeight()[Rule()];

    const FText Labels[] = {
        LOCTEXT("Calm", "Спокойствие"),
        LOCTEXT("Anger", "Гнев"),
        LOCTEXT("Heritage", "Связь с русским наследием"),
        LOCTEXT("Trust", "Доверие корпорации"),
        LOCTEXT("Neighborhood", "Репутация в квартале"),
        LOCTEXT("Cash", "Наличные"),
    };
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Labels); ++Index)
    {
        Left->AddSlot().AutoHeight().Padding(0, 5, 0, 4)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center).Padding(0, 0, 10, 0)
              [SNew(STextBlock).Text(Labels[Index]).AutoWrapText(true).LineHeightPercentage(1.28f)
                  .ApplyLineHeightToBottomLine(false)
                  .ColorAndOpacity(Ink).Font(Entry)]
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
              [SNew(STextBlock).Text_Lambda([this, Index]
                  { return Entries.IsValidIndex(Index) ? Entries[Index] : FText::GetEmpty(); })
                  .ColorAndOpacity(RedInk).Font(Number)]
        ];
        Left->AddSlot().AutoHeight()[Rule()];
    }

    return SNew(SOverlay)
        + SOverlay::Slot()
        [SNew(SBorder).Padding(0).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.025f, 0.018f, 0.013f, .79f))]
        + SOverlay::Slot()
        [
            SNew(SNotebookLayout)
            [
                SNew(SOverlay)
                + SOverlay::Slot()
                [SNew(SImage).Image(&BookBrush).Visibility(EVisibility::HitTestInvisible)]
                + SOverlay::Slot().Padding(55, 43, 56, 51)
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().FillWidth(1).Padding(0, 0, 31, 0)
                      [Left]
                    + SHorizontalBox::Slot().FillWidth(1).Padding(31, 0, 0, 0)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 14, 0, 11)
                          [SNew(STextBlock).Text(LOCTEXT("Notes", "Заметки")).ColorAndOpacity(Ink).Font(Heading)]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 12)[Rule()]
                        + SVerticalBox::Slot().FillHeight(1)
                        [
                            SNew(SScrollBox).ScrollBarThickness(FVector2D(5, 5))
                            + SScrollBox::Slot().Padding(0, 5, 12, 10)
                              [SNew(STextBlock).Text_Lambda([this] { return Notes; }).Font(Note).ColorAndOpacity(Pencil)
                                  .AutoWrapText(true).LineHeightPercentage(1.65f)]
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
