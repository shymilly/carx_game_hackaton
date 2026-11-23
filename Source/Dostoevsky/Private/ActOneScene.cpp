#include "ActOneScene.h"
#include "BrightonEnvironment.h"
#include "CityCharacter.h"
#include "CigaretteSmokeComponent.h"
#include "DoorOpeningAudio.h"
#include "DostoevskyGameSettings.h"

#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/LightComponent.h"
#include "Engine/PointLight.h"
#include "GameFramework/Pawn.h"
#include "Components/AudioComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SplineComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RotationMatrix.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "Sound/SoundBase.h"

CSV_DECLARE_CATEGORY_EXTERN(Brighton);

namespace
{
const FName CigaretteGrip(TEXT("CigaretteGrip"));
const FName SmokeMouth(TEXT("SmokeMouth"));
constexpr double CigaretteTip=5.35;
constexpr int32 RainCount=740;
constexpr int32 SplashCount=112;
constexpr int32 RainGridRadius=4;
constexpr int32 RainGridWidth=RainGridRadius*2+1;
constexpr float RainGridStep=185.f;
constexpr float RainStep=1.f/33.f;
const FRotator FirstPersonArmsRotation(0,-90,0);

USkeletalMeshComponent* CreateStoryArms(AActor& Owner, USceneComponent& Anchor, USkeletalMesh* Mesh,
    FName Name, const FVector& Offset, const FRotator& Rotation=FirstPersonArmsRotation)
{
    auto* Arms=NewObject<USkeletalMeshComponent>(&Owner,Name);
    Arms->SetSkeletalMeshAsset(Mesh);
    Arms->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Arms->SetCanEverAffectNavigation(false);
    Arms->SetCastShadow(false);
    Arms->bAffectDistanceFieldLighting=false;
    Arms->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Arms->SetupAttachment(&Anchor);
    Arms->SetRelativeLocationAndRotation(Offset,Rotation);
    Arms->RegisterComponent();
    return Arms;
}

UStaticMeshComponent* AttachCigarette(USkeletalMeshComponent& Hand,UStaticMesh* Model)
{
    if (!Model || !Hand.DoesSocketExist(CigaretteGrip)) return nullptr;
    auto* Prop=NewObject<UStaticMeshComponent>(Hand.GetOwner(),TEXT("HeldCigarette"));
    Prop->SetStaticMesh(Model);
    Prop->SetupAttachment(&Hand,CigaretteGrip);
    Prop->SetUsingAbsoluteScale(true);
    Prop->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Prop->SetCanEverAffectNavigation(false);
    Prop->SetCastShadow(false);
    Prop->bAffectDistanceFieldLighting=false;
    Prop->RegisterComponent();
    return Prop;
}
}

AActOneCast::AActOneCast()
{
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    Body=CreateDefaultSubobject<UCapsuleComponent>(TEXT("Body"));
    Body->SetupAttachment(GetRootComponent());
    Body->SetCapsuleSize(25.f,88.f);
    Body->SetRelativeLocation(FVector(0,0,88));
    Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Body->SetCollisionObjectType(ECC_Pawn);
    Body->SetCollisionResponseToAllChannels(ECR_Ignore);
    Body->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
    Body->SetGenerateOverlapEvents(false);
    Body->SetCanEverAffectNavigation(false);
    PoseRoot=CreateDefaultSubobject<USceneComponent>(TEXT("PoseRoot"));
    PoseRoot->SetupAttachment(GetRootComponent());
    CharacterMesh=CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CharacterMesh"));
    CharacterMesh->SetupAttachment(GetRootComponent());
    CharacterMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CharacterMesh->SetCanEverAffectNavigation(false);
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.bStartWithTickEnabled=false;
    PrimaryActorTick.TickInterval=.04f;
}

void AActOneCast::BeginPlay()
{
    Super::BeginPlay();
    for (const auto& Item:Parts)
        if (IsValid(Item.Value)) Rest.Add(Item.Key,Item.Value->GetRootComponent()->GetRelativeRotation());
    if (CharacterProfile && CharacterProfile->Mesh)
    {
        CharacterProfile->Configure(*CharacterMesh);
        CharacterMesh->SetRelativeLocation(FVector(0,0,CharacterProfile->FeetOffset));
    }
    Pose(DefaultPose);
    if (UAnimSingleNodeInstance* Clip=CharacterMesh->GetSingleNodeInstance())
    {
        const float Offset=AnimationPhase>0 ? AnimationPhase : (GetTypeHash(GetFName())%1000)*.001f*Clip->GetLength();
        if (bLegacySeat) Clip->SetPosition(FMath::Min(2.3f,Clip->GetLength()),false);
        else if (Clip->GetLength()>0) Clip->SetPosition(FMath::Fmod(Offset,Clip->GetLength()),false);
        if (bFreezePose)
        {
            Clip->SetPlaying(false);
            bLegacySeat=false;
        }
    }
    if (DefaultPose==EActOnePose::Smoking)
    {
        TArray<AActor*> Props;
        GetAttachedActors(Props,false,true);
        for (AActor* Prop:Props)
            if (Prop->ActorHasTag(TEXT("CigaretteSource")) || Prop->ActorHasTag(TEXT("LegacyCigarette")))
                Prop->SetActorHiddenInGame(true);
        if (CharacterProfile) HeldCigarette=AttachCigarette(*CharacterMesh,CharacterProfile->CigaretteMesh);
        if (HeldCigarette) SmokeTrail=UCigaretteSmokeComponent::CreateTrail(this);
    }
    UpdateActorTick();
}

