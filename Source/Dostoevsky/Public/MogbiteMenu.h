#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerController.h"
#include "MogbiteMenu.generated.h"

class SWidget;
class UAudioComponent;
class UMediaPlayer;
class UMediaTexture;
class UTexture2D;

UCLASS()
class DOSTOEVSKY_API AMogbiteMenuController : public APlayerController
{
    GENERATED_BODY()

public:
    void PlayGame();
    void SetRainVolume(float Volume);
    float GetRainVolume() const { return RainVolume; }
    void SaveRainVolume();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    void OpenApartment();

    UPROPERTY(Transient) TObjectPtr<UMediaPlayer> VideoPlayer;
    UPROPERTY(Transient) TObjectPtr<UMediaTexture> VideoTexture;
    UPROPERTY(Transient) TObjectPtr<UTexture2D> StillImage;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> RainAudio;

    TSharedPtr<SWidget> Menu;
    FTimerHandle StartTimer;
    float RainVolume = 0.45f;
    bool bStarting = false;
};

UCLASS()
class DOSTOEVSKY_API AMogbiteMenuMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AMogbiteMenuMode();
};

TSharedRef<SWidget> CreateMogbitePauseMenu(APlayerController* Player, FSimpleDelegate Resume,
    TSharedPtr<SWidget>& InitialFocus);
