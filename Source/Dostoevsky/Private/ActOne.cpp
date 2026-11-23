#include "ActOne.h"

#include "ActOneScene.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/SplineComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "InteractionDocument.h"
#include "Kismet/GameplayStatics.h"
#include "LocationTravel.h"
#include "NarrativeSubsystem.h"
#include "Sound/SoundBase.h"
#include "UObject/UnrealType.h"

namespace
{
const FName Clues[]={TEXT("FedorFolder"),TEXT("FedorTape"),TEXT("FedorPhoto"),TEXT("FedorBadge")};
const FKey DisarmKeys[]={EKeys::Q,EKeys::E,EKeys::F};
const TCHAR* DisarmLabels[]={TEXT("Q"),TEXT("E"),TEXT("F")};
constexpr float LockTargets[]={.31f,.68f,.47f};
constexpr float LockWindow=.075f;
constexpr float LockCycle=1.55f;

FText Text(const TCHAR* Value) { return FText::FromString(Value); }
bool Flag(AHUD* HUD,FName Name)
{
    const FBoolProperty* Field=HUD ? FindFProperty<FBoolProperty>(HUD->GetClass(),Name) : nullptr;
    return Field && Field->GetPropertyValue_InContainer(HUD);
}
}

UActOneSubsystem* UActOneSubsystem::Find(const UObject* Context)
{
    const UWorld* World=Context ? Context->GetWorld() : nullptr;
    UGameInstance* GI=World ? World->GetGameInstance() : nullptr;
    return GI ? GI->GetSubsystem<UActOneSubsystem>() : nullptr;
}

APlayerController* UActOneSubsystem::Player() const
{
    return Director.IsValid() ? UGameplayStatics::GetPlayerController(Director.Get(),0) : nullptr;
}

UNarrativeSubsystem* UActOneSubsystem::UI() const
{
    return GetGameInstance()->GetSubsystem<UNarrativeSubsystem>();
}

UInteractionDocument* UActOneSubsystem::Doc(FName Id) const
{
    const TObjectPtr<UInteractionDocument>* Entry=Data ? Data->Documents.Find(Id) : nullptr;
    if (!Entry || !IsValid(Entry->Get())) UE_LOG(LogTemp,Error,TEXT("ACT_ONE_MISSING_DOCUMENT %s"),*Id.ToString());
    return Entry ? Entry->Get() : nullptr;
}

EActOneLocation UActOneSubsystem::Place() const
{
    return Director.IsValid() ? Director->Location : EActOneLocation::Apartment;
}

void UActOneSubsystem::Arrive(AActOneDirector* Scene)
{
    Director=Scene;
    Data=Scene->Data;
    if (Phase==EActOnePhase::Apartment)
    {
        switch (Place())
        {
        case EActOneLocation::Street: case EActOneLocation::Grocery: Phase=EActOnePhase::Cigarettes; break;
        case EActOneLocation::Bar: Phase=EActOnePhase::Bar; break;
        case EActOneLocation::Precinct: Phase=EActOnePhase::Precinct; break;
        case EActOneLocation::Entrance: Phase=EActOnePhase::FedorEntrance; break;
        case EActOneLocation::Fedor: Phase=EActOnePhase::Search; break;
        case EActOneLocation::Alley: Phase=EActOnePhase::Chase; break;
        default: break;
        }
    }
    bClosingStarted=false;
    RefreshScene();
}

void UActOneSubsystem::Leave(AActOneDirector* Scene)
{
    if (Director.Get()!=Scene) return;
    Scene->GetWorldTimerManager().ClearTimer(SceneTimer);
    Scene->GetWorldTimerManager().ClearTimer(ChallengeTimer);
    if (bCinematic)
    {
        if (APlayerController* PC=Player())
        {
            PC->SetIgnoreMoveInput(false);
            PC->SetIgnoreLookInput(false);
        }
        bCinematic=false;
    }
    Lines.Reset();
    AfterLines.Unbind();
    Challenge=EChallenge::None;
    LiveDocument=nullptr;
    Director.Reset();
}

void UActOneSubsystem::Reset()
{
    if (Director.IsValid()) Leave(Director.Get());
    Phase=EActOnePhase::Apartment;
    Stats={};
    Evidence.Reset();
    bPressOpen=bVeteranDone=bVeteranFled=bPistol=bOldManFled=bGuardResolved=bArchives=bLockpickTraining=false;
    bGuardKilled=false;
    bIvanKey=bAlarm=bFloorboardOpen=bDrawerOpen=bBankKey=bAgentEscaped=bIvanSpoken=bClosingStarted=false;
    bLobbyOpened=bIvanEntered=bIvanArrived=bTripStarted=bTripRecovered=false;
    Cash=20;
    ChasePosition=0;
    ChaseSpeed=0;
    Step=0;
    Data=nullptr;
}

FText UActOneSubsystem::Objective() const
{
    switch (Phase)
    {
    case EActOnePhase::Apartment: return FText::GetEmpty();
    case EActOnePhase::Cigarettes: return Text(TEXT("Купить сигареты"));
    case EActOnePhase::Smoke: return Text(TEXT("Выйти из магазина"));
    case EActOnePhase::BarCall: return Text(TEXT("Зайти в бар «Маяк»"));
    case EActOnePhase::Bar: return Text(TEXT("Разобраться с дебошем"));
    case EActOnePhase::Precinct: return Place()==EActOneLocation::Precinct
        ? Text(TEXT("Поговорить с капитаном Криллом")) : Text(TEXT("Явиться в полицейский участок"));
    case EActOnePhase::CaptainDone: return Text(TEXT("Выйти из участка"));
    case EActOnePhase::MeetIvan: return Text(TEXT("Поговорить с Иваном"));
    case EActOnePhase::FedorEntrance:
        if (Place()==EActOneLocation::Entrance)
            return bLobbyOpened ? Text(TEXT("Подняться к квартире Фёдора на 4-й этаж")) : Text(TEXT("Войти в подъезд Фёдора"));
        return Text(TEXT("Тайком пробраться в квартиру отца"));
    case EActOnePhase::Search:
        if (bBankKey) return Text(TEXT("Выбежать за агентом Aegis"));
        if (HasEvidence(Clues[0])&&HasEvidence(Clues[1])&&HasEvidence(Clues[2])&&HasEvidence(Clues[3]))
            return Text(TEXT("Поговорить с Иваном"));
        return Text(TEXT("Осмотреть квартиру отца"));
    case EActOnePhase::Chase:
        if (bAgentEscaped && bTripRecovered) return Text(TEXT("Подобрать значок Aegis"));
        return bAgentEscaped ? Text(TEXT("Продолжить погоню")) : Text(TEXT("Догнать агента"));
    case EActOnePhase::Finale: return Text(TEXT("Прослушать кассету"));
    case EActOnePhase::Complete: return Text(TEXT("Акт завершён"));
    }
    return FText::GetEmpty();
}