void AActOneCast::Pose(EActOnePose NewPose)
{
    const bool bChanged=NewPose!=CurrentPose;
    if (bChanged) Life=0;
    CurrentPose=NewPose;
    const bool bFallen=NewPose==EActOnePose::Fallen || NewPose==EActOnePose::Dead || NewPose==EActOnePose::Subdued;
    Body->SetCollisionEnabled(NewPose==EActOnePose::Dead ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryOnly);
    Body->SetCapsuleHalfHeight(bFallen ? 29.f : 88.f);
    Body->SetRelativeLocation(FVector(0,0,bFallen ? 29.f : 88.f));
    if (bChanged || !Cast<UCityClipInstance>(CharacterMesh->GetAnimInstance())) PlayCharacterPose();
    UpdateActorTick();
}

float AActOneCast::GetPoseDuration() const
{
    if (UAnimSingleNodeInstance* Clip=CharacterMesh->GetSingleNodeInstance()) return Clip->GetLength();
    return 0.f;
}

void AActOneCast::PlayCharacterPose()
{
    if (!CharacterProfile || !CharacterProfile->Mesh) return;
    NodRemaining=0;
    FName Motion=bSpeaking ? TEXT("Talk") : TEXT("Idle");
    const FName Seat=CharacterProfile->Motions.Contains(TEXT("SeatedIdle")) ? TEXT("SeatedIdle") : TEXT("Sit");
    switch (CurrentPose)
    {
    case EActOnePose::Seated: Motion=bSpeaking && CharacterProfile->Motions.Contains(TEXT("SeatedTalk")) ? TEXT("SeatedTalk") : Seat; break;
    case EActOnePose::Smoking: Motion=TEXT("Smoke"); break;
    case EActOnePose::Armed: Motion=TEXT("Armed"); break;
    case EActOnePose::Fallen: Motion=TEXT("Fall"); break;
    case EActOnePose::Walking: Motion=TEXT("Walk"); break;
    case EActOnePose::Running: Motion=TEXT("Run"); break;
    case EActOnePose::Conversing: Motion=TEXT("Talk"); break;
    case EActOnePose::Firing: Motion=TEXT("Shot"); break;
    case EActOnePose::Dead: Motion=TEXT("Fall"); break;
    case EActOnePose::Subdued: Motion=TEXT("Fall"); break;
    default: break;
    }
    const bool bLoop=CurrentPose!=EActOnePose::Fallen && CurrentPose!=EActOnePose::Dead &&
        CurrentPose!=EActOnePose::Subdued && CurrentPose!=EActOnePose::Firing;
    const float Rate=CurrentPose==EActOnePose::Walking && WalkSpeed<1 ? .72f : 1.f;
    UAnimSequence* SeatedClip=CurrentPose==EActOnePose::Seated ? CharacterProfile->Motions.FindRef(Motion).Get() : nullptr;
    if (SeatedClip)
    {
        // Both seated clips share the same chair contacts. Play them directly
        // so switching dialogue pages does not carry the previous pose.
        CharacterMesh->PlayAnimation(SeatedClip,bLoop);
        UE_LOG(LogTemp, Verbose, TEXT("Seated cast clip %s for %s"), *SeatedClip->GetName(), *GetName());
    }
    else if (CurrentPose==EActOnePose::Subdued)
    {
        if (UAnimSequence* Fall=CharacterProfile->Motions.FindRef(Motion).Get())
        {
            UAnimSingleNodeInstance* Clip=CharacterMesh->GetSingleNodeInstance();
            if (!Clip || Clip->GetCurrentAsset()!=Fall)
            {
                CharacterProfile->Play(*CharacterMesh,Motion,false,Rate);
                Clip=CharacterMesh->GetSingleNodeInstance();
            }
            if (Clip)
            {
                Clip->SetPosition(Fall->GetPlayLength(),false);
                Clip->SetPlaying(false);
            }
        }
    }
    else CharacterProfile->Play(*CharacterMesh,Motion,bLoop,Rate);
    bLegacySeat=Motion==TEXT("Sit");
    if (UAnimSingleNodeInstance* Clip=CharacterMesh->GetSingleNodeInstance(); Clip && bLegacySeat)
        Clip->SetPosition(FMath::Min(2.3f,Clip->GetLength()),false);
}

void AActOneCast::SetSpeaking(bool bIsSpeaking)
{
    UE_LOG(LogTemp, Verbose, TEXT("Entering cast speech %s: speaking=%d, previous=%d, static=%d, posture=%d"),
        *GetName(), bIsSpeaking, bSpeaking, bFreezePose, int32(CurrentPose));
    if (bFreezePose || bSpeaking==bIsSpeaking) return;
    bSpeaking=bIsSpeaking;
    if (CurrentPose==EActOnePose::Idle || CurrentPose==EActOnePose::Seated)
    {
        PlayCharacterPose();
        UpdateActorTick();
    }
}

void AActOneCast::Face(const FVector& Target)
{
    const FVector Delta=Target-GetActorLocation();
    if (Delta.SizeSquared2D()>1) SetActorRotation(FRotator(0,Delta.Rotation().Yaw,0));
}

void AActOneCast::WalkAway(const FVector& Destination,float Speed)
{
    WalkTo(Destination,Speed);
    bHideAtWalkEnd=true;
}

void AActOneCast::WalkAway(TArray<FVector> Route,float Speed)
{
    if (Route.IsEmpty()) return;
    WalkTo(Route[0],Speed);
    WalkRoute=MoveTemp(Route);
    NextRoutePoint=1;
    bHideAtWalkEnd=true;
}

void AActOneCast::WalkTo(const FVector& Destination,float Speed)
{
    WalkRoute.Reset();
    NextRoutePoint=0;
    bHideAtWalkEnd=false;
    WalkTarget=Destination;
    WalkSpeed=Speed;
    Pose(Speed>=330.f ? EActOnePose::Running : EActOnePose::Walking);
    UpdateActorTick();
}

