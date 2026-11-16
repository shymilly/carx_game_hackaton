#include "StreetTraffic.h"

#include "Components/BoxComponent.h"
#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"

namespace
{
constexpr float BodyHalfHeight = 69.f;
constexpr float MinimumTrafficInterval = 6.05f;
constexpr float MinimumSpawnGap = 880.f;
constexpr float SteeringLookahead = 135.f;

FTransform RoadTransform(const USplineComponent& Lane, float Distance)
{
    using Coordinate = ESplineCoordinateSpace::Type;
    const float Length = Lane.GetSplineLength();
    const FVector Location = Lane.GetLocationAtDistanceAlongSpline(Distance, Coordinate::World);
    const FVector Before = Lane.GetLocationAtDistanceAlongSpline(FMath::Max(0.f, Distance - SteeringLookahead), Coordinate::World);
    const FVector After = Lane.GetLocationAtDistanceAlongSpline(FMath::Min(Length, Distance + SteeringLookahead), Coordinate::World);
    return FTransform((After - Before).Rotation(), Location + FVector(0, 0, BodyHalfHeight));
}
}

AStreetTrafficCar::AStreetTrafficCar()
{
    PrimaryActorTick.bCanEverTick = false;
    RoadBody = CreateDefaultSubobject<UBoxComponent>(TEXT("TrafficCollision"));
    SetRootComponent(RoadBody);
    RoadBody->InitBoxExtent(FVector(249, 100, BodyHalfHeight));
    RoadBody->SetCollisionProfileName(TEXT("StreetTrafficBody"));
    RoadBody->SetGenerateOverlapEvents(false);
    RoadBody->SetCanEverAffectNavigation(false);

    BodyMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BodyMesh"));
    BodyMesh->SetupAttachment(RoadBody);
    BodyMesh->SetRelativeLocation(FVector(0, 0, -BodyHalfHeight));
    BodyMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    BodyMesh->SetGenerateOverlapEvents(false);
    BodyMesh->SetCanEverAffectNavigation(false);
    BodyMesh->bAffectDistanceFieldLighting = false;
}

void AStreetTrafficCar::Configure(UStaticMesh* Model, int32 Slot, UMaterialInterface* Paint)
{
    BodyMesh->SetStaticMesh(Model);
    if (Slot != INDEX_NONE) BodyMesh->SetMaterial(Slot, Paint);
}

void AStreetTrafficCar::SetOnRoad(bool bOnRoad)
{
    SetActorEnableCollision(bOnRoad);
    SetActorHiddenInGame(!bOnRoad);
}

AStreetTrafficFlow::AStreetTrafficFlow()
{
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("TrafficRoot"));
    Eastbound = CreateDefaultSubobject<USplineComponent>(TEXT("To the east"));
    Eastbound->SetupAttachment(RootComponent);
    Westbound = CreateDefaultSubobject<USplineComponent>(TEXT("From the west"));
    Westbound->SetupAttachment(RootComponent);
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;
}

void AStreetTrafficFlow::BeginPlay()
{
    Super::BeginPlay();
    if (!CarMesh || Eastbound->GetSplineLength() < 100.f || Westbound->GetSplineLength() < 100.f)
    {
        SetActorTickEnabled(false);
        return;
    }
    DrivingRandom.Initialize(1994);
    FActorSpawnParameters Parameters;
    Parameters.Owner = this;
    Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    for (int32 Index = 0; Index < FMath::Clamp(PoolCapacity, 2, 8); ++Index)
    {
        AStreetTrafficCar* Car = GetWorld()->SpawnActor<AStreetTrafficCar>(GetActorLocation(), GetActorRotation(), Parameters);
        if (!Car) continue;
        Car->SetOnRoad(false);
        Fleet.AddDefaulted_GetRef().Car = Car;
    }
}

USplineComponent* AStreetTrafficFlow::GetLane(int32 Lane) const
{
    return Lane == 0 ? Eastbound : Westbound;
}

