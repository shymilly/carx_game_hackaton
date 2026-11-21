#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StreetTraffic.generated.h"
class UBoxComponent;
class UMaterialInterface;
class USplineComponent;
class UStaticMesh;
class UStaticMeshComponent;
class ACharacter;
class UAudioComponent;
class USoundBase;
class USoundConcurrency;

UCLASS()
class DOSTOEVSKY_API AStreetTrafficCar : public AActor
{
    GENERATED_BODY()
public:
    AStreetTrafficCar();
    void Configure(UStaticMesh* Model,int32 PaintSlot,UMaterialInterface* Paint);
    void SetOnRoad(bool bOnRoad);
    void ConfigureAudio(USoundBase* DriveBy,USoundBase* Horn,USoundConcurrency* DriveLimit,USoundConcurrency* HornLimit);
    void UpdateRoadAudio(float Speed,const FVector& Listener);
    UFUNCTION(BlueprintPure, Category="Traffic|Audio") int32 GetDriveByCount() const { return DriveByCount; }
    UFUNCTION(BlueprintPure, Category="Traffic|Audio") int32 GetHornCount() const { return HornCount; }
    bool MoveOnRoad(const FTransform& Pose,float Speed,float& Fraction);
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetImpactCount() const { return ImpactCount; }
    UFUNCTION(BlueprintPure, Category="Traffic") float GetLastImpactSpeed() const { return LastImpactSpeed; }
    static FVector CollisionExtent(const UStaticMesh* Model);
    float RoadCenterHeight() const;
private:
    UPROPERTY(VisibleAnywhere, Category="Traffic") TObjectPtr<UBoxComponent> RoadBody;
    UPROPERTY(VisibleAnywhere, Category="Traffic") TObjectPtr<UStaticMeshComponent> BodyMesh;
    UPROPERTY(VisibleAnywhere, Category="Traffic|Audio") TObjectPtr<UAudioComponent> DriveByAudio;
    UPROPERTY(VisibleAnywhere, Category="Traffic|Audio") TObjectPtr<UAudioComponent> HornAudio;
    bool bDriveByStarted=false;
    bool bHornStarted=false;
    bool bOnRoad=false;
    int32 DriveByCount=0;
    int32 HornCount=0;
    TWeakObjectPtr<ACharacter> LastHitCharacter;
    double LastHitAt=-10;
    int32 ImpactCount=0;
    float LastImpactSpeed=0;
    void Impact(const FHitResult& Hit,float Speed);
};

UCLASS()
class DOSTOEVSKY_API AStreetTrafficFlow : public AActor
{
    GENERATED_BODY()
public:
    AStreetTrafficFlow();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Traffic") TObjectPtr<USplineComponent> Eastbound;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Traffic") TObjectPtr<USplineComponent> Westbound;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Traffic") TObjectPtr<USplineComponent> Northbound;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Traffic") TObjectPtr<USplineComponent> Southbound;
    UPROPERTY(EditInstanceOnly, Category="Traffic") bool bUseCrossStreetRoutes=false;
    UPROPERTY(EditInstanceOnly, Category="Traffic") FVector2D JunctionCenter=FVector2D(2190,-1210);
    UPROPERTY(EditInstanceOnly, Category="Traffic") FVector2D JunctionHalfSize=FVector2D(1050,1570);
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetRouteCount() const { return bUseCrossStreetRoutes ? 4 : 2; }
    UFUNCTION(BlueprintPure, Category="Traffic") USplineComponent* GetLane(int32 Lane) const;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic") TObjectPtr<UStaticMesh> CarMesh;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic") TArray<TObjectPtr<UStaticMesh>> FleetMeshes;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic|Audio") TObjectPtr<USoundBase> DriveBySound;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic|Audio") TObjectPtr<USoundBase> HornSound;
    UFUNCTION(BlueprintPure, Category="Traffic|Audio") int32 GetDriveByCount() const;
    UFUNCTION(BlueprintPure, Category="Traffic|Audio") int32 GetHornCount() const;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic") int32 PaintSlot=INDEX_NONE;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic") TArray<TObjectPtr<UMaterialInterface>> Paints;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic",meta=(ClampMin="6.0")) float SpawnInterval=7.f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic",meta=(ClampMin="2",ClampMax="8")) int32 PoolCapacity=6;
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetActiveCount() const;
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetTotalSpawned() const { return TotalSpawned; }
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetImpactCount() const;
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetBlockedMoves() const { return BlockedMoves; }
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetRouteObstructionCount() const { return RouteObstructions; }
    UFUNCTION(BlueprintCallable, Category="Traffic|Validation") bool ValidateRouteClearance();
protected:
    void BeginPlay() override;
    void Tick(float DeltaSeconds) override;
    void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    struct FVehicle
    {
        TWeakObjectPtr<AStreetTrafficCar> Car;
        float Distance=0;
        float Speed=0;
        float Cruise=0;
        float BrakeRemaining=0;
        int32 Lane=INDEX_NONE;
        int32 ArrivalOrder=0;
    };
    struct FJunctionRange
    {
        float Entry=0;
        float Exit=0;
        bool bPresent=false;
    };
    TArray<FVehicle> Fleet;
    FJunctionRange JunctionRanges[4];
    int32 JunctionOwner=INDEX_NONE;
    FVector BodyExtent=FVector::ZeroVector;
    FRandomStream DrivingRandom;
    UPROPERTY(Transient) TObjectPtr<USoundConcurrency> DriveConcurrency;
    UPROPERTY(Transient) TObjectPtr<USoundConcurrency> HornConcurrency;
    bool LaneAllowed[4]={};
    float TimeUntilSpawn=1.5f;
    int32 NextLane=0;
    int32 TotalSpawned=0;
    int32 RouteObstructions=0;
    int32 BlockedMoves=0;
    void Release(FVehicle& Vehicle);
    FVector FleetExtent() const;
    void SpawnNext();
    void MeasureJunction();
    float FollowingClearance(const FVehicle& Vehicle) const;
    void ReserveJunction();
    void Advance(FVehicle& Vehicle,float DeltaSeconds,float Clearance);
};
