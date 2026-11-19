#include "ExplorationHUD.h"
#include "ActOne.h"
#include "DimaApartmentStory.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "EngineGlobals.h"
#include "Fonts/CompositeFont.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "Misc/Paths.h"
#include "Rendering/DrawElements.h"
#include "UObject/UnrealType.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SCompoundWidget.h"
#include <initializer_list>
#if WITH_EDITOR
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphSchema.h"
#include "K2Node_CallFunction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Framework/Application/SlateApplication.h"
#include "Interfaces/ISlateNullRendererModule.h"
#include "Modules/ModuleManager.h"
#include "Types/PaintArgs.h"
#include "Widgets/SWindow.h"
#endif

namespace
{
const FLinearColor ExplorationPaper = FLinearColor::FromSRGBColor(FColor(255, 239, 185));
const FLinearColor ExplorationInk = FLinearColor::FromSRGBColor(FColor(53, 42, 24));
const FLinearColor UsedKey = FLinearColor::FromSRGBColor(FColor(255, 204, 92));
const FSlateRoundedBoxBrush CardBrush(FLinearColor::White, 14.f);
const FSlateRoundedBoxBrush KeyBrush(FLinearColor::White, 5.f);
const FSlateRoundedBoxBrush StaminaCard(
    FLinearColor::FromSRGBColor(FColor(255,249,215)),14.f,
    FLinearColor::FromSRGBColor(FColor(137,97,43)),2.f);

FSlateFontInfo HUDFont(float Size)
{
    static TSharedRef<FCompositeFont> Typeface = []()
    {
        TSharedRef<FCompositeFont> Font = MakeShared<FCompositeFont>();
        Font->DefaultTypeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"),
            FPaths::ProjectContentDir() / TEXT("UI/Dialogue/Fonts/CascadiaCode-Light.otf"),
            EFontHinting::Default, EFontLoadingPolicy::LazyLoad));
        return Font;
    }();
    return FSlateFontInfo(Typeface, Size);
}

FSlateFontInfo StatusFont(float Size,bool bBold=false)
{
    static TSharedRef<FCompositeFont> Typeface=[]()
    {
        TSharedRef<FCompositeFont> Font=MakeShared<FCompositeFont>();
        const FString Directory=FPaths::ProjectContentDir()/TEXT("UI/Dialogue/Fonts");
        Font->DefaultTypeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"),Directory/TEXT("Podkova-Regular.ttf"),EFontHinting::Default,EFontLoadingPolicy::LazyLoad));
        Font->DefaultTypeface.Fonts.Add(FTypefaceEntry(TEXT("Bold"),Directory/TEXT("Podkova-Bold.ttf"),EFontHinting::Default,EFontLoadingPolicy::LazyLoad));
        return Font;
    }();
    return FSlateFontInfo(Typeface,Size,bBold ? FName(TEXT("Bold")) : FName(TEXT("Regular")));
}

