#include "JournalUI.h"
#include "ActOne.h"
#include "DocumentWindow.h"
#include "InteractionDocument.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Fonts/CompositeFont.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Styling/CoreStyle.h"
#include "UObject/UnrealType.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Text/STextBlock.h"
#if WITH_EDITOR
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "K2Node_CallFunction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#endif

namespace
{
const FLinearColor Paper = FLinearColor::FromSRGBColor(FColor(255,231,157));
const FLinearColor Ink = FLinearColor::Black;

bool Flag(const UObject* State, FName Name)
{
    const FBoolProperty* Property = State ? FindFProperty<FBoolProperty>(State->GetClass(), Name) : nullptr;
    return Property && Property->GetPropertyValue_InContainer(State);
}

bool Available(const UObject* State, const UJournalCatalog* Catalog, int32 Index)
{
    if (!Catalog || !Catalog->Entries.IsValidIndex(Index) || !IsValid(Catalog->Entries[Index].Document)) return false;
    const FName FlagName=Catalog->Entries[Index].DiscoveryFlag;
    const UActOneSubsystem* Act=UActOneSubsystem::Find(State);
    return Flag(State,FlagName) || (Act && Act->HasEvidence(FlagName));
}

enum class EJournalKeyAction { None, Back, Close };
EJournalKeyAction KeyAction(const FKey& Key, bool bHasSelection)
{
    if (Key == EKeys::J) return EJournalKeyAction::Close;
    if (Key == EKeys::Escape) return bHasSelection ? EJournalKeyAction::Back : EJournalKeyAction::Close;
    return EJournalKeyAction::None;
}

FSlateFontInfo JournalFont(float Size)
{
    static TSharedRef<FCompositeFont> Font = []()
    {
        TSharedRef<FCompositeFont> Value = MakeShared<FCompositeFont>();
        Value->DefaultTypeface.Fonts.Add(FTypefaceEntry(TEXT("Regular"),
            FPaths::ProjectContentDir()/TEXT("UI/Dialogue/Fonts/CascadiaCode-Light.otf"),
            EFontHinting::Default, EFontLoadingPolicy::LazyLoad));
        return Value;
    }();
    return FSlateFontInfo(Font, Size);
}

const FButtonStyle& EntryStyle()
{
    static FButtonStyle Style = FButtonStyle()
        .SetNormal(FSlateRoundedBoxBrush(Paper, 8.f))
        .SetHovered(FSlateRoundedBoxBrush(FLinearColor::FromSRGBColor(FColor(255,198,65)), 8.f))
        .SetPressed(FSlateRoundedBoxBrush(FLinearColor::FromSRGBColor(FColor(238,170,35)), 8.f));
    return Style;
}
}

TSharedRef<SWidget> UJournalOverlayWidget::RebuildWidget()
{
    SetIsFocusable(true);
    TSharedRef<SWidget> Root = SNew(SOverlay)
      + SOverlay::Slot()
        [ SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.015f,0.02f,0.03f,0.96f)) ]
      + SOverlay::Slot()
        [ SNew(SConstraintCanvas)
          + SConstraintCanvas::Slot().Anchors(FAnchors(0.045f,0.045f)).AutoSize(true).Offset(FMargin(0))
            [ SNew(STextBlock).Text(NSLOCTEXT("Dostoevsky", "JournalTitle", "Журнал"))
                .Font(JournalFont(26)).ColorAndOpacity(Paper) ]
          + SConstraintCanvas::Slot().Anchors(FAnchors(0.955f,0.045f)).AutoSize(true)
            .Alignment(FVector2D(1,0)).Offset(FMargin(0))
            [ SNew(SButton).ButtonStyle(&EntryStyle()).IsFocusable(false).ContentPadding(FMargin(16,10))
                .OnClicked_Lambda([this]() { if (Presenter.IsValid()) Presenter->CloseJournal(); return FReply::Handled(); })
                [ SNew(STextBlock).Text(NSLOCTEXT("Dostoevsky", "CloseJournal", "Закрыть · J / Esc"))
                    .Font(JournalFont(14)).ColorAndOpacity(Ink) ] ]
          + SConstraintCanvas::Slot().Anchors(FAnchors(0.045f,0.15f,0.67f,0.65f)).Offset(FMargin(0))
            [ SNew(SScrollBox) + SScrollBox::Slot() [ SAssignNew(EntryList,SVerticalBox) ] ] ]
      + SOverlay::Slot() [ SAssignNew(DocumentHost,SBox).Visibility(EVisibility::SelfHitTestInvisible) ];
    RefreshEntries();
    return Root;
}

