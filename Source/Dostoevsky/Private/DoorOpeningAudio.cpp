#include "DoorOpeningAudio.h"

#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"

void DoorOpeningAudio::Play(const AActor* Door, EDoorOpeningSound Kind)
{
    if (!IsValid(Door) || !Door->GetWorld()) return;
    static const TCHAR* Clips[]={
        TEXT("/Game/Prologue/Brighton/Audio/Doors/S_WoodenDoorOpen.S_WoodenDoorOpen"),
        TEXT("/Game/Prologue/Brighton/Audio/Doors/S_EntryDoorOpen.S_EntryDoorOpen"),
        TEXT("/Game/Prologue/Brighton/Audio/Doors/S_FridgeDoorOpen.S_FridgeDoorOpen")
    };
    const TCHAR* Path=Clips[static_cast<int32>(Kind)];
    USoundBase* Sound=LoadObject<USoundBase>(nullptr,Path);
    if (!Sound) return;

    USoundAttenuation* Attenuation=NewObject<USoundAttenuation>(Door->GetWorld());
    Attenuation->Attenuation.bAttenuate=true;
    Attenuation->Attenuation.bSpatialize=true;
    Attenuation->Attenuation.AttenuationShapeExtents=FVector(110.f,0,0);
    Attenuation->Attenuation.FalloffDistance=960.f;
    UGameplayStatics::PlaySoundAtLocation(Door,Sound,Door->GetActorLocation(),FRotator::ZeroRotator,
        .74f,1.f,0.f,Attenuation);
    UE_LOG(LogTemp,Display,TEXT("DOOR_OPEN_AUDIO %s at %s"),*Sound->GetName(),*Door->GetActorLocation().ToCompactString());
}
