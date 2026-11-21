#pragma once

#include "Brushes/SlateRoundedBoxBrush.h"
#include "Rendering/DrawElements.h"
#include "Widgets/SCompoundWidget.h"

class SDialoguePanel : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SDialoguePanel)
            : _Radius(28.f), _Padding(24, 18, 24, 12) {}
        SLATE_ATTRIBUTE(FLinearColor, Fill)
        SLATE_ARGUMENT(FLinearColor, Outline)
        SLATE_ARGUMENT(float, Radius)
        SLATE_ARGUMENT(FMargin, Padding)
        SLATE_DEFAULT_SLOT(FArguments, Content)
    SLATE_END_ARGS()

    void Construct(const FArguments& Args)
    {
        Fill = Args._Fill;
        CornerRadius = Args._Radius;
        FillBrush = MakeUnique<FSlateRoundedBoxBrush>(FLinearColor::White, CornerRadius);
        Outline = Args._Outline;
        ChildSlot.Padding(Args._Padding)[Args._Content.Widget];
    }

    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry,
        const FSlateRect& CullingRect, FSlateWindowElementList& Elements, int32 Layer,
        const FWidgetStyle& Style, bool bEnabled) const override
    {
        FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(), FillBrush.Get(),
            ESlateDrawEffect::None, Fill.Get(FLinearColor::Transparent) * Style.GetColorAndOpacityTint());

        // Continuous distance around the rounded perimeter keeps dash spacing even at corners.
        const FVector2D Size = Geometry.GetLocalSize();
        const float Radius = FMath::Min(CornerRadius, float(FMath::Min(Size.X, Size.Y)) / 2.f - 2.f);
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
    TAttribute<FLinearColor> Fill;
    FLinearColor Outline;
    float CornerRadius = 28.f;
};
