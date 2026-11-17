#include "DimaApartmentStory.h"
#include "ActOne.h"
#include "LocationTravel.h"
#include "Engine/Texture2D.h"
#include "InteractionDocument.h"
#include "NarrativeSubsystem.h"
#include "PrologueTimeOfDay.h"
#include "Components/AudioComponent.h"
#include "Components/BoxComponent.h"
#include "Components/LightComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundWave.h"
#include "Styling/CoreStyle.h"
#include "UObject/UnrealType.h"
#include "Widgets/Layout/SBorder.h"

namespace
{
bool Flag(const UObject* Object,FName Name)
{
    const FBoolProperty* Property = Object ? FindFProperty<FBoolProperty>(Object->GetClass(),Name) : nullptr;
    return Property && Property->GetPropertyValue_InContainer(Object);
}
double Number(const UObject* Object,FName Name)
{
    const FNumericProperty* Property = Object ? FindFProperty<FNumericProperty>(Object->GetClass(),Name) : nullptr;
    if (!Property) return 0;
    const void* Value = Property->ContainerPtrToValuePtr<void>(Object);
    return Property->IsFloatingPoint() ? Property->GetFloatingPointPropertyValue(Value) : Property->GetSignedIntPropertyValue(Value);
}
void StopAudio(TObjectPtr<UAudioComponent>& Audio)
{
    if (IsValid(Audio)) { Audio->Stop(); Audio->DestroyComponent(); }
    Audio = nullptr;
}
UDimaApartmentStoryComponent* Story(AHUD* HUD,bool bCreate)
{
    if (!HUD) return nullptr;
    UDimaApartmentStoryComponent* Result = HUD->FindComponentByClass<UDimaApartmentStoryComponent>();
    if (!Result && bCreate)
    {
        Result = NewObject<UDimaApartmentStoryComponent>(HUD);
        HUD->AddInstanceComponent(Result);
        Result->RegisterComponent();
        Result->InitializeStory();
    }
    return Result;
}
}

FReply UDimaStoryDialogueWindow::NativeOnKeyDown(const FGeometry& Geometry,const FKeyEvent& Event)
{
    if (Event.GetKey() == EKeys::E || Event.GetKey() == EKeys::SpaceBar || Event.GetKey() == EKeys::Enter || Event.GetKey() == EKeys::Escape)
    {
        if (!Event.IsRepeat()) RequestClose();
        return FReply::Handled();
    }
    return Super::NativeOnKeyDown(Geometry,Event);
}
TSharedRef<SWidget> UDimaWashOverlay::RebuildWidget()
{
    return SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
        .BorderBackgroundColor(FLinearColor::Black);
}

ADimaStoryFocusProxy::ADimaStoryFocusProxy()
{
    PrimaryActorTick.bCanEverTick = false;
    FocusBox = CreateDefaultSubobject<UBoxComponent>(TEXT("StoryFocus"));
    RootComponent = FocusBox;
    FocusBox->SetBoxExtent(FVector(20));
    FocusBox->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    FocusBox->SetCollisionObjectType(ECC_WorldDynamic);
    FocusBox->SetCollisionResponseToAllChannels(ECR_Ignore);
    FocusBox->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
    FocusBox->SetGenerateOverlapEvents(false);
    FocusBox->SetHiddenInGame(true);
}

UDimaApartmentStoryComponent::UDimaApartmentStoryComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    ScenarioAsset = TSoftObjectPtr<UDimaApartmentScenario>(FSoftObjectPath(TEXT("/Game/Story/DimaApartment/DA_DimaApartmentScenario.DA_DimaApartmentScenario")));
}