bool UActOneSubsystem::CanUseDisposition(int32 MinimumCalm,int32 MinimumAnger,int32 MaximumCalm,int32 MaximumAnger) const
{
    return Stats.Calm>=MinimumCalm && Stats.Calm<=MaximumCalm &&
        Stats.Anger>=MinimumAnger && Stats.Anger<=MaximumAnger;
}

TArray<FText> UActOneSubsystem::OptionalObjectives() const
{
    TArray<FText> Result;
    if (Place()==EActOneLocation::Apartment && Phase==EActOnePhase::Apartment && !bPistol)
        Result.Add(Text(TEXT("Взять служебный пистолет")));
    if (Place()==EActOneLocation::Street && Phase<=EActOnePhase::BarCall)
    {
        if (!HasEvidence(TEXT("BrightonNewspaper"))) Result.Add(Text(TEXT("Прочитать свежую газету")));
        if (!HasEvidence(TEXT("LizaCall"))) Result.Add(Text(TEXT("Позвонить Лизе в Москву")));
        if (!bVeteranDone) Result.Add(Text(TEXT("Поговорить с ветераном")));
    }
    if (Place()==EActOneLocation::Precinct && Phase<=EActOnePhase::CaptainDone)
    {
        if (!HasEvidence(TEXT("FedorMissing"))) Result.Add(Text(TEXT("Осмотреть доску розыска")));
        if (!bLockpickTraining) Result.Add(Text(TEXT("Изучить учебную карточку")));
        if (bArchives && !HasEvidence(TEXT("AegisArchive"))) Result.Add(Text(TEXT("Посмотреть архивную опись")));
    }
    return Result;
}

bool UActOneSubsystem::IsRain() const
{
    return Place()==EActOneLocation::Entrance || Place()==EActOneLocation::Alley ||
        (Place()==EActOneLocation::Street && Phase>=EActOnePhase::MeetIvan);
}

void UActOneSubsystem::RefreshScene()
{
    if (!Director.IsValid()) return;
    const bool bAllClues=HasEvidence(Clues[0])&&HasEvidence(Clues[1])&&HasEvidence(Clues[2])&&HasEvidence(Clues[3]);
    for (const auto& Target:Director->Interactions())
    {
        if (!Target.IsValid()) continue;
        bool bAvailable=true;
        switch (Target->Action)
        {
        case EActOneAction::Pistol: bAvailable=!bPistol && Phase<=EActOnePhase::BarCall; break;
        case EActOneAction::Newspaper: bAvailable=bPressOpen; break;
        case EActOneAction::Veteran: bAvailable=!bVeteranFled; break;
        case EActOneAction::Cigarettes: bAvailable=Phase==EActOnePhase::Cigarettes; break;
        case EActOneAction::Guard: bAvailable=Phase==EActOnePhase::Bar && !bGuardResolved; break;
        case EActOneAction::Archives: bAvailable=bArchives; break;
        case EActOneAction::IvanStreet: bAvailable=Phase==EActOnePhase::MeetIvan; break;
        case EActOneAction::Ride: bAvailable=Phase==EActOnePhase::FedorEntrance; break;
        case EActOneAction::BuildingEntry: bAvailable=Phase==EActOnePhase::FedorEntrance && !bLobbyOpened; break;
        case EActOneAction::Floorboard: bAvailable=!bFloorboardOpen; break;
        case EActOneAction::Folder: bAvailable=bFloorboardOpen; break;
        case EActOneAction::Drawer: bAvailable=!bDrawerOpen; break;
        case EActOneAction::DeskBadge: bAvailable=bDrawerOpen; break;
        case EActOneAction::IvanFedor: bAvailable=bAllClues && bIvanArrived && !bBankKey; break;
        case EActOneAction::ChaseBadge: bAvailable=bAgentEscaped && bTripRecovered && Phase==EActOnePhase::Chase; break;
        default: break;
        }
        Target->SetAvailable(bAvailable);
    }
    if (Place()==EActOneLocation::Street)
    {
        Director->Show(TEXT("IvanStreet"),Phase==EActOnePhase::MeetIvan);
        if (bVeteranFled) Director->Show(TEXT("Veteran"),false);
    }
    if (Place()==EActOneLocation::Apartment) Director->Show(TEXT("Pistol"),!bPistol && Phase<=EActOnePhase::BarCall);
    if (Place()==EActOneLocation::Bar && bGuardResolved && !bCinematic)
    {
        Director->Pose(TEXT("BarGuard"),bGuardKilled ? EActOnePose::Dead : EActOnePose::Subdued);
        Director->Show(TEXT("GuardWeapon"),false);
        Director->Show(TEXT("DroppedWeapon"),true);
    }
    if (Place()==EActOneLocation::Fedor)
    {
        Director->Show(TEXT("IvanFedor"),bIvanEntered);
        if (!bBankKey) Director->Show(TEXT("FedorListener"),false);
        Director->Show(TEXT("DeskBadgeProp"),bDrawerOpen&&!HasEvidence(TEXT("FedorBadge")));
    }
    if (Place()==EActOneLocation::Alley) Director->Show(TEXT("ChaseBadge"),bAgentEscaped && bTripRecovered);
    Director->SetRain(IsRain());
}