void UJournalOverlayWidget::RefreshEntries()
{
    if (!EntryList) return;
    EntryList->ClearChildren();
    const TArray<int32> Visible = Presenter.IsValid() ? Presenter->VisibleEntries() : TArray<int32>();
    if (Visible.IsEmpty())
    {
        EntryList->AddSlot().AutoHeight()
            [ SNew(STextBlock).Text(NSLOCTEXT("Dostoevsky", "JournalEmpty", "Осмотрите документ, чтобы добавить его в журнал."))
                .AutoWrapText(true).Font(JournalFont(16)).ColorAndOpacity(Paper) ];
    }
    for (int32 Index : Visible)
    {
        const UInteractionDocument* Document = Presenter->GetEntry(Index);
        if (!Document) continue;
        EntryList->AddSlot().AutoHeight().Padding(0,0,0,10)
            [ SNew(SButton).ButtonStyle(&EntryStyle()).IsFocusable(false).HAlign(HAlign_Left).ContentPadding(FMargin(18,14))
                .OnClicked_Lambda([this,Index]() { if (Presenter.IsValid()) Presenter->SelectEntry(Index); return FReply::Handled(); })
                [ SNew(STextBlock).Text(Document->Title).Font(JournalFont(17)).ColorAndOpacity(Ink).AutoWrapText(true) ] ];
    }
}

void UJournalOverlayWidget::ShowEntry(UInteractionDocument* Document)
{
    if (!Document || !DocumentHost) return;
    ClearSelection();
    SelectedWindow = CreateWidget<UDocumentWindow>(GetOwningPlayer());
    if (!SelectedWindow) return;
    SelectedWindow->Document = Document;
    SelectedWindow->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    SelectedWindow->OnCloseRequested.BindUObject(this, &ThisClass::ClearSelection);
    DocumentHost->SetContent(SelectedWindow->TakeWidget());
    SetKeyboardFocus();
}

void UJournalOverlayWidget::ClearSelection()
{
    if (DocumentHost) DocumentHost->SetContent(SNullWidget::NullWidget);
    if (SelectedWindow) SelectedWindow->OnCloseRequested.Unbind();
    SelectedWindow = nullptr;
    if (IsInViewport()) SetKeyboardFocus();
}

FReply UJournalOverlayWidget::NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
    const EJournalKeyAction Action = KeyAction(Event.GetKey(), HasSelection());
    if (Action == EJournalKeyAction::Back) { ClearSelection(); return FReply::Handled(); }
    if (Action == EJournalKeyAction::Close)
    {
        if (Presenter.IsValid()) Presenter->CloseJournal();
        return FReply::Handled();
    }
    return Super::NativeOnKeyDown(Geometry,Event);
}

void UJournalOverlayWidget::ReleaseSlateResources(bool bReleaseChildren)
{
    Super::ReleaseSlateResources(bReleaseChildren);
    EntryList.Reset();
    DocumentHost.Reset();
}

UJournalPresenterComponent::UJournalPresenterComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    CatalogAsset = TSoftObjectPtr<UJournalCatalog>(FSoftObjectPath(TEXT("/Game/UI/Journal/DA_JournalCatalog.DA_JournalCatalog")));
}