void UDimaApartmentStoryComponent::InitializeStory()
{
    if (bInitialized) return;
    bInitialized = true;
    Scenario = ScenarioAsset.LoadSynchronous();
    const AHUD* HUD = Cast<AHUD>(GetOwner());
    Player = HUD ? HUD->GetOwningPlayerController() : nullptr;
    if (!Scenario || !Player.IsValid() || !Player->IsLocalController()) return;
    const FString Level = UGameplayStatics::GetCurrentLevelName(this,true);
    if (Level == TEXT("L_NeptuneStreet") || Level == TEXT("L_PolicePrecinct")) return;
    if (Level == TEXT("L_DimaApartmentInterior"))
    {
        const ULocationTravelSubsystem* Travel = GetWorld()->GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>();
        if (Travel->bHasSnapshot) Progress = Travel->ApartmentProgress;
    }
    bSharedStreet = UGameplayStatics::GetActorOfClass(this, APrologueTimeOfDay::StaticClass()) != nullptr;
    if (!bSharedStreet && UGameplayStatics::GetCurrentLevelName(this,true) != Scenario->ApartmentMap.ToString()) return;
    bActive = true;
    if (bSharedStreet)
    {
        if (ACharacter* Character = Cast<ACharacter>(Player->GetPawn()))
        {
            UCharacterMovementComponent* Movement = Character->GetCharacterMovement();
            Movement->InitialPushForceFactor = 45.f;
            Movement->PushForceFactor = 650.f;
            Movement->MaxTouchForce = 40.f;
        }
    }
    if (Scenario->Ambient)
        AmbientAudio = UGameplayStatics::SpawnSound2D(this,Scenario->Ambient,Scenario->AmbientVolume,1,0,nullptr,false,false);
    // The scenario's floor lamp is broken; other room lights keep their existing behavior.
    TArray<AActor*> Lamps;
    UGameplayStatics::GetAllActorsWithTag(this,TEXT("FloorLampLight"),Lamps);
    for (AActor* Lamp : Lamps) if (ULightComponent* Light = Lamp->FindComponentByClass<ULightComponent>()) Light->SetVisibility(false,true);
}

bool UDimaApartmentStoryComponent::StartDialogue(const TArray<TObjectPtr<UInteractionDocument>>& Documents,FName Inspection,bool bPhone)
{
    if (IsBusy() || Documents.IsEmpty() || !Player.IsValid()) return false;
    for (const UInteractionDocument* Document : Documents) if (!Document) return false;
    Pages = Documents;
    PendingInspection = Inspection;
    PageIndex = 0;
    bPhoneSequence = bPhone;
    bPreviousCursor = Player->bShowMouseCursor;
    bDialogueLocked = true;
    Player->SetIgnoreMoveInput(true);
    Player->SetIgnoreLookInput(true);
    if (ACharacter* Character = Cast<ACharacter>(Player->GetPawn())) Character->GetCharacterMovement()->StopMovementImmediately();
    Player->FlushPressedKeys();
    ShowPage();
    return true;
}

bool UDimaApartmentStoryComponent::ShowDocument(UInteractionDocument* Document,FName Inspection)
{
    TArray<TObjectPtr<UInteractionDocument>> Single;
    Single.Add(Document);
    return StartDialogue(Single,Inspection);
}

void UDimaApartmentStoryComponent::ShowPage()
{
    if (Dialogue) { Dialogue->OnCloseRequested.Unbind(); Dialogue->RemoveFromParent(); Dialogue = nullptr; }
    if (!Player.IsValid() || !Pages.IsValidIndex(PageIndex)) { FinishDialogue(); return; }
    Dialogue = CreateWidget<UDimaStoryDialogueWindow>(Player.Get());
    if (!Dialogue)
    {
        PendingInspection = NAME_None;
        bPhoneSequence = false;
        FinishDialogue();
        return;
    }
    Dialogue->Document = Pages[PageIndex];
    Dialogue->OnCloseRequested.BindUObject(this,&ThisClass::AdvanceDialogue);
    Dialogue->AddToViewport(55);
    Player->bShowMouseCursor = true;
    FInputModeUIOnly Mode;
    Mode.SetWidgetToFocus(Dialogue->TakeWidget());
    Player->SetInputMode(Mode);
    Dialogue->SetKeyboardFocus();
}

void UDimaApartmentStoryComponent::AdvanceDialogue()
{
    if (!bDialogueLocked) return;
    ++PageIndex;
    if (Pages.IsValidIndex(PageIndex)) ShowPage();
    else FinishDialogue();
}

void UDimaApartmentStoryComponent::FinishDialogue()
{
    if (!bDialogueLocked) return;
    if (Dialogue) { Dialogue->OnCloseRequested.Unbind(); Dialogue->RemoveFromParent(); Dialogue = nullptr; }
    Pages.Reset();
    bDialogueLocked = false;
    if (Player.IsValid())
    {
        Player->SetIgnoreMoveInput(false);
        Player->SetIgnoreLookInput(false);
        Player->bShowMouseCursor = bPreviousCursor;
        Player->SetInputMode(FInputModeGameOnly());
        Player->FlushPressedKeys();
    }
    if (!PendingInspection.IsNone()) Progress.Inspect(PendingInspection);
    PendingInspection = NAME_None;
    if (bPhoneSequence) Progress.FinishCall();
    bPhoneSequence = false;
}

