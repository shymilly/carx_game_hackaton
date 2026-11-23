#include "DialoguePresentationLibrary.h"
#include "DocumentWindow.h"
#include "InteractionDocument.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "EngineGlobals.h"
#include "InputCoreTypes.h"
#include "UObject/UnrealType.h"
#if WITH_EDITOR
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "K2Node_CallFunction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Slate/WidgetRenderer.h"
#include "ImageUtils.h"
#include "Misc/FileHelper.h"
#include "Serialization/BufferArchive.h"
#include "RenderingThread.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Layout/SBorder.h"
#include "Styling/CoreStyle.h"
#endif

namespace
{
constexpr int32 ApartmentReportState = 9;

bool IsOpeningReport(const AHUD* HUD)
{
    const FIntProperty* State=HUD ? FindFProperty<FIntProperty>(HUD->GetClass(),TEXT("State")) : nullptr;
    return State && State->GetPropertyValue_InContainer(HUD)==ApartmentReportState;
}

ULegacyDialogueBridge* Bridge(AHUD* HUD)
{
    if (!HUD) return nullptr;
    ULegacyDialogueBridge* Result = HUD->FindComponentByClass<ULegacyDialogueBridge>();
    if (!Result)
    {
        Result = NewObject<ULegacyDialogueBridge>(HUD);
        HUD->AddInstanceComponent(Result);
        Result->RegisterComponent();
    }
    return Result;
}
}

ULegacyDialogueBridge::ULegacyDialogueBridge()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void ULegacyDialogueBridge::BeginPanel()
{
    Parts.Reset();
    LastDrawFrame = GFrameCounter;
}

void ULegacyDialogueBridge::Append(const FString& Text)
{
    Parts.Add(Text);
    if (Parts.Num() != 3) return;
    const FString Content = FString::Join(Parts, TEXT("\x1f"));
    if (Window && PreviousContent == Content) return;
    AHUD* HUD = Cast<AHUD>(GetOwner());
    APlayerController* Player = HUD ? HUD->GetOwningPlayerController() : nullptr;
    if (!Player || !Player->IsLocalController()) return;
    if (Window) Window->RemoveFromParent();
    Window = CreateWidget<UDocumentWindow>(Player);
    if (!Window) return;
    UInteractionDocument* Document = NewObject<UInteractionDocument>(Window);
    Document->Title = FText::FromString(Parts[0]);
    Document->Body = FText::FromString(Parts[1]);
    Document->CloseLabel = FText::FromString(Parts[2]);
    Window->Document = Document;
    const bool bOpeningReport=IsOpeningReport(HUD);
    Window->SetVisibility(bOpeningReport ? ESlateVisibility::Visible : ESlateVisibility::HitTestInvisible);
    Window->AddToViewport(40);
    if (bOpeningReport)
    {
        Window->OnKeyInput.BindUObject(this,&ThisClass::HandleReportKey);
        FInputModeGameAndUI Input;
        Input.SetWidgetToFocus(Window->TakeWidget());
        Input.SetHideCursorDuringCapture(false);
        bReportInputFocused = true;
        Player->SetInputMode(Input);
        Window->SetKeyboardFocus();
    }
    PreviousContent = Content;
}

bool ULegacyDialogueBridge::HandleReportKey(const FKey& Key,bool bRepeat)
{
    AHUD* HUD=Cast<AHUD>(GetOwner());
    if (Key!=EKeys::E || !IsOpeningReport(HUD)) return false;
    if (bRepeat) return true;
    if (UFunction* Finish=HUD->FindFunction(TEXT("FinishReport")))
    {
        HUD->ProcessEvent(Finish,nullptr);
        ReleaseReportFocus();
        return true;
    }
    return false;
}

void ULegacyDialogueBridge::ReleaseReportFocus()
{
    if (!bReportInputFocused) return;
    bReportInputFocused = false;
    const AHUD* HUD = Cast<AHUD>(GetOwner());
    if (APlayerController* Player = HUD ? HUD->GetOwningPlayerController() : nullptr)
    {
        if (Player->IsLocalController() && !Player->bShowMouseCursor)
        {
            Player->SetInputMode(FInputModeGameOnly());
        }
    }
}

void ULegacyDialogueBridge::TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(Delta, TickType, TickFunction);
    const bool bStale = GFrameCounter > LastDrawFrame + 1;
    if (bReportInputFocused && (bStale || !IsOpeningReport(Cast<AHUD>(GetOwner()))))
    {
        ReleaseReportFocus();
    }
    if (Window && bStale)
    {
        Window->RemoveFromParent();
        Window = nullptr;
        PreviousContent.Reset();
    }
}

