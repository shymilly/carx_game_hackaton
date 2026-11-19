#pragma once

#include "CoreMinimal.h"
#include "DocumentWindow.h"
#include "Engine/DataAsset.h"
#include "Engine/TimerHandle.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "StreetNavigation.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "ActOne.generated.h"

class AActOneDirector;
class AActOneInteraction;
class AHUD;
class UNarrativeSubsystem;
class USoundBase;

UENUM(BlueprintType)
enum class EActOneLocation : uint8 { Apartment, Street, Grocery, Bar, Precinct, Entrance, Fedor, Alley };

UENUM(BlueprintType)
enum class EActOnePhase : uint8
{
    Apartment, Cigarettes, Smoke, BarCall, Bar, Precinct, CaptainDone, MeetIvan,
    FedorEntrance, Search, Chase, Finale, Complete
};

UENUM(BlueprintType)
enum class EActOneAction : uint8
{
    Pistol, Press, Newspaper, PayPhone, Veteran, Grocery, LeaveGrocery, Cigarettes, Bar, LeaveBar,
    Guard, Missing, Office, Captain, Training, Archives, IvanStreet, Ride, Seal, Floorboard,
    Folder, Tape, Photograph, Drawer, DeskBadge, IvanFedor, LeaveFedor, ChaseBadge
};

USTRUCT(BlueprintType)
struct FActOneStatistics
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) int32 Calm = 0;
    UPROPERTY(BlueprintReadOnly) int32 Anger = 0;
    UPROPERTY(BlueprintReadOnly) int32 Heritage = 0;
    UPROPERTY(BlueprintReadOnly) int32 CorporateTrust = 0;
    UPROPERTY(BlueprintReadOnly) int32 Neighborhood = 0;
};

UCLASS(BlueprintType)
class DOSTOEVSKY_API UActOneData : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TMap<FName,TObjectPtr<UInteractionDocument>> Documents;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TMap<FName,TObjectPtr<USoundBase>> Sounds;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TMap<FName,TObjectPtr<UTexture2D>> Photos;
};

UCLASS()
class DOSTOEVSKY_API AActOneInteraction : public AStreetPortal
{
    GENERATED_BODY()
public:
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite) EActOneAction Action;
    bool Use(APlayerController* Player) const override;
    void SetAvailable(bool bAvailable);
};

UCLASS()
class DOSTOEVSKY_API UActOneSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    static UActOneSubsystem* Find(const UObject* Context);
    void Arrive(AActOneDirector* Scene);
    void Leave(AActOneDirector* Scene);
    void Update(float DeltaSeconds);
    void Reset();
    bool Use(const AActOneInteraction& Item,APlayerController* User);
    bool HandlePortal(const AStreetPortal& Portal);
    void ShowStatus();
    bool IsActive() const { return Director.IsValid() && Data!=nullptr; }
    bool IsCinematic() const { return bCinematic; }
    bool IsRain() const;
    void RefreshScene();
    UFUNCTION(BlueprintPure, Category="Act One") EActOnePhase GetPhase() const { return Phase; }
    UFUNCTION(BlueprintPure, Category="Act One") FActOneStatistics GetStatistics() const { return Stats; }
    UFUNCTION(BlueprintPure, Category="Act One") bool HasEvidence(FName Id) const { return Evidence.Contains(Id); }
    UFUNCTION(BlueprintPure, Category="Act One") FText Objective() const;
    UFUNCTION(BlueprintPure, Category="Act One") TArray<FText> OptionalObjectives() const;
    UFUNCTION(BlueprintPure, Category="Act One") bool HasActKey() const { return bIvanKey; }
    UFUNCTION(BlueprintPure, Category="Act One") bool HasArchiveAccess() const { return bArchives; }
    UFUNCTION(BlueprintPure, Category="Act One") bool IsAlarmed() const { return bAlarm; }
    UFUNCTION(BlueprintPure, Category="Act One") bool CanUseDisposition(int32 MinimumCalm,int32 MinimumAnger,int32 MaximumCalm,int32 MaximumAnger) const;
    UFUNCTION(BlueprintPure, Category="Act One") int32 GetChallengeStep() const { return Step; }
    UFUNCTION(BlueprintPure, Category="Act One") float GetChallengePosition() const;
    UFUNCTION(BlueprintPure, Category="Act One") float GetChallengeTarget() const;
    UFUNCTION(BlueprintPure, Category="Act One") bool IsPursuitFinished() const { return bAgentEscaped; }
    UFUNCTION(BlueprintPure, Category="Act One") bool HasLockpickTraining() const { return bLockpickTraining; }
    UFUNCTION(BlueprintPure, Category="Act One") bool HasPistol() const { return bPistol; }

