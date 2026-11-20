#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/DataAsset.h"
#include "BrightonEnvironment.generated.h"

class AActOneDirector;
class ACharacter;
class ASpotLight;
class APrologueTimeOfDay;
class UMaterialParameterCollection;
class USoundBase;
class UCityCharacterProfile;
class USkeletalMeshComponent;

USTRUCT(BlueprintType)
struct FBrightonFootsteps
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere) TArray<TObjectPtr<USoundBase>> Variations;
};

UCLASS(BlueprintType)
class DOSTOEVSKY_API UBrightonEnvironmentData : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere) TMap<FName,FBrightonFootsteps> Footsteps;
    UPROPERTY(EditAnywhere) TObjectPtr<UMaterialParameterCollection> WeatherParameters;
    UPROPERTY(EditAnywhere, Category="Character") TObjectPtr<UCityCharacterProfile> PlayerAppearance;
};

UCLASS(ClassGroup=(Environment))
class DOSTOEVSKY_API UBrightonEnvironmentComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UBrightonEnvironmentComponent();
    UFUNCTION(BlueprintPure,Category="Environment") float GetWetness() const { return Wetness; }
    UFUNCTION(BlueprintPure,Category="Environment") FName GetLastFootstepSurface() const { return LastSurface; }
    UFUNCTION(BlueprintPure,Category="Environment") int32 GetFootstepCount() const { return FootstepCount; }
protected:
    void BeginPlay() override;
    void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick) override;
private:
    UPROPERTY() TObjectPtr<UBrightonEnvironmentData> Data;
    TWeakObjectPtr<AActOneDirector> Director;
    TArray<TWeakObjectPtr<ASpotLight>> WindowLights;
    TWeakObjectPtr<APrologueTimeOfDay> StreetClock;
    FVector PreviousPosition=FVector::ZeroVector;
    TWeakObjectPtr<ACharacter> PreviousCharacter;
    TWeakObjectPtr<USkeletalMeshComponent> PlayerMesh;
    FName PlayerMotion;
    FRandomStream Random{19941014};
    FName LastSurface;
    int32 FootstepCount=0;
    int32 LastVariation=-1;
    float DistanceSinceStep=0;
    float Wetness=0;
    float PreviousWetness=-1.f;
    float LightTimer=0;
    bool bWasGrounded=true;
    bool bWeatherInitialized=false;
    void UpdateFootsteps(ACharacter* Character);
    void UpdatePlayerAppearance(ACharacter* Character);
    void Step(ACharacter* Character,bool bLanding);
    void UpdateWindowLights(const FVector& View);
};
