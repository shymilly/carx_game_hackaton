#include "DocumentWindow.h"
#include "InteractionDocument.h"
#include "NarrativeSubsystem.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Engine/GameInstance.h"
#include "Fonts/CompositeFont.h"
#include "InputCoreTypes.h"
#include "Misc/Paths.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
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

    // Anchors follow the supplied gameplay reference, measured against the viewport, not editor chrome.
    // All DocumentWindow subclasses use this shared design, including previously authored widget trees.
    return SNew(SConstraintCanvas)
        + SConstraintCanvas::Slot().Anchors(FAnchors(0.045f, 0.70f, 0.77f, 0.975f))
          .Offset(FMargin(0)).Alignment(FVector2D::ZeroVector)
        [ SNew(SDialoguePanel).Fill(PanelColor).Outline(AccentColor)
          [ SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,16)
              [ SNew(STextBlock).Text(Heading).AutoWrapText(true).ColorAndOpacity(TextColor)
                  .Font(DialogueFont(TEXT("SOUTHGHETTO.ttf"), 25)) ]
            + SVerticalBox::Slot().FillHeight(1)
              [ SNew(SScrollBox) + SScrollBox::Slot()
                [ SNew(STextBlock).Text(Body).AutoWrapText(true).ColorAndOpacity(TextColor)
                    .Font(DialogueFont(TEXT("CascadiaCode-Light.otf"), 18)) ] ]
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0,6,0,0)
              [ SNew(SButton).ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
                  .ContentPadding(FMargin(6,2))
                  .OnClicked_Lambda([this]() { RequestClose(); return FReply::Handled(); })
                  [ SNew(STextBlock).Text(Close).ColorAndOpacity(TextColor)
                      .Font(DialogueFont(TEXT("CascadiaCode-Light.otf"), 10)) ] ]
          ]
        ];
}

void UDocumentWindow::RequestClose()
{
    if (UGameInstance* GI = GetGameInstance()) GI->GetSubsystem<UNarrativeSubsystem>()->CloseDocument();
}

FReply UDocumentWindow::NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
    if (Event.GetKey() == EKeys::Escape) { RequestClose(); return FReply::Handled(); }
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