class SPaperFrame : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SPaperFrame) {} SLATE_DEFAULT_SLOT(FArguments,Content) SLATE_END_ARGS()
    void Construct(const FArguments& Args) { ChildSlot.Padding(FMargin(17,13,23,15))[Args._Content.Widget]; }
    int32 OnPaint(const FPaintArgs& Args,const FGeometry& Geometry,const FSlateRect& Cull,
        FSlateWindowElementList& Elements,int32 Layer,const FWidgetStyle& Style,bool bEnabled) const override
    {
        const FVector2D Size=Geometry.GetLocalSize();
        const FLinearColor Edge=FLinearColor::FromSRGBColor(FColor(130,94,40));
        const FLinearColor Sheet=FLinearColor::FromSRGBColor(FColor(255,249,215));
        FSlateDrawElement::MakeBox(Elements,Layer,Geometry.ToPaintGeometry(),&CardBrush,ESlateDrawEffect::None,Sheet);
        TArray<FVector2D> Spine={{Size.X-12,11},{Size.X-5,20},{Size.X-5,Size.Y-19},{Size.X-15,Size.Y-8}};
        FSlateDrawElement::MakeLines(Elements,Layer+1,Geometry.ToPaintGeometry(),Spine,ESlateDrawEffect::None,
            FLinearColor::FromSRGBColor(FColor(235,191,102)),true,10.f);
        TArray<FVector2D> Contour;
        constexpr float Radius=14.f;
        const FVector2D Centers[]={{Size.X-Radius-10,Radius+3},{Size.X-Radius-10,Size.Y-Radius-3},
                                  {Radius+3,Size.Y-Radius-3},{Radius+3,Radius+3}};
        for (int32 Corner=0;Corner<4;++Corner)
            for (int32 Point=0;Point<=8;++Point)
            {
                const float Angle=-PI/2+Corner*PI/2+Point*PI/16;
                Contour.Add(Centers[Corner]+FVector2D(FMath::Cos(Angle),FMath::Sin(Angle))*Radius);
            }
        const FVector2D First=Contour[0];
        Contour.Add(First);
        FSlateDrawElement::MakeLines(Elements,Layer+2,Geometry.ToPaintGeometry(),Contour,ESlateDrawEffect::None,Edge,true,2.5f);
        for (int32 Index=0;Index<Contour.Num();++Index)
            Contour[Index]+=FVector2D(FMath::Sin(Index*1.7f)*1.2f,FMath::Cos(Index*1.1f)*1.1f);
        FSlateDrawElement::MakeLines(Elements,Layer+3,Geometry.ToPaintGeometry(),Contour,ESlateDrawEffect::None,Edge.CopyWithNewOpacity(.36f),true,1.f);
        return SCompoundWidget::OnPaint(Args,Geometry,Cull,Elements,Layer+4,Style,bEnabled);
    }
};

class SQuestMarker : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SQuestMarker):_Primary(false){} SLATE_ARGUMENT(bool,Primary) SLATE_END_ARGS()
    void Construct(const FArguments& Args) { bPrimary=Args._Primary; }
    FVector2D ComputeDesiredSize(float) const override { return FVector2D(17,19); }
    int32 OnPaint(const FPaintArgs&,const FGeometry& Geometry,const FSlateRect&,FSlateWindowElementList& Elements,
        int32 Layer,const FWidgetStyle&,bool) const override
    {
        const FLinearColor Gold=FLinearColor::FromSRGBColor(FColor(181,124,35));
        if (!bPrimary)
        {
            static const FSlateRoundedBoxBrush Dot(FLinearColor::White,4.f);
            FSlateDrawElement::MakeBox(Elements,Layer,
                Geometry.ToPaintGeometry(FVector2D(8,8),FSlateLayoutTransform(FVector2D(4,5))),
                &Dot,ESlateDrawEffect::None,Gold);
            return Layer;
        }
        const TArray<FVector2D> Points={{8,1},{15,9},{8,17},{1,9},{8,1}};
        FSlateDrawElement::MakeLines(Elements,Layer,Geometry.ToPaintGeometry(),Points,ESlateDrawEffect::None,
            Gold,true,3.f);
        return Layer;
    }
private:
    bool bPrimary=false;
};

TArray<FVector2f> ClipStaminaStripe(const TArray<FVector2f>& Polygon,float Edge,bool bKeepRight)
{
    TArray<FVector2f> Result;
    if (Polygon.IsEmpty()) return Result;
    const float Sign=bKeepRight ? 1.f : -1.f;
    auto Distance=[Edge,Sign](const FVector2f& Point){ return Sign*(Point.X+.47f*Point.Y-Edge); };
    FVector2f Previous=Polygon.Last();
    float Before=Distance(Previous);
    for (const FVector2f& Point:Polygon)
    {
        const float After=Distance(Point);
        if ((Before>=0)!=(After>=0)) Result.Add(FMath::Lerp(Previous,Point,Before/(Before-After)));
        if (After>=0) Result.Add(Point);
        Previous=Point;
        Before=After;
    }
    return Result;
}