bool UActOneSubsystem::Travel(const TCHAR* To,const TCHAR* Title,FName Spawn,const AActor* OpeningDoor)
{
    const TObjectPtr<UTexture2D>* Photo=Data ? Data->Photos.Find(FName(To)) : nullptr;
    const FString Asset=FString::Printf(TEXT("/Game/Locations/%s.%s"),To,To);
    if (UI()->TravelToStreet(TSoftObjectPtr<UWorld>(FSoftObjectPath(Asset)),Text(Title),Photo ? Photo->Get() : nullptr,Spawn,OpeningDoor))
        return true;
    Hint(Text(TEXT("Переход недоступен. Повторите попытку.")));
    return false;
}

void UActOneSubsystem::Hint(const FText& Message,float Seconds) const
{
    AHUD* HUD=Player() ? Player()->GetHUD() : nullptr;
    if (!HUD) return;
    if (FStrProperty* Field=FindFProperty<FStrProperty>(HUD->GetClass(),TEXT("Hint")))
        Field->SetPropertyValue_InContainer(HUD,Message.ToString());
    if (FNumericProperty* Until=FindFProperty<FNumericProperty>(HUD->GetClass(),TEXT("HintUntil")))
        Until->SetFloatingPointPropertyValue(Until->ContainerPtrToValuePtr<void>(HUD),HUD->GetWorld()->GetTimeSeconds()+Seconds);
}

void UActOneSubsystem::AddEvidence(FName Id,bool bShow)
{
    Evidence.Add(Id);
    if (bShow) Notice(Id);
}

void UActOneSubsystem::Notice(FName Page)
{
    Say({Page});
}

void UActOneSubsystem::Say(TArray<FName> Pages,FSimpleDelegate Done)
{
    Lines=MoveTemp(Pages);
    Line=0;
    AfterLines=MoveTemp(Done);
    NextLine();
}

void UActOneSubsystem::NextLine()
{
    UI()->CloseDocument();
    if (Lines.IsValidIndex(Line))
    {
        const FName PageId=Lines[Line++];
        Director->SetSpeaker(Data->PageSpeakers.FindRef(PageId));
        UInteractionDocument* Page=Doc(PageId);
        if (Page && UI()->ShowStoryPage(Player(),Page,FSimpleDelegate::CreateUObject(this,&ThisClass::NextLine))) return;
        Lines.Reset();
    }
    FSimpleDelegate Done=MoveTemp(AfterLines);
    Director->SetSpeaker(NAME_None);
    Lines.Reset();
    Done.ExecuteIfBound();
}

void UActOneSubsystem::Ask(FName Page,TArray<FText> Choices,FDocumentChoice Choice)
{
    Director->SetSpeaker(Data->PageSpeakers.FindRef(Page));
    UI()->ShowRequiredChoices(Player(),Doc(Page),MoveTemp(Choices),
        FDocumentChoice::CreateWeakLambda(this,[this,Choice=MoveTemp(Choice)](int32 Value)
        {
            UI()->CloseDocument();
            Director->SetSpeaker(NAME_None);
            Choice.ExecuteIfBound(Value);
        }));
}

void UActOneSubsystem::PlayAudio(FName Id,float Volume) const
{
    if (const TObjectPtr<USoundBase>* Sound=Data ? Data->Sounds.Find(Id) : nullptr)
        UGameplayStatics::PlaySound2D(Director.Get(),Sound->Get(),Volume);
}

void UActOneSubsystem::Timed(float Seconds,FSimpleDelegate End)
{
    if (!Director.IsValid() || !Player()) return;
    bCinematic=true;
    Player()->SetIgnoreMoveInput(true);
    Player()->SetIgnoreLookInput(true);
    if (ACharacter* Character=Cast<ACharacter>(Player()->GetPawn())) Character->GetCharacterMovement()->StopMovementImmediately();
    Director->GetWorldTimerManager().SetTimer(SceneTimer,FTimerDelegate::CreateUObject(this,&ThisClass::EndTimed,MoveTemp(End)),Seconds,false);
}

void UActOneSubsystem::EndTimed(FSimpleDelegate End)
{
    if (APlayerController* PC=Player())
    {
        PC->SetIgnoreMoveInput(false);
        PC->SetIgnoreLookInput(false);
        PC->FlushPressedKeys();
    }
    bCinematic=false;
    End.ExecuteIfBound();
}

void UActOneSubsystem::Update(float DeltaSeconds)
{
    APlayerController* PC=Player();
    if (!IsActive() || !PC || !PC->GetHUD() || UI()->IsLocationTransitionActive()) return;
    if (Phase==EActOnePhase::Smoke && Place()==EActOneLocation::Street && !bCinematic && !bClosingStarted)
    {
        bClosingStarted=true;
        Director->StartSmoke();
        PlayAudio(TEXT("Lighter"),.7f);
        Timed(2.55f,FSimpleDelegate::CreateUObject(this,&ThisClass::Dispatch));
    }
    if (Phase==EActOnePhase::Chase && Place()==EActOneLocation::Alley && (!bAgentEscaped || !bTripStarted))
        UpdatePursuit(DeltaSeconds);
    if (Phase==EActOnePhase::Search && Place()==EActOneLocation::Fedor && bIvanEntered && !bIvanArrived)
        UpdateFedorArrival();
    if (Phase==EActOnePhase::Precinct && Place()==EActOneLocation::Precinct && !bClosingStarted)
    {
        bClosingStarted=true;
        if (AActOneCast* Officer=Cast<AActOneCast>(Director->Cue(TEXT("DutyOfficer")))) Officer->Nod();
    }
    if (Phase==EActOnePhase::Finale && Place()==EActOneLocation::Apartment && !bClosingStarted && !UI()->IsDocumentOpen())
        Finale();
}

void UActOneSubsystem::Dispatch()
{
    Director->StopSmoke();
    Stats.Calm+=1;
    Phase=EActOnePhase::BarCall;
    Say({TEXT("DispatchBar"),TEXT("Disposition")});
}

