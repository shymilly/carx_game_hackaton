#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CityRailTraffic.generated.h"

class UStaticMesh;
class UStaticMeshComponent;

USTRUCT(BlueprintType)
struct FCityRailVehicle
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Train") TObjectPtr<UStaticMesh> Mesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Train") float Length = 1400.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Train") float MeshYaw = 0.0f;
};

// Background trains travel along the actor's local X axis. The origin is rail-top height.
UCLASS()
class DOSTOEVSKY_API ACityRailTraffic : public AActor
{
    GENERATED_BODY()
public:
    ACityRailTraffic();
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Train") TArray<FCityRailVehicle> Consist;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Train", meta=(ClampMin="60")) float Interval = 300;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Train", meta=(ClampMin="0")) float FirstPassDelay = 55;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Train", meta=(ClampMin="100")) float Speed = 1510;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Train", meta=(ClampMin="1000")) float HalfRoute = 17160;
    UFUNCTION(BlueprintPure, Category="Train") bool IsPassing() const { return bPassing; }
protected:
    void BeginPlay() override;
    void Tick(float DeltaSeconds) override;
private:
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Cars;
    bool bPassing = false;
    float TrainLength = 0;
};