void AActOneCast::FollowPursuitPath(const FVector& Position,const FVector& Direction,float Speed,float DeltaSeconds)
{
    const float Heading=Direction.IsNearlyZero() ? GetActorRotation().Yaw : Direction.Rotation().Yaw;
    const float Yaw=FMath::FixedTurn(GetActorRotation().Yaw,Heading,620.f*DeltaSeconds);
    SetActorLocationAndRotation(Position,FRotator(0,Yaw,0));

    const bool bRun=Speed>320.f;
    const bool bMoving=Speed>18.f;
    Pose(bRun ? EActOnePose::Running : bMoving ? EActOnePose::Walking : EActOnePose::Idle);
    if (bMoving)
    {
        if (UAnimSingleNodeInstance* Clip=CharacterMesh->GetSingleNodeInstance())
        {
            const float StrideSpeed=bRun ? 530.f : 275.f;
            Clip->SetPlayRate(FMath::Clamp(Speed/StrideSpeed,.18f,1.5f));
        }
    }
}

void AActOneCast::Nod()
{
    if (bFreezePose) return;
    const FName Motion=CurrentPose==EActOnePose::Seated ? TEXT("SeatedNod") : TEXT("Nod");
    if (CharacterProfile && CharacterProfile->Motions.Contains(Motion))
    {
        NodRemaining=CharacterProfile->Play(*CharacterMesh,Motion,false);
        UpdateActorTick();
        return;
    }
    NodTime=0;
    UpdateActorTick();
}

void AActOneCast::UpdateActorTick()
{
    const bool bSkeletal=CharacterProfile && CharacterProfile->Mesh;
    SetActorTickInterval(WalkSpeed>0 ? 0.f : .04f);
    SetActorTickEnabled(!IsHidden() && (WalkSpeed>0 || NodRemaining>0 || !bSkeletal ||
        CurrentPose==EActOnePose::Smoking || bLegacySeat));
}

void AActOneCast::SetActorHiddenInGame(bool bNewHidden)
{
    Super::SetActorHiddenInGame(bNewHidden);
    UpdateActorTick();
}

void AActOneCast::Part(FName Name,float Pitch,float Roll)
{
    const TObjectPtr<AActor>* Item=Parts.Find(Name);
    const FRotator* Base=Rest.Find(Name);
    if (Item && IsValid(Item->Get()) && Base)
        (*Item)->GetRootComponent()->SetRelativeRotation(*Base+FRotator(Pitch,0,Roll));
}

void AActOneCast::Tick(float DeltaSeconds)
{
    CSV_SCOPED_TIMING_STAT(Brighton,CastTick);
    Super::Tick(DeltaSeconds);
    if (IsHidden()) return;
    Life+=DeltaSeconds;
    if (WalkSpeed>0)
    {
        const FVector ToTarget=WalkTarget-GetActorLocation();
        if (ToTarget.SizeSquared2D()>1.)
            SetActorRotation(FRotator(0,FMath::FixedTurn(GetActorRotation().Yaw,ToTarget.Rotation().Yaw,720.f*DeltaSeconds),0));
        CurrentWalkSpeed=FMath::FInterpConstantTo(CurrentWalkSpeed,WalkSpeed,DeltaSeconds,1250.f);
        const FVector Next=FMath::VInterpConstantTo(GetActorLocation(),WalkTarget,DeltaSeconds,CurrentWalkSpeed);
        SetActorLocation(Next);
        if (UAnimSingleNodeInstance* Clip=CharacterMesh->GetSingleNodeInstance())
        {
            const float NominalSpeed=CurrentPose==EActOnePose::Running ? 530.f : 275.f;
            Clip->SetPlayRate(FMath::Clamp(CurrentWalkSpeed/NominalSpeed,.25f,1.55f));
        }
        if (FVector::DistSquared(Next,WalkTarget)<4 && WalkRoute.IsValidIndex(NextRoutePoint))
        {
            WalkTarget=WalkRoute[NextRoutePoint++];
        }
        else if (FVector::DistSquared(Next,WalkTarget)<4)
        {
            WalkSpeed=0;
            CurrentWalkSpeed=0;
            if (bHideAtWalkEnd)
            {
                SetActorHiddenInGame(true);
                SetActorEnableCollision(false);
                TArray<AActor*> Attached;
                GetAttachedActors(Attached,false,true);
                for (AActor* Child:Attached) Child->SetActorHiddenInGame(true);
            }
            else Pose(EActOnePose::Idle);
        }
    }
    if (CharacterProfile && CharacterProfile->Mesh)
    {
        if (UAnimSingleNodeInstance* Clip=CharacterMesh->GetSingleNodeInstance())
        {
            const float T=Clip->GetCurrentTime();
            if (bLegacySeat && Clip->GetLength()>5.f && T>Clip->GetLength()-.4f)
                Clip->SetPosition(2.3f,false);
            if (SmokeTrail && HeldCigarette && CurrentPose==EActOnePose::Smoking)
            {
                const APawn* Viewer=UGameplayStatics::GetPlayerPawn(this,0);
                if (Viewer && FVector::DistSquared(Viewer->GetActorLocation(),GetActorLocation())<FMath::Square(1450.f))
                {
                    const FTransform Mouth=CharacterMesh->GetSocketTransform(SmokeMouth);
                    const FVector Tip=HeldCigarette->GetComponentTransform().TransformPosition(FVector(CigaretteTip,0,0));
                    SmokeTrail->SetSource(Tip,Mouth.GetLocation(),Mouth.GetUnitAxis(EAxis::X),T>4.45f && T<5.14f);
                }
                else SmokeTrail->StopEmitting();
            }
            else if (SmokeTrail) SmokeTrail->StopEmitting();
        }
        if (NodRemaining>0 && (NodRemaining-=DeltaSeconds)<=0) PlayCharacterPose();
        UpdateActorTick();
        return;
    }
    const float Swing=CurrentPose==EActOnePose::Walking ? 31.f*FMath::Sin(12.f*Life) : 0.f;
    const float Breath=FMath::Sin(1.8f*Life)*1.6f;
    Part(TEXT("LegL"),Swing);
    Part(TEXT("LegR"),-Swing);
    NodTime=FMath::Min(1.f,NodTime+DeltaSeconds);
    Part(TEXT("Head"),Breath+16.f*FMath::Sin(PI*NodTime),CurrentPose==EActOnePose::Seated ? -3.f : 0.f);
    Part(TEXT("ArmL"),-Swing);
    float Arm=Swing;
    if (CurrentPose==EActOnePose::Smoking) Arm=54.f+21.f*FMath::Sin(Life*1.6f);
    if (CurrentPose==EActOnePose::Armed) Arm=78.f;
    Part(TEXT("ArmR"),Arm);
    PoseRoot->SetRelativeRotation(FMath::RInterpTo(PoseRoot->GetRelativeRotation(),
        CurrentPose==EActOnePose::Fallen ? FRotator(-87,0,0) : FRotator::ZeroRotator,DeltaSeconds,11.f));
}