void UActOneSubsystem::ShowStatus()
{
    APlayerController* PC = Player();
    if (!IsActive() || !PC || !PC->GetPawn() || PC->GetViewTarget() != PC->GetPawn() ||
        PC->IsMoveInputIgnored() || Flag(PC->GetHUD(), TEXT("JournalOpen")) ||
        UI()->IsDocumentOpen() || UI()->IsLocationTransitionActive()) return;

    const UInteractionDocument* Guidance = Doc(TEXT("Disposition"));
    UI()->ShowCharacterNotebook(PC, Stats, Cash, Guidance ? Guidance->Body : FText::GetEmpty());
}

bool UActOneSubsystem::HandlePortal(const AStreetPortal& Portal)
{
    if (!IsActive()) return false;
    if (Portal.ActorHasTag(TEXT("ActPrecinctEntry")) && Phase<EActOnePhase::Precinct)
    {
        Hint(Objective());
        return true;
    }
    if (Portal.ActorHasTag(TEXT("ActPrecinctExit")) && Phase==EActOnePhase::CaptainDone)
    {
        if (Travel(TEXT("L_NeptuneStreet"),TEXT("4th Brighton beach"),TEXT("FromPrecinct"),&Portal))
            Phase=EActOnePhase::MeetIvan;
        return true;
    }
    return false;
}

bool AActOneInteraction::Use(APlayerController* Player) const
{
    UActOneSubsystem* Act=UActOneSubsystem::Find(this);
    if (!Act || !Player || !Player->IsLocalController() || !Player->GetPawn() || Player->GetViewTarget()!=Player->GetPawn() ||
        Player->IsMoveInputIgnored() || !GetActorEnableCollision() ||
        FVector::DistSquared(Player->GetPawn()->GetActorLocation(),GetActorLocation())>FMath::Square(308.0)) return false;
    return Act->Use(*this,Player);
}

void AActOneInteraction::SetAvailable(bool bAvailable)
{
    SetActorEnableCollision(bAvailable);
}

bool UActOneSubsystem::Use(const AActOneInteraction& Item,APlayerController* User)
{
    if (!IsActive() || User!=Player() || UI()->IsDocumentOpen() || UI()->IsLocationTransitionActive() ||
        bCinematic || Flag(User->GetHUD(),TEXT("JournalOpen"))) return false;
    switch (Item.Action)
    {
    case EActOneAction::Pistol:
        if (!bPistol) {bPistol=true; Director->Show(TEXT("Pistol"),false); Notice(TEXT("Pistol")); RefreshScene();}
        break;
    case EActOneAction::Press: bPressOpen=true; Notice(TEXT("Vendor")); RefreshScene(); break;
    case EActOneAction::Newspaper: if (bPressOpen) AddEvidence(TEXT("BrightonNewspaper")); break;
    case EActOneAction::PayPhone:
        Ask(TEXT("PayPhone"),{Text(TEXT("Позвонить Лизе")),Text(TEXT("Позвонить матери"))},
            FDocumentChoice::CreateWeakLambda(this,[this](int32 Index){CallFromPayphone(Index==1);}));
        break;
    case EActOneAction::Veteran: if (!bVeteranDone) AskVeteran(); else Hint(Text(TEXT("Старик больше ничего не говорит."))); break;
    case EActOneAction::Grocery:
        if (Phase==EActOnePhase::Cigarettes) Travel(TEXT("L_BrightonGrocery"),TEXT("Продукты"),TEXT("ActEntry"),&Item);
        else Hint(Text(TEXT("Сигареты уже куплены.")));
        break;
    case EActOneAction::LeaveGrocery: Travel(TEXT("L_NeptuneStreet"),TEXT("4th Brighton beach"),TEXT("FromGrocery"),&Item); break;
    case EActOneAction::Cigarettes:
        if (Phase==EActOnePhase::Cigarettes && Travel(TEXT("L_NeptuneStreet"),TEXT("4th Brighton beach"),TEXT("FromGrocery")))
            Phase=EActOnePhase::Smoke;
        break;
    case EActOneAction::Bar:
        if (Phase==EActOnePhase::BarCall || Phase==EActOnePhase::Bar)
        {
            if (Travel(TEXT("L_LighthouseBar"),TEXT("Бар «Маяк»"),TEXT("ActEntry"),&Item)) Phase=EActOnePhase::Bar;
        }
        else Hint(Objective());
        break;
    case EActOneAction::LeaveBar:
        if (Phase==EActOnePhase::Precinct) Travel(TEXT("L_NeptuneStreet"),TEXT("4th Brighton beach"),TEXT("FromBar"),&Item);
        else Hint(Text(TEXT("Сначала нужно разобраться с дебошем.")));
        break;
    case EActOneAction::Guard: if (Phase==EActOnePhase::Bar && !bGuardResolved) StartBar(); break;
    case EActOneAction::Missing: AddEvidence(TEXT("FedorMissing")); break;
    case EActOneAction::Office:
        Director->OpenDoor(TEXT("OfficeLeaf"),90.f);
        break;
    case EActOneAction::Captain: if (Phase==EActOnePhase::Precinct) StartCaptain(); else Hint(Objective()); break;
    case EActOneAction::Training: bLockpickTraining=true; AddEvidence(TEXT("LockTraining")); break;
    case EActOneAction::Archives: if (bArchives) AddEvidence(TEXT("AegisArchive")); break;
    case EActOneAction::IvanStreet: if (Phase==EActOnePhase::MeetIvan) MeetIvan(); break;
    case EActOneAction::Ride:
        if (Phase==EActOnePhase::FedorEntrance) Travel(TEXT("L_FedorEntry"),TEXT("Подъезд Фёдора"),TEXT("ActEntry"));
        break;
    case EActOneAction::BuildingEntry:
        if (Phase==EActOnePhase::FedorEntrance && !bLobbyOpened)
        {
            Director->OpenDoor(TEXT("FedorBuildingLeaf"),88.f);
            bLobbyOpened=true;
            RefreshScene();
        }
        break;
    case EActOneAction::Seal: if (Phase==EActOnePhase::FedorEntrance) OpenSeal(); break;
    case EActOneAction::Floorboard:
        bFloorboardOpen=true;
        if (AActor* Board=Director->Cue(TEXT("Floorboard"))) Board->AddActorWorldRotation(FRotator(-58,0,0));
        PlayAudio(TEXT("Wood"),.8f);
        RefreshScene();
        break;
    case EActOneAction::Folder: if (bFloorboardOpen) {AddEvidence(Clues[0]);CheckClues();} break;
    case EActOneAction::Tape: AddEvidence(Clues[1]); CheckClues(); break;
    case EActOneAction::Photograph: AddEvidence(Clues[2]); CheckClues(); break;
    case EActOneAction::Drawer:
        bDrawerOpen=true;
        if (AActor* Drawer=Director->Cue(TEXT("Drawer"))) Drawer->AddActorWorldOffset(FVector(-28,0,0));
        PlayAudio(TEXT("Wood"),.7f);
        RefreshScene();
        break;
    case EActOneAction::DeskBadge: if (bDrawerOpen) {AddEvidence(Clues[3]);CheckClues();} break;
    case EActOneAction::IvanFedor: MeetFedorIvan(); break;
    case EActOneAction::LeaveFedor:
        if (bBankKey)
        {
            if (Travel(TEXT("L_BrightonAlley"),TEXT("Переулки Брайтон-Бич"),TEXT("ActEntry"),&Item)) Phase=EActOnePhase::Chase;
        }
        else Hint(Objective());
        break;
    case EActOneAction::ChaseBadge:
        if (!bAgentEscaped) break;
        AddEvidence(TEXT("PursuitBadge"),false);
        Director->Show(TEXT("ChaseBadge"),false);
        if (User->PlayerCameraManager) User->PlayerCameraManager->StartCameraFade(0,1,.68f,FLinearColor::Black,false,true);
        Timed(.73f,FSimpleDelegate::CreateWeakLambda(this,[this]()
        {
            if (Travel(TEXT("L_DimaApartmentInterior"),TEXT("Квартира Димы"),TEXT("FromFinale"))) Phase=EActOnePhase::Finale;
            else if (Player()->PlayerCameraManager) Player()->PlayerCameraManager->StopCameraFade();
        }));
        break;
    }
    return true;
}