class SStripedStamina : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SStripedStamina) {} SLATE_ATTRIBUTE(float,Fraction) SLATE_END_ARGS()
    void Construct(const FArguments& Args) { Fraction=Args._Fraction; }
    FVector2D ComputeDesiredSize(float) const override { return FVector2D(368,29); }
    int32 OnPaint(const FPaintArgs&,const FGeometry& Geometry,const FSlateRect&,FSlateWindowElementList& Elements,
        int32 Layer,const FWidgetStyle&,bool) const override
    {
        const FVector2D Size=Geometry.GetLocalSize();
        constexpr float Border=2.f;
        const FVector2D Inner=Size-FVector2D(2*Border,2*Border);
        const float Fill=FMath::Clamp(Fraction.Get(1.f),0.f,1.f)*Inner.X;
        static const FSlateRoundedBoxBrush Outline(FLinearColor::White,8.f);
        static const FSlateRoundedBoxBrush Track(FLinearColor::White,6.f);
        const auto TrackGeometry=Geometry.ToPaintGeometry(Inner,FSlateLayoutTransform(FVector2D(Border,Border)));
        FSlateDrawElement::MakeBox(Elements,Layer,Geometry.ToPaintGeometry(),&Outline,ESlateDrawEffect::None,ExplorationInk);
        FSlateDrawElement::MakeBox(Elements,Layer+1,TrackGeometry,&Track,ESlateDrawEffect::None,
            FLinearColor::FromSRGBColor(FColor(24,21,17)));
        if (Fill>0)
        {
            Elements.PushClip(FSlateClippingZone(FSlateRect(Geometry.LocalToAbsolute(FVector2D(Border,Border)),
                Geometry.LocalToAbsolute(FVector2D(Border+Fill,Border+Inner.Y)))));
            FSlateDrawElement::MakeBox(Elements,Layer+2,TrackGeometry,&Track,ESlateDrawEffect::None,
                FLinearColor::FromSRGBColor(FColor(255,248,205)));
            constexpr float Radius=6.f;
            const FVector2f Corners[]={{float(Inner.X)-Radius,Radius},
                {float(Inner.X)-Radius,float(Inner.Y)-Radius},{Radius,float(Inner.Y)-Radius},{Radius,Radius}};
            TArray<FVector2f> Perimeter;
            for (int32 Corner=0;Corner<4;++Corner)
            {
                for (int32 Step=0;Step<=6;++Step)
                {
                    const float Angle=(Corner-1+Step/6.f)*PI*.5f;
                    Perimeter.Add(Corners[Corner]+Radius*FVector2f(FMath::Cos(Angle),FMath::Sin(Angle)));
                }
            }
            TArray<FSlateVertex> Vertices;
            TArray<SlateIndex> Indices;
            for (float X=8.f;X<Inner.X+.47f*Inner.Y;X+=39.f)
            {
                const TArray<FVector2f> Stripe=ClipStaminaStripe(ClipStaminaStripe(Perimeter,X,true),X+19.f,false);
                const SlateIndex Start=Vertices.Num();
                for (const FVector2f& Point:Stripe)
                    Vertices.Add(FSlateVertex::Make(Geometry.GetAccumulatedRenderTransform(),Point+FVector2f(Border,Border),
                        FVector2f(.5f,.5f),FColor(159,105,39)));
                for (int32 Vertex=1;Vertex+1<Stripe.Num();++Vertex)
                {
                    Indices.Add(Start);
                    Indices.Add(Start+Vertex);
                    Indices.Add(Start+Vertex+1);
                }
            }
            if (!Indices.IsEmpty())
                FSlateDrawElement::MakeCustomVerts(Elements,Layer+3,FSlateResourceHandle(),Vertices,Indices,nullptr,0,0);
            Elements.PopClip();
        }
        return Layer+3;
    }
private:
    TAttribute<float> Fraction;
};

