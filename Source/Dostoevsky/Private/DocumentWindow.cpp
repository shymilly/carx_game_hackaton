#include "DocumentWindow.h"
#include "InteractionDocument.h"
#include "NarrativeSubsystem.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "Fonts/CompositeFont.h"
#include "InputCoreTypes.h"
#include "Misc/Paths.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
FSlateFontInfo DialogueFont(const TCHAR* Filename, float Size)
{
    const FString Directory = FPaths::ProjectContentDir() / TEXT("UI/Dialogue/Fonts");
    TSharedRef<FCompositeFont> Font = MakeShared<FCompositeFont>();
    Font->DefaultTypeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"), Directory / Filename,
        EFontHinting::Default, EFontLoadingPolicy::LazyLoad));
    // Preserve readable names with Cascadia if a character is absent in SOUTHGHETTO.
    Font->FallbackTypeface.Typeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"),
        Directory / TEXT("CascadiaCode-Light.otf"), EFontHinting::Default, EFontLoadingPolicy::LazyLoad));
    return FSlateFontInfo(Font, Size);
}

class SDialoguePanel : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SDialoguePanel) {}
        SLATE_ARGUMENT(FLinearColor, Fill)
        SLATE_ARGUMENT(FLinearColor, Outline)
        SLATE_DEFAULT_SLOT(FArguments, Content)
    SLATE_END_ARGS()

    void Construct(const FArguments& Args)
    {
        FillBrush = MakeUnique<FSlateRoundedBoxBrush>(Args._Fill, 28.f);
        Outline = Args._Outline;
        ChildSlot.Padding(FMargin(24, 18, 24, 12))[Args._Content.Widget];
    }

    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry,
        const FSlateRect& CullingRect, FSlateWindowElementList& Elements, int32 Layer,
        const FWidgetStyle& Style, bool bEnabled) const override
    {
        FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(), FillBrush.Get(),
            ESlateDrawEffect::None, FillBrush->GetTint(Style) * Style.GetColorAndOpacityTint());

        // Continuous distance around the rounded perimeter keeps dash spacing even at corners.
        const FVector2D Size = Geometry.GetLocalSize();
        const float Radius = FMath::Min(28.f, float(FMath::Min(Size.X, Size.Y)) / 2.f - 2.f);
        if (Radius > 0)
        {
            TArray<FVector2D> Perimeter;
            const FVector2D Centers[] = {
                {Size.X - Radius - 2, Radius + 2}, {Size.X - Radius - 2, Size.Y - Radius - 2},
                {Radius + 2, Size.Y - Radius - 2}, {Radius + 2, Radius + 2}
            };
            for (int32 Corner = 0; Corner < 4; ++Corner)
            {
                for (int32 Step = 0; Step <= 16; ++Step)
                {
                    const float Angle = FMath::DegreesToRadians(-90.f + Corner * 90.f + Step * 90.f / 16.f);
                    Perimeter.Add(Centers[Corner] + FVector2D(FMath::Cos(Angle), FMath::Sin(Angle)) * Radius);
                }
            }
            const FVector2D FirstPoint = Perimeter[0];
            Perimeter.Add(FirstPoint);
            float Distance = 0;
            constexpr float DashLength = 20.f;
            constexpr float Period = 32.f;
            for (int32 Index = 1; Index < Perimeter.Num(); ++Index)
            {
                const FVector2D Delta = Perimeter[Index] - Perimeter[Index - 1];
                const float Length = Delta.Size();
                if (Length <= KINDA_SMALL_NUMBER) continue;
                float Offset = 0;
                while (Offset < Length - KINDA_SMALL_NUMBER)
                {
                    const float Phase = FMath::Fmod(Distance + Offset, Period);
                    const bool bDraw = Phase < DashLength;
                    const float Run = FMath::Min(Length - Offset, (bDraw ? DashLength : Period) - Phase + 0.001f);
                    if (bDraw)
                    {
                        TArray<FVector2D> Points;
                        Points.Add(Perimeter[Index - 1] + Delta * (Offset / Length));
                        Points.Add(Perimeter[Index - 1] + Delta * ((Offset + Run) / Length));
                        FSlateDrawElement::MakeLines(Elements, Layer + 1, Geometry.ToPaintGeometry(), Points,
                            ESlateDrawEffect::None, Outline * Style.GetColorAndOpacityTint(), true, 2.f);
                    }
                    Offset += Run;
                }
                Distance += Length;
            }
        }
        return SCompoundWidget::OnPaint(Args, Geometry, CullingRect, Elements, Layer + 2, Style, bEnabled);
    }