void UActOneSubsystem::CallFromPayphone(bool bMother)
{
    PlayAudio(TEXT("Dial"),.75f);
    Timed(2.15f,FSimpleDelegate::CreateWeakLambda(this,[this,bMother]()
    {
        AddEvidence(bMother ? TEXT("MotherCall") : TEXT("LizaCall"),false);
        Notice(TEXT("NoConnection"));
    }));
}

void UActOneSubsystem::AskVeteran()
{
    Ask(TEXT("VeteranAsk"),{Text(TEXT("Дать 5 долларов")),Text(TEXT("Отказать")),Text(TEXT("Наорать"))},
        FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
        {
            bVeteranDone=true;
            if (Answer==0) {Cash-=5; ++Stats.Heritage; Notice(TEXT("VeteranThanks"));}
            else if (Answer==1) Notice(TEXT("VeteranCurse"));
            else
            {
                Stats.Anger+=5;
                bVeteranFled=true;
                for (const auto& Target:Director->Interactions())
                    if (Target.IsValid() && Target->Action==EActOneAction::Veteran) Target->SetAvailable(false);
                if (AActOneCast* Person=Cast<AActOneCast>(Director->Cue(TEXT("Veteran"))))
                    if (AActor* Exit=Director->Cue(TEXT("VeteranExit"))) Person->WalkAway(Exit->GetActorLocation(),340);
            }
        }));
}

void UActOneSubsystem::StartBar()
{
    Ask(TEXT("BarChoice"),{Text(TEXT("Попытаться успокоить словами")),Text(TEXT("Сразу применить силу"))},
        FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
        {
            if (Answer==0)
                Say({TEXT("GuardTaunt"),TEXT("DimaBarReply"),TEXT("GuardEnglish")},FSimpleDelegate::CreateUObject(this,&ThisClass::DrawGuardWeapon));
            else
            {
                Stats.Anger+=10;
                bOldManFled=true;
                Director->Pose(TEXT("BarGuard"),EActOnePose::Fallen);
                PlayAudio(TEXT("Impact"),.75f);
                if (AActOneCast* Old=Cast<AActOneCast>(Director->Cue(TEXT("OldMan"))))
                    if (AActor* Exit=Director->Cue(TEXT("OldManExit"))) Old->WalkAway(Exit->GetActorLocation(),390);
                Timed(.8f,FSimpleDelegate::CreateUObject(this,&ThisClass::DrawGuardWeapon));
            }
        }));
}

void UActOneSubsystem::DrawGuardWeapon()
{
    Director->Pose(TEXT("BarGuard"),EActOnePose::Armed);
    Director->Show(TEXT("GuardWeapon"),true);
    TArray<FText> Choices={Text(TEXT("Обезоружить"))};
    if (bPistol) Choices.Add(Text(TEXT("Выстрелить")));
    Ask(TEXT("BarGun"),MoveTemp(Choices),FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
    {
        if (Answer==0) StartChallenge(EChallenge::Disarm);
        else if (bPistol) ResolveGuard(true);
    }));
}

void UActOneSubsystem::ResolveGuard(bool bShot)
{
    if (bGuardResolved) return;
    bGuardResolved=true;
    if (bShot)
    {
        Stats.Anger+=20;
        --Stats.Neighborhood;
        Director->StartBarShot();
        Timed(.48f,FSimpleDelegate::CreateWeakLambda(this,[this]()
        {
            bGuardKilled=true;
            PlayAudio(TEXT("Shot"),.85f);
            Director->BarShotImpact();
            Timed(2.12f,FSimpleDelegate::CreateWeakLambda(this,[this]()
            {
                Director->EndBarShot();
                EndBarConflict();
            }));
        }));
        return;
    }
    Director->Pose(TEXT("BarGuard"),EActOnePose::Fallen);
    Director->DropBarWeapon();
    PlayAudio(TEXT("Impact"),.85f);
    Timed(1.05f,FSimpleDelegate::CreateUObject(this,&ThisClass::EndBarConflict));
}