private:
    enum class EChallenge : uint8 { None, Disarm, Lock };
    TWeakObjectPtr<AActOneDirector> Director;
    UPROPERTY(Transient) TObjectPtr<UActOneData> Data;
    UPROPERTY(Transient) TObjectPtr<UInteractionDocument> LiveDocument;
    EActOnePhase Phase = EActOnePhase::Apartment;
    FActOneStatistics Stats;
    TSet<FName> Evidence;
    TArray<FName> Lines;
    FSimpleDelegate AfterLines;
    int32 Line = 0;
    bool bCinematic = false;
    bool bPressOpen = false;
    bool bVeteranDone = false;
    bool bVeteranFled = false;
    bool bPistol = false;
    bool bOldManFled = false;
    bool bGuardResolved = false;
    bool bArchives = false;
    bool bLockpickTraining = false;
    bool bIvanKey = false;
    bool bAlarm = false;
    bool bFloorboardOpen = false;
    bool bDrawerOpen = false;
    bool bBankKey = false;
    bool bAgentEscaped = false;
    bool bClosingStarted = false;
    bool bIvanSpoken = false;
    int32 Cash = 20;
    float ChasePosition = 0;
    EChallenge Challenge = EChallenge::None;
    int32 Step = 0;
    double StepStarted = 0;
    FTimerHandle SceneTimer;
    FTimerHandle ChallengeTimer;

    APlayerController* Player() const;
    UNarrativeSubsystem* UI() const;
    UInteractionDocument* Doc(FName Id) const;
    EActOneLocation Place() const;
    bool Travel(const TCHAR* To,const TCHAR* Title,FName Spawn);
    void Hint(const FText& Text,float Duration=3.5f) const;
    void AddEvidence(FName Id,bool bShow=true);
    void Say(TArray<FName> Pages,FSimpleDelegate Done={});
    void NextLine();
    void Ask(FName Page,TArray<FText> Choices,FDocumentChoice Choice);
    void Notice(FName Page);
    void PlayAudio(FName Id,float Volume=1.f) const;
    void Timed(float Seconds,FSimpleDelegate End);
    void EndTimed(FSimpleDelegate End);
    void Dispatch();
    void CallFromPayphone(bool bMother);
    void AskVeteran();
    void StartBar();
    void DrawGuardWeapon();
    void ResolveGuard(bool bShot);
    void StartCaptain();
    void CaptainSecond();
    void CaptainOffer();
    void CaptainWarning();
    void MeetIvan();
    void OpenSeal();
    void EnterFedor(bool bLoud);
    void CheckClues();
    void MeetFedorIvan();
    void WalkOff(FName Actor,FName Exit);
    void UpdatePursuit(float DeltaSeconds);
    void Finale();
    void Credits();
    void Restart();
    void StartChallenge(EChallenge Mode);
    void RefreshChallenge();
    bool ChallengeKey(const FKey& Key,bool bRepeat);
    void FinishChallenge(bool bSuccess);
};

UCLASS()
class DOSTOEVSKY_API UActOneBlueprintLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Act One|Editor") static bool UseDynamicObjective(UObject* BlueprintAsset);
    UFUNCTION(BlueprintCallable, Category="Act One|Editor") static bool SendEditorKey(FName KeyName);
    UFUNCTION(BlueprintCallable, Category="Act One|Editor") static bool SendEditorGameKey(APlayerController* Player,FName KeyName,bool bPressed);
    UFUNCTION(BlueprintCallable, Category="Act One|Editor") static bool CaptureEditorDocument(UDocumentWindow* Window,const FString& FileName);
    UFUNCTION(BlueprintCallable, Category="Act One|Editor") static bool CaptureEditorWidget(UUserWidget* Widget,const FString& FileName);
};
