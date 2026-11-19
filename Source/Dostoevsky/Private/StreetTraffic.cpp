#include "StreetTraffic.h"
#include "Components/BoxComponent.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundConcurrency.h"
#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"

namespace
{
// Clear the road by 11 cm but catch curbs. The visual mesh origin stays on the road.
constexpr float BodyCenterHeight=75.f;
constexpr float BodyHalfHeight=64.f;
constexpr float MinimumTrafficInterval=6.05f;
constexpr float MinimumSpawnGap=880.f;
constexpr float SteeringLookahead=135.f;
constexpr float AuditStep=50.f;
constexpr float SafetyMargin=7.f;
FTransform RoadTransform(const USplineComponent& Lane,float Distance)
{
    using Coordinate=ESplineCoordinateSpace::Type;
    const float Length=Lane.GetSplineLength();
    const FVector Location=Lane.GetLocationAtDistanceAlongSpline(Distance,Coordinate::World);
    const FVector Before=Lane.GetLocationAtDistanceAlongSpline(FMath::Max(0.f,Distance-SteeringLookahead),Coordinate::World);
    const FVector After=Lane.GetLocationAtDistanceAlongSpline(FMath::Min(Length,Distance+SteeringLookahead),Coordinate::World);
    return FTransform((After-Before).Rotation(),Location+FVector(0,0,BodyCenterHeight));
}
FVector SweptExtent(FVector Extent,const FQuat& Start,const FQuat& End,float Margin)
{
    // Translation sweeps omit rotation; this bounds the whole angular arc as well.
    const float RotationGuard=FVector2D(Extent.X,Extent.Y).Size()*FMath::Min(static_cast<float>(Start.AngularDistance(End)),2.f);
    return Extent+FVector(Margin+RotationGuard,Margin+RotationGuard,0);
}
FCollisionResponseParams VehicleResponses()
{
    FCollisionResponseContainer Responses(ECR_Ignore);
    Responses.SetResponse(ECC_WorldStatic,ECR_Block);
    Responses.SetResponse(ECC_WorldDynamic,ECR_Block);
    Responses.SetResponse(ECC_Pawn,ECR_Block);
    Responses.SetResponse(ECC_PhysicsBody,ECR_Block);
    Responses.SetResponse(ECC_Vehicle,ECR_Block);
    return FCollisionResponseParams(Responses);
}
}