TArray<int32> UJournalPresenterComponent::VisibleEntries() const
{
    TArray<int32> Result;
    if (Catalog) for (int32 Index = 0; Index < Catalog->Entries.Num(); ++Index)
        if (Available(GetOwner(),Catalog,Index)) Result.Add(Index);
    return Result;
}

UInteractionDocument* UJournalPresenterComponent::GetEntry(int32 Index) const
{
    return Available(GetOwner(),Catalog,Index) ? Catalog->Entries[Index].Document.Get() : nullptr;
}

void UJournalPresenterComponent::Present()
{
    if (Overlay || !Flag(GetOwner(),TEXT("JournalOpen"))) return;
    const AHUD* HUD = Cast<AHUD>(GetOwner());
    APlayerController* Player = HUD ? HUD->GetOwningPlayerController() : nullptr;
    if (!Player || !Player->IsLocalController()) return;
    Catalog = CatalogAsset.LoadSynchronous();
    if (!Catalog)
    {
        if (!bWarnedMissingCatalog) UE_LOG(LogTemp,Error,TEXT("Journal catalog missing; assign/cook /Game/UI/Journal/DA_JournalCatalog"));
        bWarnedMissingCatalog = true;
        return;
    }
    Overlay = CreateWidget<UJournalOverlayWidget>(Player);
    if (!Overlay) return;
    ModalPlayer = Player;
    bPreviousCursor = Player->bShowMouseCursor;
    Overlay->Presenter = this;
    Overlay->AddToViewport(60);
    PreviousVisibleEntries = VisibleEntries();
    Player->FlushPressedKeys();
    Player->bShowMouseCursor = true;
    FInputModeUIOnly Mode;
    Mode.SetWidgetToFocus(Overlay->TakeWidget());
    Player->SetInputMode(Mode);
    Overlay->SetKeyboardFocus();
}

void UJournalPresenterComponent::SelectEntry(int32 Index)
{
    if (Overlay) if (UInteractionDocument* Document = GetEntry(Index)) Overlay->ShowEntry(Document);
}

void UJournalPresenterComponent::CloseJournal()
{
    if (!Overlay) return;
    const bool bLegacyLockHeld = Flag(GetOwner(),TEXT("JournalOpen"));
    if (FBoolProperty* Property = FindFProperty<FBoolProperty>(GetOwner()->GetClass(),TEXT("JournalOpen")))
        Property->SetPropertyValue_InContainer(GetOwner(),false);
    Overlay->ClearSelection();
    Overlay->RemoveFromParent();
    Overlay = nullptr;
    if (ModalPlayer.IsValid())
    {
        // The existing opening branch acquires this pair once. Never increment/decrement it every frame.
        if (bLegacyLockHeld)
        {
            ModalPlayer->SetIgnoreMoveInput(false);
            ModalPlayer->SetIgnoreLookInput(false);
        }
        ModalPlayer->bShowMouseCursor = bPreviousCursor;
        ModalPlayer->SetInputMode(FInputModeGameOnly());
        ModalPlayer->FlushPressedKeys();
    }
    ModalPlayer.Reset();
}

void UJournalPresenterComponent::TickComponent(float Delta,ELevelTick TickType,FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(Delta,TickType,TickFunction);
    if (!Overlay) return;
    if (!Flag(GetOwner(),TEXT("JournalOpen"))) { CloseJournal(); return; }
    const TArray<int32> Visible = VisibleEntries();
    if (Visible != PreviousVisibleEntries)
    {
        PreviousVisibleEntries = Visible;
        Overlay->ClearSelection();
        Overlay->RefreshEntries();
    }
}

void UJournalPresenterComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    CloseJournal();
    Super::EndPlay(Reason);
}

