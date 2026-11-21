#include "DostoevskyGameSettings.h"

#include "AudioDevice.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

namespace
{
float Normalized(float Value,float Default)
{
    return FMath::Clamp(FMath::IsFinite(Value) ? Value : Default,0.f,1.f);
}

void ApplyBrightness(float Value)
{
    if (IConsoleVariable* Mid=IConsoleManager::Get().FindConsoleVariable(TEXT("r.Color.Mid")))
        Mid->Set(FMath::Lerp(.31f,.69f,Value),ECVF_SetByGameSetting);
}

void ApplyVolume(float Value,UWorld* World)
{
    if (!GEngine) return;
    FAudioDeviceHandle Device=World ? World->GetAudioDevice() : GEngine->GetMainAudioDevice();
    if (Device) Device->SetTransientPrimaryVolume(Value);
}
}

UDostoevskyGameSettings* UDostoevskyGameSettings::Get()
{
    return GEngine ? Cast<UDostoevskyGameSettings>(GEngine->GetGameUserSettings()) : nullptr;
}

float UDostoevskyGameSettings::GetMasterVolume() const
{
    return Normalized(MasterVolume,1.f);
}

float UDostoevskyGameSettings::GetSceneBrightness() const
{
    return Normalized(SceneBrightness,.5f);
}

void UDostoevskyGameSettings::ApplyNonResolutionSettings()
{
    Super::ApplyNonResolutionSettings();
    ApplyToWorld(nullptr);
}

void UDostoevskyGameSettings::SetMasterVolume(float Value,UWorld* World)
{
    MasterVolume=Normalized(Value,1.f);
    ApplyVolume(MasterVolume,World);
}

void UDostoevskyGameSettings::SetSceneBrightness(float Value)
{
    SceneBrightness=Normalized(Value,.5f);
    ApplyBrightness(SceneBrightness);
}

void UDostoevskyGameSettings::ApplyToWorld(UWorld* World) const
{
    ApplyBrightness(GetSceneBrightness());
    ApplyVolume(GetMasterVolume(),World);
}