void UActOneSubsystem::EndBarConflict()
{
    if (!bGuardKilled) Director->Pose(TEXT("BarGuard"),EActOnePose::Subdued);
    TArray<FName> Pages;
    if (!bOldManFled)
    {
        if (AActOneCast* Old=Cast<AActOneCast>(Director->Cue(TEXT("OldMan"))))
            if (AActor* Mark=Director->Cue(TEXT("OldManThanks"))) {Old->SetActorLocation(Mark->GetActorLocation()); Old->Face(Player()->GetPawn()->GetActorLocation());}
        Pages.Add(TEXT("OldManThanks"));
    }
    Pages.Add(TEXT("DispatchPrecinct"));
    Say(MoveTemp(Pages),FSimpleDelegate::CreateWeakLambda(this,[this]()
    {
        Phase=EActOnePhase::Precinct;
        PlayAudio(TEXT("RadioHangup"),.62f);
        RefreshScene();
    }));
}

void UActOneSubsystem::StartCaptain()
{
    Ask(TEXT("CaptainNews"),{Text(TEXT("Почему корпорация? Он же просто инженер")),Text(TEXT("Мой отец — не их собственность")),Text(TEXT("(Молчать)"))},
        FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
        {
            if (Answer<2) Say({Answer==0 ? TEXT("CaptainReply01") : TEXT("CaptainReply02")},FSimpleDelegate::CreateUObject(this,&ThisClass::CaptainSecond));
            else CaptainSecond();
        }));
}

void UActOneSubsystem::CaptainSecond()
{
    Ask(TEXT("CaptainKGB"),{Text(TEXT("Вы знали? И молчали?")),Text(TEXT("Где мне найти информацию?")),Text(TEXT("Я найду его сам"))},
        FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
        {
            if (Answer==0) Stats.Anger+=5;
            TArray<FName> Pages={Answer==0 ? TEXT("CaptainAnger") : Answer==1 ? TEXT("CaptainInfo") : TEXT("CaptainSearch")};
            if (Answer>0) Pages.Add(Answer==1 ? TEXT("CaptainInfoReply") : TEXT("CaptainSearchReply"));
            Say(MoveTemp(Pages),FSimpleDelegate::CreateUObject(this,&ThisClass::CaptainOffer));
        }));
}

void UActOneSubsystem::CaptainOffer()
{
    Director->Show(TEXT("OfferBadge"),true);
    PlayAudio(TEXT("Badge"),.6f);
    Ask(TEXT("CaptainOffer"),{Text(TEXT("Взять значок")),Text(TEXT("Отказаться")),Text(TEXT("Бросить значок в мусорку"))},
        FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
        {
            if (Answer==0) {++Stats.CorporateTrust; bArchives=true; AddEvidence(TEXT("OfferBadge"),false);}
            else if (Answer==1) ++Stats.Heritage;
            else
            {
                Stats.Anger+=5;
                Director->Show(TEXT("TrashBadge"),true);
                PlayAudio(TEXT("Badge"));
            }
            if (Answer!=1) Director->Show(TEXT("OfferBadge"),false);
            RefreshScene();
            if (Answer==2) Say({TEXT("CaptainFather")},FSimpleDelegate::CreateUObject(this,&ThisClass::CaptainWarning));
            else CaptainWarning();
        }));
}

void UActOneSubsystem::CaptainWarning()
{
    Say({TEXT("CaptainWarning")},FSimpleDelegate::CreateWeakLambda(this,[this]()
    {
        Phase=EActOnePhase::CaptainDone;
        RefreshScene();
    }));
}

void UActOneSubsystem::MeetIvan()
{
    if (bIvanSpoken) return;
    bIvanSpoken=true;
    Say({TEXT("IvanStreet01"),TEXT("IvanStreet02"),TEXT("IvanStreet03")},FSimpleDelegate::CreateWeakLambda(this,[this]()
    {
        Ask(TEXT("IvanKeyOffer"),{Text(TEXT("Взять ключ Ивана")),Text(TEXT("Обойтись без ключа"))},
            FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
            {
                bIvanKey=Answer==0;
                if (bIvanKey) AddEvidence(TEXT("IvanKey"),false);
                Phase=EActOnePhase::FedorEntrance;
                RefreshScene();
                WalkOff(TEXT("IvanStreet"),TEXT("IvanStreetExit"));
            }));
    }));
}

void UActOneSubsystem::OpenSeal()
{
    TArray<FText> Choices={Text(TEXT("Сорвать ленту"))};
    if (bIvanKey) Choices.Add(Text(TEXT("Использовать ключ Ивана")));
    else if (bLockpickTraining) Choices.Add(Text(TEXT("Взломать замок")));
    Ask(TEXT("SealDoor"),MoveTemp(Choices),FDocumentChoice::CreateWeakLambda(this,[this](int32 Answer)
    {
        if (Answer==0) EnterFedor(true);
        else if (bIvanKey) EnterFedor(false);
        else if (bLockpickTraining) StartChallenge(EChallenge::Lock);
    }));
}

void UActOneSubsystem::EnterFedor(bool bLoud)
{
    const bool bSeen=bLoud && Director->PatrolCanSeePlayer(Player());
    if (bLoud)
    {
        Director->Show(TEXT("PoliceTape"),false);
        PlayAudio(TEXT("Paper"));
    }
    Director->OpenDoor(TEXT("SealedLeaf"),87.f);
    if (bSeen)
    {
        bAlarm=true;
        PlayAudio(TEXT("Alarm"));
        Director->Show(TEXT("AlarmLamp"),true);
        Timed(1.05f,FSimpleDelegate::CreateWeakLambda(this,[this]()
        {
            Say({TEXT("AlarmNotice")},FSimpleDelegate::CreateWeakLambda(this,[this]()
            {
                if (Travel(TEXT("L_FedorApartment"),TEXT("Квартира Фёдора"),TEXT("ActEntry"))) Phase=EActOnePhase::Search;
            }));
        }));
    }
    else Timed(.62f,FSimpleDelegate::CreateWeakLambda(this,[this]()
    {
        if (Travel(TEXT("L_FedorApartment"),TEXT("Квартира Фёдора"),TEXT("ActEntry"))) Phase=EActOnePhase::Search;
    }));
}

