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
class UCigaretteSmokeComponent;

UENUM(BlueprintType)
enum class EActOnePose : uint8 { Idle, Seated, Smoking, Armed, Fallen, Walking, Conversing, Running, Firing, Dead, Subdued };

UCLASS()
class DOSTOEVSKY_API AActOneCast : public AActor
{
    GENERATED_BODY()
public:
    AActOneCast();
    void SetActorHiddenInGame(bool bNewHidden) override;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<USceneComponent> PoseRoot;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<UCapsuleComponent> Body;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Character") TObjectPtr<USkeletalMeshComponent> CharacterMesh;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite,Category="Character") TObjectPtr<UCityCharacterProfile> CharacterProfile;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite,Category="Character") float AnimationPhase = 0;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite) EActOnePose DefaultPose = EActOnePose::Idle;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite,Category="Character") bool bFreezePose = false;
    UPROPERTY(EditInstanceOnly,BlueprintReadWrite) TMap<FName,TObjectPtr<AActor>> Parts;
    void Pose(EActOnePose NewPose);
    float GetPoseDuration() const;
    void Face(const FVector& Target);
    void Nod();
    void WalkAway(const FVector& Destination,float Speed);
    void WalkAway(TArray<FVector> Route,float Speed);
    void WalkTo(const FVector& Destination,float Speed);
    void FollowPursuitPath(const FVector& Position,const FVector& Direction,float Speed,float DeltaSeconds);
    bool IsWalkingToMark() const { return WalkSpeed>0; }
    void SetSpeaking(bool bIsSpeaking);
protected:
    void BeginPlay() override;
    void Tick(float DeltaSeconds) override;
private:
    TMap<FName,FRotator> Rest;
    EActOnePose CurrentPose = EActOnePose::Idle;
    float Life = 0;
    float WalkSpeed = 0;
    float CurrentWalkSpeed = 0;
    float NodTime = 1;
    float NodRemaining = 0;
    UPROPERTY(Transient) TObjectPtr<UCigaretteSmokeComponent> SmokeTrail;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> HeldCigarette;
    bool bSpeaking = false;
    bool bLegacySeat = false;
    bool bHideAtWalkEnd = false;
    FVector WalkTarget = FVector::ZeroVector;
    TArray<FVector> WalkRoute;
    int32 NextRoutePoint = 0;
    void Part(FName Name,float Pitch,float Roll=0);
    void PlayCharacterPose();
    void UpdateActorTick();
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
    void SetSpeaker(FName CueName);
    bool PatrolCanSeePlayer(APlayerController* Player) const;
    void StartSmoke();
    void StopSmoke();
    void StartBarShot();
    void BarShotImpact();
    void DropBarWeapon();
    void EndBarShot();
    void StartPursuitTrip(const FVector& Direction);
    void EndPursuitTrip();
    UFUNCTION(BlueprintPure,Category="Pursuit") bool IsPursuitTripPlaying() const { return TripCamera != nullptr; }
    float PlayRecorder();
    void FinishRecorder();
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
    TArray<float> DropSpeeds;
    TArray<float> SplashAges;
    TArray<FVector> SplashLocations;
    TArray<FTransform> SplashTransforms;
    TArray<float> GroundGrid;
    FVector GroundGridCenter=FVector(1.e9,1.e9,1.e9);
    int32 NextSplash=0;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> RainLoop;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> SceneMusic;
    UPROPERTY() TObjectPtr<USceneComponent> SmokeRig;
    UPROPERTY(Transient) TObjectPtr<UCigaretteSmokeComponent> SmokeTrail;
    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> SmokingArms;
    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> RecorderArms;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> HeldCigarette;
    TWeakObjectPtr<AActor> PreviousBarView;
    TWeakObjectPtr<AActor> PreviousTripView;
    UPROPERTY(Transient) TObjectPtr<ACameraActor> TripCamera;
    FVector TripEye=FVector::ZeroVector;
    FVector TripDirection=FVector::ForwardVector;
    FRotator TripView=FRotator::ZeroRotator;
    float TripElapsed=0;
    float TripDrop=0;
    TWeakObjectPtr<AActor> FallingBarWeapon;
    FTransform ReleaseTransform, LandingTransform;
    float DropElapsed=0, DropDuration=0;
    TWeakObjectPtr<AActOneCast> Speaker;
    float FlashRemaining = 0;
    FRandomStream Random{1994};
    float WeatherTime = 0;
    float TapeTime = -1;
    float RainFrameTime = 0;
    FVector RecorderKeyRest = FVector::ZeroVector;
    bool bRecorderPressed = false;
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
    void UpdateSmoke(APlayerController* Player);
    void UpdateRecorder(float DeltaSeconds);
    void ClickRecorder();
    void PlaySceneMusic(FName Track, float Volume);
    void RefreshTickInterval();
    void UpdatePursuitTrip(float DeltaSeconds);
};
