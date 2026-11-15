#include "ExplorationHUD.h"
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
#include <initializer_list>
#if WITH_EDITOR
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
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
const FLinearColor Paper = FLinearColor::FromSRGBColor(FColor(255, 239, 185));
const FLinearColor Ink = FLinearColor::FromSRGBColor(FColor(53, 42, 24));
const FLinearColor UsedKey = FLinearColor::FromSRGBColor(FColor(255, 204, 92));
const FSlateRoundedBoxBrush CardBrush(FLinearColor::White, 14.f);
const FSlateRoundedBoxBrush KeyBrush(FLinearColor::White, 5.f);

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
        const FLinearColor Color = Ink * Style.GetColorAndOpacityTint();
        auto Stroke = [&](std::initializer_list<FVector2D> Vertices, float Width = 2.f)
        {
            TArray<FVector2D> Points;
            for (const FVector2D& Point : Vertices) Points.Add(Point * Scale);
            FSlateDrawElement::MakeLines(Elements, Layer + 1, Geometry.ToPaintGeometry(), Points,
                ESlateDrawEffect::None, Color, true, Width);
        };
        FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(), &CardBrush,
            ESlateDrawEffect::None, Paper * Style.GetColorAndOpacityTint());
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
              [ SNew(STextBlock).Text(FText::FromString(Label)).Font(HUDFont(14)).ColorAndOpacity(Ink) ] ];
    };
    auto Label = [](const FText& Text) -> TSharedRef<SWidget>
    {
        return SNew(STextBlock).Text(Text).Font(HUDFont(15)).ColorAndOpacity(Ink);
    };
    return SNew(SConstraintCanvas)
      + SConstraintCanvas::Slot().Anchors(FAnchors(0.045f, 0.06f)).AutoSize(true)
        .Offset(FMargin(0)).Alignment(FVector2D::ZeroVector)
        [ SNew(SBorder).BorderImage(&CardBrush).BorderBackgroundColor(Paper).Padding(16)
          .Visibility_Lambda([Owner]() { return Owner.IsValid() && Owner->ShouldShowControls() ? EVisibility::SelfHitTestInvisible : EVisibility::Collapsed; })
          [ SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,12)
              [ Label(NSLOCTEXT("Dostoevsky", "ControlsTitle", "Управление")) ]
            + SVerticalBox::Slot().AutoHeight()
              [ SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth()
                  [ SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0,0,0,4) [ Key(TEXT("W"),0) ]
                    + SVerticalBox::Slot().AutoHeight()
                      [ SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().AutoWidth().Padding(0,0,4,0) [ Key(TEXT("A"),1) ]
                        + SHorizontalBox::Slot().AutoWidth().Padding(0,0,4,0) [ Key(TEXT("S"),2) ]
                        + SHorizontalBox::Slot().AutoWidth() [ Key(TEXT("D"),3) ] ] ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(14,0,0,0)
                  [ Label(NSLOCTEXT("Dostoevsky", "Movement", "Движение")) ] ]
            + SVerticalBox::Slot().AutoHeight().Padding(0,12,0,0)
              [ SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth() [ Key(TEXT("Space"),4,104) ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(14,0,0,0)
                  [ Label(NSLOCTEXT("Dostoevsky", "Jump", "Прыжок")) ] ]
            + SVerticalBox::Slot().AutoHeight().Padding(0,8,0,0)
              [ SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth() [ Key(TEXT("Shift"),5,104) ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(14,0,0,0)
                  [ Label(NSLOCTEXT("Dostoevsky", "Sprint", "Бег")) ] ]
          ] ]
      + SConstraintCanvas::Slot().Anchors(FAnchors(0.955f, 0.06f)).AutoSize(true)
        .Offset(FMargin(0)).Alignment(FVector2D(1,0))
        [ SNew(SVerticalBox)
          + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center) [ SNew(SJournalGlyph) ]
          + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0,8,0,0)
            [ SNew(SBorder).BorderImage(&KeyBrush).BorderBackgroundColor(Paper).Padding(FMargin(10,5))
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
    // Sample after the existing HUD has processed the seated/free-roam state and player input.
    if (bOfferControls && !Progress.IsComplete() && !Player->IsMoveInputIgnored())
    {
        const FKey Keys[] = {EKeys::W,EKeys::A,EKeys::S,EKeys::D,EKeys::SpaceBar,EKeys::LeftShift,EKeys::RightShift};
        for (const FKey& Key : Keys) if (Player->WasInputKeyJustPressed(Key)) Progress.RecordKey(Key);
    }
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