void UActOneSubsystem::CheckClues()
{
    if (!bIvanEntered)
    {
        for (FName Entry:Clues) if (!HasEvidence(Entry)) { RefreshScene(); return; }
        AActOneCast* Ivan=Cast<AActOneCast>(Director->Cue(TEXT("IvanFedor")));
        const AActor* Arrival=Director->Cue(TEXT("IvanFedorArrival"));
        bIvanEntered=true;
        Director->Show(TEXT("IvanFedor"),true);
        Director->OpenDoor(TEXT("FedorFlatLeaf"),82.f);
        if (Ivan && Arrival)
            Ivan->WalkTo(Arrival->GetActorLocation(),155.f);
        else
            bIvanArrived=true;
    }
    RefreshScene();
}

void UActOneSubsystem::UpdateFedorArrival()
{
    AActOneCast* Ivan=Cast<AActOneCast>(Director->Cue(TEXT("IvanFedor")));
    if (Ivan && Ivan->IsWalkingToMark()) return;
    bIvanArrived=true;
    if (Ivan && Player()->GetPawn()) Ivan->Face(Player()->GetPawn()->GetActorLocation());
    RefreshScene();
}

void UActOneSubsystem::MeetFedorIvan()
{
    if (bBankKey || !bIvanArrived) return;
    for (FName Entry:Clues) if (!HasEvidence(Entry)) return;
    Say({TEXT("IvanFedor"),TEXT("FedorWho")},FSimpleDelegate::CreateWeakLambda(this,[this]()
    {
        bBankKey=true;
        AddEvidence(TEXT("BankKey"),false);
        AActOneCast* Listener=Cast<AActOneCast>(Director->Cue(TEXT("FedorListener")));
        const AActor* Exit=Director->Cue(TEXT("FedorListenerExit"));
        if (Listener && Exit)
        {
            Director->Show(TEXT("FedorListener"),true);
            Listener->WalkAway(Exit->GetActorLocation(),460.f);
        }
        if (AActOneCast* Ivan=Cast<AActOneCast>(Director->Cue(TEXT("IvanFedor"))))
            if (const AActor* Wait=Director->Cue(TEXT("IvanFedorWait")))
                Ivan->WalkTo(Wait->GetActorLocation(),112.f);
        Hint(Text(TEXT("Кто-то подслушивал за дверью. За ним!")),3.f);
        RefreshScene();
    }));
}

void UActOneSubsystem::WalkOff(FName Actor,FName Exit)
{
    AActOneCast* Character=Cast<AActOneCast>(Director->Cue(Actor));
    const AActor* Mark=Director->Cue(Exit);
    if (!Character || !Mark) return;
    Director->Show(Actor,true);
    Character->WalkAway(Mark->GetActorLocation(),225.f);
}

void UActOneSubsystem::UpdatePursuit(float DeltaSeconds)
{
    AActOneCast* Agent=Cast<AActOneCast>(Director->Cue(TEXT("Agent")));
    USplineComponent* Route=Director->PursuitRoute;
    const APawn* Pawn=Player() ? Player()->GetPawn() : nullptr;
    if (!Agent || !Route || Route->GetNumberOfSplinePoints()<3 || !Pawn || DeltaSeconds<=UE_SMALL_NUMBER) return;
    const auto AlongRoute=[Route](const FVector& Position)
    {
        return Route->GetDistanceAlongSplineAtSplineInputKey(Route->FindInputKeyClosestToWorldLocation(Position));
    };
    const float At=AlongRoute(Pawn->GetActorLocation());
    const float Length=Route->GetSplineLength();
    const AActor* Stumble=Director->Cue(TEXT("PursuitTripStart"));
    const float TripAt=Stumble ? AlongRoute(Stumble->GetActorLocation())
        : Route->GetDistanceAlongSplineAtSplinePoint(Route->GetNumberOfSplinePoints()-2)-186.f;
    const float Lead=bAlarm ? 1000.f : 820.f;
    if (ChasePosition<=0)
    {
        ChasePosition=530.f;
        ChaseSpeed=460.f;
        Hint(Text(TEXT("Агент Aegis уходит в переулок. Бегите за ним.")),4.f);
    }
    if (!bTripStarted && At>=TripAt)
    {
        bTripStarted=true;
        Director->StartPursuitTrip(Route->GetDirectionAtDistanceAlongSpline(TripAt,ESplineCoordinateSpace::World));
        Timed(1.94f,FSimpleDelegate::CreateWeakLambda(this,[this]()
        {
            bTripRecovered=true;
            Director->EndPursuitTrip();
            RefreshScene();
        }));
    }
    if (bAgentEscaped) return;

    // A lead changes the pace, but never leaves the agent waiting in view before the stumble.
    constexpr auto WorldSpace=ESplineCoordinateSpace::World;
    const float StrideBlend=FMath::Clamp((ChasePosition-At-Lead)/720.f,0.f,1.f);
    const float DesiredSpeed=bTripStarted ? 745.f : FMath::Lerp(bAlarm ? 555.f : 505.f,390.f,StrideBlend);
    ChaseSpeed=FMath::FInterpConstantTo(ChaseSpeed,DesiredSpeed,DeltaSeconds,920.f);
    ChasePosition=FMath::Min(Length,ChasePosition+ChaseSpeed*DeltaSeconds);
    const FVector Next=Route->GetLocationAtDistanceAlongSpline(ChasePosition,WorldSpace);
    const FVector Heading=Route->GetLocationAtDistanceAlongSpline(FMath::Min(Length,ChasePosition+38.f),WorldSpace)-
        Route->GetLocationAtDistanceAlongSpline(FMath::Max(0.f,ChasePosition-38.f),WorldSpace);
    Agent->FollowPursuitPath(Next,Heading,ChaseSpeed,DeltaSeconds);
    if (ChasePosition>=Length-1)
    {
        bAgentEscaped=true;
        Director->Show(TEXT("Agent"),false);
        PlayAudio(TEXT("Badge"),.55f);
        RefreshScene();
    }
}