void UDimaApartmentStoryComponent::StartWash()
{
    if (IsBusy() || !Player.IsValid()) return;
    bWashing = true;
    WashElapsed = 0;
    Player->SetIgnoreMoveInput(true);
    Player->SetIgnoreLookInput(true);
    if (ACharacter* Character = Cast<ACharacter>(Player->GetPawn())) Character->GetCharacterMovement()->StopMovementImmediately();
    WashOverlay = CreateWidget<UDimaWashOverlay>(Player.Get());
    if (WashOverlay)
    {
        WashOverlay->SetVisibility(ESlateVisibility::HitTestInvisible);
        WashOverlay->SetRenderOpacity(0);
        WashOverlay->AddToViewport(1000);
    }
    if (Scenario->WashWater) WaterAudio = UGameplayStatics::SpawnSound2D(this,Scenario->WashWater,Scenario->WaterVolume,1,0,nullptr,false,false);
}

void UDimaApartmentStoryComponent::FinishWash()
{
    if (!bWashing) return;
    bWashing = false;
    StopAudio(WaterAudio);
    if (WashOverlay) { WashOverlay->RemoveFromParent(); WashOverlay = nullptr; }
    if (Player.IsValid()) { Player->SetIgnoreMoveInput(false); Player->SetIgnoreLookInput(false); Player->FlushPressedKeys(); }
    if (bActive) Progress.Inspect(TEXT("Tap"));
}

void UDimaApartmentStoryComponent::RingPhone()
{
    TArray<AActor*> Phones;
    UGameplayStatics::GetAllActorsWithTag(this,TEXT("Phone"),Phones);
    const FVector Position = !Phones.IsEmpty() ? Phones[0]->GetActorLocation() :
        (Player.IsValid() && Player->GetPawn() ? Player->GetPawn()->GetActorLocation() : GetOwner()->GetActorLocation());
    if (Scenario->PhoneRing)
    {
        USoundAttenuation* Attenuation = NewObject<USoundAttenuation>(this);
        Attenuation->Attenuation.bAttenuate = true;
        Attenuation->Attenuation.bSpatialize = true;
        Attenuation->Attenuation.AttenuationShapeExtents = FVector(250);
        Attenuation->Attenuation.FalloffDistance = 1800;
        RingAudio = UGameplayStatics::SpawnSoundAtLocation(this,Scenario->PhoneRing,Position,FRotator::ZeroRotator,
            Scenario->PhoneVolume,1,0,Attenuation,nullptr,false);
    }
    ShowDocument(Scenario->RingNotice,NAME_None);
}

void UDimaApartmentStoryComponent::Hint(const FText& Text)
{
    if (FStrProperty* Property = FindFProperty<FStrProperty>(GetOwner()->GetClass(),TEXT("Hint")))
        Property->SetPropertyValue_InContainer(GetOwner(),Text.ToString());
    if (FNumericProperty* Property = FindFProperty<FNumericProperty>(GetOwner()->GetClass(),TEXT("HintUntil")))
        if (Property->IsFloatingPoint()) Property->SetFloatingPointPropertyValue(Property->ContainerPtrToValuePtr<void>(GetOwner()),GetWorld()->GetTimeSeconds()+3);
}

