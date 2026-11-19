#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Engine/DataAsset.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "CityCharacter.generated.h"

class UAnimSequence;
class UMaterialInterface;
class USkeletalMesh;
class USkeletalMeshComponent;

UCLASS(Transient)
class DOSTOEVSKY_API UCityClipInstance : public UAnimSingleNodeInstance
{
    GENERATED_BODY()
public:
    void TransitionTo(UAnimSequence* Clip, bool bLoop, float Rate, bool bMatchStride);
protected:
    FAnimInstanceProxy* CreateAnimInstanceProxy() override;
};

UCLASS()
class DOSTOEVSKY_API UCityGestureSequence : public UAnimSequence
{
    GENERATED_BODY()
public:
#if WITH_EDITOR
    void UseRawBoneTracks();
#endif
};

UCLASS(BlueprintType)
class DOSTOEVSKY_API UCityCharacterProfile : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Character") TObjectPtr<USkeletalMesh> Mesh;
    UPROPERTY(EditAnywhere, Category="Character") TArray<TObjectPtr<UMaterialInterface>> Materials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Animation") TMap<FName,TObjectPtr<UAnimSequence>> Motions;
    UPROPERTY(EditAnywhere, Category="Character") float ModelScale = 1.0f;
    UPROPERTY(EditAnywhere, Category="Character") float FacingYaw = 0.0f;
    UPROPERTY(EditAnywhere, Category="Character") float FeetOffset = 0.0f;

    void Configure(USkeletalMeshComponent& Component) const;
    float Play(USkeletalMeshComponent& Component, FName Motion, bool bLoop, float Rate = 1.0f) const;
};

UCLASS()
class DOSTOEVSKY_API UCityCharacterAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="City|Authoring")
    static FVector PoseBonePosition(const USkeletalMesh* Mesh, const UAnimSequence* Animation, FName Bone, float Time);

    UFUNCTION(BlueprintCallable, Category="City|Authoring")
    static bool AuthorGesture(USkeletalMesh* Mesh,UAnimSequence* Idle,UCityGestureSequence* Destination,FName Gesture);
};
