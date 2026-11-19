#include "ActOne.h"

#if WITH_EDITOR
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphSchema.h"
#include "Engine/Blueprint.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Input/Events.h"
#include "InputKeyEventArgs.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Misc/Paths.h"
#include "Slate/WidgetRenderer.h"
#include "K2Node_CallFunction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#endif

bool UActOneBlueprintLibrary::UseDynamicObjective(UObject* BlueprintAsset)
{
#if WITH_EDITOR
    UBlueprint* Blueprint=Cast<UBlueprint>(BlueprintAsset);
    if (!Blueprint) return false;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph:Graphs)
    {
        for (UEdGraphNode* Node:Graph->Nodes)
        {
            UK2Node_CallFunction* Call=Cast<UK2Node_CallFunction>(Node);
            if (!Call || Call->FunctionReference.GetMemberName()!=TEXT("SelectString")) continue;
            UEdGraphPin* Location=Call->FindPin(TEXT("A"));
            if (!Location || !Location->DefaultValue.StartsWith(TEXT("Американский квартал"))) continue;
            UEdGraphPin* Goal=Call->FindPin(TEXT("B"));
            UEdGraphPin* Return=Call->FindPin(TEXT("ReturnValue"));
            if (!Goal || Goal->LinkedTo.Num()!=1 || !Return) return false;
            UEdGraphPin* Objective=Goal->LinkedTo[0];
            const TArray<UEdGraphPin*> Consumers=Return->LinkedTo;
            Blueprint->Modify();
            Graph->Modify();
            for (UEdGraphPin* Consumer:Consumers) Return->BreakLinkTo(Consumer);
            for (UEdGraphPin* Consumer:Consumers)
                if (!Graph->GetSchema()->TryCreateConnection(Objective,Consumer)) return false;
            Graph->RemoveNode(Call);
            FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
            FKismetEditorUtilities::CompileBlueprint(Blueprint);
            return Blueprint->Status!=BS_Error;
        }
    }
    return Blueprint->Status!=BS_Error;
#else
    return false;
#endif
}

bool UActOneBlueprintLibrary::SendEditorKey(FName KeyName)
{
#if WITH_EDITOR
    if (!FSlateApplication::IsInitialized()) return false;
    const FKey Key(KeyName);
    if (!Key.IsValid()) return false;
    const FKeyEvent Event(Key,FModifierKeysState(),0,false,0,0);
    FSlateApplication& Slate=FSlateApplication::Get();
    const bool bHandled=Slate.ProcessKeyDownEvent(Event);
    Slate.ProcessKeyUpEvent(Event);
    return bHandled;
#else
    return false;
#endif
}

bool UActOneBlueprintLibrary::CaptureEditorDocument(UDocumentWindow* Window,const FString& FileName)
{
    return CaptureEditorWidget(Window,FileName);
}

bool UActOneBlueprintLibrary::CaptureEditorWidget(UUserWidget* Widget,const FString& FileName)
{
#if WITH_EDITOR
    if (!Widget || !FSlateApplication::IsInitialized()) return false;
    FWidgetRenderer* Renderer=new FWidgetRenderer(true,true);
    UTextureRenderTarget2D* Target=NewObject<UTextureRenderTarget2D>();
    Target->RenderTargetFormat=RTF_RGBA8;
    Target->ClearColor=FLinearColor::Transparent;
    Target->InitAutoFormat(1280,720);
    Target->UpdateResourceImmediate(true);
    Renderer->DrawWidget(Target,Widget->TakeWidget(),FVector2D(1280,720),0);
    if (Target) UKismetRenderingLibrary::ExportRenderTarget(Widget,Target,FPaths::GetPath(FileName),FPaths::GetCleanFilename(FileName));
    BeginCleanup(Renderer);
    return Target!=nullptr;
#else
    return false;
#endif
}

bool UActOneBlueprintLibrary::SendEditorGameKey(APlayerController* Player,FName KeyName,bool bPressed)
{
#if WITH_EDITOR
    const FKey Key(KeyName);
    if (!Player || !Player->IsLocalController() || !Key.IsValid()) return false;
    Player->InputKey(FInputKeyEventArgs::CreateSimulated(Key,bPressed ? IE_Pressed : IE_Released,bPressed ? 1.f : 0.f));
    return true;
#else
    return false;
#endif
}