bool UDimaApartmentStoryComponent::TryInteract(FName Tag)
{
    InitializeStory();
    if (!bActive) return false;
    if (IsBusy()) return true;
    if (bSharedStreet && Tag == TEXT("StreetDoor"))
    {
        if (Progress.Phase == EDimaApartmentPhase::ReadyToExit)
        {
            if (UGameplayStatics::GetCurrentLevelName(this,true) != TEXT("L_DimaApartmentInterior")) return false;
            GetWorld()->GetGameInstance()->GetSubsystem<UNarrativeSubsystem>()->TravelToStreet(
                TSoftObjectPtr<UWorld>(FSoftObjectPath(TEXT("/Game/Locations/L_NeptuneStreet.L_NeptuneStreet"))),
                NSLOCTEXT("Dostoevsky","BrightonDestination","4-я улица · Брайтон-Бич"),
                LoadObject<UTexture2D>(nullptr,TEXT("/Game/Prologue/Street/Transitions/T_Transition_Neptune.T_Transition_Neptune")),TEXT("FromApartment"));
            return true;
        }
        Hint(FText::FromString(Objective(TEXT("Осмотрите квартиру"))));
        return true;
    }
    if (Tag == TEXT("Exit"))
    {
        if (Progress.Phase != EDimaApartmentPhase::ReadyToExit) { Hint(FText::FromString(Objective(TEXT("Осмотрите квартиру")))); return true; }
        if (Scenario->StreetMap.IsNull()) { Hint(NSLOCTEXT("Dostoevsky","StreetNotAssigned","Следующая локация ещё не подключена.")); return true; }
        GetWorld()->GetGameInstance()->GetSubsystem<UNarrativeSubsystem>()->TravelToStreet(Scenario->StreetMap,
            NSLOCTEXT("Dostoevsky","StreetStoryTitle","Улица Американского квартала"));
        return true;
    }
    if (Tag == TEXT("Phone"))
    {
        if (Progress.Phase == EDimaApartmentPhase::Ringing)
        {
            if (StartDialogue(Scenario->PhoneConversation,NAME_None,true)) { Progress.PickUp(); StopAudio(RingAudio); }
        }
        return true;
    }
    if (Tag == TEXT("FridgeDoor"))
    {
        bWaitingForFridge = !Flag(GetOwner(),TEXT("FridgeDoorToggled")) && !Progress.Inspected.Contains(Tag);
        return false; // Keep the existing animated door and collision checks.
    }
    if (Tag == TEXT("Television")) { ShowDocument(Scenario->Television,Tag); return true; }
    if (Tag == TEXT("Wardrobe")) { ShowDocument(Scenario->Wardrobe,Tag); return true; }
    if (Tag == TEXT("FloorLamp")) { ShowDocument(Scenario->FloorLamp,Tag); return true; }
    if (Tag == TEXT("Tap")) { StartWash(); return true; }
    return false;
}

FString UDimaApartmentStoryComponent::Objective(const FString& Fallback) const
{
    const FString Level = UGameplayStatics::GetCurrentLevelName(this,true);
    if (Level == TEXT("L_NeptuneStreet")) return TEXT("Исследуйте улицу Нептун.");
    if (Level == TEXT("L_PolicePrecinct")) return TEXT("Осмотрите полицейский участок.");
    if (!bActive) return Fallback;
    if (Progress.Phase == EDimaApartmentPhase::ReadyToExit) return Scenario->ExitObjective.ToString();
    if (Progress.Phase == EDimaApartmentPhase::Ringing || Progress.Phase == EDimaApartmentPhase::Calling) return Scenario->PhoneObjective.ToString();
    return Scenario->ExploreObjective.ToString();
}
FString UDimaApartmentStoryComponent::Prompt(FName Tag,const FString& Fallback) const
{
    if (!bActive) return Fallback;
    if (Tag == TEXT("Phone")) return Progress.Phase == EDimaApartmentPhase::Ringing ? TEXT("[E]  Ответить на звонок") : TEXT("Телефон");
    if (bSharedStreet && Tag == TEXT("StreetDoor"))
        return TEXT("[E]  Выйти на улицу");
    if (Tag == TEXT("Exit")) return TEXT("[E]  Выйти на улицу");
    return Fallback;
}

void UDimaApartmentStoryComponent::TickComponent(float Delta,ELevelTick TickType,FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(Delta,TickType,TickFunction);
    if (!bActive || !Player.IsValid()) return;
    AHUD* HUD = Cast<AHUD>(GetOwner());
    if (bSharedStreet && AmbientAudio)
    {
        const bool bNowOutside = UPrologueWorldLibrary::IsOutsideApartment(HUD);
        if (bNowOutside != bOutside)
        {
            bOutside = bNowOutside;
            AmbientAudio->AdjustVolume(.7f, bOutside ? .12f : 1.f, EAudioFaderCurve::SCurve);
        }
    }
    if (Progress.Phase == EDimaApartmentPhase::AwaitingReport && Flag(GetOwner(),TEXT("ReportFound")) && Number(GetOwner(),TEXT("State")) == 0) Progress.FinishReport();
    if (bWashing)
    {
        WashElapsed += Delta;
        const float Duration = FMath::Clamp(Scenario->WashDuration,2.f,3.f);
        const float Opacity = FMath::SmoothStep(0.f, 1.f, FMath::Min(WashElapsed, Duration-WashElapsed) / .32f);
        if (WashOverlay) WashOverlay->SetRenderOpacity(Opacity);
        if (WashElapsed >= Duration) FinishWash();
    }
    if (bWaitingForFridge && !IsBusy() && !Flag(GetOwner(),TEXT("JournalOpen")))
    {
        if (!Flag(GetOwner(),TEXT("FridgeDoorToggled"))) bWaitingForFridge = false;
        else if (Number(GetOwner(),TEXT("FridgeDoorProgress")) >= 0.85)
        {
            bWaitingForFridge = false;
            ShowDocument(Scenario->Fridge,TEXT("FridgeDoor"));
        }
    }
    const bool bModal = bSharedStreet && UPrologueWorldLibrary::IsWorldInteractionModal(HUD);
    if (Progress.TryRing(Scenario->RequiredInspections,IsBusy() || bModal || Flag(GetOwner(),TEXT("JournalOpen")))) RingPhone();
}

void UDimaApartmentStoryComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    // Discard pending completion before teardown; stopping PIE must not advance the story.
    PendingInspection = NAME_None;
    bActive = false;
    bPhoneSequence = false;
    FinishDialogue();
    FinishWash();
    StopAudio(AmbientAudio);
    StopAudio(RingAudio);
    StopAudio(WaterAudio);
    Super::EndPlay(Reason);
}

void UDimaApartmentStoryLibrary::InitializeStory(AHUD* HUD) { Story(HUD,true); }
bool UDimaApartmentStoryLibrary::TryInteract(AHUD* HUD,FName Tag)
{
    UDimaApartmentStoryComponent* Component = Story(HUD,true);
    return Component && Component->TryInteract(Tag);
}
bool UDimaApartmentStoryLibrary::IsBusy(AHUD* HUD)
{
    const UDimaApartmentStoryComponent* Component = Story(HUD,false);
    return Component && Component->IsBusy();
}
FString UDimaApartmentStoryLibrary::Objective(AHUD* HUD,const FString& Fallback)
{
    if (const UActOneSubsystem* Act=UActOneSubsystem::Find(HUD); Act && Act->IsActive() && Act->GetPhase()!=EActOnePhase::Apartment)
        return Act->Objective().ToString();
    const UDimaApartmentStoryComponent* Component = Story(HUD,false);
    return Component ? Component->Objective(Fallback) : Fallback;
}
FString UDimaApartmentStoryLibrary::InteractionPrompt(AHUD* HUD,FName Tag,const FString& Fallback)
{
    const UDimaApartmentStoryComponent* Component = Story(HUD,false);
    return Component ? Component->Prompt(Tag,Fallback) : Fallback;
}

bool UDimaApartmentStoryLibrary::ValidateScenario()
{
    const UDimaApartmentScenario* Data = LoadObject<UDimaApartmentScenario>(nullptr,TEXT("/Game/Story/DimaApartment/DA_DimaApartmentScenario.DA_DimaApartmentScenario"));
    if (!Data || Data->RequiredInspections.Num() != 5 || !Data->Television || !Data->Fridge || !Data->Wardrobe || !Data->FloorLamp || !Data->RingNotice || Data->PhoneConversation.Num() != 9) return false;
    for (const UInteractionDocument* Document : Data->PhoneConversation) if (!Document || Document->Body.IsEmpty()) return false;
    const USoundBase* Sounds[] = {Data->Ambient,Data->PhoneRing,Data->WashWater};
    for (const USoundBase* Sound : Sounds)
    {
        const USoundWave* Wave = Cast<USoundWave>(Sound);
        if (!Wave || !Wave->bLooping || Wave->GetDuration() <= 0) return false;
    }
    // Every missing prerequisite must prevent the ring; duplicates and early pickup cannot bypass it.
    for (int32 Missing=0; Missing<5; ++Missing)
    {
        FDimaApartmentProgress Flow;
        if (Flow.PickUp() || Flow.TryRing(Data->RequiredInspections,false)) return false;
        Flow.FinishReport();
        for (int32 Index=0; Index<5; ++Index) if (Index != Missing)
        {
            Flow.Inspect(Data->RequiredInspections[Index]);
            Flow.Inspect(Data->RequiredInspections[Index]);
        }
        if (Flow.TryRing(Data->RequiredInspections,false)) return false;
        Flow.Inspect(Data->RequiredInspections[Missing]);
        if (Flow.TryRing(Data->RequiredInspections,true) || !Flow.TryRing(Data->RequiredInspections,false)
            || Flow.TryRing(Data->RequiredInspections,false) || !Flow.PickUp() || Flow.PickUp()) return false;
        if (Flow.Phase == EDimaApartmentPhase::ReadyToExit) return false;
        Flow.FinishCall();
        if (Flow.Phase != EDimaApartmentPhase::ReadyToExit || Flow.TryRing(Data->RequiredInspections,false)) return false;
    }
    return true;
}