void UJournalUILibrary::PresentJournal(AHUD* HUD)
{
    if (!HUD) return;
    UJournalPresenterComponent* Component = HUD->FindComponentByClass<UJournalPresenterComponent>();
    if (!Component)
    {
        Component = NewObject<UJournalPresenterComponent>(HUD);
        HUD->AddInstanceComponent(Component);
        Component->RegisterComponent();
    }
    Component->Present();
}

int32 UJournalUILibrary::UpgradeJournalUI(UObject* BlueprintAsset)
{
#if WITH_EDITOR
    UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintAsset);
    if (!Blueprint) return -1;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    int32 Changed = 0;
    for (UEdGraph* Graph : Graphs) for (UEdGraphNode* Node : Graph->Nodes)
    {
        for (UEdGraphPin* Pin : Node->Pins)
        {
            if (!Pin || Pin->PinType.PinCategory != TEXT("string")) continue;
            FString Text = Pin->DefaultValue;
            const int32 Controls = Text.Find(TEXT("WASD"));
            if (Controls != INDEX_NONE) Text = Text.Left(Controls).TrimEnd();
            else if (Text.StartsWith(TEXT("E — осмотр")) && Text.Contains(TEXT("R — заново"))) Text.Reset();
            if (Text != Pin->DefaultValue) { Node->Modify(); Pin->DefaultValue = Text; ++Changed; }
        }
        UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
        if (!Call || Call->FunctionReference.GetMemberName() != TEXT("DrawRect")) continue;
        UEdGraphPin* Then = Call->FindPin(TEXT("then"));
        if (!Then || Then->LinkedTo.Num() != 1) continue;
        UK2Node_CallFunction* Heading = Cast<UK2Node_CallFunction>(Then->LinkedTo[0]->GetOwningNode());
        UEdGraphPin* Text = Heading ? Heading->FindPin(TEXT("Text")) : nullptr;
        if (!Heading || Heading->FunctionReference.GetMemberName() != TEXT("DrawText") || !Text || Text->DefaultValue != TEXT("ЖУРНАЛ")) continue;
        Call->Modify();
        // Bypass the entire old rendering/number-selection branch; its pure key nodes no longer execute.
        Then->BreakAllPinLinks();
        // These layout inputs belong to DrawRect, not the new full-screen widget call.
        // Explicitly discard them so reconstruction cannot retain linked orphan pins.
        const FName LayoutPins[] = {TEXT("RectColor"),TEXT("ScreenX"),TEXT("ScreenY"),TEXT("ScreenW"),TEXT("ScreenH")};
        for (const FName Name : LayoutPins) if (UEdGraphPin* Pin = Call->FindPin(Name))
        {
            Pin->BreakAllPinLinks();
            Pin->SetSavePinIfOrphaned(false);
        }
        Call->SetFromFunction(StaticClass()->FindFunctionByName(GET_FUNCTION_NAME_CHECKED(UJournalUILibrary,PresentJournal)));
        Call->ReconstructNode();
        ++Changed;
    }
    if (Changed)
    {
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        FKismetEditorUtilities::CompileBlueprint(Blueprint);
    }
    return Blueprint->Status == BS_Error ? -1 : Changed;
#else
    return -1;
#endif
}

