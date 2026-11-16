#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "StreetNavigation.generated.h"

class AHUD;
class APlayerController;
class ATargetPoint;
class UBoxComponent;
class UInteractionDocument;
class UTexture2D;

UCLASS()
class DOSTOEVSKY_API AStreetPortal : public AActor
{
    GENERATED_BODY()
public:
    AStreetPortal();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Location") TObjectPtr<UBoxComponent> FocusBox;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") FText Prompt;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") FText DestinationTitle;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") TObjectPtr<UTexture2D> DestinationPhoto;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") TObjectPtr<ATargetPoint> Arrival;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") TSoftObjectPtr<UWorld> DestinationMap;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") TObjectPtr<UInteractionDocument> ClosedNotice;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") FName DestinationSpawn;
    bool Use(APlayerController* Player) const;
};

UCLASS()
class DOSTOEVSKY_API AStreetDoorThreshold : public AActor
{
    GENERATED_BODY()
public:
    AStreetDoorThreshold();
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") TObjectPtr<UTexture2D> StreetPhoto;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Location") TObjectPtr<UTexture2D> ApartmentPhoto;

protected:
    void Tick(float DeltaSeconds) override;

private:
    TWeakObjectPtr<APawn> LastPawn;
    int8 Side = 0;
};

UCLASS()
class DOSTOEVSKY_API UStreetNavigationLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintPure, Category="Street") static FString PortalPrompt(AActor* Hit);
    UFUNCTION(BlueprintCallable, Category="Street", meta=(DefaultToSelf="HUD", HidePin="HUD"))
    static bool EnterPortal(AHUD* HUD, AActor* Hit);
};
