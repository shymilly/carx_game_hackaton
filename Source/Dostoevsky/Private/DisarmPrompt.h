#pragma once

#include "Brushes/SlateRoundedBoxBrush.h"
#include "DocumentWindow.h"
#include "Fonts/SlateFontInfo.h"
#include "Widgets/SLeafWidget.h"

class SDisarmPrompt final : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SDisarmPrompt) {}
        SLATE_ARGUMENT(TArray<FText>, Keys)
        SLATE_ATTRIBUTE(int32, Step)
        SLATE_ATTRIBUTE(float, Remaining)
        SLATE_EVENT(FDocumentKeyInput, OnKey)
    SLATE_END_ARGS()

    void Construct(const FArguments& Args);
    virtual bool SupportsKeyboardFocus() const override { return true; }
    virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
    virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& CullingRect,
        FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool bEnabled) const override;

protected:
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }
    virtual bool ComputeVolatility() const override { return true; }

private:
    TArray<FText> Keys;
    TAttribute<int32> Step;
    TAttribute<float> Remaining;
    FDocumentKeyInput OnKey;
    FSlateFontInfo Font;
    const FSlateRoundedBoxBrush Disk{FLinearColor::White};
};