int32 AStreetTrafficFlow::GetActiveCount() const
{
    int32 Count = 0;
    for (const FVehicle& Vehicle : Fleet)
        if (Vehicle.Car.IsValid() && Vehicle.Lane != INDEX_NONE) ++Count;
    return Count;
}

void AStreetTrafficFlow::Release(FVehicle& Vehicle)
{
    if (AStreetTrafficCar* Car = Vehicle.Car.Get()) Car->SetOnRoad(false);
    Vehicle.Lane = INDEX_NONE;
}

void AStreetTrafficFlow::SpawnNext()
{
    const int32 LaneIndex = NextLane;
    NextLane = 1 - NextLane;
    if (Fleet.ContainsByPredicate([LaneIndex](const FVehicle& Vehicle) {
        return Vehicle.Lane == LaneIndex && Vehicle.Distance < MinimumSpawnGap;
    })) return;

    FVehicle* Slot = Fleet.FindByPredicate([](const FVehicle& Vehicle) {
        return Vehicle.Car.IsValid() && Vehicle.Lane == INDEX_NONE;
    });
    if (!Slot) return;

    const int32 Variant = Paints.IsEmpty() ? INDEX_NONE
        : (TotalSpawned < Paints.Num() ? TotalSpawned : DrivingRandom.RandRange(0, Paints.Num() - 1));
    AStreetTrafficCar* Car = Slot->Car.Get();
    Car->Configure(CarMesh, PaintSlot, Paints.IsValidIndex(Variant) ? Paints[Variant].Get() : nullptr);
    Car->SetActorTransform(RoadTransform(*GetLane(LaneIndex), 0), false, nullptr, ETeleportType::TeleportPhysics);
    Slot->Lane = LaneIndex;
    Slot->Distance = 0.f;
    Slot->Cruise = DrivingRandom.FRandRange(730.f, 920.f);
    Slot->Speed = Slot->Cruise;
    Car->SetOnRoad(true);
    ++TotalSpawned;
}

void AStreetTrafficFlow::Advance(FVehicle& Vehicle, float DeltaSeconds)
{
    AStreetTrafficCar* Car = Vehicle.Car.Get();
    if (!Car) { Release(Vehicle); return; }
    const USplineComponent& Lane = *GetLane(Vehicle.Lane);
    Vehicle.Speed = FMath::FInterpConstantTo(Vehicle.Speed, Vehicle.Cruise, DeltaSeconds, 570.f);
    const float Step = Vehicle.Speed * DeltaSeconds;
    const float Next = FMath::Min(Vehicle.Distance + Step, Lane.GetSplineLength());
    const FTransform Pose = RoadTransform(Lane, Next);
    FHitResult Hit;
    Car->SetActorLocationAndRotation(Pose.GetLocation(), Pose.GetRotation(), true, &Hit);
    Vehicle.Distance = FMath::Lerp(Vehicle.Distance, Next, Hit.bBlockingHit ? Hit.Time : 1.f);
    if (Hit.bBlockingHit) Vehicle.Speed = 0.f;
    if (Vehicle.Distance >= Lane.GetSplineLength() - UE_KINDA_SMALL_NUMBER) Release(Vehicle);
}

void AStreetTrafficFlow::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    TimeUntilSpawn -= DeltaSeconds;
    if (TimeUntilSpawn <= 0.f)
    {
        SpawnNext();
        TimeUntilSpawn = FMath::Max(SpawnInterval, MinimumTrafficInterval);
    }
    const float Step = FMath::Min(DeltaSeconds, 0.045f);
    for (FVehicle& Vehicle : Fleet)
        if (Vehicle.Lane != INDEX_NONE) Advance(Vehicle, Step);
}

void AStreetTrafficFlow::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Reason == EEndPlayReason::Destroyed)
        for (const FVehicle& Vehicle : Fleet)
            if (AStreetTrafficCar* Car = Vehicle.Car.Get()) Car->Destroy();
    Fleet.Reset();
    Super::EndPlay(Reason);
}