AActOneDirector::AActOneDirector()
{
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    PursuitRoute=CreateDefaultSubobject<USplineComponent>(TEXT("PursuitRoute"));
    PursuitRoute->SetupAttachment(RootComponent);
    Rain=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Rain"));
    Rain->SetupAttachment(RootComponent);
    Rain->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Rain->SetCanEverAffectNavigation(false);
    Rain->SetCastShadow(false);
    Rain->bAffectDistanceFieldLighting=false;
    RainSplashes=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("RainSplashes"));
    RainSplashes->SetupAttachment(RootComponent);
    RainSplashes->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    RainSplashes->SetCastShadow(false);
    RainSplashes->SetCanEverAffectNavigation(false);
    RainSplashes->bAffectDistanceFieldLighting=false;
    RainSplashes->SetNumCustomDataFloats(1);
    Environment=CreateDefaultSubobject<UBrightonEnvironmentComponent>(TEXT("Environment"));
    SmokeRig=CreateDefaultSubobject<USceneComponent>(TEXT("SmokeRig"));
    SmokeRig->SetupAttachment(RootComponent);
    SmokeHand=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SmokeHand"));
    Cigarette=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Cigarette"));
    Ember=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Ember"));
    for (UStaticMeshComponent* Part:{SmokeHand.Get(),Cigarette.Get(),Ember.Get()})
    {
        Part->SetupAttachment(SmokeRig);
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetCanEverAffectNavigation(false);
        Part->SetCastShadow(false);
        Part->SetHiddenInGame(true);
    }
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickInterval=.025f;
    StopSmoke();
}

void AActOneDirector::BeginPlay()
{
    Super::BeginPlay();
    if (const UDostoevskyGameSettings* Settings=UDostoevskyGameSettings::Get())
        Settings->ApplyPresentationSettings();
    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        for (FName Tag:It->Tags)
        {
            FString Text=Tag.ToString();
            if (Text.RemoveFromStart(TEXT("ActCue:"))) Cues.Add(FName(*Text),*It);
        }
        if (AActOneInteraction* Interaction=Cast<AActOneInteraction>(*It)) Targets.Add(Interaction);
    }
    if (UActOneSubsystem* Act=UActOneSubsystem::Find(this)) Act->Arrive(this);
}

void AActOneDirector::EndPlay(const EEndPlayReason::Type Reason)
{
    if (RainLoop) RainLoop->Stop();
    if (RecorderArms) RecorderArms->DestroyComponent();
    if (UActOneSubsystem* Act=UActOneSubsystem::Find(this)) Act->Leave(this);
    Super::EndPlay(Reason);
}

AActor* AActOneDirector::Cue(FName Key) const
{
    const TWeakObjectPtr<AActor>* Found=Cues.Find(Key);
    return Found ? Found->Get() : nullptr;
}

void AActOneDirector::Show(FName Key,bool bVisible) const
{
    if (AActor* Actor=Cue(Key))
    {
        Actor->SetActorHiddenInGame(!bVisible);
        Actor->SetActorEnableCollision(bVisible);
        TArray<AActor*> Attached;
        Actor->GetAttachedActors(Attached,false,true);
        for (AActor* Piece:Attached) Piece->SetActorHiddenInGame(!bVisible);
    }
}

void AActOneDirector::Pose(FName Key,EActOnePose InPose) const
{
    if (AActOneCast* CastActor=Cast<AActOneCast>(Cue(Key))) CastActor->Pose(InPose);
}

void AActOneDirector::SetSpeaker(FName CueName)
{
    AActOneCast* Next=Cast<AActOneCast>(Cue(CueName));
    UE_LOG(LogTemp, Verbose, TEXT("Story speaker %s resolves to %s"), *CueName.ToString(), *GetNameSafe(Next));
    if (Speaker.Get()==Next) return;
    if (Speaker.IsValid()) Speaker->SetSpeaking(false);
    Speaker=Next;
    if (Next) Next->SetSpeaking(true);
}

void AActOneDirector::StartBarShot()
{
    APlayerController* PC=UGameplayStatics::GetPlayerController(this,0);
    if (!PC) return;
    PreviousBarView=PC->GetViewTarget();
    if (AActor* Camera=Cue(TEXT("BarShotCamera"))) PC->SetViewTargetWithBlend(Camera,.14f);
    if (APawn* Pawn=PC->GetPawn()) Pawn->SetActorHiddenInGame(true);
    Show(TEXT("BarDima"),true);
    Pose(TEXT("BarDima"),EActOnePose::Firing);
}

void AActOneDirector::BarShotImpact()
{
    DropBarWeapon();
    Pose(TEXT("BarGuard"),EActOnePose::Dead);
    if (auto* Light=Cast<APointLight>(Cue(TEXT("BarFlash"))))
    {
        if (AActor* Prop=Cue(TEXT("BarShotProp"))) Light->SetActorLocation(Prop->GetActorLocation()+Prop->GetActorForwardVector()*10);
        Light->GetLightComponent()->SetVisibility(true);
        FlashRemaining=.075f;
    }
}

