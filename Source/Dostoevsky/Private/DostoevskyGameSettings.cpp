#include "DostoevskyGameSettings.h"

#include "AudioDevice.h"
#include "AudioDeviceManager.h"
#include "Engine/Engine.h"
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

void ApplyVolume(float Value)
{
    if (FAudioDeviceManager* Devices=GEngine ? GEngine->GetAudioDeviceManager() : nullptr)
        Devices->IterateOverAllDevices([Value](Audio::FDeviceId, FAudioDevice* Device)
        {
            Device->SetSubmixOutputVolume(&Device->GetMainSubmixObject(), Value);
        });
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
    ApplyPresentationSettings();
}

void UDostoevskyGameSettings::SetMasterVolume(float Value)
{
    MasterVolume=Normalized(Value,1.f);
    PreviewMasterVolume(MasterVolume);
}

void UDostoevskyGameSettings::PreviewMasterVolume(float Value) const
{
    ApplyVolume(Normalized(Value,GetMasterVolume()));
}

void UDostoevskyGameSettings::SetSceneBrightness(float Value)
{
    SceneBrightness=Normalized(Value,.5f);
    ApplyBrightness(SceneBrightness);
}

void UDostoevskyGameSettings::ApplyPresentationSettings() const
{
    ApplyBrightness(GetSceneBrightness());
    PreviewMasterVolume(GetMasterVolume());
}