AStreetTrafficCar::AStreetTrafficCar()
{
    PrimaryActorTick.bCanEverTick=false;
    RoadBody=CreateDefaultSubobject<UBoxComponent>(TEXT("TrafficCollision"));
    SetRootComponent(RoadBody);
    RoadBody->InitBoxExtent(FVector(249,110,BodyHalfHeight));
    RoadBody->SetCollisionProfileName(TEXT("StreetTrafficBody"));
    // Scenery ignores the legacy custom StreetTraffic channel. Use the standard dynamic channel;
    // StreetPawnBoundary explicitly ignores this channel, so off-screen traffic still passes it.
    RoadBody->SetCollisionObjectType(ECC_WorldDynamic);
    RoadBody->SetCollisionResponseToChannel(ECC_WorldStatic,ECR_Block);
    RoadBody->SetCollisionResponseToChannel(ECC_WorldDynamic,ECR_Block);
    RoadBody->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
    RoadBody->SetCollisionResponseToChannel(ECC_PhysicsBody,ECR_Block);
    RoadBody->SetCollisionResponseToChannel(ECC_Vehicle,ECR_Block);
    RoadBody->SetGenerateOverlapEvents(false);
    RoadBody->SetCanEverAffectNavigation(false);
    BodyMesh=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BodyMesh"));
    BodyMesh->SetupAttachment(RoadBody);
    BodyMesh->SetRelativeLocation(FVector(0,0,-BodyCenterHeight));
    BodyMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    BodyMesh->SetGenerateOverlapEvents(false);
    BodyMesh->SetCanEverAffectNavigation(false);
    BodyMesh->bAffectDistanceFieldLighting=false;
    DriveByAudio=CreateDefaultSubobject<UAudioComponent>(TEXT("DriveByAudio"));
    HornAudio=CreateDefaultSubobject<UAudioComponent>(TEXT("HornAudio"));
    for (UAudioComponent* Audio : {DriveByAudio.Get(),HornAudio.Get()})
    {
        Audio->SetupAttachment(RoadBody);
        Audio->bAutoActivate=false;
        Audio->bAutoDestroy=false;
        Audio->bStopWhenOwnerDestroyed=true;
        Audio->bOverrideAttenuation=true;
        Audio->AttenuationOverrides.bAttenuate=true;
        Audio->AttenuationOverrides.bSpatialize=true;
        Audio->AttenuationOverrides.AttenuationShape=EAttenuationShape::Sphere;
        Audio->AttenuationOverrides.AttenuationShapeExtents=FVector(180,0,0);
        Audio->AttenuationOverrides.FalloffDistance=4700;
        Audio->AttenuationOverrides.DistanceAlgorithm=EAttenuationDistanceModel::Logarithmic;
    }
    DriveByAudio->SetVolumeMultiplier(.48f);
    HornAudio->SetVolumeMultiplier(.33f);
}
FVector AStreetTrafficCar::CollisionExtent(const UStaticMesh* Model)
{
    FVector Extent(249,110,BodyHalfHeight);
    if (Model)
    {
        const FBoxSphereBounds& Bounds=Model->GetBounds();
        Extent.X=FMath::Max(Extent.X,FMath::Abs(Bounds.Origin.X)+Bounds.BoxExtent.X);
        Extent.Y=FMath::Max(Extent.Y,FMath::Abs(Bounds.Origin.Y)+Bounds.BoxExtent.Y);
    }
    return Extent;
}
void AStreetTrafficCar::Configure(UStaticMesh* Model,int32 Slot,UMaterialInterface* Paint)
{
    BodyMesh->SetStaticMesh(Model);
    RoadBody->SetBoxExtent(CollisionExtent(Model),false);
    if (Slot!=INDEX_NONE) BodyMesh->SetMaterial(Slot,Paint);
}
void AStreetTrafficCar::ConfigureAudio(USoundBase* DriveBy,USoundBase* Horn,USoundConcurrency* DriveLimit,USoundConcurrency* HornLimit)
{
    DriveByAudio->SetSound(DriveBy);
    HornAudio->SetSound(Horn);
    if (DriveLimit) DriveByAudio->ConcurrencySet.Add(DriveLimit);
    if (HornLimit) HornAudio->ConcurrencySet.Add(HornLimit);
}
void AStreetTrafficCar::SetOnRoad(bool bActive)
{
    bOnRoad=bActive;
    bDriveByStarted=false;
    bHornStarted=false;
    DriveByAudio->Stop();
    HornAudio->Stop();
    SetActorEnableCollision(bActive);
    SetActorHiddenInGame(!bActive);
}
void AStreetTrafficCar::UpdateRoadAudio(float Speed,const FVector& Listener)
{
    if (!bOnRoad) return;
    const FVector ToListener=(Listener-GetActorLocation()).GetSafeNormal2D();
    const float Distance=FVector::Dist2D(Listener,GetActorLocation());
    if (!bDriveByStarted && Speed>180 && Distance<3200 && FVector::DotProduct(ToListener,GetActorForwardVector())>-.15f && DriveByAudio->Sound)
    {
        bDriveByStarted=true;
        DriveByAudio->SetPitchMultiplier(FMath::Clamp(Speed/820.f,.90f,1.08f));
        DriveByAudio->Play();
        ++DriveByCount;
        UE_LOG(LogTemp,Display,TEXT("TRAFFIC_AUDIO_DRIVE car=%s distance=%.0f"),*GetName(),Distance);
    }
    const FVector Delta=Listener-GetActorLocation();
    const FVector Forward=GetActorForwardVector().GetSafeNormal2D();
    const float Ahead=FVector::DotProduct(Delta,Forward);
    const FVector Side=Delta-Forward*Ahead;
    if (!bHornStarted && Speed>180 && Ahead>220 && Ahead<1350 && Side.SizeSquared2D()<FMath::Square(145.f) && HornAudio->Sound)
    {
        bHornStarted=true;
        HornAudio->Play();
        ++HornCount;
        UE_LOG(LogTemp,Display,TEXT("TRAFFIC_AUDIO_HORN car=%s ahead=%.0f"),*GetName(),Ahead);
    }
}
void AStreetTrafficCar::Impact(const FHitResult& Hit,float Speed)
{
    ACharacter* Character=Cast<ACharacter>(Hit.GetActor());
    const double Now=GetWorld()->GetTimeSeconds();
    if (!Character || Speed<180.f || (LastHitCharacter.Get()==Character && Now-LastHitAt<1.2)) return;
    const FVector Direction=GetActorForwardVector().GetSafeNormal2D();
    Character->GetCharacterMovement()->StopMovementImmediately();
    Character->LaunchCharacter(Direction*FMath::Clamp(Speed*.72f,300.f,720.f)+FVector(0,0,275),true,true);
    LastHitCharacter=Character;
    LastHitAt=Now;
    LastImpactSpeed=Speed;
    ++ImpactCount;
    UE_LOG(LogTemp,Display,TEXT("TRAFFIC_IMPACT car=%s character=%s speed_cm_s=%.1f count=%d"),*GetName(),*Character->GetName(),Speed,ImpactCount);
}
bool AStreetTrafficCar::MoveOnRoad(const FTransform& Pose,float Speed,float& Fraction)
{
    const FVector Start=GetActorLocation();
    FCollisionQueryParams Query(SCENE_QUERY_STAT(StreetTrafficMove),false,this);
    const FVector Extent=SweptExtent(RoadBody->GetScaledBoxExtent(),GetActorQuat(),Pose.GetRotation(),2.f);
    FHitResult Hit;
    const bool bBlocked=GetWorld()->SweepSingleByChannel(Hit,Start,Pose.GetLocation(),Pose.GetRotation(),ECC_WorldDynamic,FCollisionShape::MakeBox(Extent),Query,VehicleResponses());
    Fraction=bBlocked ? FMath::Max(0.f,Hit.Time-.015f) : 1.f;
    SetActorLocationAndRotation(FMath::Lerp(Start,Pose.GetLocation(),Fraction),bBlocked ? GetActorQuat() : Pose.GetRotation(),false,nullptr,ETeleportType::TeleportPhysics);
    if (bBlocked) Impact(Hit,Speed);
    return !bBlocked;
}