class SJournalGlyph : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SJournalGlyph) {} SLATE_END_ARGS()
    void Construct(const FArguments&) {}
    virtual FVector2D ComputeDesiredSize(float Scale) const override { return FVector2D(112, 100); }
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& Cull,
        FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool bEnabled) const override
    {
        const FVector2D Size = Geometry.GetLocalSize();
        const FVector2D Scale(Size.X / 140.0, Size.Y / 120.0);
        const FLinearColor Color = ExplorationInk * Style.GetColorAndOpacityTint();
        auto Stroke = [&](std::initializer_list<FVector2D> Vertices, float Width = 2.f)
        {
            TArray<FVector2D> Points;
            for (const FVector2D& Point : Vertices) Points.Add(Point * Scale);
            FSlateDrawElement::MakeLines(Elements, Layer + 1, Geometry.ToPaintGeometry(), Points,
                ESlateDrawEffect::None, Color, true, Width);
        };
        FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(), &CardBrush,
            ESlateDrawEffect::None, ExplorationPaper * Style.GetColorAndOpacityTint());
        // Two slightly uneven contours and open rings reproduce the notebook in the sketch.
        Stroke({{36,10},{124,13},{122,108},{34,105},{36,10}}, 2.3f);
        Stroke({{40,13},{128,10},{125,110},{36,109}}, 1.f);
        Stroke({{46,16},{45,101}}, 1.f);
        for (int32 Ring = 0; Ring < 4; ++Ring)
        {
            TArray<FVector2D> Points;
            for (int32 Step = 0; Step <= 20; ++Step)
            {
                const float Angle = FMath::DegreesToRadians(35.f + Step * 290.f / 20.f);
                Points.Add(FVector2D(33 + FMath::Cos(Angle) * 15, 25 + Ring * 23 + FMath::Sin(Angle) * 8) * Scale);
            }
            FSlateDrawElement::MakeLines(Elements, Layer + 2, Geometry.ToPaintGeometry(), Points,
                ESlateDrawEffect::None, Color, true, 2.f);
        }
        Stroke({{60,36},{70,33},{78,36},{87,32},{101,35}}, 2.2f);
        Stroke({{58,55},{108,57}}, 1.4f);
        Stroke({{59,70},{100,71}}, 1.4f);
        Stroke({{58,87},{106,88}}, 1.4f);
        return Layer + 2;
    }
};

UExplorationHUDComponent* PresenterFor(AHUD* HUD)
{
    if (!HUD) return nullptr;
    UExplorationHUDComponent* Component = HUD->FindComponentByClass<UExplorationHUDComponent>();
    if (!Component)
    {
        Component = NewObject<UExplorationHUDComponent>(HUD);
        HUD->AddInstanceComponent(Component);
        Component->RegisterComponent();
    }
    return Component;
}
}