private:
    TUniquePtr<FSlateRoundedBoxBrush> FillBrush;
    FLinearColor Outline;
};
}

TSharedRef<SWidget> UDocumentWindow::RebuildWidget()
{
    SetIsFocusable(true);
    const FText Heading = Document
        ? (Document->Speaker.IsEmpty() ? Document->Title : Document->Speaker) : FText::GetEmpty();
    const FText Body = Document ? Document->Body : FText::GetEmpty();
    const FText Close = Document && !Document->CloseLabel.IsEmpty()
        ? Document->CloseLabel : NSLOCTEXT("Dostoevsky", "DialogueClose", "Закрыть · Esc");
    if (Document && Document->Layout == EDocumentLayout::Newspaper) return BuildNewspaper(Close);
    if (Document && Document->Layout == EDocumentLayout::Credits) return BuildCredits();

    TSharedRef<SScrollBox> Contents = SNew(SScrollBox);
    if (!Body.IsEmpty() || OnKeyInput.IsBound())
    {
        TSharedRef<STextBlock> Text = SNew(STextBlock)
            .Text_Lambda([this]() { return Document ? Document->Body : FText::GetEmpty(); })
            .AutoWrapText(true).ColorAndOpacity(TextColor).Font(DialogueFont(TEXT("CascadiaCode-Light.otf"), 18));
        if (Document && Document->Illustration)
        {
            IllustrationBrush = FSlateBrush();
            IllustrationBrush.SetResourceObject(Document->Illustration.Get());
            IllustrationBrush.ImageSize = Document->bCropToPortrait ? FVector2D(75,100) : FVector2D(175,108);
            if (Document->bCropToPortrait)
                IllustrationBrush.SetUVRegion(FBox2f(FVector2f(.12f,.08f),FVector2f(.46f,.66f)));
            Contents->AddSlot()
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().Padding(0,0,16,0).VAlign(VAlign_Top)
                  [SNew(SImage).Image(&IllustrationBrush)]
                + SHorizontalBox::Slot().FillWidth(1)[Text]
            ];
        }
        else Contents->AddSlot()[Text];
    }
    for (int32 First = 0; First < Choices.Num(); First += 2)
    {
        TSharedRef<SHorizontalBox> Row = SNew(SHorizontalBox);
        for (int32 Index = First; Index < FMath::Min(First + 2, Choices.Num()); ++Index)
        {
            Row->AddSlot().FillWidth(1).Padding(0, 2, 10, 2)
                [ SNew(SButton).ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
                    .ButtonColorAndOpacity(FLinearColor::White).ContentPadding(FMargin(8, 3))
                    .OnClicked_Lambda([this, Index]() { ChooseOption(Index); return FReply::Handled(); })
                    [ SNew(STextBlock).Text(FText::Format(NSLOCTEXT("Dostoevsky", "DocumentOption", "{0}. {1}"),
                        FText::AsNumber(Index + 1), Choices[Index])).ColorAndOpacity(TextColor).AutoWrapText(true)
                        .Font(DialogueFont(TEXT("CascadiaCode-Light.otf"), 14)) ] ];
        }
        Contents->AddSlot()[Row];
    }

    // Anchors follow the supplied gameplay reference, measured against the viewport, not editor chrome.
    // All DocumentWindow subclasses use this shared design, including previously authored widget trees.
    return SNew(SConstraintCanvas).Visibility(EVisibility::SelfHitTestInvisible)
        + SConstraintCanvas::Slot().Anchors(FAnchors(0.045f, 0.70f, 0.77f, 0.975f))
          .Offset(FMargin(0)).Alignment(FVector2D::ZeroVector)
        [ SNew(SDialoguePanel).Fill(PanelColor).Outline(AccentColor)
          [ SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,16)
              [ SNew(STextBlock).Text(Heading).AutoWrapText(true).ColorAndOpacity(TextColor)
                  .Font(DialogueFont(TEXT("SOUTHGHETTO.ttf"), 25)) ]
            + SVerticalBox::Slot().FillHeight(1)[Contents]
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0,6,0,0)
              [ SNew(SButton).ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
                  .ContentPadding(FMargin(6,2))
                  .Visibility(bRequireChoice ? EVisibility::Collapsed : EVisibility::Visible)
                  .OnClicked_Lambda([this]() { RequestClose(); return FReply::Handled(); })
                  [ SNew(STextBlock).Text(Close).ColorAndOpacity(TextColor)
                      .Font(DialogueFont(TEXT("CascadiaCode-Light.otf"), 10)) ] ]
          ]
        ];
}

