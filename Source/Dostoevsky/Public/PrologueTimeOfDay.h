#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "PrologueTimeOfDay.generated.h"

class ACameraActor;
class ADirectionalLight;
class AHUD;
class ALight;
class APlayerController;
class APawn;
class ASkyLight;
class AStaticMeshActor;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UMaterialParameterCollection;

UCLASS()
class DOSTOEVSKY_API APrologueTimeOfDay : public AActor
{
    GENERATED_BODY()
public:
    APrologueTimeOfDay();
    double GetWorldHours() const { return WorldHours; }

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time") float OpeningHour = 18.0f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time", meta=(ClampMin="0")) float ClockRate = 8.0f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Lighting") TObjectPtr<ADirectionalLight> Sun;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Lighting") TObjectPtr<ASkyLight> AmbientSky;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Lighting") TObjectPtr<AStaticMeshActor> SkyDome;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Lighting") TArray<TObjectPtr<ALight>> StreetLights;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Lighting") TObjectPtr<UMaterialParameterCollection> StreetLightParameters;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Clock") TObjectPtr<AActor> HourHand;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Clock") TObjectPtr<AActor> MinuteHand;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Time|Sleep") TObjectPtr<ACameraActor> PillowView;

    UFUNCTION(BlueprintPure, Category="Time") float GetClockHour() const;
    UFUNCTION(BlueprintPure, Category="Time") int32 GetDayIndex() const;
    UFUNCTION(BlueprintPure, Category="Time") bool IsAsleep() const { return SleepPlayer.IsValid(); }
    bool OpenSleepMenu(APlayerController* Player);
    bool ConsumeRestRecovery();

protected:
    void BeginPlay() override;
    void Tick(float DeltaSeconds) override;
    void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> SkyMaterial;
    UPROPERTY(Transient) TObjectPtr<ACameraActor> SleepCamera;
    TArray<float> StreetLightIntensity;
    TWeakObjectPtr<APlayerController> SleepPlayer;
    TWeakObjectPtr<APlayerController> MenuPlayer;
    TWeakObjectPtr<APawn> SleepPawn;
    FTransform StartView;
    FTransform EndView;
    float StartFov = 90.f;
    float EndFov = 75.f;
    FQuat HourHandBase;
    FQuat MinuteHandBase;
    double WorldHours = 18.0;
    double WakeHours = 18.0;
    float LightUpdateRemaining = 0.f;
    float SleepElapsed = 0.f;
    bool bPawnWasHidden = false;
    bool bFading = false;
    bool bWokeUp = false;
    bool bRested = false;

    void ApplyTime();
    void BeginSleep(int32 Choice);
    void AdvanceSleep(float DeltaSeconds);
    void FinishSleep(bool bRestored);
};

UCLASS()
class DOSTOEVSKY_API UPrologueWorldLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Time", meta=(DefaultToSelf="HUD", HidePin="HUD")) static void OpenBedMenu(AHUD* HUD);
    UFUNCTION(BlueprintPure, Category="Time", meta=(DefaultToSelf="HUD", HidePin="HUD")) static bool IsWorldInteractionModal(AHUD* HUD);
    UFUNCTION(BlueprintCallable, Category="Time", meta=(DefaultToSelf="HUD", HidePin="HUD")) static bool ConsumeBedRest(AHUD* HUD);
    UFUNCTION(BlueprintPure, Category="Time", meta=(DefaultToSelf="HUD", HidePin="HUD")) static bool IsOutsideApartment(AHUD* HUD);
    UFUNCTION(BlueprintCallable, Category="Apartment|Doors")
    static double StepDoor(double Progress, double Velocity, double DeltaSeconds, bool bOpen, double& NewVelocity);
    UFUNCTION(BlueprintPure, Category="Apartment|Doors")
    static double DoorAngle(double Progress, double OpenAngle);
};

UCLASS()
class DOSTOEVSKY_API AStreetMeshInstances : public AActor
{
    GENERATED_BODY()
public:
    AStreetMeshInstances();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Street") TObjectPtr<UInstancedStaticMeshComponent> Instances;
};