TSharedRef<SWidget> UExplorationOverlayWidget::RebuildWidget()
{
    const TWeakObjectPtr<UExplorationHUDComponent> Owner = Presenter;
    auto Key = [Owner](const TCHAR* Label, int32 Index, float Width = 32.f) -> TSharedRef<SWidget>
    {
        return SNew(SBox).WidthOverride(Width).HeightOverride(30)
            [ SNew(SBorder).BorderImage(&KeyBrush).HAlign(HAlign_Center).VAlign(VAlign_Center)
              .BorderBackgroundColor_Lambda([Owner, Index]()
              {
                  return Owner.IsValid() && Owner->HasUsed(Index) ? UsedKey : FLinearColor::FromSRGBColor(FColor(255, 250, 224));
              })
              [ SNew(STextBlock).Text(FText::FromString(Label)).Font(HUDFont(14)).ColorAndOpacity(ExplorationInk) ] ];
    };
    auto Label = [](const FText& Text) -> TSharedRef<SWidget>
    {
        return SNew(STextBlock).Text(Text).Font(HUDFont(15)).ColorAndOpacity(ExplorationInk);
    };
    TSharedRef<SVerticalBox> Tasks=SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,10)
          [SNew(STextBlock).Text(FText::FromString(TEXT("Задачи"))).Font(StatusFont(23,true)).ColorAndOpacity(ExplorationInk)]
        + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,10)
          [SNew(SHorizontalBox)
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(0,2,9,0)[SNew(SQuestMarker).Primary(true)]
            + SHorizontalBox::Slot().FillWidth(1)
              [SNew(STextBlock).Text_Lambda([Owner](){return Owner.IsValid() ? Owner->MainObjective() : FText::GetEmpty();})
                .Font(StatusFont(19,true)).ColorAndOpacity(ExplorationInk).WrapTextAt(263)]];
    for (int32 Index=0;Index<4;++Index)
        Tasks->AddSlot().AutoHeight().Padding(0,5,0,0)
        [SNew(SHorizontalBox)
          .Visibility_Lambda([Owner,Index](){return Owner.IsValid() && Owner->OptionalObjectives().IsValidIndex(Index) ? EVisibility::Visible : EVisibility::Collapsed;})
          + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(0,1,9,0)[SNew(SQuestMarker)]
          + SHorizontalBox::Slot().FillWidth(1)
            [SNew(STextBlock).Text_Lambda([Owner,Index]()
              {
                  const TArray<FText> Side=Owner.IsValid() ? Owner->OptionalObjectives() : TArray<FText>();
                  return Side.IsValidIndex(Index) ? Side[Index] : FText::GetEmpty();
              }).Font(StatusFont(18)).ColorAndOpacity(ExplorationInk).WrapTextAt(263)]];
    return SNew(SConstraintCanvas)
      + SConstraintCanvas::Slot().Anchors(FAnchors(0.045f,0.045f)).AutoSize(true)
        .Offset(FMargin(0)).Alignment(FVector2D::ZeroVector)
        [SNew(SVerticalBox)
          + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,10)
            [SNew(SBox).WidthOverride(330)
              .Visibility_Lambda([Owner](){return Owner.IsValid() && Owner->ShouldShowStatus() ? EVisibility::SelfHitTestInvisible : EVisibility::Collapsed;})
              [SNew(SPaperFrame)[Tasks]]]
          + SVerticalBox::Slot().AutoHeight()
            [SNew(SBox).WidthOverride(330)
              .Visibility_Lambda([Owner](){return Owner.IsValid() && Owner->ShouldShowControls() ? EVisibility::SelfHitTestInvisible : EVisibility::Collapsed;})
              [SNew(SBorder).BorderImage(&CardBrush).BorderBackgroundColor(ExplorationPaper).Padding(16)
                [SNew(SVerticalBox)
                  + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,8)
                    [SNew(SHorizontalBox)
                      + SHorizontalBox::Slot().AutoWidth().Padding(0,0,4,0)[Key(TEXT("W"),0)]
                      + SHorizontalBox::Slot().AutoWidth().Padding(0,0,4,0)[Key(TEXT("A"),1)]
                      + SHorizontalBox::Slot().AutoWidth().Padding(0,0,4,0)[Key(TEXT("S"),2)]
                      + SHorizontalBox::Slot().AutoWidth().Padding(0,0,10,0)[Key(TEXT("D"),3)]
                      + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[Label(FText::FromString(TEXT("Ходьба")))]]
                  + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,8)
                    [SNew(SHorizontalBox)
                      + SHorizontalBox::Slot().AutoWidth().Padding(0,0,10,0)[Key(TEXT("Space"),4,104)]
                      + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[Label(FText::FromString(TEXT("Прыжок")))]]
                  + SVerticalBox::Slot().AutoHeight()
                    [SNew(SHorizontalBox)
                      + SHorizontalBox::Slot().AutoWidth().Padding(0,0,10,0)[Key(TEXT("Shift"),5,104)]
                      + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[Label(FText::FromString(TEXT("Бег")))]]]]]]
      + SConstraintCanvas::Slot().Anchors(FAnchors(0.045f,0.955f)).AutoSize(true)
        .Offset(FMargin(0)).Alignment(FVector2D(0,1))
        [SNew(SBox).WidthOverride(410)
          .Visibility_Lambda([Owner](){return Owner.IsValid() && Owner->ShouldShowStatus() ? EVisibility::SelfHitTestInvisible : EVisibility::Collapsed;})
          [SNew(SBorder).BorderImage(&StaminaCard).Padding(FMargin(18,12,18,14))
            [SNew(SVerticalBox)
              + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,7)
                [SNew(STextBlock).Text(FText::FromString(TEXT("Выносливость"))).Font(StatusFont(23,true)).ColorAndOpacity(ExplorationInk)]
              + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,1)
                [SNew(SStripedStamina).Fraction_Lambda([Owner](){return Owner.IsValid() ? Owner->StaminaFraction() : 1.f;})]]]]
      + SConstraintCanvas::Slot().Anchors(FAnchors(0.955f, 0.06f)).AutoSize(true)
        .Offset(FMargin(0)).Alignment(FVector2D(1,0))
        [ SNew(SVerticalBox)
          + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center) [ SNew(SJournalGlyph) ]
          + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0,8,0,0)
            [ SNew(SBorder).BorderImage(&KeyBrush).BorderBackgroundColor(ExplorationPaper).Padding(FMargin(10,5))
              [ Label(NSLOCTEXT("Dostoevsky", "JournalShortcut", "J — журнал")) ] ] ];
}