void AActOneDirector::DropBarWeapon()
{
    AActor* Held=Cue(TEXT("GuardWeapon"));
    AActor* Dropped=Cue(TEXT("DroppedWeapon"));
    if (Held && Dropped)
    {
        ReleaseTransform=Held->GetActorTransform();
        LandingTransform=Dropped->GetActorTransform();
        const double Height=FMath::Max(1.,ReleaseTransform.GetLocation().Z-LandingTransform.GetLocation().Z);
        DropDuration=FMath::Sqrt(2.*Height/980.);
        DropElapsed=0;
        FallingBarWeapon=Dropped;
        Dropped->SetActorTransform(ReleaseTransform);
    }
    Show(TEXT("GuardWeapon"),false);
    Show(TEXT("DroppedWeapon"),true);
}

void AActOneDirector::EndBarShot()
{
    if (APlayerController* PC=UGameplayStatics::GetPlayerController(this,0))
    {
        if (APawn* Pawn=PC->GetPawn()) Pawn->SetActorHiddenInGame(false);
        AActor* Target=PreviousBarView.IsValid() ? PreviousBarView.Get() : PC->GetPawn();
        if (Target) PC->SetViewTargetWithBlend(Target,.18f);
    }
    PreviousBarView.Reset();
    Show(TEXT("BarDima"),false);
}

void AActOneDirector::StartPursuitTrip(const FVector& Direction)
{
    APlayerController* PC=UGameplayStatics::GetPlayerController(this,0);
    if (!PC || !PC->PlayerCameraManager || !PC->GetPawn() || TripCamera) return;
    FActorSpawnParameters Parameters;
    Parameters.Owner=this;
    Parameters.ObjectFlags|=RF_Transient;
    TripEye=PC->PlayerCameraManager->GetCameraLocation();
    TripView=PC->PlayerCameraManager->GetCameraRotation();
    TripDirection=Direction.GetSafeNormal2D();
    TripCamera=GetWorld()->SpawnActor<ACameraActor>(TripEye,TripView,Parameters);
    if (!TripCamera) return;
    PreviousTripView=PC->GetViewTarget();
    UCameraComponent* Camera=TripCamera->GetCameraComponent();
    Camera->SetFieldOfView(PC->PlayerCameraManager->GetFOVAngle());
    FCollisionQueryParams Query(SCENE_QUERY_STAT(PursuitTripFloor),false,PC->GetPawn());
    FHitResult Ground;
    const bool bOnGround=GetWorld()->LineTraceSingleByChannel(Ground,TripEye,TripEye-FVector(0,0,245),ECC_Visibility,Query);
    TripDrop=bOnGround ? FMath::Clamp(TripEye.Z-Ground.ImpactPoint.Z-50.0,45.0,146.0) : 115.f;
    TripElapsed=0;
    if (Data && Data->SmokingArms && Data->TripArms)
    {
        USkeletalMeshComponent* Arms=CreateStoryArms(*TripCamera,*Camera,Data->SmokingArms,
            TEXT("FirstPersonTripArms"),FVector(0,0,-174.32));
        Arms->PlayAnimation(Data->TripArms,false);
    }
    PC->SetViewTarget(TripCamera);
}

void AActOneDirector::UpdatePursuitTrip(float DeltaSeconds)
{
    const float Before=TripElapsed;
    TripElapsed+=DeltaSeconds;
    const float Throw=FMath::SmoothStep(.05f,.39f,TripElapsed);
    const float Drop=FMath::SmoothStep(.12f,.56f,TripElapsed);
    const float GetUp=FMath::SmoothStep(1.05f,1.88f,TripElapsed);
    const float Low=Drop*(1.f-GetUp);
    const float Jolt=FMath::Sin(PI*FMath::Clamp((TripElapsed-.48f)/.17f,0.f,1.f));
    const FVector Position=TripEye+TripDirection*(Throw*(1.f-GetUp)*55.f)-FVector(0,0,TripDrop*Low+4.f*Jolt);
    const float Align=FMath::SmoothStep(0.f,.30f,TripElapsed)*(1.f-GetUp);
    const float Yaw=TripView.Yaw+FMath::FindDeltaAngleDegrees(TripView.Yaw,TripDirection.Rotation().Yaw)*Align;
    FRotator Look(FMath::Lerp(TripView.Pitch,-24.f,Low)-4.f*Jolt,Yaw,7.f*Low+5.f*Jolt);
    TripCamera->SetActorLocationAndRotation(Position,Look);
    if (Before<.52f && TripElapsed>=.52f)
        if (USoundBase* Contact=LoadObject<USoundBase>(nullptr,TEXT("/Game/Prologue/Brighton/Audio/Wet2.Wet2")))
            UGameplayStatics::PlaySoundAtLocation(this,Contact,Position-FVector(0,0,55),.66f,.80f);
}

void AActOneDirector::EndPursuitTrip()
{
    if (!TripCamera) return;
    if (APlayerController* PC=UGameplayStatics::GetPlayerController(this,0))
        if (AActor* Previous=PreviousTripView.IsValid() ? PreviousTripView.Get() : PC->GetPawn())
            PC->SetViewTargetWithBlend(Previous,.08f);
    TripCamera->SetLifeSpan(.12f);
    TripCamera=nullptr;
    PreviousTripView.Reset();
}

bool AActOneDirector::PatrolCanSeePlayer(APlayerController* Player) const
{
    const AActor* Patrol=Cue(TEXT("Patrol"));
    if (!Patrol || !Player || !Player->GetPawn()) return false;
    const FVector Eye=Patrol->GetActorLocation()+FVector(0,0,155);
    const FVector End=Player->GetPawn()->GetActorLocation()+FVector(0,0,55);
    const FVector Delta=End-Eye;
    if (Delta.SizeSquared()>FMath::Square(690) || FVector::DotProduct(Delta.GetSafeNormal(),Patrol->GetActorForwardVector())<.18) return false;
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(ActPatrol),true,Patrol);
    Query.AddIgnoredActor(Player->GetPawn());
    return !GetWorld()->LineTraceSingleByChannel(Hit,Eye,End,ECC_Visibility,Query);
}