void ULegacyDialogueBridge::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Window) { Window->RemoveFromParent(); Window = nullptr; }
    if (Reason==EEndPlayReason::Destroyed) ReleaseReportFocus();
    Super::EndPlay(Reason);
}

void UDialoguePresentationLibrary::BeginStyledDialogue(AHUD* HUD, FLinearColor RectColor, float ScreenX, float ScreenY, float ScreenW, float ScreenH)
{
    if (ULegacyDialogueBridge* Target = Bridge(HUD)) Target->BeginPanel();
}

void UDialoguePresentationLibrary::AppendStyledDialogue(AHUD* HUD, const FString& Text, FLinearColor TextColor, float ScreenX, float ScreenY, UFont* Font, float Scale, bool bScalePosition)
{
    if (ULegacyDialogueBridge* Target = Bridge(HUD)) Target->Append(Text);
}

int32 UDialoguePresentationLibrary::UpgradeLegacyHUD(UObject* BlueprintAsset)
{
#if WITH_EDITOR
    UBlueprint* Blueprint = Cast<UBlueprint>(BlueprintAsset);
    if (!Blueprint) return -1;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    TArray<TArray<UK2Node_CallFunction*>> Groups;
    for (UEdGraph* Graph : Graphs)
    {
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
            if (!Call || Call->FunctionReference.GetMemberName() != TEXT("DrawRect")) continue;
            UEdGraphPin* Height = Call->FindPin(TEXT("ScreenH"));
            if (!Height || !Height->LinkedTo.IsEmpty() || !FMath::IsNearlyEqual(FCString::Atof(*Height->DefaultValue), 160.f)) continue;
            TArray<UK2Node_CallFunction*> Group;
            Group.Add(Call);
            UK2Node_CallFunction* Current = Call;
            for (int32 Index = 0; Index < 3; ++Index)
            {
                UEdGraphPin* Then = Current->FindPin(TEXT("then"));
                if (!Then || Then->LinkedTo.Num() != 1) break;
                Current = Cast<UK2Node_CallFunction>(Then->LinkedTo[0]->GetOwningNode());
                if (!Current || Current->FunctionReference.GetMemberName() != TEXT("DrawText")) break;
                Group.Add(Current);
            }
            if (Group.Num() == 4) Groups.Add(Group);
        }
    }
    if (Groups.IsEmpty()) return 0;
    Blueprint->Modify();
    UFunction* Begin = StaticClass()->FindFunctionByName(GET_FUNCTION_NAME_CHECKED(UDialoguePresentationLibrary, BeginStyledDialogue));
    UFunction* Append = StaticClass()->FindFunctionByName(GET_FUNCTION_NAME_CHECKED(UDialoguePresentationLibrary, AppendStyledDialogue));
    for (const auto& Group : Groups)
    {
        for (int32 Index = 0; Index < Group.Num(); ++Index)
        {
            Group[Index]->Modify();
            Group[Index]->SetFromFunction(Index == 0 ? Begin : Append);
            Group[Index]->ReconstructNode();
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    return Blueprint->Status == BS_Error ? -1 : Groups.Num();
#else
    return -1;
#endif
}

bool UDialoguePresentationLibrary::ExportDialoguePreview(const FString& OutputFile)
{
#if WITH_EDITOR
    UDocumentWindow* Preview = NewObject<UDocumentWindow>();
    Preview->Initialize();
    UInteractionDocument* Document = NewObject<UInteractionDocument>(Preview);
    Document->Title = FText::FromString(TEXT("Имя персонажа"));
    Document->Body = FText::FromString(TEXT("Текст диалога / dialogue text.\nПроверка кириллицы: Дима, Фёдор, отчёт."));
    Preview->Document = Document;
    TSharedRef<SWidget> Widget = SNew(SOverlay)
        + SOverlay::Slot()
            [ SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                .BorderBackgroundColor(FLinearColor(0.08f, 0.08f, 0.08f)) ]
        + SOverlay::Slot() [ Preview->TakeWidget() ];
    FWidgetRenderer Renderer(true);
    UTextureRenderTarget2D* Target = Renderer.DrawWidget(Widget, FVector2D(1280, 720));
    FlushRenderingCommands();
    FBufferArchive Buffer;
    return Target && FImageUtils::ExportRenderTarget2DAsPNG(Target, Buffer)
        && FFileHelper::SaveArrayToFile(Buffer, *OutputFile);
#else
    return false;
#endif
}