UExplorationHUDComponent::UExplorationHUDComponent() { PrimaryComponentTick.bCanEverTick = true; }

bool UExplorationHUDComponent::IsHUDVisible() const
{
    return LastObservedFrame > 0 && GFrameCounter <= LastObservedFrame + 1;
}

bool UExplorationHUDComponent::ShouldShowControls() const
{
    return IsHUDVisible() && bControlsOffered && !Progress.IsComplete();
}

bool UExplorationHUDComponent::ShouldShowStatus() const
{
    return IsHUDVisible() && bControlsOffered;
}

float UExplorationHUDComponent::StaminaFraction() const
{
    const FNumericProperty* Field=FindFProperty<FNumericProperty>(GetOwner()->GetClass(),TEXT("Stamina"));
    return Field ? FMath::Clamp(float(Field->GetFloatingPointPropertyValue(Field->ContainerPtrToValuePtr<void>(GetOwner()))/100),0.f,1.f) : 1.f;
}

FText UExplorationHUDComponent::MainObjective() const
{
    AHUD* HUD=Cast<AHUD>(GetOwner());
    return FText::FromString(UDimaApartmentStoryLibrary::Objective(HUD,TEXT("Осмотреть квартиру")));
}

TArray<FText> UExplorationHUDComponent::OptionalObjectives() const
{
    const UActOneSubsystem* Story=UActOneSubsystem::Find(this);
    return Story ? Story->OptionalObjectives() : TArray<FText>();
}

void UExplorationHUDComponent::ObserveMovementInput(APlayerController* Player)
{
    if (!Player || !Player->IsLocalController() || !IsHUDVisible() || !bControlsOffered ||
        Progress.IsComplete() || Player->IsMoveInputIgnored()) return;
    if (const FBoolProperty* Journal=FindFProperty<FBoolProperty>(GetOwner()->GetClass(),TEXT("JournalOpen")))
        if (Journal->GetPropertyValue_InContainer(GetOwner())) return;
    const FKey Keys[]={EKeys::W,EKeys::A,EKeys::S,EKeys::D,EKeys::SpaceBar,EKeys::LeftShift,EKeys::RightShift};
    for (const FKey& Key:Keys) if (Player->WasInputKeyJustPressed(Key)) Progress.RecordKey(Key);
}

