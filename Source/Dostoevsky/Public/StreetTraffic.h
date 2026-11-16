#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StreetTraffic.generated.h"

class UBoxComponent;
class UMaterialInterface;
class USplineComponent;
class UStaticMesh;
class UStaticMeshComponent;

UCLASS()
class DOSTOEVSKY_API AStreetTrafficCar : public AActor
{
    GENERATED_BODY()
public:
    AStreetTrafficCar();
    void Configure(UStaticMesh* Model, int32 PaintSlot, UMaterialInterface* Paint);
    void SetOnRoad(bool bOnRoad);
private:
    UPROPERTY(VisibleAnywhere, Category="Traffic") TObjectPtr<UBoxComponent> RoadBody;
    UPROPERTY(VisibleAnywhere, Category="Traffic") TObjectPtr<UStaticMeshComponent> BodyMesh;
};

UCLASS()
class DOSTOEVSKY_API AStreetTrafficFlow : public AActor
{
    GENERATED_BODY()
public:
    AStreetTrafficFlow();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Traffic") TObjectPtr<USplineComponent> Eastbound;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Traffic") TObjectPtr<USplineComponent> Westbound;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic") TObjectPtr<UStaticMesh> CarMesh;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic") int32 PaintSlot = INDEX_NONE;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic") TArray<TObjectPtr<UMaterialInterface>> Paints;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic", meta=(ClampMin="6.0")) float SpawnInterval = 7.0f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Traffic", meta=(ClampMin="2", ClampMax="8")) int32 PoolCapacity = 6;

    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetActiveCount() const;
    UFUNCTION(BlueprintPure, Category="Traffic") int32 GetTotalSpawned() const { return TotalSpawned; }

protected:
    void BeginPlay() override;
    void Tick(float DeltaSeconds) override;
    void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    struct FVehicle
    {
        TWeakObjectPtr<AStreetTrafficCar> Car;
        float Distance = 0.f;
        float Speed = 0.f;
        float Cruise = 0.f;
        int32 Lane = INDEX_NONE;
    };
    TArray<FVehicle> Fleet;
    FRandomStream DrivingRandom;
    float TimeUntilSpawn = 1.5f;
    int32 NextLane = 0;
    int32 TotalSpawned = 0;

    USplineComponent* GetLane(int32 Lane) const;
    void Release(FVehicle& Vehicle);
    void SpawnNext();
    void Advance(FVehicle& Vehicle, float DeltaSeconds);
};
