#pragma once

#include "CoreMinimal.h"
#include "ActOne.h"
#include "ActOneScene.generated.h"

class ACameraActor;
class UAudioComponent;
class UBrightonEnvironmentComponent;
class UCapsuleComponent;
class UInstancedStaticMeshComponent;
class USplineComponent;
class UStaticMeshComponent;
class USkeletalMeshComponent;
class UCityCharacterProfile;

UENUM(BlueprintType)
enum class EActOnePose : uint8 { Idle, Seated, Smoking, Armed, Fallen, Walking, Conversing, Running };

UCLASS()
class DOSTOEVSKY_API AActOneCast : public AActor
{
    GENERATED_BODY()
public:
    AActOneCast();
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<USceneComponent> PoseRoot;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<UCapsuleComponent> Body;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Character") TObjectPtr<USkeletalMeshComponent> CharacterMesh;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite,Category="Character") TObjectPtr<UCityCharacterProfile> CharacterProfile;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite,Category="Character") float AnimationPhase = 0;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite) EActOnePose DefaultPose = EActOnePose::Idle;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite) TMap<FName,TObjectPtr<AActor>> Parts;
    void Pose(EActOnePose NewPose);
    void Face(const FVector& Target);
    void Nod();
    void WalkAway(const FVector& Destination,float Speed);
protected:
    void BeginPlay() override;
    void Tick(float DeltaSeconds) override;
private:
    TMap<FName,FRotator> Rest;
    EActOnePose CurrentPose = EActOnePose::Idle;
    float Life = 0;
    float WalkSpeed = 0;
    float NodTime = 1;
    float NodRemaining = 0;
    FVector WalkTarget = FVector::ZeroVector;
    void Part(FName Name,float Pitch,float Roll=0);
    void PlayCharacterPose();
};

UCLASS()
class DOSTOEVSKY_API AActOneDirector : public AActor
{
    GENERATED_BODY()
public:
    AActOneDirector();
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Story") EActOneLocation Location;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Story") TObjectPtr<UActOneData> Data;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Story") TObjectPtr<ACameraActor> FinaleCamera;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Story") TObjectPtr<USplineComponent> PursuitRoute;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Weather") TObjectPtr<UInstancedStaticMeshComponent> Rain;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Weather") TObjectPtr<UInstancedStaticMeshComponent> RainSplashes;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") TObjectPtr<UBrightonEnvironmentComponent> Environment;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Props") TObjectPtr<UStaticMeshComponent> SmokeHand;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Props") TObjectPtr<UStaticMeshComponent> Cigarette;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Props") TObjectPtr<UStaticMeshComponent> Ember;
    AActor* Cue(FName Key) const;
    void Show(FName Key,bool bVisible) const;
    void Pose(FName Key,EActOnePose Pose) const;
    bool PatrolCanSeePlayer(APlayerController* Player) const;
    void StartSmoke();
    void StopSmoke();
    void PressRecorder();
    void OpenDoor(FName Hinge,float Yaw);
    UFUNCTION(BlueprintCallable,Category="Weather") void SetRain(bool bOn);
    UFUNCTION(BlueprintPure,Category="Weather") bool IsRaining() const { return bRain; }
    const TArray<TWeakObjectPtr<AActOneInteraction>>& Interactions() const { return Targets; }

protected:
    void BeginPlay() override;
    void EndPlay(const EEndPlayReason::Type Reason) override;
    void Tick(float DeltaSeconds) override;
private:
    TMap<FName,TWeakObjectPtr<AActor>> Cues;
    TArray<TWeakObjectPtr<AActOneInteraction>> Targets;
    TArray<FTransform> Drops;
    TArray<float> DropFloors;
    TArray<float> SplashAges;
    TArray<FVector> SplashLocations;
    TArray<FTransform> SplashTransforms;
    TArray<float> GroundGrid;
    FVector GroundGridCenter=FVector(1.e9,1.e9,1.e9);
    int32 NextSplash=0;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> RainLoop;
    UPROPERTY() TObjectPtr<USceneComponent> SmokeRig;
    FRandomStream Random{1994};
    float WeatherTime = 0;
    float SmokeTime = 0;
    float TapeTime = -1;
    float DoorProgress = 1;
    float DoorFrom = 0;
    float DoorTo = 0;
    TWeakObjectPtr<AActor> MovingDoor;
    bool bRain = false;
    bool bSmoking = false;
    bool bInputBound = false;
    void StatusKey();
    void UpdateRain(const FVector& Around,float DeltaSeconds);
    void SampleRainGround(const FVector& Around);
    void UpdateSmoke(APlayerController* Player,float DeltaSeconds);
    void UpdateRecorder(APlayerController* Player,float DeltaSeconds);
};