void UExplorationHUDComponent::ObserveHUD(bool bOfferControls)
{
    // The old journal can be drawn by the same HUD; its navigation must not complete movement training.
    if (const FBoolProperty* Journal = FindFProperty<FBoolProperty>(GetOwner()->GetClass(), TEXT("JournalOpen")))
        bOfferControls &= !Journal->GetPropertyValue_InContainer(GetOwner());
    if (LastObservedFrame != GFrameCounter) bControlsOffered = false;
    LastObservedFrame = GFrameCounter;
    bControlsOffered |= bOfferControls;
    AHUD* HUD = Cast<AHUD>(GetOwner());
    APlayerController* Player = HUD ? HUD->GetOwningPlayerController() : nullptr;
    if (!Player || !Player->IsLocalController()) return;
    ObserveMovementInput(Player);
    if (!Overlay)
    {
        Overlay = CreateWidget<UExplorationOverlayWidget>(Player);
        if (!Overlay) return;
        Overlay->Presenter = this;
        Overlay->AddToViewport(15);
    }
    Overlay->SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UExplorationHUDComponent::TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(Delta, TickType, TickFunction);
    // The Blueprint jump branch skips its drawing continuation on the press frame.
    // Keep recording eligible movement actions independently of that Canvas branch.
    AHUD* HUD=Cast<AHUD>(GetOwner());
    ObserveMovementInput(HUD ? HUD->GetOwningPlayerController() : nullptr);
    if (Overlay) Overlay->SetVisibility(IsHUDVisible() ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
}

void UExplorationHUDComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Overlay) { Overlay->RemoveFromParent(); Overlay = nullptr; }
    Super::EndPlay(Reason);
}

void UExplorationHUDLibrary::PresentExplorationHUD(AHUD* HUD, const FString& Text, FLinearColor TextColor, float ScreenX, float ScreenY, UFont* Font, float Scale, bool bScalePosition)
{
    if (UExplorationHUDComponent* Target = PresenterFor(HUD)) Target->ObserveHUD(true);
}

void UExplorationHUDLibrary::PresentJournalHUD(AHUD* HUD, const FString& Text, FLinearColor TextColor, float ScreenX, float ScreenY, UFont* Font, float Scale, bool bScalePosition)
{
    if (UExplorationHUDComponent* Target = PresenterFor(HUD)) Target->ObserveHUD(false);
}

int32 UExplorationHUDLibrary::UpgradeExplorationHUD(UObject* BlueprintAsset)
{
#if WITH_EDITOR
    UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintAsset);
    if (!Blueprint) return -1;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    int32 Count = 0;
    for (UEdGraph* Graph : Graphs)
    {
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
            if (!Call || Call->FunctionReference.GetMemberName() != TEXT("DrawText")) continue;
            UEdGraphPin* Text = Call->FindPin(TEXT("Text"));
            if (!Text || !Text->LinkedTo.IsEmpty()) continue;
            const FString& Value = Text->DefaultValue;
            const bool bControls = Value.Contains(TEXT("WASD")) || (Value.StartsWith(TEXT("E — осмотр")) && Value.Contains(TEXT("J — журнал")));
            const bool bJournal = Value.TrimStartAndEnd() == TEXT("[J]  Журнал");
            if (!bControls && !bJournal) continue;
            Blueprint->Modify();
            Call->Modify();
            Call->SetFromFunction(StaticClass()->FindFunctionByName(bControls
                ? GET_FUNCTION_NAME_CHECKED(UExplorationHUDLibrary, PresentExplorationHUD)
                : GET_FUNCTION_NAME_CHECKED(UExplorationHUDLibrary, PresentJournalHUD)));
            Call->ReconstructNode();
            ++Count;
        }
    }
    if (Count)
    {
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        FKismetEditorUtilities::CompileBlueprint(Blueprint);
    }
    return Blueprint->Status == BS_Error ? -1 : Count;
#else
    return -1;
#endif
}