TSharedRef<SWidget> UDocumentWindow::BuildNewspaper(const FText& Close)
{
    const FLinearColor Newsprint = FLinearColor::FromSRGBColor(FColor(244,239,224));
    const FSlateFontInfo Regular = DialogueFont(TEXT("ActPressSerif-Regular.ttf"),16);
    const FSlateFontInfo Bold = DialogueFont(TEXT("ActPressSerif-Bold.ttf"),21);
    const FSlateBrush* White = FCoreStyle::Get().GetBrush("WhiteBrush");
    TSharedRef<SHorizontalBox> Columns = SNew(SHorizontalBox);
    for (int32 Index=0; Index<Document->Articles.Num(); ++Index)
    {
        const FNewspaperArticle& Row = Document->Articles[Index];
        if (Index) Columns->AddSlot().AutoWidth().Padding(14,0)
            [SNew(SBox).WidthOverride(1)[SNew(SBorder).BorderImage(White).BorderBackgroundColor(FLinearColor(.32f,.30f,.26f,1))]];
        Columns->AddSlot().FillWidth(Index==0 ? 1.15f : 1.f).VAlign(VAlign_Top)
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,9)
              [SNew(STextBlock).Text(Row.Section).Font(Regular).ColorAndOpacity(TextColor).AutoWrapText(true)]
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,8)
              [SNew(STextBlock).Text(Row.Headline).Font(Bold).ColorAndOpacity(TextColor).AutoWrapText(true)]
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,13)
              [SNew(STextBlock).Text(Row.Deck).Font(Regular).ColorAndOpacity(TextColor).AutoWrapText(true)]
            + SVerticalBox::Slot().AutoHeight()
              [SNew(STextBlock).Text(Row.Text).Font(Regular).ColorAndOpacity(TextColor).AutoWrapText(true)]
        ];
    }
    return SNew(SBorder).BorderImage(White).BorderBackgroundColor(Newsprint).Padding(FMargin(32,18))
    [
        SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
          [SNew(STextBlock).Text(Document->Title).ColorAndOpacity(TextColor)
             .Font(DialogueFont(TEXT("ActPressMasthead.ttf"),54))]
        + SVerticalBox::Slot().AutoHeight().Padding(0,4)
          [SNew(SBox).HeightOverride(2)[SNew(SBorder).BorderImage(White).BorderBackgroundColor(FLinearColor::Black)]]
        + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0,2,0,4)
          [SNew(STextBlock).Text(Document->Edition).Font(Regular).ColorAndOpacity(TextColor)]
        + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,13)
          [SNew(SBox).HeightOverride(1)[SNew(SBorder).BorderImage(White).BorderBackgroundColor(FLinearColor::Black)]]
        + SVerticalBox::Slot().FillHeight(1)
          [SNew(SScrollBox) + SScrollBox::Slot()[Columns]]
        + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0,6,0,0)
          [SNew(SButton).OnClicked_Lambda([this]() { RequestClose(); return FReply::Handled(); })
              [SNew(STextBlock).Text(Close).Font(Regular).ColorAndOpacity(TextColor)]]
    ];
}

TSharedRef<SWidget> UDocumentWindow::BuildCredits()
{
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(FLinearColor::Black).HAlign(HAlign_Center).VAlign(VAlign_Center)
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
              [SNew(STextBlock).Text(Document->Body).ColorAndOpacity(FLinearColor(.92f,.83f,.66f,1))
                  .Font(DialogueFont(TEXT("CascadiaCode-Light.otf"),26)).WrapTextAt(720).Justification(ETextJustify::Center)]
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0,38,0,0)
              [SNew(SButton).ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
                  .OnClicked_Lambda([this]() { RequestClose(); return FReply::Handled(); })
                  [SNew(STextBlock).Text(Document->CloseLabel).ColorAndOpacity(FLinearColor(.70f,.64f,.56f,1))]]
        ];
}