void AActOneDirector::StartSmoke()
{
    APawn* Pawn=UGameplayStatics::GetPlayerPawn(this,0);
    if (!Pawn || !Data || !Data->SmokingArms || !Data->SmokingAnimClass || !Data->SmokingMontage) return;
    if (SmokingArms) StopSmoke();
    USceneComponent* Anchor=Pawn->FindComponentByClass<UCameraComponent>();
    SmokingArms=CreateStoryArms(*Pawn,*(Anchor ? Anchor : Pawn->GetRootComponent()),Data->SmokingArms,
        TEXT("FirstPersonSmokingArms"),FVector(0,0,-174.32));
    SmokingArms->SetAnimInstanceClass(Data->SmokingAnimClass);
    UAnimInstance* Animation=SmokingArms->GetAnimInstance();
    if (!Animation || Animation->Montage_Play(Data->SmokingMontage)<=0)
    {
        StopSmoke();
        return;
    }
    HeldCigarette=AttachCigarette(*SmokingArms,Data->CigaretteMesh);
    bSmoking=true;
    if (!SmokeTrail) SmokeTrail=UCigaretteSmokeComponent::CreateTrail(this);
    RefreshTickInterval();
}

void AActOneDirector::StopSmoke()
{
    bSmoking=false;
    if (HeldCigarette) HeldCigarette->DestroyComponent();
    if (SmokingArms) SmokingArms->DestroyComponent();
    HeldCigarette=nullptr;
    SmokingArms=nullptr;
    if (SmokeTrail) SmokeTrail->StopEmitting();
    SmokeRig->SetHiddenInGame(true,true);
}

float AActOneDirector::PlayRecorder()
{
    const AActor* Contact=Cue(TEXT("FinaleTapeButton"));
    if (const AActor* Key=Cue(TEXT("FinalePlaybackKey"))) RecorderKeyRest=Key->GetActorLocation();
    constexpr float FallbackDuration=.72f;
    TapeTime=0.f;
    bRecorderPressed=false;
    RefreshTickInterval();
    if (!Contact || !FinaleCamera || !Data || !Data->SmokingArms || !Data->SmokingAnimClass || !Data->RecorderMontage)
        return FallbackDuration;

    UCameraComponent* Camera=FinaleCamera->GetCameraComponent();
    const FTransform CameraTransform=Camera->GetComponentTransform();
    const FQuat Upright=FRotator(0,CameraTransform.Rotator().Yaw-90,0).Quaternion();
    const FQuat ArmsInCamera=CameraTransform.GetRotation().Inverse()*Upright;
    const FVector ContactInCamera=CameraTransform.InverseTransformPosition(Contact->GetActorLocation());
    const FVector Offset=ContactInCamera-ArmsInCamera.RotateVector(Data->RecorderContactPoint);
    RecorderArms=CreateStoryArms(*FinaleCamera,*Camera,Data->SmokingArms,TEXT("FirstPersonRecorderArms"),Offset,
        ArmsInCamera.Rotator());
    RecorderArms->HideBoneByName(TEXT("upper_arm_L"),PBO_None);
    RecorderArms->SetCastShadow(true);
    RecorderArms->SetAnimInstanceClass(Data->SmokingAnimClass);
    if (UAnimInstance* Animation=RecorderArms->GetAnimInstance())
    {
        const float Duration=Animation->Montage_Play(Data->RecorderMontage);
        if (Duration>0) return Duration;
    }
    RecorderArms->DestroyComponent();
    RecorderArms=nullptr;
    return FallbackDuration;
}

void AActOneDirector::ClickRecorder()
{
    if (bRecorderPressed) return;
    bRecorderPressed=true;
    const AActor* Contact=Cue(TEXT("FinaleTapeButton"));
    if (Contact && Data)
        if (const TObjectPtr<USoundBase>* Click=Data->Sounds.Find(TEXT("TapeClick")); Click && *Click)
            UGameplayStatics::PlaySoundAtLocation(this,Click->Get(),Contact->GetActorLocation(),.78f);
}

void AActOneDirector::FinishRecorder()
{
    ClickRecorder();
    if (AActor* Key=Cue(TEXT("FinalePlaybackKey"))) Key->SetActorLocation(RecorderKeyRest);
    if (RecorderArms) RecorderArms->DestroyComponent();
    RecorderArms=nullptr;
    TapeTime=-1.f;
}

void AActOneDirector::OpenDoor(FName Hinge,float Yaw)
{
    if (AActor* Actor=Cue(Hinge))
    {
        if (MovingDoor.Get()==Actor || FMath::Abs(FMath::FindDeltaAngleDegrees(Actor->GetActorRotation().Yaw,Yaw))<.25f) return;
        DoorFrom=Actor->GetActorRotation().Yaw;
        DoorTo=DoorFrom+FMath::FindDeltaAngleDegrees(DoorFrom,Yaw);
        DoorProgress=0;
        MovingDoor=Actor;
        RefreshTickInterval();
        const bool bEntry=Hinge==TEXT("SealedLeaf") || Hinge==TEXT("FedorBuildingLeaf");
        DoorOpeningAudio::Play(Actor,bEntry ? EDoorOpeningSound::Entry : EDoorOpeningSound::Wood);
    }
}

