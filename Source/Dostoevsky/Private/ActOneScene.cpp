#include "ActOneScene.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SplineComponent.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

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
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickInterval=.033f;
}

void AActOneCast::BeginPlay()
{
    Super::BeginPlay();
    for (const auto& Item:Parts)
        if (IsValid(Item.Value)) Rest.Add(Item.Key,Item.Value->GetRootComponent()->GetRelativeRotation());
    Pose(DefaultPose);
}

void AActOneCast::Pose(EActOnePose NewPose)
{
    if (NewPose!=CurrentPose) Life=0;
    CurrentPose=NewPose;
    const bool bFallen=NewPose==EActOnePose::Fallen;
    Body->SetCapsuleHalfHeight(bFallen ? 29.f : 88.f);
    Body->SetRelativeLocation(FVector(0,0,bFallen ? 29.f : 88.f));
}

void AActOneCast::Face(const FVector& Target)
{
    const FVector Delta=Target-GetActorLocation();
    if (Delta.SizeSquared2D()>1) SetActorRotation(FRotator(0,Delta.Rotation().Yaw,0));
}

void AActOneCast::WalkAway(const FVector& Destination,float Speed)
{
    WalkTarget=Destination;
    WalkSpeed=Speed;
    Pose(EActOnePose::Walking);
}

void AActOneCast::Nod()
{
    NodTime=0;
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
    Super::Tick(DeltaSeconds);
    if (IsHidden()) return;
    Life+=DeltaSeconds;
    if (WalkSpeed>0)
    {
        Face(WalkTarget);
        const FVector Next=FMath::VInterpConstantTo(GetActorLocation(),WalkTarget,DeltaSeconds,WalkSpeed);
        SetActorLocation(Next);
        if (FVector::DistSquared(Next,WalkTarget)<4)
        {
            WalkSpeed=0;
            SetActorHiddenInGame(true);
            SetActorEnableCollision(false);
            TArray<AActor*> Attached;
            GetAttachedActors(Attached,false,true);
            for (AActor* Child:Attached) Child->SetActorHiddenInGame(true);
        }
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
    bSmoking=true;
    SmokeTime=0;
    SmokeRig->SetHiddenInGame(false,true);
}

void AActOneDirector::StopSmoke()
{
    bSmoking=false;
    SmokeRig->SetHiddenInGame(true,true);
}

void AActOneDirector::PressRecorder()
{
    if (!Cue(TEXT("FinaleTapeButton"))) return;
    TapeTime=0;
    SmokeRig->SetHiddenInGame(false,true);
    Cigarette->SetHiddenInGame(true);
    Ember->SetHiddenInGame(true);
}

void AActOneDirector::OpenDoor(FName Hinge,float Yaw)
{
    if (AActor* Actor=Cue(Hinge))
    {
        DoorFrom=Actor->GetActorRotation().Yaw;
        DoorTo=DoorFrom+FMath::FindDeltaAngleDegrees(DoorFrom,Yaw);
        DoorProgress=0;
        MovingDoor=Actor;
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
        Drops.Reset();
        if (RainLoop) RainLoop->FadeOut(.6f,0);
        RainLoop=nullptr;
    }
}

void AActOneDirector::StatusKey()
{
    if (UActOneSubsystem* Act=UActOneSubsystem::Find(this)) Act->ShowStatus();
}

void AActOneDirector::UpdateRain(const FVector& Around,float DeltaSeconds)
{
    if (!Rain->GetStaticMesh()) return;
    constexpr int32 Count=138;
    if (Drops.IsEmpty())
    {
        Drops.Reserve(Count);
        for (int32 Index=0;Index<Count;++Index)
            Drops.Emplace(FRotator(-7,15,7),Around+FVector(Random.FRandRange(-520,520),Random.FRandRange(-520,520),Random.FRandRange(-120,640)),
                         FVector(.007,.008,Random.FRandRange(.18,.34)));
        Rain->AddInstances(Drops,false,true,false);
    }
    for (FTransform& Drop:Drops)
    {
        FVector At=Drop.GetLocation()+FVector(125,36,-925)*DeltaSeconds;
        if (At.Z<Around.Z-145 || FVector::DistSquared2D(At,Around)>FMath::Square(780))
            At=Around+FVector(Random.FRandRange(-530,530),Random.FRandRange(-530,530),Random.FRandRange(460,650));
        Drop.SetLocation(At);
    }
    Rain->BatchUpdateInstancesTransforms(0,Drops,true,true,true);
}

void AActOneDirector::UpdateSmoke(APlayerController* Player,float DeltaSeconds)
{
    if (!Player->PlayerCameraManager) return;
    SmokeTime+=DeltaSeconds;
    const float Rise=FMath::SmoothStep(0.f,1.f,FMath::Clamp(SmokeTime/.65f,0.f,1.f));
    const float Rest=FMath::SmoothStep(0.f,1.f,FMath::Clamp((SmokeTime-1.28f)/.78f,0.f,1.f));
    const float Lift=Rise-Rest;
    const FRotator View=Player->PlayerCameraManager->GetCameraRotation();
    const FVector Position=Player->PlayerCameraManager->GetCameraLocation()+
        View.RotateVector(FVector(54-23*Lift,25-14*Lift,-34+18*Lift+FMath::Sin(SmokeTime*8)*.5f));
    SmokeRig->SetWorldLocationAndRotation(Position,View+FRotator(8+25*Lift,-17,0));
}

void AActOneDirector::UpdateRecorder(APlayerController* Player,float DeltaSeconds)
{
    const AActor* Button=Cue(TEXT("FinaleTapeButton"));
    const APlayerCameraManager* Camera=Player->PlayerCameraManager;
    if (!Button || !Camera) return;
    TapeTime+=DeltaSeconds;
    const FRotator Rotation=Camera->GetCameraRotation();
    const FVector Start=Camera->GetCameraLocation()+Rotation.RotateVector(FVector(32,21,-31));
    const FVector End=Button->GetActorLocation()+FVector(0,-3,4);
    const float Reach=FMath::SmoothStep(.16f,.78f,TapeTime)-FMath::SmoothStep(.83f,1.35f,TapeTime);
    SmokeRig->SetWorldLocationAndRotation(FMath::Lerp(Start,End,Reach),Rotation+FRotator(-12,-20,0));
    if (TapeTime>=1.35f)
    {
        TapeTime=-1;
        StopSmoke();
    }
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
    if (bRain) UpdateRain(Player->GetPawn()->GetActorLocation(),DeltaSeconds);
    if (bSmoking) UpdateSmoke(Player,DeltaSeconds);
    if (TapeTime>=0) UpdateRecorder(Player,DeltaSeconds);
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
                const FVector Next=Marker->GetActorLocation()+FVector(0,185*Sweep,0);
                Patrol->SetActorLocation(Next);
                if (FVector::DistSquared(Prev,Next)>.01) Patrol->SetActorRotation(FRotator(0,Next.Y>Prev.Y ? 76.f : -76.f,0));
            }
        }
    }
}
