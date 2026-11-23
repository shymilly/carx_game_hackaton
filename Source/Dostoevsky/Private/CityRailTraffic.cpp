#include "CityRailTraffic.h"
#include "LocationTravel.h"

#include "Components/DecalComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/GameInstance.h"

namespace
{
constexpr float CityCouplerGap=22.f;
}

ACityRailTraffic::ACityRailTraffic()
{
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("RailOrigin"));
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickInterval=.22f;
}

void ACityRailTraffic::BeginPlay()
{
    Super::BeginPlay();
    for (const FCityRailVehicle& Vehicle:Consist)
    {
        UStaticMeshComponent* Car=NewObject<UStaticMeshComponent>(this);
        Car->SetupAttachment(RootComponent);
        Car->SetStaticMesh(Vehicle.Mesh);
        Car->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Car->SetCanEverAffectNavigation(false);
        Car->SetCullDistance(48000);
        Car->SetVisibility(false);
        Car->RegisterComponent();
        Cars.Add(Car);
        for (const FCityRailCarGraffiti& Paint : Vehicle.Graffiti)
        {
            if (!Paint.Material) continue;
            UDecalComponent* Decal = NewObject<UDecalComponent>(this);
            Decal->SetupAttachment(Car);
            Decal->SetRelativeLocationAndRotation(Paint.Center, FRotator(0, Paint.ProjectionYaw, 0));
            Decal->DecalSize = FVector(7, Paint.Size.X * .5, Paint.Size.Y * .5);
            Decal->SetDecalMaterial(Paint.Material);
            Decal->SetFadeScreenSize(.018f);
            Decal->SetVisibility(false);
            Decal->RegisterComponent();
        }
        TrainLength+=Vehicle.Length+CityCouplerGap;
    }
    SetActorTickEnabled(TrainLength>0);
    GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->GetRailServiceSeconds();
}

void ACityRailTraffic::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const double Elapsed=GetGameInstance()->GetSubsystem<ULocationTravelSubsystem>()->GetRailServiceSeconds()-FirstPassDelay;
    const double Period=FMath::Max(Interval,60.f);
    const double Phase=Elapsed>=0 ? FMath::Fmod(Elapsed,Period) : -1;
    const bool bMoving=Phase>=0 && Phase*Speed<2*HalfRoute+TrainLength;
    if (bPassing!=bMoving)
    {
        bPassing=bMoving;
        if (!bPassing)
            for (UStaticMeshComponent* Car:Cars) Car->SetVisibility(false,true);
        SetActorTickInterval(bPassing ? 0.f : .22f);
    }
    if (!bPassing) return;
    const double Direction=FMath::Fmod(FMath::FloorToDouble(Elapsed/Period),2.)>=1 ? -1 : 1;
    double Head=(Phase*Speed-HalfRoute)*Direction;
    for (int32 Index=0;Index<Cars.Num();++Index)
    {
        const FCityRailVehicle& Vehicle=Consist[Index];
        const double Center=Head-Direction*Vehicle.Length*.5;
        Cars[Index]->SetRelativeLocationAndRotation(FVector(Center,0,0),FRotator(0,Vehicle.MeshYaw+(Direction<0 ? 180 : 0),0));
        const bool bInsideTrack=!bCoveredEnds || FMath::Abs(Center)+Vehicle.Length*.5<=HalfRoute;
        if (Cars[Index]->IsVisible()!=bInsideTrack) Cars[Index]->SetVisibility(bInsideTrack,true);
        Head-=Direction*(Vehicle.Length+CityCouplerGap);
    }
}
