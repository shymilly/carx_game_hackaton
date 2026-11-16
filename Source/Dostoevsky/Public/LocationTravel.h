#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "DimaApartmentStory.h"
#include "LocationTravel.generated.h"
class AHUD;
class APlayerController;

// Session state survives OpenLevel, but deliberately resets when a new game/PIE starts.
UCLASS()
class DOSTOEVSKY_API ULocationTravelSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    bool bHasSnapshot = false;
    FDimaApartmentProgress ApartmentProgress;
    double ClockHours = 18;
    FName ArrivalTag;
    TMap<FName,bool> Found;
    double Stamina = 100;
    bool bExhausted = false;
    uint8 TutorialMask = 0;
    void Capture(AHUD* HUD);
    bool Restore(AHUD* HUD);
    // True only after a validated placement. False retains the tag for a short loading retry.
    bool ApplyArrival(UWorld* World, bool bAllowFallback = false);
    bool bLastArrivalExact = true;
    FVector LastArrivalLocation = FVector::ZeroVector;
    static bool IsArrivalSafe(APlayerController* Player, FName Tag);
    void ResetSession();
};

UCLASS()
class DOSTOEVSKY_API ULocationTravelLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Location",meta=(DefaultToSelf="HUD",HidePin="HUD"))
    static bool RestoreLocation(AHUD* HUD);
    UFUNCTION(BlueprintCallable, Category="Location",meta=(DefaultToSelf="HUD",HidePin="HUD"))
    static void ResetSession(AHUD* HUD);
    UFUNCTION(BlueprintPure, Category="Location|Validation")
    static bool IsArrivalPointSafe(APlayerController* Player, FName Tag);
    UFUNCTION(BlueprintPure, Category="Location|Validation")
    static bool WasLastArrivalExact(APlayerController* Player);
};