bool UJournalUILibrary::ValidateJournalUI()
{
#if WITH_EDITOR
    APlayerController* State = GetMutableDefault<APlayerController>();
    const bool PreviousCursor = State->bShowMouseCursor;
    const bool PreviousClicks = State->bEnableClickEvents;
    ON_SCOPE_EXIT { State->bShowMouseCursor = PreviousCursor; State->bEnableClickEvents = PreviousClicks; };
    UJournalCatalog* Catalog = NewObject<UJournalCatalog>();
    UInteractionDocument* First = NewObject<UInteractionDocument>(Catalog);
    UInteractionDocument* Second = NewObject<UInteractionDocument>(Catalog);
    FJournalEntry Entry;
    Entry.DiscoveryFlag = TEXT("bShowMouseCursor"); Entry.Document = First; Catalog->Entries.Add(Entry);
    Entry.DiscoveryFlag = TEXT("bEnableClickEvents"); Entry.Document = Second; Catalog->Entries.Add(Entry);
    State->bShowMouseCursor = false; State->bEnableClickEvents = false;
    if (Available(State,Catalog,0) || Available(State,Catalog,1)) return false;
    State->bShowMouseCursor = true;
    if (!Available(State,Catalog,0) || Available(State,Catalog,1)) return false;
    State->bEnableClickEvents = true;
    if (!Available(State,Catalog,1) || Available(State,Catalog,-1) || Available(State,Catalog,2)) return false;
    Catalog->Entries[1].DiscoveryFlag = TEXT("UnknownFlag");
    if (Available(State,Catalog,1)) return false;
    State->bShowMouseCursor = false;
    if (Available(State,Catalog,0)) return false;
    const FKey Digits[] = {EKeys::One,EKeys::Two,EKeys::Three,EKeys::Four,EKeys::NumPadOne,EKeys::NumPadTwo,EKeys::NumPadThree,EKeys::NumPadFour};
    for (const FKey& Key : Digits)
        if (KeyAction(Key,false) != EJournalKeyAction::None || KeyAction(Key,true) != EJournalKeyAction::None) return false;
    if (KeyAction(EKeys::J,true) != EJournalKeyAction::Close || KeyAction(EKeys::J,false) != EJournalKeyAction::Close
        || KeyAction(EKeys::Escape,true) != EJournalKeyAction::Back || KeyAction(EKeys::Escape,false) != EJournalKeyAction::Close) return false;
    int32 Closed = 0;
    UDocumentWindow* Window = NewObject<UDocumentWindow>();
    Window->OnCloseRequested.BindLambda([&Closed]() { ++Closed; });
    Window->RequestClose();
    return Closed == 1;
#else
    return false;
#endif
}

bool UJournalUILibrary::ValidateJournalBlueprint(UObject* BlueprintAsset)
{
#if WITH_EDITOR
    const UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintAsset);
    if (!Blueprint || Blueprint->Status == BS_Error || !Blueprint->GeneratedClass) return false;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    int32 Presenters = 0;
    for (UEdGraph* Graph : Graphs) for (UEdGraphNode* Node : Graph->Nodes)
    {
        for (const UEdGraphPin* Pin : Node->Pins)
            if (Pin && Pin->PinType.PinCategory == TEXT("string") && (Pin->DefaultValue.Contains(TEXT("WASD"))
                || (Pin->DefaultValue.StartsWith(TEXT("E — осмотр")) && Pin->DefaultValue.Contains(TEXT("R — заново"))))) return false;
        const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
        if (Call && Call->FunctionReference.GetMemberName() == TEXT("PresentJournal"))
        {
            const UEdGraphPin* Then = Call->FindPin(TEXT("then"));
            if (!Then || !Then->LinkedTo.IsEmpty()) return false;
            ++Presenters;
        }
    }
    const UJournalCatalog* Catalog = LoadObject<UJournalCatalog>(nullptr,TEXT("/Game/UI/Journal/DA_JournalCatalog.DA_JournalCatalog"));
    if (Presenters != 1 || !Catalog || Catalog->Entries.IsEmpty()) return false;
    const UActOneData* Story = LoadObject<UActOneData>(nullptr,TEXT("/Game/Story/ActOne/DA_ActOne.DA_ActOne"));
    for (const FJournalEntry& Entry : Catalog->Entries)
    {
        if (!Entry.Document) return false;
        if (Story && Story->Documents.FindRef(Entry.DiscoveryFlag)==Entry.Document) continue;
        if (!FindFProperty<FBoolProperty>(Blueprint->GeneratedClass,Entry.DiscoveryFlag)) return false;
    }
    return true;
#else
    return false;
#endif
}
