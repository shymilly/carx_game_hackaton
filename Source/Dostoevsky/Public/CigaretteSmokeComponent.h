#pragma once

#include "CoreMinimal.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "CigaretteSmokeComponent.generated.h"

UCLASS()
class DOSTOEVSKY_API UCigaretteSmokeComponent : public UInstancedStaticMeshComponent
{
    GENERATED_BODY()
public:
    UCigaretteSmokeComponent();
    static UCigaretteSmokeComponent* CreateTrail(AActor* Owner);
    void SetSource(const FVector& Tip,const FVector& Mouth,bool bExhaling);
    void StopEmitting() { bEmitting=false; }
protected:
    void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick) override;
private:
    struct FPuff
    {
        float Age=10.f, Lifetime=1.f, Width=1.f, Phase=0;
        FVector Location=FVector::ZeroVector, Velocity=FVector::ZeroVector;
    };
    TArray<FPuff> Puffs;
    TArray<FTransform> Transforms;
    FVector TipLocation=FVector::ZeroVector, MouthLocation=FVector::ZeroVector;
    FRandomStream Random;
    float UntilNext=0;
    int32 NextIndex=0;
    bool bEmitting=false, bExhale=false;
};
