#pragma once

#include "GameFramework/GameUserSettings.h"
#include "DostoevskyGameSettings.generated.h"

UCLASS(Config=GameUserSettings)
class DOSTOEVSKY_API UDostoevskyGameSettings : public UGameUserSettings
{
    GENERATED_BODY()
public:
    static UDostoevskyGameSettings* Get();
    virtual void ApplyNonResolutionSettings() override;

    UFUNCTION(BlueprintPure, Category="Settings") float GetMasterVolume() const;
    UFUNCTION(BlueprintPure, Category="Settings") float GetSceneBrightness() const;
    void SetMasterVolume(float Value,UWorld* World);
    void SetSceneBrightness(float Value);
    void ApplyToWorld(UWorld* World) const;

private:
    UPROPERTY(Config) float MasterVolume = 1.f;
    UPROPERTY(Config) float SceneBrightness = .5f;
};