void UDocumentWindow::SetChoices(TArray<FText> InChoices, FDocumentChoice InChoice)
{
    Choices = MoveTemp(InChoices);
    OnChoice = MoveTemp(InChoice);
}

bool UDocumentWindow::ChooseOption(int32 Index)
{
    if (!Choices.IsValidIndex(Index) || !OnChoice.IsBound()) return false;
    FDocumentChoice Choice = OnChoice;
    Choice.Execute(Index);
    return true;
}

void UDocumentWindow::RequestClose()
{
    if (bRequireChoice) return;
    const FSimpleDelegate Callback = OnCloseRequested;
    if (Callback.IsBound()) { Callback.Execute(); return; }
    if (UGameInstance* GI = GetGameInstance()) GI->GetSubsystem<UNarrativeSubsystem>()->CloseDocument();
}

FReply UDocumentWindow::NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
    const FDocumentKeyInput Action = OnKeyInput;
    if (Action.IsBound() && Action.Execute(Event.GetKey(),Event.IsRepeat())) return FReply::Handled();
    if (Event.GetKey() == EKeys::Escape) { RequestClose(); return FReply::Handled(); }
    if (Document && Document->Layout != EDocumentLayout::Standard && !Event.IsRepeat() &&
        (Event.GetKey()==EKeys::E || (Document->Layout==EDocumentLayout::Credits && Event.GetKey()==EKeys::R)))
    {
        RequestClose();
        return FReply::Handled();
    }
    if (!Event.IsRepeat() && !Choices.IsEmpty())
    {
        const FKey Digits[] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four};
        const FKey Numpad[] = {EKeys::NumPadOne, EKeys::NumPadTwo, EKeys::NumPadThree, EKeys::NumPadFour};
        for (int32 Index = 0; Index < UE_ARRAY_COUNT(Digits); ++Index)
            if ((Event.GetKey() == Digits[Index] || Event.GetKey() == Numpad[Index]) && ChooseOption(Index))
                return FReply::Handled();
    }
    return Super::NativeOnKeyDown(Geometry, Event);
}

#include "DialoguePresentationLibrary.h"
#if WITH_EDITOR
#include "Types/PaintArgs.h"
#include "Framework/Application/SlateApplication.h"
#include "Interfaces/ISlateNullRendererModule.h"
#include "Modules/ModuleManager.h"
#include "Widgets/SWindow.h"
#include "Widgets/SNullWidget.h"
#endif

bool UDialoguePresentationLibrary::ValidateDialoguePainting()
{
#if WITH_EDITOR
    if (!FSlateApplication::IsInitialized())
        FSlateApplication::InitializeAsStandaloneApplication(FModuleManager::LoadModuleChecked<ISlateNullRendererModule>(TEXT("SlateNullRenderer")).CreateSlateNullRenderer());
    TSharedRef<SWindow> Window = SNew(SWindow).ClientSize(FVector2D(1280, 720));
    TSharedRef<SDialoguePanel> Panel = SNew(SDialoguePanel)
        .Fill(FLinearColor::Yellow).Outline(FLinearColor::Black)[SNullWidget::NullWidget];
    // Exercise the real OnPaint contour path, including closing the TArray, without a GPU.
    const FVector2D Sizes[] = {{928, 198}, {1392, 297}, {320, 120}, {64, 32}, {2, 2}};
    for (const FVector2D& Size : Sizes)
    {
        FSlateWindowElementList Elements(Window);
        FPaintArgs Args(&Window.Get(), Window->GetHittestGrid(), FVector2D::ZeroVector, 0, 0);
        const FGeometry Geometry = FGeometry::MakeRoot(Size, FSlateLayoutTransform());
        Panel->OnPaint(Args, Geometry, FSlateRect(0, 0, Size.X, Size.Y), Elements, 0, FWidgetStyle(), true);
    }
    return true;
#else
    return false;
#endif
}