void UActOneSubsystem::Finale()
{
    APlayerController* PC=Player();
    if (!PC) return;
    bClosingStarted=true;
    if (Director->FinaleCamera) PC->SetViewTarget(Director->FinaleCamera);
    if (PC->PlayerCameraManager) PC->PlayerCameraManager->StartCameraFade(1,0,.55f,FLinearColor::Black,false,false);
    Timed(Director->PlayRecorder(),FSimpleDelegate::CreateWeakLambda(this,[this]()
    {
        Director->FinishRecorder();
        const UInteractionDocument* Recording=Doc(TEXT("FedorRecording"));
        const float Duration=Recording && Recording->Voice ? Recording->Voice->GetDuration() : 7.f;
        Director->GetWorldTimerManager().SetTimer(SceneTimer,this,&ThisClass::Credits,Duration+.38f,false);
        Say({TEXT("FedorRecording")},FSimpleDelegate::CreateUObject(this,&ThisClass::Credits));
    }));
}

void UActOneSubsystem::Credits()
{
    if (Phase!=EActOnePhase::Finale) return;
    Director->GetWorldTimerManager().ClearTimer(SceneTimer);
    UI()->CloseDocument();
    if (Player()->PlayerCameraManager) Player()->PlayerCameraManager->StartCameraFade(0,1,.7f,FLinearColor::Black,false,true);
    Timed(.72f,FSimpleDelegate::CreateWeakLambda(this,[this]()
    {
        Phase=EActOnePhase::Complete;
        UI()->ShowStoryPage(Player(),Doc(TEXT("Credits")),FSimpleDelegate::CreateUObject(this,&ThisClass::Restart));
    }));
}

void UActOneSubsystem::Restart()
{
    UI()->CloseDocument();
    GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->ResetSession();
    UGameplayStatics::OpenLevel(GetGameInstance(),TEXT("/Game/Locations/L_DimaApartmentInterior"));
}

float UActOneSubsystem::GetChallengePosition() const
{
    if (!Director.IsValid() || Challenge!=EChallenge::Lock) return 0;
    return FMath::Fmod(Director->GetWorld()->GetTimeSeconds()-StepStarted,LockCycle)/LockCycle;
}

float UActOneSubsystem::GetChallengeTarget() const
{
    return Step>=0 && Step<UE_ARRAY_COUNT(LockTargets) ? LockTargets[Step] : 0.f;
}

void UActOneSubsystem::StartChallenge(EChallenge Mode)
{
    Challenge=Mode;
    Step=0;
    StepStarted=Director->GetWorld()->GetTimeSeconds();
    LiveDocument=NewObject<UInteractionDocument>(this);
    LiveDocument->Title=Mode==EChallenge::Disarm ? Text(TEXT("Обезоружить")) : Text(TEXT("Замок"));
    LiveDocument->CloseLabel=Text(TEXT("Прервать · Esc"));
    RefreshChallenge();
    if (!UI()->ShowChallenge(Player(),LiveDocument,FDocumentKeyInput::CreateUObject(this,&ThisClass::ChallengeKey),
        FSimpleDelegate::CreateUObject(this,&ThisClass::FinishChallenge,false)))
    {Challenge=EChallenge::None;return;}
    Director->GetWorldTimerManager().SetTimer(ChallengeTimer,this,&ThisClass::RefreshChallenge,.045f,true);
}

void UActOneSubsystem::RefreshChallenge()
{
    if (!Director.IsValid() || !LiveDocument || Challenge==EChallenge::None) return;
    const float Elapsed=Director->GetWorld()->GetTimeSeconds()-StepStarted;
    if (Challenge==EChallenge::Disarm)
    {
        const float Window=FMath::Clamp(1.55f+.09f*Stats.Calm-.012f*Stats.Anger,1.15f,1.9f);
        if (Elapsed>Window) { FinishChallenge(false); return; }
        LiveDocument->Body=FText::FromString(FString::Printf(
            TEXT("Последовательность  Q  →  E  →  F\nСейчас  [%s]     %d / 3     %.1f с"),
            DisarmLabels[Step],Step,Window-Elapsed));
    }
    else
    {
        const int32 Mark=FMath::RoundToInt(GetChallengePosition()*24);
        FString Track;
        for (int32 Index=0; Index<=24; ++Index)
            Track.AppendChar(Index==Mark ? TCHAR(0x25CF) :
                (FMath::Abs(Index/24.f-GetChallengeTarget())<=LockWindow ? TCHAR(0x2588) : TCHAR(0x2500)));
        LiveDocument->Body=FText::FromString(FString::Printf(TEXT("Нажмите Пробел, когда точка войдёт в светлый участок.\n[%s]    %d / 3"),*Track,Step));
    }
}

bool UActOneSubsystem::ChallengeKey(const FKey& Key,bool bRepeat)
{
    if (Challenge==EChallenge::None || Key==EKeys::Escape) return false;
    if (bRepeat) return true;
    if (Challenge==EChallenge::Lock && Key!=EKeys::SpaceBar) return true;
    const bool bCorrect=Challenge==EChallenge::Disarm ? Key==DisarmKeys[Step] :
        FMath::Abs(GetChallengePosition()-GetChallengeTarget())<=LockWindow;
    if (!bCorrect) {FinishChallenge(false);return true;}
    PlayAudio(TEXT("StepClick"),.58f);
    if (++Step>=3) FinishChallenge(true);
    else {StepStarted=Director->GetWorld()->GetTimeSeconds();RefreshChallenge();}
    return true;
}

void UActOneSubsystem::FinishChallenge(bool bSuccess)
{
    if (Challenge==EChallenge::None) return;
    const EChallenge Mode=Challenge;
    Challenge=EChallenge::None;
    Director->GetWorldTimerManager().ClearTimer(ChallengeTimer);
    UI()->CloseDocument();
    if (bSuccess)
    {
        if (Mode==EChallenge::Disarm) ResolveGuard(false);
        else EnterFedor(false);
    }
    else
    {
        Say({Mode==EChallenge::Disarm ? TEXT("DisarmRetry") : TEXT("LockRetry")},
            FSimpleDelegate::CreateWeakLambda(this,[this,Mode]()
            {
                if (Mode==EChallenge::Disarm) DrawGuardWeapon();
                else OpenSeal();
            }));
    }
}
