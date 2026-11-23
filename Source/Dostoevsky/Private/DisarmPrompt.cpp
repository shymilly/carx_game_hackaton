#include "DisarmPrompt.h"

#include "DialogueFont.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Rendering/SlateRenderer.h"
#include "Rendering/SlateRenderer.h"

namespace
{
void DrawArc(FSlateWindowElementList& Elements, const FGeometry& Geometry, int32 Layer,
    FVector2D Center, float Radius, float From, float To, const FLinearColor& Color, float Width)
{
    const int32 Segments = FMath::Max(2, FMath::CeilToInt((To - From) * 64.f));
    TArray<FVector2D> Points;
    Points.Reserve(Segments + 1);
    for (int32 Index = 0; Index <= Segments; ++Index)
    {
        const float Angle = 2.f * PI * FMath::Lerp(From, To, float(Index) / Segments) - .5f * PI;
        Points.Add(Center + FVector2D(FMath::Cos(Angle), FMath::Sin(Angle)) * Radius);
    }
    FSlateDrawElement::MakeLines(Elements, Layer, Geometry.ToPaintGeometry(), Points,
        ESlateDrawEffect::None, Color, true, Width);
}
}

void SDisarmPrompt::Construct(const FArguments& Args)
{
    Keys = Args._Keys;
    Step = Args._Step;
    Remaining = Args._Remaining;
    OnKey = Args._OnKey;
    Font = DialogueFont(TEXT("CascadiaCode-Light.otf"), 38);
}

FReply SDisarmPrompt::OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
    if (OnKey.IsBound()) OnKey.Execute(Event.GetKey(), Event.IsRepeat());
    return FReply::Handled();
}

FReply SDisarmPrompt::OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event)
{
    return FReply::Handled().SetUserFocus(SharedThis(this));
}

int32 SDisarmPrompt::OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& CullingRect,
    FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool bEnabled) const
{
    const int32 Index = Step.Get(0);
    if (!Keys.IsValidIndex(Index)) return Layer;

    static const FVector2D Positions[] = {{.40, .62}, {.63, .43}, {.49, .30}, {.35, .43}, {.58, .64}};
    const FVector2D Size = Geometry.GetLocalSize();
    const FVector2D Center = Size * Positions[Index % UE_ARRAY_COUNT(Positions)];
    const float Scale = FMath::Clamp(float(FMath::Min(Size.X, Size.Y)) / 760.f, .62f, 1.45f);
    const float Radius = 48.f * Scale;
    const FLinearColor Paper = FLinearColor::FromSRGBColor(FColor(255, 231, 157));
    const FLinearColor Gold = FLinearColor::FromSRGBColor(FColor(255, 185, 0));
    const FLinearColor Ink(0.023f, 0.016f, 0.008f);
    const float Left = Remaining.Get(0.f);

    FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(FVector2D((Radius + 2.f) * 2.f),
        FSlateLayoutTransform(Center - FVector2D(Radius + 2.f, Radius))),
        &Disk, ESlateDrawEffect::None, Ink.CopyWithNewOpacity(.84f));
    FSlateDrawElement::MakeBox(Elements, Layer + 1, Geometry.ToPaintGeometry(FVector2D(2.f * Radius),
        FSlateLayoutTransform(Center - FVector2D(Radius))), &Disk, ESlateDrawEffect::None, Paper);

    constexpr int32 DashCount = 12;
    for (int32 Dash = 0; Dash < DashCount; ++Dash)
        DrawArc(Elements, Geometry, Layer + 2, Center, Radius - 5.f * Scale,
            float(Dash) / DashCount, (float(Dash) + .63f) / DashCount, Gold, 2.f * Scale);

    const float TimerRadius = Radius + 8.f * Scale;
    DrawArc(Elements, Geometry, Layer + 2, Center, TimerRadius, 0.f, 1.f, Ink.CopyWithNewOpacity(.73f), 6.f * Scale);
    if (Left > 0.f)
        DrawArc(Elements, Geometry, Layer + 3, Center, TimerRadius, 0.f, Left,
            FMath::Lerp(Gold, Paper, .25f), 3.5f * Scale);

    FSlateFontInfo KeyFont = Font;
    KeyFont.Size *= Scale;
    const FVector2D Extent = FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Keys[Index], KeyFont);
    FSlateDrawElement::MakeText(Elements, Layer + 4,
        Geometry.ToPaintGeometry(Extent, FSlateLayoutTransform(Center - Extent * .5)),
        Keys[Index], KeyFont, ESlateDrawEffect::None, Ink);
    return Layer + 4;
}