int32 UExplorationHUDLibrary::UpgradeStatusHUD(UObject* BlueprintAsset)
{
#if WITH_EDITOR
    UBlueprint* Blueprint=Cast<UBlueprint>(BlueprintAsset);
    if (!Blueprint) return -1;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    int32 Removed=0;
    for (UEdGraph* Graph:Graphs)
    {
        const auto Nodes=Graph->Nodes;
        for (UEdGraphNode* Node:Nodes)
        {
            UK2Node_CallFunction* Call=Cast<UK2Node_CallFunction>(Node);
            if (!Call) continue;
            const FName Function=Call->FunctionReference.GetMemberName();
            bool bRemove=false;
            if (Function==TEXT("DrawRect"))
            {
                const UEdGraphPin* X=Call->FindPin(TEXT("ScreenX"));
                const UEdGraphPin* Height=Call->FindPin(TEXT("ScreenH"));
                bRemove=X && Height && X->DefaultValue==TEXT("30") && Height->DefaultValue==TEXT("5");
            }
            if (Function==TEXT("DrawText"))
            {
                const UEdGraphPin* Text=Call->FindPin(TEXT("Text"));
                bRemove=Text && Text->DefaultValue==TEXT("ВЫНОСЛИВОСТЬ");
                if (Text) for (const UEdGraphPin* Source:Text->LinkedTo)
                    if (const UK2Node_CallFunction* Goal=Cast<UK2Node_CallFunction>(Source->GetOwningNode()))
                        bRemove|=Goal->FunctionReference.GetMemberName()==TEXT("Objective");
            }
            if (!bRemove) continue;
            UEdGraphPin* In=Call->FindPin(TEXT("execute"));
            UEdGraphPin* Out=Call->FindPin(TEXT("then"));
            if (!In || !Out) return -1;
            const TArray<UEdGraphPin*> Before=In->LinkedTo;
            const TArray<UEdGraphPin*> After=Out->LinkedTo;
            Blueprint->Modify();
            Graph->Modify();
            In->BreakAllPinLinks();
            Out->BreakAllPinLinks();
            for (UEdGraphPin* Start:Before) for (UEdGraphPin* End:After)
                if (!Graph->GetSchema()->TryCreateConnection(Start,End)) return -1;
            Graph->RemoveNode(Call);
            ++Removed;
        }
    }
    if (Removed)
    {
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        FKismetEditorUtilities::CompileBlueprint(Blueprint);
    }
    return Blueprint->Status==BS_Error ? -1 : Removed;
#else
    return -1;
#endif
}

bool UExplorationHUDLibrary::ValidateExplorationHUD()
{
    const FKey Keys[] = {EKeys::W,EKeys::A,EKeys::S,EKeys::D,EKeys::SpaceBar,EKeys::LeftShift};
    // Missing any one of the six requirements must keep the tutorial visible.
    for (int32 Missing = 0; Missing < 6; ++Missing)
    {
        FExplorationTutorialProgress Progress;
        Progress.RecordKey(EKeys::J);
        Progress.RecordKey(EKeys::E);
        for (int32 Index = 0; Index < 6; ++Index) if (Index != Missing)
        {
            Progress.RecordKey(Keys[Index]);
            Progress.RecordKey(Keys[Index]);
        }
        if (Progress.IsComplete() || Progress.HasUsed(Missing)) return false;
        Progress.RecordKey(Keys[Missing]);
        if (!Progress.IsComplete()) return false;
    }
    FExplorationTutorialProgress RightShift;
    for (int32 Index = 0; Index < 5; ++Index) RightShift.RecordKey(Keys[Index]);
    RightShift.RecordKey(EKeys::RightShift);
    if (!RightShift.IsComplete()) return false;
#if WITH_EDITOR
    if (!FSlateApplication::IsInitialized())
        FSlateApplication::InitializeAsStandaloneApplication(FModuleManager::LoadModuleChecked<ISlateNullRendererModule>(TEXT("SlateNullRenderer")).CreateSlateNullRenderer());
    TSharedRef<SWindow> Window = SNew(SWindow).ClientSize(FVector2D(1280,720));
    TSharedRef<SJournalGlyph> Glyph = SNew(SJournalGlyph);
    const FVector2D Sizes[] = {{112,100},{168,150},{56,50}};
    for (const FVector2D& Size : Sizes)
    {
        FSlateWindowElementList Elements(Window);
        FPaintArgs Args(&Window.Get(), Window->GetHittestGrid(), FVector2D::ZeroVector,0,0);
        Glyph->OnPaint(Args, FGeometry::MakeRoot(Size,FSlateLayoutTransform()),FSlateRect(0,0,Size.X,Size.Y),Elements,0,FWidgetStyle(),true);
    }
#endif
    return true;
}