AStreetTrafficFlow::AStreetTrafficFlow()
{
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("TrafficRoot"));
    Eastbound=CreateDefaultSubobject<USplineComponent>(TEXT("To the east"));
    Eastbound->SetupAttachment(RootComponent);
    Westbound=CreateDefaultSubobject<USplineComponent>(TEXT("From the west"));
    Westbound->SetupAttachment(RootComponent);
    Northbound=CreateDefaultSubobject<USplineComponent>(TEXT("Cross street northbound"));
    Northbound->SetupAttachment(RootComponent);
    Southbound=CreateDefaultSubobject<USplineComponent>(TEXT("Cross street southbound"));
    Southbound->SetupAttachment(RootComponent);
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickGroup=TG_PrePhysics;
}
void AStreetTrafficFlow::BeginPlay()
{
    Super::BeginPlay();
    if (!CarMesh || Eastbound->GetSplineLength()<100.f || Westbound->GetSplineLength()<100.f) {SetActorTickEnabled(false);return;}
    ValidateRouteClearance();
    DrivingRandom.Initialize(1994);
    DriveConcurrency=NewObject<USoundConcurrency>(this);
    DriveConcurrency->Concurrency.MaxCount=3;
    DriveConcurrency->Concurrency.ResolutionRule=EMaxConcurrentResolutionRule::StopFarthestThenOldest;
    HornConcurrency=NewObject<USoundConcurrency>(this);
    HornConcurrency->Concurrency.MaxCount=2;
    HornConcurrency->Concurrency.ResolutionRule=EMaxConcurrentResolutionRule::StopFarthestThenOldest;
    FActorSpawnParameters Parameters;
    Parameters.Owner=this;
    Parameters.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    for (int32 Index=0;Index<FMath::Clamp(PoolCapacity,2,8);++Index)
    {
        AStreetTrafficCar* Car=GetWorld()->SpawnActor<AStreetTrafficCar>(GetActorLocation(),GetActorRotation(),Parameters);
        if (!Car) continue;
        Car->ConfigureAudio(DriveBySound,HornSound,DriveConcurrency,HornConcurrency);
        Car->SetOnRoad(false);
        Fleet.AddDefaulted_GetRef().Car=Car;
    }
}
USplineComponent* AStreetTrafficFlow::GetLane(int32 Lane) const
{
    USplineComponent* Lanes[]={Eastbound,Westbound,Northbound,Southbound};
    return Lane>=0 && Lane<GetRouteCount() ? Lanes[Lane] : nullptr;
}
int32 AStreetTrafficFlow::GetActiveCount() const
{
    int32 Count=0;
    for (const FVehicle& V:Fleet) if (V.Car.IsValid() && V.Lane!=INDEX_NONE) ++Count;
    return Count;
}
int32 AStreetTrafficFlow::GetDriveByCount() const
{
    int32 Count=0;
    for (const FVehicle& V:Fleet) if (V.Car.IsValid()) Count+=V.Car->GetDriveByCount();
    return Count;
}
int32 AStreetTrafficFlow::GetHornCount() const
{
    int32 Count=0;
    for (const FVehicle& V:Fleet) if (V.Car.IsValid()) Count+=V.Car->GetHornCount();
    return Count;
}
int32 AStreetTrafficFlow::GetImpactCount() const
{
    int32 Count=0;
    for (const FVehicle& V:Fleet) if (V.Car.IsValid()) Count+=V.Car->GetImpactCount();
    return Count;
}
bool AStreetTrafficFlow::ValidateRouteClearance()
{
    RouteObstructions=0;
    const FVector Extent=AStreetTrafficCar::CollisionExtent(CarMesh);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(StreetTrafficRouteAudit),false,this);
    for (const FVehicle& V:Fleet) if (V.Car.IsValid()) Query.AddIgnoredActor(V.Car.Get());
    // Pedestrians are moving obstacles, not an invalid road. Runtime sweeps still hit them.
    for (TActorIterator<APawn> It(GetWorld());It;++It) Query.AddIgnoredActor(*It);
    bool bAllClear=true;
    for (int32 Index=0;Index<GetRouteCount();++Index)
    {
        const USplineComponent& Lane=*GetLane(Index);
        LaneAllowed[Index]=Lane.GetSplineLength()>=100.f;
        int32 SamplesBlocked=0;
        FTransform Before=RoadTransform(Lane,0);
        const int32 Steps=FMath::CeilToInt(Lane.GetSplineLength()/AuditStep);
        for (int32 Step=0;Step<=Steps;++Step)
        {
            const float Distance=FMath::Min(Step*AuditStep,Lane.GetSplineLength());
            const FTransform After=RoadTransform(Lane,Distance);
            FHitResult Hit;
            if (GetWorld()->SweepSingleByChannel(Hit,Before.GetLocation(),After.GetLocation(),After.GetRotation(),ECC_WorldDynamic,FCollisionShape::MakeBox(SweptExtent(Extent,Before.GetRotation(),After.GetRotation(),SafetyMargin)),Query,VehicleResponses()))
            {
                ++RouteObstructions;
                ++SamplesBlocked;
                LaneAllowed[Index]=false;
                if (SamplesBlocked<=8) UE_LOG(LogTemp,Warning,TEXT("TRAFFIC_ROUTE_BLOCKED lane=%d distance=%.0f actor=%s component=%s"),Index,Distance,*GetNameSafe(Hit.GetActor()),*GetNameSafe(Hit.GetComponent()));
            }
            Before=After;
        }
        bAllClear&=LaneAllowed[Index];
    }
    UE_LOG(LogTemp,Display,TEXT("TRAFFIC_ROUTE_AUDIT obstructions=%d routes=%d"),RouteObstructions,GetRouteCount());
    return bAllClear;
}
void AStreetTrafficFlow::Release(FVehicle& V)
{
    if (AStreetTrafficCar* Car=V.Car.Get()) Car->SetOnRoad(false);
    V.Lane=INDEX_NONE;
    V.BrakeRemaining=0;
}
void AStreetTrafficFlow::SpawnNext()
{
    const int32 LaneIndex=NextLane;
    NextLane=(NextLane+1)%GetRouteCount();
    if (!LaneAllowed[LaneIndex] || Fleet.ContainsByPredicate([LaneIndex](const FVehicle& V) {return V.Lane==LaneIndex && V.Distance<MinimumSpawnGap;})) return;
    FVehicle* Slot=Fleet.FindByPredicate([](const FVehicle& V) {return V.Car.IsValid() && V.Lane==INDEX_NONE;});
    if (!Slot) return;
    const FTransform Pose=RoadTransform(*GetLane(LaneIndex),0);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(StreetTrafficSpawn),false,this);
    Query.AddIgnoredActor(Slot->Car.Get());
    if (GetWorld()->OverlapBlockingTestByChannel(Pose.GetLocation(),Pose.GetRotation(),ECC_WorldDynamic,FCollisionShape::MakeBox(AStreetTrafficCar::CollisionExtent(CarMesh)+FVector(SafetyMargin,SafetyMargin,0)),Query,VehicleResponses())) return;
    const int32 Variant=Paints.IsEmpty() ? INDEX_NONE : (TotalSpawned<Paints.Num() ? TotalSpawned : DrivingRandom.RandRange(0,Paints.Num()-1));
    AStreetTrafficCar* Car=Slot->Car.Get();
    Car->Configure(CarMesh,PaintSlot,Paints.IsValidIndex(Variant) ? Paints[Variant].Get() : nullptr);
    Car->SetActorTransform(Pose,false,nullptr,ETeleportType::TeleportPhysics);
    Slot->Lane=LaneIndex;
    Slot->Distance=0;
    Slot->Cruise=DrivingRandom.FRandRange(730.f,920.f);
    Slot->Speed=Slot->Cruise;
    Slot->BrakeRemaining=0;
    Car->SetOnRoad(true);
    ++TotalSpawned;
}
void AStreetTrafficFlow::Advance(FVehicle& V,float DeltaSeconds)
{
    AStreetTrafficCar* Car=V.Car.Get();
    if (!Car) {Release(V);return;}
    if (V.BrakeRemaining>0) {V.BrakeRemaining-=DeltaSeconds;return;}
    const USplineComponent& Lane=*GetLane(V.Lane);
    V.Speed=FMath::FInterpConstantTo(V.Speed,V.Cruise,DeltaSeconds,570.f);
    float Remaining=V.Speed*DeltaSeconds;
    while (Remaining>UE_KINDA_SMALL_NUMBER && V.Lane!=INDEX_NONE)
    {
        const float Step=FMath::Min(Remaining,18.f);
        const float Next=FMath::Min(V.Distance+Step,Lane.GetSplineLength());
        float Fraction=1;
        if (!Car->MoveOnRoad(RoadTransform(Lane,Next),V.Speed,Fraction))
        {
            V.Distance=FMath::Lerp(V.Distance,Next,Fraction);
            V.Speed=0;
            V.BrakeRemaining=.45f;
            ++BlockedMoves;
            return;
        }
        V.Distance=Next;
        Remaining-=Step;
        if (V.Distance>=Lane.GetSplineLength()-UE_KINDA_SMALL_NUMBER) Release(V);
    }
}
void AStreetTrafficFlow::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    TimeUntilSpawn-=DeltaSeconds;
    if (TimeUntilSpawn<=0) {SpawnNext();TimeUntilSpawn=FMath::Max(SpawnInterval,MinimumTrafficInterval);}
    const float Step=FMath::Min(DeltaSeconds,.045f);
    const APlayerController* Player=UGameplayStatics::GetPlayerController(this,0);
    const APawn* Listener=Player ? Player->GetPawn() : nullptr;
    for (FVehicle& V:Fleet) if (V.Lane!=INDEX_NONE)
    {
        Advance(V,Step);
        if (Listener && V.Lane!=INDEX_NONE && V.Car.IsValid()) V.Car->UpdateRoadAudio(V.Speed,Listener->GetActorLocation());
    }
}
void AStreetTrafficFlow::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Reason==EEndPlayReason::Destroyed) for (const FVehicle& V:Fleet) if (AStreetTrafficCar* Car=V.Car.Get()) Car->Destroy();
    Fleet.Reset();
    Super::EndPlay(Reason);
}