void AActOneDirector::SetRain(bool bOn)
{
    if (bRain==bOn) return;
    bRain=bOn;
    if (bOn && Data)
    {
        if (const TObjectPtr<USoundBase>* Sound=Data->Sounds.Find(TEXT("Rain")))
            RainLoop=UGameplayStatics::SpawnSound2D(this,Sound->Get(),.48f);
    }
    if (!bOn)
    {
        Rain->ClearInstances();
        RainSplashes->ClearInstances();
        Drops.Reset();
        DropSpeeds.Reset();
        SplashAges.Reset();
        SplashLocations.Reset();
        SplashTransforms.Reset();
        GroundGrid.Reset();
        GroundGridCenter=FVector(1.e9,1.e9,1.e9);
        RainFrameTime=0;
        if (RainLoop) RainLoop->FadeOut(.6f,0);
        RainLoop=nullptr;
    }
    RefreshTickInterval();
}

void AActOneDirector::StatusKey()
{
    if (UActOneSubsystem* Act=UActOneSubsystem::Find(this)) Act->ShowStatus();
}

void AActOneDirector::UpdateRain(const FVector& Around,float DeltaSeconds)
{
    CSV_SCOPED_TIMING_STAT(Brighton,RainInstances);
    if (!Rain->GetStaticMesh()) return;
    SampleRainGround(Around);
    if (Drops.IsEmpty())
    {
        Drops.Reserve(RainCount);
        DropSpeeds.Reserve(RainCount);
        for (int32 Index=0;Index<RainCount;++Index)
        {
            const float Speed=Random.FRandRange(1040,1770);
            DropSpeeds.Add(Speed);
            const float Radius=Index<RainCount/2 ? 490.f : 820.f;
            const float Thickness=Random.FRandRange(.0016,.0034);
            Drops.Emplace(FRotationMatrix::MakeFromZ(FVector(-150,-52,Speed)).ToQuat(),Around+FVector(Random.FRandRange(-Radius,Radius),
                Random.FRandRange(-Radius,Radius),Random.FRandRange(-115,910)),
                FVector(Thickness,Thickness,Random.FRandRange(.105,.32)));
        }
        Rain->AddInstances(Drops,false,true,false);
        SplashAges.Init(1.f,SplashCount);
        SplashLocations.Init(FVector::ZeroVector,SplashCount);
        SplashTransforms.Init(FTransform(FQuat::Identity,Around,FVector::ZeroVector),SplashCount);
        if (RainSplashes->GetStaticMesh()) RainSplashes->AddInstances(SplashTransforms,false,true,false);
    }
    for (int32 Index=0;Index<Drops.Num();++Index)
    {
        FTransform& Drop=Drops[Index];
        const FVector Velocity(150,52,-DropSpeeds[Index]);
        FVector At=Drop.GetLocation()+Velocity*DeltaSeconds;
        const int32 X=FMath::Clamp(FMath::RoundToInt((At.X-GroundGridCenter.X)/RainGridStep)+RainGridRadius,0,RainGridWidth-1);
        const int32 Y=FMath::Clamp(FMath::RoundToInt((At.Y-GroundGridCenter.Y)/RainGridStep)+RainGridRadius,0,RainGridWidth-1);
        const float Floor=GroundGrid[Y*RainGridWidth+X];
        const bool bHit=(At.Z<Floor && Drop.GetLocation().Z>=Floor);
        if (At.Z<Floor || FVector::DistSquared2D(At,Around)>FMath::Square(1150.f))
        {
            if (bHit && Floor>Around.Z-280 && Floor<Around.Z+80 && Index%2==0)
            {
                SplashLocations[NextSplash]=FVector(At.X,At.Y,Floor+.8f);
                SplashAges[NextSplash]=0;
                NextSplash=(NextSplash+1)%SplashCount;
            }
            const float Radius=Index<RainCount/2 ? 490.f : 820.f;
            At=Around+FVector(Random.FRandRange(-Radius,Radius),Random.FRandRange(-Radius,Radius),
                Random.FRandRange(625,960));
        }
        Drop.SetLocation(At);
    }
    Rain->BatchUpdateInstancesTransforms(0,Drops,true,true,true);
    if (RainSplashes->GetInstanceCount()==SplashCount)
    {
        for (int32 Index=0;Index<SplashCount;++Index)
        {
            SplashAges[Index]+=DeltaSeconds;
            const float Age=SplashAges[Index];
            const float Size=Age<.36f ? .043f+.47f*Age : 0.f;
            const float Fade=(1.f-FMath::SmoothStep(.035f,.35f,Age))*(.73f+(Index%6)*.06f);
            SplashTransforms[Index]=FTransform(FQuat::Identity,SplashLocations[Index],FVector(Size,Size,Size));
            RainSplashes->SetCustomDataValue(Index,0,Fade,false);
        }
        RainSplashes->BatchUpdateInstancesTransforms(0,SplashTransforms,true,true,true);
    }
}

void AActOneDirector::SampleRainGround(const FVector& Around)
{
    if (!GroundGrid.IsEmpty() && FVector::DistSquared2D(Around,GroundGridCenter)<FMath::Square(140.f) &&
        FMath::Abs(Around.Z-GroundGridCenter.Z)<85.f) return;
    GroundGridCenter=Around;
    GroundGrid.Reset(RainGridWidth*RainGridWidth);
    FCollisionObjectQueryParams Objects(ECC_WorldStatic);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BrightonRainGround),false,this);
    for (int32 Y=-RainGridRadius;Y<=RainGridRadius;++Y)
        for (int32 X=-RainGridRadius;X<=RainGridRadius;++X)
        {
            const FVector At=Around+FVector(X*RainGridStep,Y*RainGridStep,0);
            FHitResult Hit;
            const bool bHit=GetWorld()->LineTraceSingleByObjectType(Hit,At+FVector(0,0,1150),At-FVector(0,0,310),Objects,Query);
            GroundGrid.Add(bHit && !Hit.bStartPenetrating ? Hit.ImpactPoint.Z : Around.Z+1100);
        }
    if (RainLoop)
    {
        const float NearbyRoof=GroundGrid[RainGridRadius*RainGridWidth+RainGridRadius];
        RainLoop->SetVolumeMultiplier(NearbyRoof>Around.Z+100.f && NearbyRoof<Around.Z+1080.f ? .23f : .48f);
    }
}

void AActOneDirector::UpdateSmoke(APlayerController* Player)
{
    if (!Player->PlayerCameraManager || !SmokingArms) return;
    const UAnimInstance* Animation=SmokingArms->GetAnimInstance();
    const float SmokeTime=Animation && Data ? Animation->Montage_GetPosition(Data->SmokingMontage) : 0.f;
    const FRotator View=Player->PlayerCameraManager->GetCameraRotation();
    const FVector Eye=Player->PlayerCameraManager->GetCameraLocation();
    if (!Cast<UCameraComponent>(SmokingArms->GetAttachParent()))
        SmokingArms->SetWorldLocationAndRotation(Eye+View.RotateVector(FVector(0,0,-174.32)),
            View.Quaternion()*FRotator(0,-90,0).Quaternion());
    if (SmokeTrail && HeldCigarette)
        SmokeTrail->SetSource(HeldCigarette->GetComponentTransform().TransformPosition(FVector(CigaretteTip,0,0)),
            Eye+View.RotateVector(FVector(14,0,-9)),View.Vector(),SmokeTime>1.50f && SmokeTime<2.10f);
}

void AActOneDirector::UpdateRecorder(float DeltaSeconds)
{
    TapeTime+=DeltaSeconds;
    const UAnimInstance* Animation=RecorderArms ? RecorderArms->GetAnimInstance() : nullptr;
    const float Time=Animation && Data ? Animation->Montage_GetPosition(Data->RecorderMontage) : TapeTime;
    const float Contact=RecorderArms && Data ? Data->RecorderPressTime : .56f;
    if (Time>=Contact) ClickRecorder();
    if (AActor* Key=Cue(TEXT("FinalePlaybackKey")); Key && Time>=Contact-.03f)
    {
        const float Depression=FMath::SmoothStep(Contact-.03f,Contact+.035f,Time)
            * (1.f-FMath::SmoothStep(Contact+.09f,Contact+.165f,Time));
        const FVector Position=RecorderKeyRest-FVector(0,0,.65f*Depression);
        if (!Key->GetActorLocation().Equals(Position,.002f)) Key->SetActorLocation(Position);
    }
}

void AActOneDirector::RefreshTickInterval()
{
    const bool bCinematic=TripCamera || bSmoking || TapeTime>=0 || MovingDoor.IsValid()
        || FallingBarWeapon.IsValid() || FlashRemaining>0;
    const float Interval=bCinematic ? 0.f : bRain ? RainStep : Location==EActOneLocation::Alley ? .025f
        : Location==EActOneLocation::Entrance ? .04f : .10f;
    if (PrimaryActorTick.TickInterval!=Interval) SetActorTickInterval(Interval);
}

void AActOneDirector::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    APlayerController* Player=UGameplayStatics::GetPlayerController(this,0);
    if (!Player || !Player->GetPawn()) return;
    if (!bInputBound && Player->IsLocalController())
    {
        EnableInput(Player);
        if (InputComponent) InputComponent->BindKey(EKeys::K,IE_Pressed,this,&ThisClass::StatusKey);
        bInputBound=true;
    }
    if (UActOneSubsystem* Act=UActOneSubsystem::Find(this)) Act->Update(DeltaSeconds);
    if (bRain)
    {
        RainFrameTime+=DeltaSeconds;
        if (RainFrameTime+KINDA_SMALL_NUMBER>=RainStep)
        {
            UpdateRain(Player->GetPawn()->GetActorLocation(),RainFrameTime);
            RainFrameTime=0;
        }
    }
    if (TripCamera) UpdatePursuitTrip(DeltaSeconds);
    if (bSmoking) UpdateSmoke(Player);
    if (AActor* Prop=FallingBarWeapon.Get())
    {
        DropElapsed+=DeltaSeconds;
        const float T=FMath::Min(1.f,DropElapsed/DropDuration);
        FTransform Pose;
        Pose.Blend(ReleaseTransform,LandingTransform,T);
        FVector Position=Pose.GetLocation();
        Position.Z=FMath::Lerp(ReleaseTransform.GetLocation().Z,LandingTransform.GetLocation().Z,T*T);
        Pose.SetLocation(Position);
        Prop->SetActorTransform(Pose);
        if (T>=1.f) FallingBarWeapon.Reset();
    }
    if (FlashRemaining>0 && (FlashRemaining-=DeltaSeconds)<=0)
        if (auto* Light=Cast<APointLight>(Cue(TEXT("BarFlash")))) Light->GetLightComponent()->SetVisibility(false);
    if (TapeTime>=0) UpdateRecorder(DeltaSeconds);
    if (MovingDoor.IsValid())
    {
        DoorProgress=FMath::Min(1.f,DoorProgress+DeltaSeconds/.52f);
        const float Angle=FMath::Lerp(DoorFrom,DoorTo,FMath::SmoothStep(0.f,1.f,DoorProgress));
        MovingDoor->SetActorRotation(FRotator(0,Angle,0));
        if (DoorProgress>=1.f) MovingDoor.Reset();
    }
    if (Location==EActOneLocation::Entrance)
    {
        WeatherTime+=DeltaSeconds;
        if (AActor* Patrol=Cue(TEXT("Patrol")))
        {
            const float Sweep=FMath::Sin(WeatherTime*.65f);
            if (AActor* Marker=Cue(TEXT("PatrolOrigin")))
            {
                const FVector Prev=Patrol->GetActorLocation();
                const float Range=Marker->GetActorLocation().Z>500 ? 56.f : 185.f;
                const FVector Next=Marker->GetActorLocation()+FVector(0,Range*Sweep,0);
                Patrol->SetActorLocation(Next);
                if (FVector::DistSquared(Prev,Next)>.01) Patrol->SetActorRotation(FRotator(0,Next.Y>Prev.Y ? 76.f : -76.f,0));
            }
        }
    }
    RefreshTickInterval();
}
